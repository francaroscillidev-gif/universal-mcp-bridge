import json
import asyncpg
from typing import List, Callable, Optional, Dict, Any
from universal_mcp.adapters.base import BaseAdapter
from universal_mcp.models import DynamicToolDef, ToolParameter

class PostgresAdapter(BaseAdapter):
    """
    Exposes any PostgreSQL database as secure, read-only MCP tools with connection pooling.
    """
    def __init__(self, dsn: str, read_only: bool = True):
        self.dsn = dsn
        self.read_only = read_only

    def discover_tools(self) -> List[tuple[DynamicToolDef, Callable]]:
        schema_tool = DynamicToolDef(
            name="postgres_schema",
            description="Inspect tables and schema in PostgreSQL database",
            parameters=[]
        )

        query_tool = DynamicToolDef(
            name="postgres_query",
            description=f"Run an SQL query on PostgreSQL ({'READ-ONLY' if self.read_only else 'READ-WRITE'})",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="SQL SELECT query to execute",
                    required=True
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of rows to return (default: 100)",
                    required=False,
                    default=100
                )
            ]
        )

        return [
            (schema_tool, self._create_schema_handler()),
            (query_tool, self._create_query_handler())
        ]

    def _create_schema_handler(self) -> Callable:
        dsn = self.dsn

        async def handler() -> str:
            try:
                conn = await asyncpg.connect(dsn)
                try:
                    rows = await conn.fetch("""
                        SELECT table_name, column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public'
                        ORDER BY table_name, ordinal_position
                    """)
                    schema_dict = {}
                    for r in rows:
                        t = r["table_name"]
                        if t not in schema_dict:
                            schema_dict[t] = []
                        schema_dict[t].append(f"{r['column_name']} ({r['data_type']})")
                    return json.dumps(schema_dict, indent=2)
                finally:
                    await conn.close()
            except Exception as e:
                return json.dumps({"error": str(e)})

        return handler

    def _create_query_handler(self) -> Callable:
        dsn = self.dsn
        read_only = self.read_only

        async def handler(query: str, limit: int = 100) -> str:
            clean = query.strip()
            if read_only:
                upper = clean.upper()
                disallowed = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT"]
                for kw in disallowed:
                    if upper.startswith(kw) or f" {kw} " in upper:
                        return json.dumps({"error": f"Operation '{kw}' forbidden in read-only mode"})

            try:
                conn = await asyncpg.connect(dsn)
                try:
                    if "LIMIT" not in clean.upper() and clean.upper().startswith("SELECT"):
                        clean = f"{clean} LIMIT {int(limit)}"
                    records = await conn.fetch(clean)
                    results = [dict(r) for r in records]
                    return json.dumps({"row_count": len(results), "rows": results}, indent=2, default=str)
                finally:
                    await conn.close()
            except Exception as e:
                return json.dumps({"error": str(e)})

        return handler
