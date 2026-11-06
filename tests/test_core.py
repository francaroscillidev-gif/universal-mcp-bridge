import pytest
import os
import json
import asyncio
from universal_mcp.security.sandbox import CommandSandbox, SecurityViolationError
from universal_mcp.security.rate_limiter import RateLimiter, RateLimitExceededError
from universal_mcp.security.audit import AuditLogger
from universal_mcp.security.cache import ResponseCache
from universal_mcp.config import EnvInterpolator
from universal_mcp.watcher import FileWatcher
from universal_mcp.models import SecurityPolicy, RateLimitPolicy, CachePolicy
from universal_mcp.adapters.openapi_adapter import OpenAPIAdapter
from universal_mcp.adapters.script_adapter import ScriptAdapter
from universal_mcp.adapters.sqlite_adapter import SQLiteAdapter
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

    # Test schema
    schema_res = await schema_handler()
    assert "users" in schema_res

    # Test query
    query_res = await query_handler("SELECT name, role FROM users WHERE role='admin'")
    data = json.loads(query_res)
    assert data["row_count"] == 1
    assert data["rows"][0]["name"] == "Alice Rossi"

    # Test read-only guard against write queries
    blocked_res = await query_handler("DELETE FROM users")
    assert "forbidden" in blocked_res

@pytest.mark.asyncio
async def test_audit_logger(tmp_path):
    log_file = str(tmp_path / "audit.jsonl")
    logger = AuditLogger(log_file)
    logger.log_call("test_tool", {"a": 1}, 12.5, True)

    assert os.path.exists(log_file)
    with open(log_file, "r") as f:
        line = json.loads(f.readline())
        assert line["tool"] == "test_tool"
        assert line["success"] is True

def test_universal_mcp_bridge_mounting_all():
    bridge = UniversalMCPBridge(name="FullBridge")
    bridge.mount_openapi("examples/petstore.json")
    bridge.mount_script("examples/text_analyzer.py")
    bridge.mount_sqlite("examples/sample.db")
    bridge.mount_cli("echo")
    
    # 2 from openapi + 1 script + 2 sqlite (schema & query) + 1 cli (echo) = 6 tools
    assert len(bridge.registered_tools) == 6
