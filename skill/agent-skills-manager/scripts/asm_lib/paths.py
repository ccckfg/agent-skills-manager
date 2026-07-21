import json
import os
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


def load_profiles(profile_file: Path) -> List[AgentProfile]:
    payload = json.loads(profile_file.read_text(encoding="utf-8"))
    profiles = []
    for item in payload["agents"]:
        profiles.append(
            AgentProfile(
                id=item["id"],
                display_name=item["display_name"],
                skills_path=expand_path(item["skills_path"]),
                mcp_path=expand_path(item["mcp_path"]),
                mcp_format=item["mcp_format"],
                supports_link=bool(item.get("supports_link", True)),
            )
        )
    return profiles
