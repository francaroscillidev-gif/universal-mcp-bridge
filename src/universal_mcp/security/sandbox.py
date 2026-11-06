import os
import re
import shlex
import subprocess
import asyncio
from typing import List, Optional
from universal_mcp.models import SecurityPolicy

class SecurityViolationError(Exception):
    """Raised when an operation violates security policy"""
    pass

class CommandSandbox:
    def __init__(self, policy: Optional[SecurityPolicy] = None):
        self.policy = policy or SecurityPolicy()

    def validate_command(self, cmd: List[str] | str) -> List[str]:
        """Validates command tokens against security policy without arbitrary shell execution."""
        if isinstance(cmd, str):
            cmd_tokens = shlex.split(cmd)
        else:
            cmd_tokens = list(cmd)

        if not cmd_tokens:
            raise SecurityViolationError("Empty command is not allowed")

        executable = os.path.basename(cmd_tokens[0])
        full_cmd_str = " ".join(cmd_tokens)

        # Check whitelist if specified
        if self.policy.allowed_commands is not None:
            if executable not in self.policy.allowed_commands and cmd_tokens[0] not in self.policy.allowed_commands:
                raise SecurityViolationError(
                    f"Command '{executable}' is not in the whitelist: {self.policy.allowed_commands}"
                )

        # Check blacklisted command patterns
        for blocked in self.policy.blocked_commands:
            if blocked in full_cmd_str:
                raise SecurityViolationError(f"Command contains forbidden expression: '{blocked}'")

        # Check dangerous regex patterns (shell escape / injection)
        for pattern in self.policy.blocked_patterns:
            if re.search(pattern, full_cmd_str, re.IGNORECASE):
                raise SecurityViolationError(f"Command matches security-blocked pattern: '{pattern}'")

        return cmd_tokens

    def validate_path(self, target_path: str) -> str:
        """Ensures file paths reside within allowed directories if directory containment is enabled."""
        if not self.policy.allowed_dirs:
            return target_path

        resolved_target = os.path.realpath(target_path)
        is_allowed = False
        for allowed in self.policy.allowed_dirs:
            resolved_allowed = os.path.realpath(allowed)
            if resolved_target == resolved_allowed or resolved_target.startswith(resolved_allowed + os.sep):
                is_allowed = True
                break

        if not is_allowed:
            raise SecurityViolationError(
                f"Path '{target_path}' is outside allowed directories: {self.policy.allowed_dirs}"
            )
        return resolved_target

    async def execute_safe(self, cmd: List[str] | str, cwd: Optional[str] = None, env: Optional[dict] = None) -> dict:
        """Executes the command asynchronously without shell=True, respecting timeouts and output limits."""
        cmd_tokens = self.validate_command(cmd)

        if cwd:
            cwd = self.validate_path(cwd)

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_tokens,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=merged_env
            )

            try:
                stdout_data, stderr_data = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self.policy.timeout_seconds
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
                return {
                    "success": False,
                    "returncode": -1,
                    "stdout": "",
                    "stderr": f"Command timed out after {self.policy.timeout_seconds} seconds"
                }

            stdout_str = stdout_data.decode(errors="replace")[:self.policy.max_output_length]
            stderr_str = stderr_data.decode(errors="replace")[:self.policy.max_output_length]

            return {
                "success": proc.returncode == 0,
                "returncode": proc.returncode,
                "stdout": stdout_str,
                "stderr": stderr_str
            }
        except Exception as e:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e)
            }
