import os
import json
import sqlite3
import aiosqlite
from typing import List, Callable, Optional, Dict, Any
from universal_mcp.adapters.base import BaseAdapter
from universal_mcp.models import DynamicToolDef, ToolParameter

class SQLiteAdapter(BaseAdapter):
    """
    Exposes any SQLite database file as secure, read-only (or controlled write) MCP tools.
    Provides schema inspection, table preview, and query execution.
    """
    def __init__(self, db_path: str, read_only: bool = True):
        self.db_path = os.path.abspath(db_path)
        self.read_only = read_only

    def discover_tools(self) -> List[tuple[DynamicToolDef, Callable]]:
        db_name = os.path.splitext(os.path.basename(self.db_path))[0].replace("-", "_").replace(".", "_")

        # Tool 1: Schema inspector
        schema_tool = DynamicToolDef(
            name=f"db_{db_name}_schema",
            description=f"Inspect tables and column schemas in database '{os.path.basename(self.db_path)}'",
            parameters=[]
        )

        # Tool 2: SQL query executor
        query_tool = DynamicToolDef(
            name=f"db_{db_name}_query",
            description=f"Run an SQL query on database '{os.path.basename(self.db_path)}' ({'READ-ONLY' if self.read_only else 'READ-WRITE'})",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="SQL SELECT query to execute" if self.read_only else "SQL query to execute",
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
        db_path = self.db_path

        async def handler() -> str:
            if not os.path.exists(db_path):
                return json.dumps({"error": f"Database file not found: {db_path}"})

            async with aiosqlite.connect(f"file:{db_path}?mode=ro", uri=True) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'") as cursor:
                    rows = await cursor.fetchall()
                    tables = [{"table": row["name"], "definition": row["sql"]} for row in rows]
                    return json.dumps(tables, indent=2)

        return handler

    def _create_query_handler(self) -> Callable:
        db_path = self.db_path
        read_only = self.read_only

        async def handler(query: str, limit: int = 100) -> str:
            clean_query = query.strip()

            if read_only:
                upper = clean_query.upper()
                disallowed = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE", "TRUNCATE"]
                for kw in disallowed:
                    if upper.startswith(kw) or f" {kw} " in upper:
                        return json.dumps({"error": f"Operation '{kw}' forbidden in read-only mode"})

            uri_mode = "ro" if read_only else "rw"
            try:
                async with aiosqlite.connect(f"file:{db_path}?mode={uri_mode}", uri=True) as db:
                    db.row_factory = aiosqlite.Row
                    # Append limit if not present
                    exec_query = clean_query
                    if "LIMIT" not in exec_query.upper() and exec_query.upper().startswith("SELECT"):
                        exec_query = f"{exec_query} LIMIT {int(limit)}"

                    async with db.execute(exec_query) as cursor:
                        rows = await cursor.fetchall()
                        results = [dict(row) for row in rows]
                        return json.dumps({
                            "row_count": len(results),
                            "rows": results
                        }, indent=2)
            except Exception as e:
                return json.dumps({"error": str(e)})

        return handler
