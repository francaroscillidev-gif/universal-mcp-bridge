import time
import hashlib
import json
from typing import Optional, Dict, Any, Tuple

class ResponseCache:
    """
    In-memory TTL response cache for MCP Tool calls.
    Prevents duplicate expensive queries, API rate exhaustions, or repetitive script executions.
    """
    def __init__(self, default_ttl_seconds: int = 60, max_entries: int = 1000):
        self.default_ttl = default_ttl_seconds
        self.max_entries = max_entries
        self.cache: Dict[str, Tuple[str, float]] = {}  # key -> (result_str, expires_at)

    def _make_key(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        serialized = json.dumps(arguments, sort_keys=True, default=str)
        payload = f"{tool_name}:{serialized}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
        key = self._make_key(tool_name, arguments)
        entry = self.cache.get(key)
        if not entry:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del self.cache[key]
            return None
        return value

    def set(self, tool_name: str, arguments: Dict[str, Any], result: str, ttl_seconds: Optional[int] = None):
        if len(self.cache) >= self.max_entries:
            # Clean expired
            now = time.time()
            keys_to_del = [k for k, v in self.cache.items() if v[1] < now]
            for k in keys_to_del:
                del self.cache[k]
            # If still full, pop first
            if len(self.cache) >= self.max_entries:
                first_key = next(iter(self.cache))
                del self.cache[first_key]

        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        key = self._make_key(tool_name, arguments)
        self.cache[key] = (result, time.time() + ttl)

    def clear(self):
        self.cache.clear()
