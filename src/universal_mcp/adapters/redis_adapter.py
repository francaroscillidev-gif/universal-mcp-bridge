import json
import redis.asyncio as aioredis
from typing import List, Callable, Optional, Dict, Any
from universal_mcp.adapters.base import BaseAdapter
from universal_mcp.models import DynamicToolDef, ToolParameter

class RedisAdapter(BaseAdapter):
    """
    Exposes Redis keys & values inspection as secure MCP tools.
    """
    def __init__(self, redis_url: str = "redis://localhost:6379/0", read_only: bool = True):
        self.redis_url = redis_url
        self.read_only = read_only

    def discover_tools(self) -> List[tuple[DynamicToolDef, Callable]]:
        keys_tool = DynamicToolDef(
            name="redis_list_keys",
            description="List Redis keys matching a pattern (default: '*')",
            parameters=[
                ToolParameter(
                    name="pattern",
                    type="string",
                    description="Key pattern filter (e.g. user:*, cache:*)",
                    required=False,
                    default="*"
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Max keys to return",
                    required=False,
                    default=50
                )
            ]
        )

        get_tool = DynamicToolDef(
            name="redis_get_value",
            description="Get string or hash value of a Redis key",
            parameters=[
                ToolParameter(
                    name="key",
                    type="string",
                    description="Redis key to retrieve",
                    required=True
                )
            ]
        )

        return [
            (keys_tool, self._create_list_handler()),
            (get_tool, self._create_get_handler())
        ]

    def _create_list_handler(self) -> Callable:
        url = self.redis_url

        async def handler(pattern: str = "*", limit: int = 50) -> str:
            try:
                r = aioredis.from_url(url, decode_responses=True)
                async with r:
                    keys = await r.keys(pattern)
                    limited = keys[:limit]
                    return json.dumps({"pattern": pattern, "count": len(limited), "keys": limited}, indent=2)
            except Exception as e:
                return json.dumps({"error": str(e)})

        return handler

    def _create_get_handler(self) -> Callable:
        url = self.redis_url

        async def handler(key: str) -> str:
            try:
                r = aioredis.from_url(url, decode_responses=True)
                async with r:
                    k_type = await r.type(key)
                    if k_type == "string":
                        val = await r.get(key)
                    elif k_type == "hash":
                        val = await r.hgetall(key)
                    elif k_type == "list":
                        val = await r.lrange(key, 0, 50)
                    elif k_type == "set":
                        val = list(await r.smembers(key))
                    else:
                        val = f"(unsupported or empty key type: {k_type})"
                    return json.dumps({"key": key, "type": k_type, "value": val}, indent=2)
            except Exception as e:
                return json.dumps({"error": str(e)})

        return handler
