import time
import asyncio
from typing import Optional, Dict, Any, Callable

class ConfirmationRequiredError(Exception):
    pass

class HumanInTheLoopManager:
    """
    Manages human approvals for sensitive tool invocations.
    Can request interactive approval via CLI or programmatic callback.
    """
    def __init__(self, auto_approve: bool = False, interactive: bool = False):
        self.auto_approve = auto_approve
        self.interactive = interactive
        self.pending_requests: Dict[str, Dict[str, Any]] = {}

    async def verify_approval(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        if self.auto_approve:
            return True

        if self.interactive:
            print(f"\n⚠️  [HITL APPROVAL REQUIRED] Tool '{tool_name}' wants to run with arguments:")
            print(f"   {arguments}")
            try:
                loop = asyncio.get_event_loop()
                ans = await loop.run_in_executor(None, input, "👉 Approve execution? (y/N): ")
                return ans.strip().lower() in ["y", "yes"]
            except Exception:
                return False

        # In non-interactive mode without auto_approve, reject dangerous action
        raise ConfirmationRequiredError(
            f"Action '{tool_name}' requires explicit human approval (HITL). Blocked by security policy."
        )
