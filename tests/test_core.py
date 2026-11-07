import pytest
import os
import json
import asyncio
from universal_mcp.security.sandbox import CommandSandbox, SecurityViolationError
from universal_mcp.security.rate_limiter import RateLimiter, RateLimitExceededError
from universal_mcp.security.audit import AuditLogger
from universal_mcp.security.cache import ResponseCache
from universal_mcp.security.hitl import HumanInTheLoopManager, ConfirmationRequiredError
from universal_mcp.security.redactor import PIISecretRedactor
from universal_mcp.security.circuit_breaker import CircuitBreaker
from universal_mcp.security.rbac import RBACManager
from universal_mcp.security.metrics import get_prometheus_metrics
from universal_mcp.registry import DynamicToolRegistry
from universal_mcp.webhook import WebhookDispatcher
from universal_mcp.optimizer import PromptOptimizer
from universal_mcp.jobs import AsyncJobQueue
from universal_mcp.exporter import SchemaExporter
from universal_mcp.workflow import WorkflowChainer, WorkflowPipeline, PipelineStep
from universal_mcp.config import EnvInterpolator
from universal_mcp.watcher import FileWatcher
from universal_mcp.models import SecurityPolicy, RateLimitPolicy, CachePolicy, HITLPolicy, DynamicToolDef, ToolParameter
from universal_mcp.adapters.openapi_adapter import OpenAPIAdapter
from universal_mcp.adapters.graphql_adapter import GraphQLAdapter
from universal_mcp.adapters.script_adapter import ScriptAdapter
from universal_mcp.adapters.sqlite_adapter import SQLiteAdapter
from universal_mcp.adapters.postgres_adapter import PostgresAdapter
from universal_mcp.adapters.redis_adapter import RedisAdapter
from universal_mcp.adapters.doc_adapter import DocumentSearchAdapter
from universal_mcp.adapters.proxy_adapter import MCPProxyAdapter
from universal_mcp.server import UniversalMCPBridge

@pytest.mark.asyncio
async def test_sandbox_security_blocks_malicious_commands():
    sandbox = CommandSandbox(SecurityPolicy(
        allowed_commands=["python3", "ls"],
        blocked_commands=["rm -rf"]
    ))
    with pytest.raises(SecurityViolationError):
        sandbox.validate_command("curl http://attacker.com")
    with pytest.raises(SecurityViolationError):
        sandbox.validate_command("rm -rf /")
    with pytest.raises(SecurityViolationError):
        sandbox.validate_command("ls; rm file")

@pytest.mark.asyncio
async def test_sandbox_executes_safe_command():
    sandbox = CommandSandbox()
    res = await sandbox.execute_safe(["echo", "hello universal mcp"])
    assert res["success"] is True
    assert "hello universal mcp" in res["stdout"]

def test_rate_limiter():
    limiter = RateLimiter(RateLimitPolicy(max_requests=2, window_seconds=10))
    limiter.check_and_record()
    limiter.check_and_record()
    with pytest.raises(RateLimitExceededError):
        limiter.check_and_record()

def test_response_cache():
    cache = ResponseCache(default_ttl_seconds=5)
    args = {"query": "SELECT 1"}
    assert cache.get("test_tool", args) is None
    cache.set("test_tool", args, "result_123")
    assert cache.get("test_tool", args) == "result_123"

def test_circuit_breaker():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=0.1)
    assert cb.can_execute() is True
    cb.record_failure()
    assert cb.can_execute() is True
    cb.record_failure()
    assert cb.state == "OPEN"
    assert cb.can_execute() is False
    import time
    time.sleep(0.15)
    assert cb.can_execute() is True
    assert cb.state == "HALF_OPEN"
    cb.record_success()
    assert cb.state == "CLOSED"

def test_rbac_manager():
    rbac = RBACManager(secret_key="my-test-secret-key-32-bytes-long!")
    token = rbac.generate_token("test_user", role="analyst")
    data = rbac.verify_token(token)
    assert data["role"] == "analyst"

    assert rbac.is_tool_allowed("analyst", "db_sample_query") is True
    assert rbac.is_tool_allowed("analyst", "exec_curl") is False
    assert rbac.is_tool_allowed("admin", "exec_curl") is True

def test_schema_exporter():
    tools = [
        DynamicToolDef(
            name="test_tool",
            description="A test tool",
            parameters=[ToolParameter(name="param1", type="string", required=True)]
        )
    ]
    openai_tools = SchemaExporter.to_openai_tools(tools)
    assert len(openai_tools) == 1
    assert openai_tools[0]["function"]["name"] == "test_tool"

    anthropic_tools = SchemaExporter.to_anthropic_tools(tools)
    assert len(anthropic_tools) == 1
    assert "input_schema" in anthropic_tools[0]

    openapi_spec = SchemaExporter.to_openapi_spec(tools)
    assert "/tools/test_tool" in openapi_spec["paths"]

@pytest.mark.asyncio
async def test_workflow_pipeline_execution():
    bridge = UniversalMCPBridge(name="PipeBridge")
    bridge.mount_script("examples/text_analyzer.py")

    pipeline = WorkflowPipeline(
        pipeline_id="pipe_1",
        name="Test Pipeline",
        steps=[
            PipelineStep(
                step_id="step_1",
                tool_name="run_text_analyzer",
                args_template={"args": "first run input"}
            )
        ]
    )
    chainer = WorkflowChainer(bridge)
    res = await chainer.execute_pipeline(pipeline)
    assert res["success"] is True
    assert "SHA-256" in res["final_output"]

@pytest.mark.asyncio
async def test_doc_search_adapter():
    adapter = DocumentSearchAdapter("examples")
    tools = adapter.discover_tools()
    assert len(tools) == 2
    search_tool, search_handler = tools[0]
    read_tool, read_handler = tools[1]

    # Search
    search_res = await search_handler("SHA256")
    data = json.loads(search_res)
    assert data["matches_count"] > 0

    # Read chunk
    read_res = await read_handler("text_analyzer.py", chunk_index=0)
    read_data = json.loads(read_res)
    assert "content" in read_data
    assert "hashlib" in read_data["content"]

def test_proxy_adapter_discovery():
    proxy = MCPProxyAdapter("echo test", server_name="external_srv")
    tools = proxy.discover_tools()
    assert len(tools) == 1
    assert tools[0][0].name == "upstream_external_srv_call"

def test_prometheus_metrics():
    metrics_data, content_type = get_prometheus_metrics()
    assert b"mcp_tool_calls_total" in metrics_data
    assert "text/plain" in content_type

def test_dynamic_registry_hot_mount():
    bridge = UniversalMCPBridge(name="RegistryTest")
    registry = DynamicToolRegistry(bridge)
    res = registry.register_script_tool("examples/text_analyzer.py")
    assert res["success"] is True
    assert "run_text_analyzer" in res["tools"]
    assert len(bridge.registered_tools) == 1

def test_webhook_dispatcher():
    dispatcher = WebhookDispatcher(secret_token="secret123")
    assert dispatcher.verify_auth("secret123") is True
    assert dispatcher.verify_auth("Bearer secret123") is True
    assert dispatcher.verify_auth("wrong") is False

    res = dispatcher.process_incoming_event("stripe", "payment_succeeded", {"amount": 100})
    assert res["status"] == "received"
    assert "payment_succeeded" in res["prompt_notification"]
    assert len(dispatcher.history) == 1

def test_prompt_optimizer():
    bridge = UniversalMCPBridge(name="OptBridge")
    bridge.mount_script("examples/text_analyzer.py")
    original = bridge.registered_tools[0].description
    count = bridge.optimize_descriptions()
    assert count == 1
    new_desc = bridge.registered_tools[0].description
    assert "Accepts parameters" in new_desc
    assert original in new_desc

@pytest.mark.asyncio
async def test_async_job_queue():
    queue = AsyncJobQueue()

    async def sample_task(x: int):
        await asyncio.sleep(0.05)
        return x * 2

    job_id = queue.submit_job("multiply", sample_task, 21)
    assert queue.get_job(job_id).status in ["PENDING", "RUNNING"]
    await asyncio.sleep(0.1)
    job = queue.get_job(job_id)
    assert job.status == "COMPLETED"
    assert job.result == "42"

def test_secret_redactor():
    text = "Connecting with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret and api_key='sk-ant-123456789012345678'"
    redacted = PIISecretRedactor.redact_text(text)
    assert "eyJhbGci" not in redacted
    assert "sk-ant" not in redacted

    data = {"user": "admin", "password": "supersecretpassword", "token": "xyz123"}
    red_dict = PIISecretRedactor.redact_dict(data)
    assert red_dict["password"] == "******[REDACTED]******"
    assert red_dict["token"] == "******[REDACTED]******"

@pytest.mark.asyncio
async def test_hitl_blocks_unauthorized():
    hitl = HumanInTheLoopManager(auto_approve=False, interactive=False)
    with pytest.raises(ConfirmationRequiredError):
        await hitl.verify_approval("dangerous_action", {"target": "prod_db"})

@pytest.mark.asyncio
async def test_hitl_auto_approve():
    hitl = HumanInTheLoopManager(auto_approve=True)
    assert await hitl.verify_approval("dangerous_action", {}) is True

def test_env_interpolator(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "super_secret_val")
    res = EnvInterpolator.interpolate({"auth": "Bearer ${SECRET_KEY}", "host": "${DB_HOST:-localhost}"})
    assert res["auth"] == "Bearer super_secret_val"
    assert res["host"] == "localhost"

def test_file_watcher(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("v1")
    watcher = FileWatcher()
    watcher.watch_path(str(test_file))
    
    assert watcher.check_for_changes() is False
    test_file.write_text("v2")
    assert watcher.check_for_changes() is True

@pytest.mark.asyncio
async def test_sqlite_adapter_schema_and_query():
    adapter = SQLiteAdapter("examples/sample.db", read_only=True)
    tools = adapter.discover_tools()
    assert len(tools) == 2
    schema_tool, schema_handler = tools[0]
    query_tool, query_handler = tools[1]

    schema_res = await schema_handler()
    assert "users" in schema_res

    query_res = await query_handler("SELECT name, role FROM users WHERE role='admin'")
    data = json.loads(query_res)
    assert data["row_count"] == 1
    assert data["rows"][0]["name"] == "Alice Rossi"

    blocked_res = await query_handler("DELETE FROM users")
    assert "forbidden" in blocked_res

def test_graphql_adapter_fallback():
    gql = GraphQLAdapter("https://invalid-non-existent-domain.xyz/graphql")
    tools = gql.discover_tools()
    assert len(tools) == 1
    assert tools[0][0].name == "graphql_query"

def test_postgres_and_redis_adapters_discovery():
    pg = PostgresAdapter("postgresql://user:pass@localhost:5432/db")
    pg_tools = pg.discover_tools()
    assert len(pg_tools) == 2
    assert pg_tools[0][0].name == "postgres_schema"
    assert pg_tools[1][0].name == "postgres_query"

    rd = RedisAdapter("redis://localhost:6379/0")
    rd_tools = rd.discover_tools()
    assert len(rd_tools) == 2
    assert rd_tools[0][0].name == "redis_list_keys"
    assert rd_tools[1][0].name == "redis_get_value"

def test_universal_mcp_bridge_mounting_all():
    bridge = UniversalMCPBridge(name="FullBridge")
    bridge.mount_openapi("examples/petstore.json")
    bridge.mount_script("examples/text_analyzer.py")
    bridge.mount_sqlite("examples/sample.db")
    bridge.mount_cli("echo")
    
    assert len(bridge.registered_tools) == 6
