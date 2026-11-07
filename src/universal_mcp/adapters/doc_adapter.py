import os
import re
from pathlib import Path
from typing import List, Callable, Optional, Dict, Any
from universal_mcp.adapters.base import BaseAdapter
from universal_mcp.models import DynamicToolDef, ToolParameter

class DocumentSearchAdapter(BaseAdapter):
    """
    Exposes a directory of documents (.md, .txt, .csv, .json, .log, etc.)
    with fuzzy text search, chunked reading, and metadata inspection.
    """
    SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".log", ".yaml", ".yml", ".py", ".sh", ".sql"}

    def __init__(self, directory_path: str, max_chunk_chars: int = 4000):
        self.directory = Path(directory_path).resolve()
        self.max_chunk_chars = max_chunk_chars
        if not self.directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")

    def discover_tools(self) -> List[tuple[DynamicToolDef, Callable]]:
        dir_name = self.directory.name.replace("-", "_").replace(".", "_")

        search_tool = DynamicToolDef(
            name=f"search_{dir_name}_docs",
            description=f"Search documents in '{self.directory.name}' matching a keyword or phrase",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Keyword or regex pattern to search for",
                    required=True
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum matching files/snippets to return",
                    required=False,
                    default=10
                )
            ]
        )

        read_chunk_tool = DynamicToolDef(
            name=f"read_{dir_name}_chunk",
            description=f"Read a specific paginated chunk of a document in '{self.directory.name}'",
            parameters=[
                ToolParameter(
                    name="file_path",
                    type="string",
                    description="Relative path of file inside directory",
                    required=True
                ),
                ToolParameter(
                    name="chunk_index",
                    type="integer",
                    description="0-indexed chunk number (default: 0)",
                    required=False,
                    default=0
                )
            ]
        )

        return [
            (search_tool, self._create_search_handler()),
            (read_chunk_tool, self._create_read_handler())
        ]

    def _create_search_handler(self) -> Callable:
        directory = self.directory
        supported = self.SUPPORTED_EXTENSIONS

        async def handler(query: str, max_results: int = 10) -> str:
            matches = []
            pattern = re.compile(re.escape(query), re.IGNORECASE)

            for file in directory.rglob("*"):
                if file.is_file() and file.suffix.lower() in supported and not file.name.startswith("."):
                    rel_p = str(file.relative_to(directory))
                    try:
                        content = file.read_text(encoding="utf-8", errors="ignore")
                        for line_num, line in enumerate(content.splitlines(), start=1):
                            if pattern.search(line):
                                matches.append({
                                    "file": rel_p,
                                    "line": line_num,
                                    "snippet": line.strip()[:200]
                                })
                                if len(matches) >= max_results:
                                    break
                    except Exception:
                        pass
                if len(matches) >= max_results:
                    break

            import json
            return json.dumps({
                "query": query,
                "matches_count": len(matches),
                "matches": matches
            }, indent=2)

        return handler

    def _create_read_handler(self) -> Callable:
        directory = self.directory
        chunk_size = self.max_chunk_chars

        async def handler(file_path: str, chunk_index: int = 0) -> str:
            target = (directory / file_path).resolve()
            # Prevent directory traversal
            if not str(target).startswith(str(directory)):
                return "Error: Access denied (path traversal outside allowed directory)"
            if not target.exists() or not target.is_file():
                return f"Error: File '{file_path}' not found"

            content = target.read_text(encoding="utf-8", errors="ignore")
            total_chars = len(content)
            start = chunk_index * chunk_size
            end = min(start + chunk_size, total_chars)
            total_chunks = max(1, (total_chars + chunk_size - 1) // chunk_size)

            if start >= total_chars and total_chars > 0:
                return f"Error: chunk_index {chunk_index} out of range (total chunks: {total_chunks})"

            chunk_text = content[start:end]
            import json
            return json.dumps({
                "file": file_path,
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "characters": f"{start}-{end} of {total_chars}",
                "content": chunk_text
            }, indent=2)

        return handler
