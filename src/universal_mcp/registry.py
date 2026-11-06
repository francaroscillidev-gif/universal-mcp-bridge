import os
import json
import uuid
import time
from typing import Dict, Any, Optional
from universal_mcp.server import UniversalMCPBridge

class DynamicToolRegistry:
    """
    Allows registering, unregistering and updating tools at runtime
    via MCP calls or REST webhooks without restarting the server.
    """
    def __init__(self, bridge: UniversalMCPBridge):
        self.bridge = bridge

    def register_script_tool(self, script_path: str) -> Dict[str, Any]:
        before_count = len(self.bridge.registered_tools)
        self.bridge.mount_script(script_path)
        new_tools = self.bridge.registered_tools[before_count:]
        return {
            "success": True,
            "registered_count": len(new_tools),
            "tools": [t.name for t in new_tools]
        }

    def register_openapi_tool(self, spec_or_url: str, base_url: Optional[str] = None) -> Dict[str, Any]:
        before_count = len(self.bridge.registered_tools)
        self.bridge.mount_openapi(spec_or_url, base_url=base_url)
        new_tools = self.bridge.registered_tools[before_count:]
        return {
            "success": True,
            "registered_count": len(new_tools),
            "tools": [t.name for t in new_tools]
        }

    def register_sqlite_tool(self, db_path: str, read_only: bool = True) -> Dict[str, Any]:
        before_count = len(self.bridge.registered_tools)
        self.bridge.mount_sqlite(db_path, read_only=read_only)
        new_tools = self.bridge.registered_tools[before_count:]
        return {
            "success": True,
            "registered_count": len(new_tools),
            "tools": [t.name for t in new_tools]
        }
