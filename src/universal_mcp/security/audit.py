import time
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("universal_mcp.audit")

class AuditLogger:
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file

    def log_call(self, tool_name: str, arguments: Dict[str, Any], duration_ms: float, success: bool, error: Optional[str] = None):
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tool": tool_name,
            "args": arguments,
            "duration_ms": round(duration_ms, 2),
            "success": success,
            "error": error
        }
        json_line = json.dumps(entry)
        if self.log_file:
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(json_line + "\n")
            except Exception as e:
                logger.error(f"Failed to write audit log: {e}")
        return entry
