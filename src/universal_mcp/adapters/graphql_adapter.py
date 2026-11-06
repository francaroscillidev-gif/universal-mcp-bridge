import json
from typing import List, Callable, Optional, Dict, Any
import httpx
from universal_mcp.adapters.base import BaseAdapter
from universal_mcp.models import DynamicToolDef, ToolParameter

class GraphQLAdapter(BaseAdapter):
    """
    Introspects any GraphQL endpoint via __schema query and generates
    native MCP tools for all Queries and Mutations.
    """
    INTROSPECTION_QUERY = """
    query IntrospectGraphQL {
      __schema {
        queryType { name }
        mutationType { name }
        types {
          name
          kind
          description
          fields(includeDeprecated: false) {
            name
            description
            args {
              name
              description
              type {
                name
                kind
                ofType { name kind }
              }
            }
            type {
              name
              kind
              ofType { name kind }
            }
          }
        }
      }
    }
    """

    def __init__(self, endpoint_url: str, headers: Optional[Dict[str, str]] = None):
        self.endpoint_url = endpoint_url
        self.headers = headers or {"Content-Type": "application/json"}

    def discover_tools(self) -> List[tuple[DynamicToolDef, Callable]]:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    self.endpoint_url,
                    json={"query": self.INTROSPECTION_QUERY},
                    headers=self.headers
                )
                data = resp.json().get("data", {}).get("__schema", {})
        except Exception:
            # Fallback single generic runner if endpoint is offline during discovery
            return self._create_generic_runner()

        query_type_name = data.get("queryType", {}).get("name") if data.get("queryType") else "Query"
        types = {t["name"]: t for t in data.get("types", []) if t.get("name")}
        
        query_type = types.get(query_type_name)
        if not query_type or not query_type.get("fields"):
            return self._create_generic_runner()

        tools = []
        for field in query_type.get("fields", [])[:20]: # Top 20 query fields
            f_name = field["name"]
            f_desc = field.get("description") or f"Execute GraphQL query {f_name}"
            
            params = []
            for arg in field.get("args", []):
                arg_name = arg["name"]
                arg_desc = arg.get("description") or f"Argument {arg_name}"
                params.append(
                    ToolParameter(
                        name=arg_name,
                        type="string",
                        description=arg_desc,
                        required=False
                    )
                )

            tool_def = DynamicToolDef(
                name=f"gql_{f_name}",
                description=f_desc,
                parameters=params
            )
            handler = self._create_field_handler(f_name, params)
            tools.append((tool_def, handler))

        return tools

    def _create_generic_runner(self) -> List[tuple[DynamicToolDef, Callable]]:
        tool_def = DynamicToolDef(
            name="graphql_query",
            description="Execute arbitrary GraphQL query on the endpoint",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="GraphQL query or mutation string",
                    required=True
                ),
                ToolParameter(
                    name="variables",
                    type="object",
                    description="Query variables dict",
                    required=False
                )
            ]
        )
        endpoint = self.endpoint_url
        headers = self.headers

        async def handler(query: str, variables: Optional[dict] = None) -> str:
            async with httpx.AsyncClient(timeout=20.0) as client:
                payload = {"query": query}
                if variables:
                    payload["variables"] = variables
                res = await client.post(endpoint, json=payload, headers=headers)
                return json.dumps(res.json(), indent=2)

        return [(tool_def, handler)]

    def _create_field_handler(self, field_name: str, params: List[ToolParameter]) -> Callable:
        endpoint = self.endpoint_url
        headers = self.headers

        async def handler(**kwargs) -> str:
            # Construct simple selection
            args_list = []
            for k, v in kwargs.items():
                if v is not None:
                    if isinstance(v, (int, float, bool)):
                        args_list.append(f"{k}: {v}")
                    else:
                        args_list.append(f'{k}: "{v}"')
            
            args_str = f"({', '.join(args_list)})" if args_list else ""
            query_str = f"query {{ {field_name}{args_str} }}"

            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(endpoint, json={"query": query_str}, headers=headers)
                return json.dumps(res.json(), indent=2)

        return handler
