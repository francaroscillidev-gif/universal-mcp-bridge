import os
import sys
import yaml
import json
import click
import uvicorn
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from universal_mcp.server import UniversalMCPBridge
from universal_mcp.models import SecurityPolicy
from universal_mcp.config import EnvInterpolator
from universal_mcp.dashboard import create_dashboard_app
from universal_mcp.optimizer import PromptOptimizer
from universal_mcp.exporter import SchemaExporter

load_dotenv()
console = Console()

def build_bridge_from_config(config_file: str, audit_log: str = None, interactive_hitl: bool = False, optimize_prompts: bool = False) -> UniversalMCPBridge:
    with open(config_file, "r", encoding="utf-8") as f:
        raw_cfg = yaml.safe_load(f)
    
    cfg = EnvInterpolator.interpolate(raw_cfg)

    server_name = cfg.get("name", "Universal-MCP")
    security_policy = SecurityPolicy(**cfg.get("security", {}))
    audit_file = audit_log or cfg.get("audit_log")

    bridge = UniversalMCPBridge(
        name=server_name,
        security_policy=security_policy,
        audit_log_path=audit_file,
        interactive_hitl=interactive_hitl
    )

    for item in cfg.get("mounts", []):
        m_type = item.get("type")
        m_target = item.get("target")
        if m_type == "openapi":
            bridge.mount_openapi(m_target, base_url=item.get("base_url"), headers=item.get("headers"))
        elif m_type == "graphql":
            bridge.mount_graphql(m_target, headers=item.get("headers"))
        elif m_type == "script":
            bridge.mount_script(m_target)
        elif m_type == "cli":
            bridge.mount_cli(m_target, subcommands=item.get("subcommands"))
        elif m_type == "sqlite":
            bridge.mount_sqlite(m_target, read_only=item.get("read_only", True))
        elif m_type == "postgres":
            bridge.mount_postgres(m_target, read_only=item.get("read_only", True))
        elif m_type == "redis":
            bridge.mount_redis(m_target, read_only=item.get("read_only", True))
        elif m_type == "documents":
            bridge.mount_documents(m_target, max_chunk_chars=item.get("max_chunk_chars", 4000))
        elif m_type == "upstream_mcp":
            bridge.mount_upstream_mcp(m_target, server_name=item.get("name", "upstream"))
        elif m_type == "directory":
            bridge.mount_directory(m_target)


    if optimize_prompts:
        bridge.optimize_descriptions()

    return bridge

@click.group()
def cli():
    """Universal MCP Bridge - Turn OpenAPI, GraphQL, Scripts, Databases & CLIs into MCP Servers instantly."""
    pass

@cli.command("serve")
@click.option("--openapi", "openapi_path", help="Path or URL to OpenAPI JSON/YAML spec")
@click.option("--graphql", "graphql_url", help="GraphQL endpoint URL")
@click.option("--base-url", "base_url", help="Override base URL for OpenAPI calls")
@click.option("--script", "script_path", help="Path to Python (.py) or Shell (.sh) script")
@click.option("--cli", "cli_name", help="CLI tool to wrap (e.g. git, jq, curl)")
@click.option("--sqlite", "sqlite_path", help="Path to SQLite database file (.db, .sqlite)")
@click.option("--postgres", "postgres_dsn", help="PostgreSQL connection DSN")
@click.option("--redis", "redis_url", help="Redis connection URL")
@click.option("--dir", "dir_path", help="Directory with scripts, specs & DBs to auto-discover")
@click.option("--config", "config_file", help="Path to universal-mcp.yaml configuration file")
@click.option("--audit-log", "audit_log", help="Path to write JSONL audit log entries")
@click.option("--hitl", is_flag=True, help="Enable interactive terminal Human-in-the-Loop confirmations")
@click.option("--optimize", is_flag=True, help="Enrich and optimize tool descriptions for LLM reasoning")
@click.option("--transport", default="stdio", type=click.Choice(["stdio", "sse"]), help="MCP transport mode")
@click.option("--port", default=8080, type=int, help="Port for SSE mode")
def serve(openapi_path, graphql_url, base_url, script_path, cli_name, sqlite_path, postgres_dsn, redis_url, dir_path, config_file, audit_log, hitl, optimize, transport, port):
    """Start an MCP server exposing specified tools."""
    if config_file:
        bridge = build_bridge_from_config(config_file, audit_log=audit_log, interactive_hitl=hitl, optimize_prompts=optimize)
    else:
        bridge = UniversalMCPBridge(name="Universal-MCP", audit_log_path=audit_log, interactive_hitl=hitl)

    if openapi_path:
        bridge.mount_openapi(openapi_path, base_url=base_url)
    if graphql_url:
        bridge.mount_graphql(graphql_url)
    if script_path:
        bridge.mount_script(script_path)
    if cli_name:
        bridge.mount_cli(cli_name)
    if sqlite_path:
        bridge.mount_sqlite(sqlite_path)
    if postgres_dsn:
        bridge.mount_postgres(postgres_dsn)
    if redis_url:
        bridge.mount_redis(redis_url)
    if dir_path:
        bridge.mount_directory(dir_path)

    if optimize:
        bridge.optimize_descriptions()

    if not bridge.registered_tools:
        console.print("[bold red]Error:[/bold red] No tools mounted! Specify target or config.")
        sys.exit(1)

    sys.stderr.write(f"\n[Universal MCP] Running '{bridge.name}' with {len(bridge.registered_tools)} tools on {transport} transport.\n")
    if bridge.audit_logger.log_file:
        sys.stderr.write(f"[Universal MCP] Audit logging active at: {bridge.audit_logger.log_file}\n")
    if bridge.cache:
        sys.stderr.write(f"[Universal MCP] Response caching enabled (TTL: {bridge.cache.default_ttl}s)\n")
    if bridge.hitl:
        sys.stderr.write("[Universal MCP] Human-in-the-Loop (HITL) protection enabled.\n")
    if bridge.rbac:
        sys.stderr.write("[Universal MCP] Multi-tenant RBAC enforcement enabled.\n")
    for tool in bridge.registered_tools:
        sys.stderr.write(f"  -> Tool: {tool.name} ({tool.description[:60]}...)\n")

    if transport == "stdio":
        bridge.run_stdio()
    else:
        bridge.run_sse(port=port)

@cli.command("test-tool")
@click.option("--config", "config_file", default="examples/universal-mcp.yaml", help="Path to YAML configuration")
@click.option("--name", "tool_name", required=True, help="Tool name to execute")
@click.option("--args", "args_json", default="{}", help="JSON string of arguments")
def test_tool_cmd(config_file, tool_name, args_json):
    """Directly test and invoke an MCP tool from CLI without starting an LLM client."""
    import asyncio
    bridge = build_bridge_from_config(config_file)
    tool = next((t for t in bridge.registered_tools if t.name == tool_name), None)
    if not tool:
        console.print(f"[bold red]Error:[/bold red] Tool '{tool_name}' not found in configuration.")
        console.print(f"Available tools: {', '.join([t.name for t in bridge.registered_tools])}")
        return

    try:
        kwargs = json.loads(args_json)
    except Exception as e:
        console.print(f"[bold red]Error parsing --args JSON:[/bold red] {e}")
        return

    console.print(f"[bold cyan]Invoking tool:[/bold cyan] {tool_name}")
    console.print(f"[bold cyan]Arguments:[/bold cyan] {kwargs}\n")

    async def _run():
        res = await bridge.server.call_tool(tool_name, kwargs)
        text_out = ""
        if hasattr(res, "content"):
            for c in res.content:
                text_out += getattr(c, "text", str(c))
        else:
            text_out = str(res)
        return text_out

    try:
        output = asyncio.run(_run())
        console.print(f"[bold green]Result:[/bold green]\n{output}")
    except Exception as e:
        console.print(f"[bold red]Execution failed:[/bold red] {e}")


@cli.command("export-schema")
@click.option("--config", "config_file", default="examples/universal-mcp.yaml", help="Path to YAML configuration")
@click.option("--format", "export_fmt", type=click.Choice(["openai", "anthropic", "openapi"]), default="openai", help="Target tool format")
@click.option("--output", "out_file", help="File to write exported JSON")
def export_schema_cmd(config_file, export_fmt, out_file):
    """Export tool schemas to OpenAI Tools, Anthropic Tools, or OpenAPI format."""
    bridge = build_bridge_from_config(config_file)
    tools = bridge.registered_tools

    if export_fmt == "openai":
        res = SchemaExporter.to_openai_tools(tools)
    elif export_fmt == "anthropic":
        res = SchemaExporter.to_anthropic_tools(tools)
    else:
        res = SchemaExporter.to_openapi_spec(tools, server_title=bridge.name)

    json_str = json.dumps(res, indent=2)
    if out_file:
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(json_str)
        console.print(f"[bold green]Exported {len(tools)} tools to '{out_file}' in {export_fmt} format.[/bold green]")
    else:
        console.print(json_str)

@cli.command("generate-token")
@click.option("--subject", prompt="Agent or User ID", help="Subject name")
@click.option("--role", type=click.Choice(["admin", "analyst", "agent"]), default="agent", help="Assigned RBAC role")
@click.option("--tenant", default="default", help="Tenant ID")
@click.option("--secret", default="super-secret-mcp-key", help="JWT secret key")
def generate_token_cmd(subject, role, tenant, secret):
    """Generate a signed multi-tenant RBAC JWT token for agent authentication."""
    from universal_mcp.security.rbac import RBACManager
    rbac = RBACManager(secret_key=secret)
    token = rbac.generate_token(subject=subject, role=role, tenant_id=tenant)
    console.print(f"\n[bold green]Generated JWT Token for '{subject}' (Role: {role}):[/bold green]\n")
    console.print(token)
    console.print("\nPass this token to tools via `_auth_token` or `Authorization: Bearer <token>`.")

@cli.command("optimize-prompts")
@click.option("--config", "config_file", default="examples/universal-mcp.yaml", help="Path to YAML configuration")
def optimize_prompts_cmd(config_file):
    """Enrich tool descriptions and export an enhanced manifest for agent prompts."""
    bridge = build_bridge_from_config(config_file)
    count = bridge.optimize_descriptions()
    console.print(f"[bold green]Successfully optimized prompt descriptions for {count} tools![/bold green]\n")
    
    table = Table(title="LLM-Optimized Tool Manifest")
    table.add_column("Tool Name", style="cyan")
    table.add_column("Optimized Prompt Description", style="white")
    for t in bridge.registered_tools:
        table.add_row(t.name, t.description)
    console.print(table)

@cli.command("dashboard")
@click.option("--config", "config_file", default="examples/universal-mcp.yaml", help="Path to YAML configuration")
@click.option("--host", default="127.0.0.1", help="Host interface")
@click.option("--port", default=8000, type=int, help="Port for the Dashboard")
def dashboard(config_file, host, port):
    """Start the interactive Web Dashboard and live monitoring UI."""
    bridge = build_bridge_from_config(config_file)
    app = create_dashboard_app(bridge)
    console.print(f"\n[bold green]🚀 Universal MCP Web Dashboard running on http://{host}:{port}[/bold green]\n")
    uvicorn.run(app, host=host, port=port, log_level="info")

@cli.command("inspect")
@click.option("--openapi", "openapi_path", help="Path or URL to OpenAPI JSON/YAML spec")
@click.option("--graphql", "graphql_url", help="GraphQL endpoint URL")
@click.option("--script", "script_path", help="Path to Python/Shell script")
@click.option("--cli", "cli_name", help="CLI tool to wrap")
@click.option("--sqlite", "sqlite_path", help="Path to SQLite database")
@click.option("--postgres", "postgres_dsn", help="PostgreSQL DSN")
@click.option("--redis", "redis_url", help="Redis URL")
@click.option("--dir", "dir_path", help="Directory with scripts & specs")
@click.option("--config", "config_file", help="Path to YAML configuration")
def inspect_tools(openapi_path, graphql_url, script_path, cli_name, sqlite_path, postgres_dsn, redis_url, dir_path, config_file):
    """Inspect and list tools that will be exposed without running the server."""
    if config_file:
        bridge = build_bridge_from_config(config_file)
    else:
        bridge = UniversalMCPBridge(name="Inspector")

    if openapi_path:
        bridge.mount_openapi(openapi_path)
    if graphql_url:
        bridge.mount_graphql(graphql_url)
    if script_path:
        bridge.mount_script(script_path)
    if cli_name:
        bridge.mount_cli(cli_name)
    if sqlite_path:
        bridge.mount_sqlite(sqlite_path)
    if postgres_dsn:
        bridge.mount_postgres(postgres_dsn)
    if redis_url:
        bridge.mount_redis(redis_url)
    if dir_path:
        bridge.mount_directory(dir_path)

    table = Table(title=f"Universal MCP Bridge - Discovered Tools ({len(bridge.registered_tools)})")
    table.add_column("Tool Name", style="cyan", no_wrap=True)
    table.add_column("Parameters", style="green")
    table.add_column("Description", style="white")

    for tool in bridge.registered_tools:
        params_str = ", ".join([f"{p.name}: {p.type}" for p in tool.parameters]) or "none"
        table.add_row(tool.name, params_str, tool.description)

    console.print(table)

@cli.command("export-client-config")
@click.option("--config", "config_file", default="universal-mcp.yaml", help="Path to configuration file")
@click.option("--target", default="claude", type=click.Choice(["claude", "cursor", "all"]), help="Client format")
def export_client_config(config_file, target):
    """Export copy-paste JSON configuration for Claude Desktop or Cursor."""
    abs_cwd = os.getcwd()
    abs_cfg = os.path.abspath(config_file) if os.path.exists(config_file) else config_file
    
    server_snippet = {
        "command": "uv",
        "args": [
            "run",
            "--directory",
            abs_cwd,
            "universal-mcp",
            "serve",
            "--config",
            abs_cfg
        ]
    }
    
    claude_cfg = {
        "mcpServers": {
            "universal-mcp-bridge": server_snippet
        }
    }
    
    console.print(f"\n[bold green]Configuration snippet for Claude Desktop / Cursor ({target}):[/bold green]\n")
    console.print(json.dumps(claude_cfg, indent=2))
    console.print(f"\nPaste this into your client's settings (e.g. `~/Library/Application Support/Claude/claude_desktop_config.json`).")

@cli.command("init")
@click.option("--name", default="My-Universal-MCP", help="Name of the MCP server")
def init_config(name):
    """Scaffold a new universal-mcp.yaml configuration file."""
    template = f"""name: "{name}"
audit_log: "mcp_audit.jsonl"

security:
  timeout_seconds: 30
  max_output_length: 50000
  redact_secrets: true
  allowed_commands:
    - python3
    - bash
    - curl
    - jq
  blocked_commands:
    - "rm -rf"
    - "mkfs"
    - "dd"
  rate_limit:
    max_requests: 60
    window_seconds: 60
  cache:
    enabled: true
    default_ttl_seconds: 60
    max_entries: 500
  hitl:
    require_confirmation: false
    sensitive_tools: []
  rbac:
    enabled: false
    jwt_secret: "super-secret-mcp-key"

mounts:
  # - type: openapi
  #   target: "https://petstore.swagger.io/v2/swagger.json"
  #   headers:
  #     Authorization: "Bearer ${{API_KEY:-dev-token}}"
  # - type: graphql
  #   target: "https://countries.trevorblades.com/"
  # - type: sqlite
  #   target: "./data.db"
  #   read_only: true
  # - type: postgres
  #   target: "postgresql://user:pass@localhost:5432/dbname"
  #   read_only: true
  # - type: redis
  #   target: "redis://localhost:6379/0"
  #   read_only: true
  # - type: script
  #   target: "./scripts/deploy.py"
  # - type: cli
  #   target: "git"
  #   subcommands: ["status", "diff", "log"]
  # - type: directory
  #   target: "./tools/"
"""
    if os.path.exists("universal-mcp.yaml"):
        console.print("[yellow]universal-mcp.yaml already exists![/yellow]")
    else:
        with open("universal-mcp.yaml", "w", encoding="utf-8") as f:
            f.write(template)
        console.print("[green]Created universal-mcp.yaml template successfully![/green]")

if __name__ == "__main__":
    cli()
