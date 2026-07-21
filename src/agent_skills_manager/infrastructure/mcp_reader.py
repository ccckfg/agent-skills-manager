from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


class McpReader:
    """Read MCP server names without mutating the agent configuration file."""

    def server_names(self, path: Path, format_name: str) -> list[str]:
        if not path.is_file():
            return []
        try:
            text = path.read_text(encoding="utf-8")
            data = tomllib.loads(text) if format_name == "toml" else json.loads(self._jsonc(text))
        except (OSError, ValueError, tomllib.TOMLDecodeError):
            return []
        servers = (
            data.get("mcpServers")
            or data.get("mcp_servers")
            or data.get("mcp", {}).get("servers", {})
        )
        return sorted(servers) if isinstance(servers, dict) else []

    @staticmethod
    def _jsonc(text: str) -> str:
        """Remove JSONC comments while preserving comment-like string contents."""
        result: list[str] = []
        quoted = escaped = False
        index = 0
        while index < len(text):
            char, following = text[index], text[index + 1 : index + 2]
            if quoted:
                result.append(char)
                escaped = char == "\\" and not escaped
                if char == '"' and not escaped:
                    quoted = False
                elif char != "\\":
                    escaped = False
                index += 1
            elif char == '"':
                quoted = True
                result.append(char)
                index += 1
            elif char == "/" and following == "/":
                newline = text.find("\n", index)
                index = len(text) if newline < 0 else newline
            elif char == "/" and following == "*":
                end = text.find("*/", index + 2)
                index = len(text) if end < 0 else end + 2
            else:
                result.append(char)
                index += 1
        return re.sub(r",\s*([}\]])", r"\1", "".join(result))
