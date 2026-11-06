import asyncio
import os
import json
import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger("universal_mcp.webhook")

class WebhookDispatcher:
    """
    Receives incoming webhook payloads (e.g. from GitHub, Stripe, Datadog)
    and formats them as actionable prompt notifications for MCP agents.
    """
    def __init__(self, secret_token: Optional[str] = None):
        self.secret_token = secret_token
        self.history: list[Dict[str, Any]] = []

    def verify_auth(self, auth_header: Optional[str]) -> bool:
        if not self.secret_token:
            return True
        if not auth_header:
            return False
        return auth_header.strip() == self.secret_token or auth_header.strip() == f"Bearer {self.secret_token}"

    def process_incoming_event(self, source: str, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        import time
        event_record = {
            "source": source,
            "event_type": event_type,
            "payload": payload,
            "timestamp": time.time()
        }

        self.history.append(event_record)
        if len(self.history) > 100:
            self.history.pop(0)

        # Build notification prompt text for LLM
        prompt = f"[SYSTEM NOTIFICATION: Webhook Event Received]\nSource: {source}\nEvent: {event_type}\nPayload:\n{json.dumps(payload, indent=2)}"
        return {
            "status": "received",
            "prompt_notification": prompt,
            "event": event_record
        }
