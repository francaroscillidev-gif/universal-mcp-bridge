import os
import json
import logging
from typing import Dict, Any, List, Optional
from universal_mcp.models import DynamicToolDef

logger = logging.getLogger("universal_mcp.exporter")

class SchemaExporter:
    """
    Exports registered MCP tools into formats natively consumable by:
    - OpenAI Tools / Assistants API (`tools=[{"type": "function", ...}]`)
    - Anthropic Claude Messages API (`tools=[{"name": ..., "input_schema": ...}]`)
    - LangChain / LlamaIndex Tool specs
    - OpenAPI 3.1 Swagger Specification
    """

    @classmethod
    def to_anthropic_tools(cls, tools: List[DynamicToolDef]) -> List[Dict[str, Any]]:
        anthropic_list = []
        for t in tools:
            properties = {}
            required = []
            for p in t.parameters:
                prop_type = p.type if p.type in ["string", "integer", "number", "boolean", "array", "object"] else "string"
                properties[p.name] = {
                    "type": prop_type,
                    "description": p.description or f"Parameter {p.name}"
                }
                if p.choices:
                    properties[p.name]["enum"] = p.choices
                if p.required:
                    required.append(p.name)

            anthropic_list.append({
                "name": t.name,
                "description": t.description,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            })
        return anthropic_list

    @classmethod
    def to_openai_tools(cls, tools: List[DynamicToolDef]) -> List[Dict[str, Any]]:
        openai_list = []
        for t in tools:
            properties = {}
            required = []
            for p in t.parameters:
                prop_type = p.type if p.type in ["string", "integer", "number", "boolean", "array", "object"] else "string"
                properties[p.name] = {
                    "type": prop_type,
                    "description": p.description or f"Parameter {p.name}"
                }
                if p.choices:
                    properties[p.name]["enum"] = p.choices
                if p.required:
                    required.append(p.name)

            openai_list.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            })
        return openai_list

    @classmethod
    def to_openapi_spec(cls, tools: List[DynamicToolDef], server_title: str = "Universal MCP Gateway") -> Dict[str, Any]:
        paths = {}
        for t in tools:
            path_url = f"/tools/{t.name}"
            properties = {}
            required = []
            for p in t.parameters:
                properties[p.name] = {"type": p.type, "description": p.description}
                if p.required:
                    required.append(p.name)

            paths[path_url] = {
                "post": {
                    "summary": t.description[:100],
                    "description": t.description,
                    "operationId": t.name,
                    "requestBody": {
                        "required": bool(required),
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": properties,
                                    "required": required
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Tool execution result",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "result": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }

        return {
            "openapi": "3.1.0",
            "info": {
                "title": server_title,
                "version": "1.0.0",
                "description": "Auto-generated OpenAPI spec from Universal MCP Bridge"
            },
            "paths": paths
        }
