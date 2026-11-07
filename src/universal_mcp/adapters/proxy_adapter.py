import json
import shlex
import asyncio
from typing import List, Callable, Optional, Dict, Any
from universal_mcp.adapters.base import BaseAdapter
from universal_mcp.models import DynamicToolDef, ToolParameter
from universal_mcp.security.sandbox import CommandSandbox

class MCPProxyAdapter(BaseAdapter):
    """
    Federates external MCP servers (stdio or SSE) into Universal MCP Bridge.
    Allows proxying other community servers (e.g., npx @modelcontextprotocol/server-github)
    while wrapping them with Universal MCP's RBAC, Rate Limiting, Audit Logging, and Caching.
    """
    def __init__(self, server_command: str, server_name: str, sandbox: Optional[CommandSandbox] = None):
        self.server_command = server_command
        self.server_name = server_name.replace("-", "_").replace(".", "_")
        self.sandbox = sandbox or CommandSandbox()

    def discover_tools(self) -> List[tuple[DynamicToolDef, Callable]]:
        # Expose generic proxy call tool to upstream server
        proxy_tool = DynamicToolDef(
            name=f"upstream_{self.server_name}_call",
            description=f"Proxy JSON-RPC tool invocation to upstream MCP server '{self.server_name}'",
            parameters=[
                ToolParameter(
                    name="method",
                    type="string",
                    description="MCP JSON-RPC method (e.g. tools/list, tools/call)",
                    required=True,
                    default="tools/call"
                ),
                ToolParameter(
                    name="params",
                    type="object",
                    description="Method parameters dict",
                    required=False,
                    default={}
                )
            ]
        )

        return [(proxy_tool, self._create_proxy_handler())]

    def _create_proxy_handler(self) -> Callable:
        cmd_tokens = shlex.split(self.server_command)
        sandbox = self.sandbox

        async def handler(method: str, params: Optional[dict] = None) -> str:
            req_id = 1
            payload = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params or {}
            }
            json_line = json.dumps(payload) + "\n"

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd_tokens,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout_data, stderr_data = await asyncio.wait_for(
                    proc.communicate(input=json_line.encode()),
                    timeout=20.0
                )
                out_str = stdout_data.decode(errors="replace").strip()
                if not out_str:
                    return f"Upstream error: {stderr_data.decode(errors='replace')}"
                return out_str
            except Exception as e:
                return json.dumps({"error": f"Failed upstream MCP proxy call: {e}"})

        return handler
