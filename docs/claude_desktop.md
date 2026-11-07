# 🤖 Claude Desktop Integration Guide

To connect **Universal MCP Bridge** with Anthropic's **Claude Desktop**:

### 1. Locate Claude Desktop Configuration
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### 2. Export Configuration Snippet
Run inside your Universal MCP directory:
```bash
uv run universal-mcp export-client-config --config examples/universal-mcp.yaml
```

### 3. Add to `claude_desktop_config.json`
```json
{
  "mcpServers": {
    "universal-mcp-bridge": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/universal-mcp-bridge",
        "universal-mcp",
        "serve",
        "--config",
        "/absolute/path/to/universal-mcp.yaml",
        "--transport",
        "stdio"
      ]
    }
  }
}
```

### 4. Restart Claude Desktop
Once restarted, click the 🔨 hammer icon in Claude Desktop to see all your mounted OpenAPI endpoints, SQL databases, scripts, and documents ready for reasoning.
