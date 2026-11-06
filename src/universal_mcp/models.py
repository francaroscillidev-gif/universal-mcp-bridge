from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class AdapterType(str, Enum):
    OPENAPI = "openapi"
    CLI = "cli"
    SCRIPT = "script"
    SQLITE = "sqlite"
    POSTGRES = "postgres"
    REDIS = "redis"
    GRAPHQL = "graphql"

class RateLimitPolicy(BaseModel):
    max_requests: int = Field(default=60, description="Max requests in window")
    window_seconds: int = Field(default=60, description="Time window in seconds")

class CachePolicy(BaseModel):
    enabled: bool = Field(default=False, description="Enable response caching")
    default_ttl_seconds: int = Field(default=60, description="Default cache TTL")
    max_entries: int = Field(default=1000, description="Max cache entries")

class CircuitBreakerPolicy(BaseModel):
    enabled: bool = Field(default=True, description="Enable circuit breaker protection")
    failure_threshold: int = Field(default=5, description="Consecutive errors before opening circuit")
    recovery_timeout_seconds: float = Field(default=30.0, description="Cooldown time before retry")

class HITLPolicy(BaseModel):
    require_confirmation: bool = Field(default=False, description="Require human approval for sensitive tools")
    sensitive_tools: List[str] = Field(default_factory=list, description="Explicit tools requiring approval")

class SecurityPolicy(BaseModel):
    allowed_commands: Optional[List[str]] = Field(default=None, description="Whitelist of allowed executable commands")
    blocked_commands: List[str] = Field(
        default=["rm -rf", "mkfs", "dd", "shutdown", "reboot", ":(){ :|:& };:"],
        description="Forbidden command patterns"
    )
    timeout_seconds: int = Field(default=30, description="Execution timeout in seconds")
    allowed_dirs: Optional[List[str]] = Field(default=None, description="Allowed working directories")
    blocked_patterns: List[str] = Field(
        default=[r"(\||;|&&|\|\||`|\$\().*(rm|dd|mkfs|sh|bash)"],
        description="Dangerous shell injection regex patterns"
    )
    max_output_length: int = Field(default=100000, description="Max response string size")
    redact_secrets: bool = Field(default=True, description="Automatically mask tokens and passwords in output")
    rate_limit: Optional[RateLimitPolicy] = Field(default=None, description="Optional rate limiter configuration")
    cache: Optional[CachePolicy] = Field(default=None, description="Optional TTL cache configuration")
    circuit_breaker: Optional[CircuitBreakerPolicy] = Field(default_factory=CircuitBreakerPolicy, description="Circuit breaker configuration")
    hitl: Optional[HITLPolicy] = Field(default=None, description="Human-in-the-loop confirmation policy")

class ToolParameter(BaseModel):
    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Optional[Any] = None
    choices: Optional[List[Any]] = None

class DynamicToolDef(BaseModel):
    name: str
    description: str
    parameters: List[ToolParameter] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
