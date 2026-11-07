#!/usr/bin/env bash
# Universal MCP Bridge & Proxy - One-Line Installer
# Installs Python 3.12+ (via uv if needed) and setups universal-mcp globally.

set -e

echo "🌉 Installing Universal MCP Bridge & Proxy..."

# Check or install uv
if ! command -v uv &> /dev/null; then
    echo "📦 uv package manager not found. Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

INSTALL_DIR="$HOME/.universal-mcp"
echo "📁 Installing to $INSTALL_DIR..."

if [ -d "$INSTALL_DIR" ]; then
    echo "🔄 Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull --quiet || true
else
    git clone --quiet https://github.com/francaroscillidev-gif/universal-mcp-bridge.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

uv sync --quiet

# Symlink executable to /usr/local/bin or ~/.local/bin
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
ln -sf "$INSTALL_DIR/.venv/bin/universal-mcp" "$BIN_DIR/universal-mcp"

echo ""
echo "✅ Universal MCP Bridge successfully installed!"
echo "🚀 Try running: universal-mcp --help"
echo "🌐 Repo: https://github.com/francaroscillidev-gif/universal-mcp-bridge"
