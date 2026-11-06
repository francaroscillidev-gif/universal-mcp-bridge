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
from universal_mcp.security.metrics import get_prometheus_metrics
from universal_mcp.config import EnvInterpolator
from universal_mcp.watcher import FileWatcher
from universal_mcp.models import SecurityPolicy, RateLimitPolicy, CachePolicy, HITLPolicy
from universal_mcp.adapters.openapi_adapter import OpenAPIAdapter
from universal_mcp.adapters.graphql_adapter import GraphQLAdapter
from universal_mcp.adapters.script_adapter import ScriptAdapter
from universal_mcp.adapters.sqlite_adapter import SQLiteAdapter
from universal_mcp.adapters.postgres_adapter import PostgresAdapter
from universal_mcp.adapters.redis_adapter import RedisAdapter
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
    # Test recovery
    import time
    time.sleep(0.15)
    assert cb.can_execute() is True
    assert cb.state == "HALF_OPEN"
    cb.record_success()
    assert cb.state == "CLOSED"

def test_prometheus_metrics():
    metrics_data, content_type = get_prometheus_metrics()
    assert b"mcp_tool_calls_total" in metrics_data
    assert "text/plain" in content_type

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
