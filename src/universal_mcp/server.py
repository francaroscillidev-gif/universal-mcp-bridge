import os
import json
import inspect
import time
from pathlib import Path
from typing import List, Optional, Union, Dict, Any
import yaml

from mcp.server.mcpserver import MCPServer
from universal_mcp.models import SecurityPolicy, DynamicToolDef
from universal_mcp.security.rbac import RoleDefinition, RBACManager
from universal_mcp.security.sandbox import CommandSandbox
from universal_mcp.security.rate_limiter import RateLimiter, RateLimitExceededError
from universal_mcp.security.audit import AuditLogger
from universal_mcp.security.cache import ResponseCache
from universal_mcp.security.hitl import HumanInTheLoopManager, ConfirmationRequiredError
from universal_mcp.security.redactor import PIISecretRedactor
from universal_mcp.security.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from universal_mcp.security.rbac import RBACManager
from universal_mcp.security.metrics import (
    TOOL_CALLS_TOTAL, TOOL_EXECUTION_DURATION_SECONDS,
    CACHE_HITS_TOTAL, RATE_LIMIT_EXCEEDED_TOTAL
)
from universal_mcp.optimizer import PromptOptimizer
from universal_mcp.jobs import AsyncJobQueue
from universal_mcp.workflow import WorkflowChainer, WorkflowPipeline
from universal_mcp.watcher import FileWatcher
from universal_mcp.config import EnvInterpolator
from universal_mcp.adapters.openapi_adapter import OpenAPIAdapter
from universal_mcp.adapters.script_adapter import ScriptAdapter
from universal_mcp.adapters.cli_adapter import CLIAdapter
from universal_mcp.adapters.sqlite_adapter import SQLiteAdapter
from universal_mcp.adapters.postgres_adapter import PostgresAdapter
from universal_mcp.adapters.redis_adapter import RedisAdapter
from universal_mcp.adapters.graphql_adapter import GraphQLAdapter

class UniversalMCPBridge:
    """
    Enterprise-grade Bridge & Proxy engine with Prometheus metrics,
    Circuit Breakers, RBAC, Multi-step Pipelines, Secret Redaction, Async Jobs, and Prompt Optimization.
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

        # RBAC setup
        rbac_policy = self.security.policy.rbac
        if rbac_policy and rbac_policy.enabled:
            roles_dict = {}
            for r_name, r_conf in rbac_policy.roles.items():
                roles_dict[r_name] = RoleDefinition(
                    name=r_name,
                    allowed_tools=r_conf.get("allowed", ["*"]),
                    denied_tools=r_conf.get("denied", [])
                )
            self.rbac = RBACManager(secret_key=rbac_policy.jwt_secret, roles=roles_dict)
        else:
            self.rbac = None

        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.cb_policy = self.security.policy.circuit_breaker

        self.audit_logger = AuditLogger(audit_log_path)
        self.job_queue = AsyncJobQueue()
        self.workflow_chainer = WorkflowChainer(self)
        self.watcher = FileWatcher()
        self.registered_tools: List[DynamicToolDef] = []
        self._setup_system_resources()
        self._setup_system_tools()

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
                    "has_hitl": self.hitl is not None,
                    "has_rbac": self.rbac is not None,
                    "redact_secrets": self.security.policy.redact_secrets,
                    "has_circuit_breaker": self.cb_policy.enabled if self.cb_policy else False
                }
            }
            return json.dumps(manifest, indent=2)

    def _setup_system_tools(self):
        """Registers built-in system tools for managing async jobs and pipelines."""
        @self.server.tool()
        def job_status(job_id: str) -> str:
            """Check the status and result of a background asynchronous job."""
            job = self.job_queue.get_job(job_id)
            if not job:
                return json.dumps({"error": f"Job '{job_id}' not found"})
            return json.dumps(job.model_dump(), indent=2)

        @self.server.tool()
        async def run_pipeline(pipeline_definition: str, initial_inputs_json: str = "{}") -> str:
            """Execute a multi-step workflow pipeline chaining multiple MCP tools sequentially."""
            try:
                pipe_dict = json.loads(pipeline_definition)
                pipeline = WorkflowPipeline(**pipe_dict)
                initial_inputs = json.loads(initial_inputs_json) if initial_inputs_json else {}
                res = await self.workflow_chainer.execute_pipeline(pipeline, initial_inputs)
                return json.dumps(res, indent=2)
            except Exception as e:
                return json.dumps({"error": f"Pipeline execution failed: {e}"})

    def optimize_descriptions(self):
        """Enriches all registered tools descriptions for better LLM comprehension."""
        return PromptOptimizer.optimize_bridge_tools(self)

    def mount_openapi(self, spec_dict_or_path: Union[dict, str], base_url: Optional[str] = None, headers: Optional[Dict[str, str]] = None):
        interp_headers = EnvInterpolator.interpolate(headers) if headers else None
        interp_base_url = EnvInterpolator.interpolate_str(base_url) if base_url else None
        
        if isinstance(spec_dict_or_path, str) and os.path.exists(spec_dict_or_path):
            self.watcher.watch_path(spec_dict_or_path)

        adapter = OpenAPIAdapter(spec_dict_or_path, base_url=interp_base_url, default_headers=interp_headers)
        self._register_adapter_tools(adapter)
        return self

    def mount_graphql(self, endpoint_url: str, headers: Optional[Dict[str, str]] = None):
        interp_headers = EnvInterpolator.interpolate(headers) if headers else None
        interp_url = EnvInterpolator.interpolate_str(endpoint_url)
        adapter = GraphQLAdapter(interp_url, headers=interp_headers)
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
        redact = self.security.policy.redact_secrets
        rbac = self.rbac

        if self.cb_policy and self.cb_policy.enabled:
            cb = CircuitBreaker(
                failure_threshold=self.cb_policy.failure_threshold,
                recovery_timeout_seconds=self.cb_policy.recovery_timeout_seconds
            )
            self.circuit_breakers[tool_def.name] = cb
        else:
            cb = None

        async def wrapped_handler(**kwargs):
            logged_args = PIISecretRedactor.redact_dict(kwargs) if redact else kwargs

            # RBAC Check (if caller provided _auth_token or context role)
            caller_token = kwargs.pop("_auth_token", None)
            if rbac and caller_token:
                try:
                    token_data = rbac.verify_token(caller_token)
                    role = token_data.get("role", "agent")
                    if not rbac.is_tool_allowed(role, tool_def.name):
                        msg = f"RBAC Access Denied: Role '{role}' cannot invoke tool '{tool_def.name}'"
                        audit_logger.log_call(tool_def.name, logged_args, 0, False, msg)
                        return f"Error: {msg}"
                except Exception as e:
                    return f"Authentication Error: {e}"

            # Circuit Breaker check
            if cb and not cb.can_execute():
                err_msg = f"Circuit breaker OPEN for tool '{tool_def.name}': upstream is failing or cooling down."
                TOOL_CALLS_TOTAL.labels(tool_name=tool_def.name, status="circuit_open").inc()
                audit_logger.log_call(tool_def.name, logged_args, 0, False, err_msg)
                return f"Error: {err_msg}"

            # HITL check
            if hitl and (not sensitive_tools or tool_def.name in sensitive_tools):
                approved = await hitl.verify_approval(tool_def.name, logged_args)
                if not approved:
                    TOOL_CALLS_TOTAL.labels(tool_name=tool_def.name, status="hitl_rejected").inc()
                    audit_logger.log_call(tool_def.name, logged_args, 0, False, "User rejected execution")
                    return f"Action '{tool_def.name}' was rejected by human operator."

            # Cache check
            if cache:
                cached_res = cache.get(tool_def.name, kwargs)
                if cached_res is not None:
                    CACHE_HITS_TOTAL.labels(tool_name=tool_def.name).inc()
                    TOOL_CALLS_TOTAL.labels(tool_name=tool_def.name, status="cache_hit").inc()
                    return cached_res

            # Rate limit check
            if rate_limiter:
                try:
                    rate_limiter.check_and_record()
                except RateLimitExceededError as e:
                    RATE_LIMIT_EXCEEDED_TOTAL.labels(tool_name=tool_def.name).inc()
                    TOOL_CALLS_TOTAL.labels(tool_name=tool_def.name, status="rate_limited").inc()
                    audit_logger.log_call(tool_def.name, logged_args, 0, False, str(e))
                    return f"Error: {e}"

            start_time = time.time()
            success = True
            error_msg = None
            try:
                if inspect.iscoroutinefunction(handler_func):
                    res = await handler_func(**kwargs)
                else:
                    res = handler_func(**kwargs)

                if redact and isinstance(res, str):
                    res = PIISecretRedactor.redact_text(res)

                if cache and success:
                    cache.set(tool_def.name, kwargs, res)

                if cb:
                    cb.record_success()

                TOOL_CALLS_TOTAL.labels(tool_name=tool_def.name, status="success").inc()
                return res
            except Exception as e:
                success = False
                error_msg = str(e)
                if cb:
                    cb.record_failure()
                TOOL_CALLS_TOTAL.labels(tool_name=tool_def.name, status="error").inc()
                return f"Execution Error: {e}"
            finally:
                duration = time.time() - start_time
                TOOL_EXECUTION_DURATION_SECONDS.labels(tool_name=tool_def.name).observe(duration)
                audit_logger.log_call(tool_def.name, logged_args, duration * 1000, success, error_msg)

        import functools
        functools.update_wrapper(wrapped_handler, handler_func)
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
