import os
import re
import shlex
import shutil
import asyncio
from typing import List, Callable, Optional, Dict, Any
from universal_mcp.adapters.base import BaseAdapter
from universal_mcp.models import DynamicToolDef, ToolParameter
from universal_mcp.security.sandbox import CommandSandbox

class CLIAdapter(BaseAdapter):
    """
    Introspects a CLI tool (e.g. git, curl, jq, docker, custom CLI) by parsing --help
    and auto-generating subcommands as native MCP tools with security sandboxing.
    """
    def __init__(self, cli_name: str, subcommands: Optional[List[str]] = None, sandbox: Optional[CommandSandbox] = None):
        self.cli_name = cli_name
        self.subcommands = subcommands
        self.sandbox = sandbox or CommandSandbox()

    def discover_tools(self) -> List[tuple[DynamicToolDef, Callable]]:
        cli_path = shutil.which(self.cli_name)
        if not cli_path:
            raise FileNotFoundError(f"CLI executable '{self.cli_name}' not found on system PATH")

        # Get top-level help
        try:
            res = asyncio.run(self.sandbox.execute_safe([cli_path, "--help"]))
            help_text = res["stdout"] or res["stderr"]
        except Exception:
            help_text = f"CLI Tool wrapper for {self.cli_name}"

        tools = []

        # If explicit subcommands requested or found
        detected_subcommands = self.subcommands or self._parse_subcommands(help_text)

        if not detected_subcommands:
            # Single tool wrapper
            tool_def = DynamicToolDef(
                name=f"exec_{self.cli_name.replace('-', '_')}",
                description=f"Executes '{self.cli_name}'. Help summary:\n{help_text[:300]}...",
                parameters=[
                    ToolParameter(
                        name="args",
                        type="string",
                        description=f"Command line arguments for {self.cli_name} (e.g. -v, --flag)",
                        required=False,
                        default=""
                    )
                ]
            )
            handler = self._create_handler(cli_path, subcommand=None)
            tools.append((tool_def, handler))
        else:
            for subcmd in detected_subcommands:
                # Introspect subcommand help
                try:
                    sub_res = asyncio.run(self.sandbox.execute_safe([cli_path, subcmd, "--help"]))
                    sub_help = sub_res["stdout"] or sub_res["stderr"]
                    sub_desc = sub_help.split("\n\n")[0] if sub_help else f"Subcommand {subcmd}"
                except Exception:
                    sub_desc = f"Executes '{self.cli_name} {subcmd}'"

                tool_name = f"{self.cli_name}_{subcmd}".replace("-", "_")
                tool_def = DynamicToolDef(
                    name=tool_name,
                    description=sub_desc[:400],
                    parameters=[
                        ToolParameter(
                            name="args",
                            type="string",
                            description=f"Arguments passed to '{self.cli_name} {subcmd}'",
                            required=False,
                            default=""
                        )
                    ]
                )
                handler = self._create_handler(cli_path, subcommand=subcmd)
                tools.append((tool_def, handler))

        return tools

    def _parse_subcommands(self, help_text: str) -> List[str]:
        """Heuristics to extract subcommands from --help output (e.g. Commands:, Available Commands: etc)"""
        subcommands = []
        in_commands_section = False

        for line in help_text.splitlines():
            clean = line.strip()
            if re.search(r"^(Commands|Available Commands|Subcommands):", clean, re.IGNORECASE):
                in_commands_section = True
                continue
            if in_commands_section:
                if not clean or clean.startswith("Flags:") or clean.startswith("Options:"):
                    break
                # Command format: usually '  name    Description'
                match = re.match(r"^([a-z0-9_-]+)\s{2,}", clean)
                if match:
                    cmd_name = match.group(1)
                    if len(cmd_name) > 1 and cmd_name not in ["help", "version"]:
                        subcommands.append(cmd_name)

        return subcommands[:15]  # limit to top 15 subcommands

    def _create_handler(self, cli_path: str, subcommand: Optional[str]) -> Callable:
        sandbox = self.sandbox
        cli_name = self.cli_name

        async def handler(args: str = "") -> str:
            cmd = [cli_path]
            if subcommand:
                cmd.append(subcommand)
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
