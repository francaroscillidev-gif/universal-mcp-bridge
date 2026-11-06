import os
import re
import inspect
from pathlib import Path
from typing import List, Callable, Optional
from universal_mcp.adapters.base import BaseAdapter
from universal_mcp.models import DynamicToolDef, ToolParameter, SecurityPolicy
from universal_mcp.security.sandbox import CommandSandbox

class ScriptAdapter(BaseAdapter):
    """
    Auto-discovers and wraps scripts (.py, .sh, .bash) into MCP tools.
    Extracts docstrings and comments for description and arguments.
    """
    def __init__(self, script_path: str, sandbox: Optional[CommandSandbox] = None):
        self.script_path = os.path.abspath(script_path)
        self.sandbox = sandbox or CommandSandbox()

    def discover_tools(self) -> List[tuple[DynamicToolDef, Callable]]:
        path = Path(self.script_path)
        if not path.exists():
            raise FileNotFoundError(f"Script not found: {self.script_path}")

        tool_name = path.stem.replace("-", "_").replace(".", "_")
        description = f"Execute script {path.name}"
        parameters: List[ToolParameter] = []

        content = path.read_text(encoding="utf-8", errors="ignore")

        # Inspect python scripts for docstring and argument hints
        if path.suffix == ".py":
            doc_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
            if not doc_match:
                doc_match = re.search(r"'''(.*?)'''", content, re.DOTALL)
            if doc_match:
                description = doc_match.group(1).strip()

            # Check if it takes arguments
            parameters.append(
                ToolParameter(
                    name="args",
                    type="string",
                    description="Command line arguments passed to the Python script",
                    required=False,
                    default=""
                )
            )
            parameters.append(
                ToolParameter(
                    name="stdin_input",
                    type="string",
                    description="Standard input passed to the script",
                    required=False,
                    default=""
                )
            )

            cmd_prefix = ["python3", str(path)]
        else:
            # Bash or shell script
            lines = content.splitlines()
            comment_docs = []
            for line in lines[:10]:
                if line.startswith("#") and not line.startswith("#!"):
                    comment_docs.append(line.lstrip("#").strip())
            if comment_docs:
                description = " ".join(comment_docs)

            parameters.append(
                ToolParameter(
                    name="args",
                    type="string",
                    description="Command line arguments passed to the script",
                    required=False,
                    default=""
                )
            )
            cmd_prefix = ["bash", str(path)]

        tool_def = DynamicToolDef(
            name=f"run_{tool_name}",
            description=description,
            parameters=parameters,
            metadata={"script_path": str(path)}
        )

        handler = self._create_handler(cmd_prefix)
        return [(tool_def, handler)]

    def _create_handler(self, cmd_prefix: List[str]) -> Callable:
        sandbox = self.sandbox

        async def handler(args: str = "", stdin_input: str = "") -> str:
            import shlex
            cmd = list(cmd_prefix)
            if args and args.strip():
                cmd.extend(shlex.split(args))

            res = await sandbox.execute_safe(cmd)
            output = []
            if res["stdout"]:
                output.append(f"STDOUT:\n{res['stdout']}")
            if res["stderr"]:
                output.append(f"STDERR:\n{res['stderr']}")
            if not output:
                output.append(f"Process finished with exit code {res['returncode']}")
            return "\n".join(output)

        return handler
