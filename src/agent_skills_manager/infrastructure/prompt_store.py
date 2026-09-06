from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agent_skills_manager.domain.models import PromptStyle


def normalize_text(text: str) -> str:
    """Compare prompt files ignoring CRLF and trailing-newline differences."""
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")


class PromptStore:
    """The only place that reads, renders, writes, or backs up prompt files."""

    def read(self, path: Path) -> str | None:
        return path.read_text(encoding="utf-8") if path.is_file() else None

    def write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(normalize_text(content).encode("utf-8") + b"\n")

    def matches(self, path: Path, content: str) -> bool:
        current = self.read(path)
        return current is not None and normalize_text(current) == normalize_text(content)

    def canonical(self, content: str) -> str:
        return normalize_text(content) + "\n"

    def render(self, content: str, style: PromptStyle) -> str:
        body = normalize_text(content)
        if style is PromptStyle.CURSOR:
            return f"---\ndescription: User coding instructions\nalwaysApply: true\n---\n\n{body}\n"
        return f"{body}\n"

    def backup_file(self, path: Path, backup_root: Path) -> Path | None:
        """Move an existing prompt file to a timestamped, recoverable backup."""
        if not path.is_file():
            return None
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        backup_root.mkdir(parents=True, exist_ok=True)
        destination = backup_root / f"{path.name}-{timestamp}"
        path.replace(destination)
        return destination
