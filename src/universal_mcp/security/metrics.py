from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Metrics
TOOL_CALLS_TOTAL = Counter(
    "mcp_tool_calls_total",
    "Total number of MCP tool invocations",
    ["tool_name", "status"]
)

TOOL_EXECUTION_DURATION_SECONDS = Histogram(
    "mcp_tool_execution_duration_seconds",
    "Duration of MCP tool executions in seconds",
    ["tool_name"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)

CACHE_HITS_TOTAL = Counter(
    "mcp_cache_hits_total",
    "Total number of response cache hits",
    ["tool_name"]
)

RATE_LIMIT_EXCEEDED_TOTAL = Counter(
    "mcp_rate_limit_exceeded_total",
    "Total number of rate limit rejections",
    ["tool_name"]
)

def get_prometheus_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
