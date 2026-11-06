import os
import json
import inspect
import time
from pathlib import Path
from typing import List, Optional, Union, Dict, Any
import yaml

from mcp.server.mcpserver import MCPServer
from universal_mcp.models import SecurityPolicy, DynamicToolDef
from universal_mcp.security.sandbox import CommandSandbox
from universal_mcp.security.rate_limiter import RateLimiter, RateLimitExceededError
from universal_mcp.security.audit import AuditLogger
from universal_mcp.security.cache import ResponseCache
from universal_mcp.security.hitl import HumanInTheLoopManager, ConfirmationRequiredError
from universal_mcp.watcher import FileWatcher
from universal_mcp.config import EnvInterpolator
from universal_mcp.adapters.openapi_adapter import OpenAPIAdapter
from universal_mcp.adapters.script_adapter import ScriptAdapter
from universal_mcp.adapters.cli_adapter import CLIAdapter
from universal_mcp.adapters.sqlite_adapter import SQLiteAdapter
from universal_mcp.adapters.postgres_adapter import PostgresAdapter
from universal_mcp.adapters.redis_adapter import RedisAdapter

class UniversalMCPBridge:
    """
    Enterprise-grade Bridge & Proxy engine that dynamically transforms
    OpenAPI, Scripts, CLIs, SQLite, PostgreSQL and Redis into standard MCP servers.
    """
    def __init__(
        self,
        name: str = "Universal-MCP-Server",
        security_policy: Optional[SecurityPolicy] = None,
        audit_log_path: Optional[str] = None,
        interactive_hitl: bool = False
    ):
        self.name = name
        self.server = MCPServer(name)
        self.security = CommandSandbox(security_policy or SecurityPolicy())
        self.rate_limiter = RateLimiter(self.security.policy.rate_limit) if self.security.policy.rate_limit else None
        
        # Cache setup
        cache_policy = self.security.policy.cache
        if cache_policy and cache_policy.enabled:
            self.cache = ResponseCache(
                default_ttl_seconds=cache_policy.default_ttl_seconds,
                max_entries=cache_policy.max_entries
            )
        else:
            self.cache = None

        # HITL setup
        hitl_policy = self.security.policy.hitl
        if hitl_policy and hitl_policy.require_confirmation:
            self.hitl = HumanInTheLoopManager(interactive=interactive_hitl)
            self.sensitive_tools = set(hitl_policy.sensitive_tools)
        else:
            self.hitl = None
            self.sensitive_tools = set()

        self.audit_logger = AuditLogger(audit_log_path)
        self.watcher = FileWatcher()
        self.registered_tools: List[DynamicToolDef] = []
        self._setup_system_resources()

    def _setup_system_resources(self):
        @self.server.resource("bridge://manifest")
        def get_manifest() -> str:
            manifest = {
                "server_name": self.name,
                "tool_count": len(self.registered_tools),
                "tools": [t.model_dump() for t in self.registered_tools],
                "security": {
                    "timeout": self.security.policy.timeout_seconds,
                    "has_whitelist": self.security.policy.allowed_commands is not None,
                    "has_rate_limit": self.rate_limiter is not None,
                    "has_cache": self.cache is not None,
                    "has_hitl": self.hitl is not None
                }
            }
            return json.dumps(manifest, indent=2)

    def mount_openapi(self, spec_dict_or_path: Union[dict, str], base_url: Optional[str] = None, headers: Optional[Dict[str, str]] = None):
        interp_headers = EnvInterpolator.interpolate(headers) if headers else None
        interp_base_url = EnvInterpolator.interpolate_str(base_url) if base_url else None
        
        if isinstance(spec_dict_or_path, str) and os.path.exists(spec_dict_or_path):
            self.watcher.watch_path(spec_dict_or_path)

        adapter = OpenAPIAdapter(spec_dict_or_path, base_url=interp_base_url, default_headers=interp_headers)
        self._register_adapter_tools(adapter)
        return self

    def mount_script(self, script_path: str):
        if os.path.exists(script_path):
            self.watcher.watch_path(script_path)
        adapter = ScriptAdapter(script_path, sandbox=self.security)
        self._register_adapter_tools(adapter)
        return self

    def mount_cli(self, cli_name: str, subcommands: Optional[List[str]] = None):
        adapter = CLIAdapter(cli_name, subcommands=subcommands, sandbox=self.security)
        self._register_adapter_tools(adapter)
        return self

    def mount_sqlite(self, db_path: str, read_only: bool = True):
        if os.path.exists(db_path):
            self.watcher.watch_path(db_path)
        adapter = SQLiteAdapter(db_path, read_only=read_only)
        self._register_adapter_tools(adapter)
        return self

    def mount_postgres(self, dsn: str, read_only: bool = True):
        interp_dsn = EnvInterpolator.interpolate_str(dsn)
        adapter = PostgresAdapter(interp_dsn, read_only=read_only)
        self._register_adapter_tools(adapter)
        return self

    def mount_redis(self, redis_url: str = "redis://localhost:6379/0", read_only: bool = True):
        interp_url = EnvInterpolator.interpolate_str(redis_url)
        adapter = RedisAdapter(interp_url, read_only=read_only)
        self._register_adapter_tools(adapter)
        return self

    def mount_directory(self, dir_path: str):
        folder = Path(dir_path)
        if not folder.is_dir():
            raise NotADirectoryError(f"Not a directory: {dir_path}")

        self.watcher.watch_path(str(folder))

        for file in folder.iterdir():
            if file.name.startswith("."):
                continue
            if file.suffix in [".json", ".yaml", ".yml"]:
                try:
                    content = file.read_text(encoding="utf-8")
                    data = yaml.safe_load(content) if file.suffix in [".yaml", ".yml"] else json.loads(content)
                    if isinstance(data, dict) and ("openapi" in data or "swagger" in data):
                        self.mount_openapi(data)
                except Exception:
                    pass
            elif file.suffix in [".py", ".sh", ".bash"]:
                self.mount_script(str(file))
            elif file.suffix in [".db", ".sqlite", ".sqlite3"]:
                self.mount_sqlite(str(file), read_only=True)

        return self

    def _register_adapter_tools(self, adapter):
        tools = adapter.discover_tools()
        for tool_def, handler in tools:
            self._register_tool(tool_def, handler)

    def _register_tool(self, tool_def: DynamicToolDef, handler_func):
        rate_limiter = self.rate_limiter
        audit_logger = self.audit_logger
        cache = self.cache
        hitl = self.hitl
        sensitive_tools = self.sensitive_tools

        async def wrapped_handler(**kwargs):
            # HITL confirmation check
            if hitl and (not sensitive_tools or tool_def.name in sensitive_tools):
                approved = await hitl.verify_approval(tool_def.name, kwargs)
                if not approved:
                    audit_logger.log_call(tool_def.name, kwargs, 0, False, "User rejected execution")
                    return f"Action '{tool_def.name}' was rejected by human operator."

            # Cache check
            if cache:
                cached_res = cache.get(tool_def.name, kwargs)
                if cached_res is not None:
                    return cached_res

            # Rate limit check
            if rate_limiter:
                try:
                    rate_limiter.check_and_record()
                except RateLimitExceededError as e:
                    audit_logger.log_call(tool_def.name, kwargs, 0, False, str(e))
                    return f"Error: {e}"

            start_time = time.time()
            success = True
            error_msg = None
            try:
                if inspect.iscoroutinefunction(handler_func):
                    res = await handler_func(**kwargs)
                else:
                    res = handler_func(**kwargs)

                if cache and success:
                    cache.set(tool_def.name, kwargs, res)

                return res
            except Exception as e:
                success = False
                error_msg = str(e)
                return f"Execution Error: {e}"
            finally:
                duration_ms = (time.time() - start_time) * 1000
                audit_logger.log_call(tool_def.name, kwargs, duration_ms, success, error_msg)

        wrapped_handler.__name__ = tool_def.name
        wrapped_handler.__doc__ = tool_def.description

        self.server.add_tool(
            fn=wrapped_handler,
            name=tool_def.name,
            description=tool_def.description
        )
        self.registered_tools.append(tool_def)

    def run_stdio(self):
        self.server.run(transport="stdio")

    def run_sse(self, host: str = "127.0.0.1", port: int = 8080):
        self.server.run(transport="sse")
