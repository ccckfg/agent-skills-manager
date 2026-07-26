import json
import os
import platform
from pathlib import Path
from typing import List, Optional

from .models import AgentProfile


DEFAULT_CENTRAL = "~/.agent/skills"


def expand_path(value: str) -> Path:
    raw = os.path.expandvars(value)
    if raw == "~" or raw.startswith("~/") or raw.startswith("~\\"):
        home = os.environ.get("HOME") or os.environ.get("USERPROFILE")
        if home:
            raw = home if raw == "~" else str(Path(home) / raw[2:])
    return Path(raw).expanduser()


def central_path(value: Optional[str] = None) -> Path:
    return expand_path(value or DEFAULT_CENTRAL)


def path_candidates(paths: dict, system: Optional[str] = None) -> List[str]:
    """Return one kind of path for this platform, most preferred first.

    A value is either a single path or a list of candidates.
    """
    key = (system or platform.system()).lower()
    value = paths.get(key, paths.get("default", ""))
    if isinstance(value, str):
        return [value] if value else []
    return [item for item in value if item]


def resolve_path(paths: dict, system: Optional[str] = None) -> Path:
    """Prefer the location this machine actually uses, else the documented default."""
    candidates = [expand_path(item) for item in path_candidates(paths, system)]
    if not candidates:
        return Path()
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def load_profiles(profile_file: Path) -> List[AgentProfile]:
    payload = json.loads(profile_file.read_text(encoding="utf-8"))
    profiles = []
    for item in payload["agents"]:
        profiles.append(
            AgentProfile(
                id=item["id"],
                display_name=item["display_name"],
                skills_path=resolve_path(item["skills_paths"]),
                mcp_path=resolve_path(item["mcp_paths"]),
                mcp_format=item["mcp_format"],
                supports_link=bool(item.get("supports_link", True)),
            )
        )
    return profiles
