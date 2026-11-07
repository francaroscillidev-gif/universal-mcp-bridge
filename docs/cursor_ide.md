# ⚡ Cursor IDE Integration Guide

Cursor natively supports the Model Context Protocol (MCP) in its Agent/Composer mode.

### 1. Open Cursor MCP Settings
- Go to `Cursor Settings` > `Features` > `MCP Servers`
- Click **+ Add New MCP Server**

### 2. Enter Configuration
- **Name**: `universal-mcp`
- **Type**: `command`
- **Command**:
  ```bash
  uv run --directory "/absolute/path/to/universal-mcp-bridge" universal-mcp serve --config "/absolute/path/to/universal-mcp.yaml" --transport stdio
  ```

### 3. Verify Tools
Once added, Cursor Composer will display a green checkmark next to `universal-mcp` indicating all tools (PostgreSQL, SQLite, Redis, Python scripts, CLI wrappers) are live and available for agentic pair-programming.
