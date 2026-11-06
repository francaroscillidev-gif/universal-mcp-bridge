import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("universal_mcp.redactor")

class PIISecretRedactor:
    """
    Scans outputs and logs for leaked API keys, tokens, passwords, and sensitive credentials,
    redacting them automatically before they reach the LLM or audit files.
    """
    SENSITIVE_KEYWORDS = [
        "authorization", "api_key", "apikey", "secret", "password", "token", "access_token", "private_key"
    ]

    @classmethod
    def redact_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        redacted = {}
        for k, v in data.items():
            lower_k = k.lower()
            if any(s in lower_k for s in cls.SENSITIVE_KEYWORDS):
                redacted[k] = "******[REDACTED]******"
            elif isinstance(v, dict):
                redacted[k] = cls.redact_dict(v)
            else:
                redacted[k] = v
        return redacted

    @classmethod
    def redact_text(cls, text: str) -> str:
        if not isinstance(text, str):
            return text
        import re
        # Bearer tokens
        redacted = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]{15,}", r"\1******[REDACTED]******", text)
        # Generic API keys
        redacted = re.sub(r"(api[_-]?key[\"'\s:=]+)[\"'][A-Za-z0-9_\-\.]{16,}[\"']", r"\1'******[REDACTED]******'", redacted, flags=re.IGNORECASE)
        # Passwords in URLs
        redacted = re.sub(r"://([^:]+):([^@]+)@", r"://\1:******@", redacted)
        return redacted
