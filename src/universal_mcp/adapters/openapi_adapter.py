import json
import inspect
from typing import List, Callable, Dict, Any, Optional
import httpx
from universal_mcp.adapters.base import BaseAdapter
from universal_mcp.models import DynamicToolDef, ToolParameter

class OpenAPIAdapter(BaseAdapter):
    def __init__(self, spec_dict_or_path: Dict[str, Any] | str, base_url: Optional[str] = None, default_headers: Optional[Dict[str, str]] = None):
        if isinstance(spec_dict_or_path, str):
            if spec_dict_or_path.startswith("http://") or spec_dict_or_path.startswith("https://"):
                resp = httpx.get(spec_dict_or_path, timeout=15)
                self.spec = resp.json()
            else:
                with open(spec_dict_or_path, "r", encoding="utf-8") as f:
                    self.spec = json.load(f)
        else:
            self.spec = spec_dict_or_path

        # Determine base url
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            servers = self.spec.get("servers", [])
            if servers and "url" in servers[0]:
                self.base_url = servers[0]["url"].rstrip("/")
            else:
                self.base_url = "http://localhost:8000"

        self.default_headers = default_headers or {}

    def _resolve_schema(self, schema_ref: Any) -> Dict[str, Any]:
        if not isinstance(schema_ref, dict):
            return {}
        if "$ref" in schema_ref:
            ref_path = schema_ref["$ref"].split("/")
            curr = self.spec
            for part in ref_path:
                if part == "#":
                    curr = self.spec
                else:
                    curr = curr.get(part, {})
            return curr
        return schema_ref

    def discover_tools(self) -> List[tuple[DynamicToolDef, Callable]]:
        tools = []
        paths = self.spec.get("paths", {})

        for path, methods in paths.items():
            for method, op in methods.items():
                if method.lower() not in ["get", "post", "put", "delete", "patch"]:
                    continue

                operation_id = op.get("operationId")
                if not operation_id:
                    clean_path = path.replace("/", "_").replace("{", "").replace("}", "")
                    operation_id = f"{method.lower()}{clean_path}"

                # Normalize tool name for MCP (alphanumeric + underscore/hyphen)
                tool_name = operation_id.replace("-", "_").replace(".", "_")
                description = op.get("summary") or op.get("description") or f"{method.upper()} {path}"

                parameters: List[ToolParameter] = []
                api_params = op.get("parameters", [])

                for p in api_params:
                    if "$ref" in p:
                        p = self._resolve_schema(p)
                    p_name = p.get("name")
                    p_in = p.get("in", "query")
                    p_required = p.get("required", False)
                    p_desc = p.get("description", f"Parameter in {p_in}")
                    p_schema = self._resolve_schema(p.get("schema", {}))
                    p_type = p_schema.get("type", "string")

                    parameters.append(
                        ToolParameter(
                            name=p_name,
                            type=p_type,
                            description=f"[{p_in}] {p_desc}",
                            required=p_required,
                            default=p_schema.get("default")
                        )
                    )

                # Request body (e.g. application/json)
                req_body = op.get("requestBody", {})
                if req_body:
                    if "$ref" in req_body:
                        req_body = self._resolve_schema(req_body)
                    content = req_body.get("content", {})
                    json_schema = content.get("application/json", {}).get("schema", {})
                    json_schema = self._resolve_schema(json_schema)

                    if json_schema.get("type") == "object":
                        props = json_schema.get("properties", {})
                        body_required = json_schema.get("required", [])
                        for prop_name, prop_def in props.items():
                            prop_def = self._resolve_schema(prop_def)
                            parameters.append(
                                ToolParameter(
                                    name=prop_name,
                                    type=prop_def.get("type", "string"),
                                    description=f"[body] {prop_def.get('description', '')}",
                                    required=prop_name in body_required,
                                    default=prop_def.get("default")
                                )
                            )
                    else:
                        parameters.append(
                            ToolParameter(
                                name="payload",
                                type="object",
                                description="[body] JSON Request body payload",
                                required=req_body.get("required", False)
                            )
                        )

                tool_def = DynamicToolDef(
                    name=tool_name,
                    description=description,
                    parameters=parameters,
                    metadata={"path": path, "method": method.upper()}
                )

                handler = self._create_handler(path, method.upper(), parameters)
                tools.append((tool_def, handler))

        return tools

    def _create_handler(self, path_template: str, http_method: str, params: List[ToolParameter]) -> Callable:
        base_url = self.base_url
        headers = self.default_headers

        async def handler(**kwargs) -> str:
            req_path = path_template
            query_params = {}
            body_payload = {}

            for p in params:
                val = kwargs.get(p.name)
                if val is None:
                    continue

                if f"{{{p.name}}}" in req_path:
                    req_path = req_path.replace(f"{{{p.name}}}", str(val))
                elif p.description.startswith("[body]"):
                    if p.name == "payload" and isinstance(val, dict):
                        body_payload.update(val)
                    else:
                        body_payload[p.name] = val
                else:
                    query_params[p.name] = val

            full_url = f"{base_url}{req_path}"

            async with httpx.AsyncClient(timeout=30.0) as client:
                req_kwargs = {
                    "headers": headers,
                    "params": query_params
                }
                if http_method in ["POST", "PUT", "PATCH"]:
                    req_kwargs["json"] = body_payload

                resp = await client.request(http_method, full_url, **req_kwargs)
                try:
                    return json.dumps(resp.json(), indent=2)
                except Exception:
                    return resp.text

        return handler
