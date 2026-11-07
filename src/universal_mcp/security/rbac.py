import time
import jwt
from typing import Dict, Any, Optional, Set, List
from pydantic import BaseModel, Field

class RoleDefinition(BaseModel):
    name: str
    allowed_tools: List[str] = Field(default_factory=list, description="List of tool names or '*' for all")
    denied_tools: List[str] = Field(default_factory=list, description="Explicit blacklist of tools")

class RBACManager:
    """
    Role-Based Access Control (RBAC) & Multi-Tenant Token Validator for MCP.
    Validates JWT tokens or API keys and ensures an Agent or User only invokes
    tools allowed for their assigned role/tenant.
    """
    def __init__(self, secret_key: str = "super-secret-mcp-key", roles: Optional[Dict[str, RoleDefinition]] = None):
        self.secret_key = secret_key
        self.roles = roles or {
            "admin": RoleDefinition(name="admin", allowed_tools=["*"]),
            "analyst": RoleDefinition(name="analyst", allowed_tools=["db_*_query", "db_*_schema", "postgres_*", "find*"]),
            "agent": RoleDefinition(name="agent", allowed_tools=["*"], denied_tools=["exec_curl", "run_sys_health"])
        }

    def generate_token(self, subject: str, role: str = "agent", tenant_id: str = "default", expires_in: int = 3600) -> str:
        payload = {
            "sub": subject,
            "role": role,
            "tenant_id": tenant_id,
            "iat": time.time(),
            "exp": time.time() + expires_in
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def verify_token(self, token: str) -> Dict[str, Any]:
        try:
            return jwt.decode(token, self.secret_key, algorithms=["HS256"])
        except Exception as e:
            raise PermissionError(f"Invalid authentication token: {e}")

    def is_tool_allowed(self, role_name: str, tool_name: str) -> bool:
        role = self.roles.get(role_name)
        if not role:
            return False

        # Check explicit denial
        for denied in role.denied_tools:
            if denied == tool_name or (denied.endswith("*") and tool_name.startswith(denied[:-1])):
                return False

        # Check allowance
        if "*" in role.allowed_tools:
            return True

        for allowed in role.allowed_tools:
            if allowed == tool_name:
                return True
            if allowed.endswith("*") and tool_name.startswith(allowed[:-1]):
                return True
            if allowed.startswith("*") and tool_name.endswith(allowed[1:]):
                return True
            if "*" in allowed:
                # Simple wildcard match (e.g. db_*_query)
                parts = allowed.split("*")
                if len(parts) == 2 and tool_name.startswith(parts[0]) and tool_name.endswith(parts[1]):
                    return True

        return False
