import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("universal_mcp.optimizer")

class PromptOptimizer:
    """
    Analyzes tool names, parameters, and descriptions to produce optimized,
    high-clarity descriptions following Anthropic and OpenAI best practices for tool use.
    Provides local rule-based heuristic enrichment and optional LLM-assisted rephrasing.
    """
    
    ACTION_VERBS = {
        "get": "Retrieve and inspect",
        "find": "Search, filter, and locate",
        "run": "Safely execute the standalone process for",
        "exec": "Invoke the command-line utility for",
        "db": "Perform controlled database query or schema exploration on",
        "list": "Enumerate and return active elements of",
    }

    @classmethod
    def optimize_tool_description(cls, tool_name: str, original_description: str, parameters: list) -> str:
        clean_desc = original_description.strip() if original_description else ""
        
        # Determine primary action
        prefix = tool_name.split("_")[0].lower()
        action_phrase = cls.ACTION_VERBS.get(prefix, "Interact with and manage")

        # Clarify parameters in the description
        param_hints = []
        for p in parameters:
            p_name = p.name if hasattr(p, "name") else p.get("name", "")
            p_type = p.type if hasattr(p, "type") else p.get("type", "string")
            p_req = p.required if hasattr(p, "required") else p.get("required", False)
            req_str = "required" if p_req else "optional"
            param_hints.append(f"'{p_name}' ({p_type}, {req_str})")

        hint_str = f" Accepts parameters: {', '.join(param_hints)}." if param_hints else " Takes no arguments."

        if not clean_desc or len(clean_desc) < 20:
            optimized = f"{action_phrase} '{tool_name}'. Use this tool to reliably query or run operations.{hint_str}"
        else:
            optimized = f"{clean_desc} - {action_phrase}.{hint_str}"

        # Instruction for LLMs on return value format
        optimized += " Returns structured JSON or plain text. In case of error, returns descriptive error message."
        return optimized

    @classmethod
    def optimize_bridge_tools(cls, bridge) -> int:
        count = 0
        for tool in bridge.registered_tools:
            new_desc = cls.optimize_tool_description(tool.name, tool.description, tool.parameters)
            tool.description = new_desc
            count += 1
        return count
