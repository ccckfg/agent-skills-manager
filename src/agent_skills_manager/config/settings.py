from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from platformdirs import user_config_dir

from agent_skills_manager.domain.models import AgentPreference, SyncMode

APP_NAME = "agent-skills-manager"
CONFIG_NAME = "settings.yaml"


def expand_path(value: str | Path) -> Path:
    """Expand environment variables and a home marker on every supported OS."""
    raw = os.path.expandvars(str(value))
    if raw == "~" or raw.startswith("~/") or raw.startswith("~\\"):
        home = os.environ.get("HOME") or os.environ.get("USERPROFILE")
        if home:
            raw = str(Path(home) / raw[2:]) if len(raw) > 1 else home
    return Path(raw).expanduser()


@dataclass(slots=True)
class Settings:
    central_skills_path: Path = field(default_factory=lambda: expand_path("~/agent-skills"))
    agents: dict[str, AgentPreference] = field(default_factory=dict)
    path: Path | None = None

    @classmethod
    def default_path(cls) -> Path:
        return Path(user_config_dir(APP_NAME)) / CONFIG_NAME

    @classmethod
    def load(cls, path: Path | str | None = None) -> "Settings":
        config_path = expand_path(path) if path else cls.default_path()
        if not config_path.exists():
            return cls(path=config_path)
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        raw_agents = data.get("agents", {})
        agents = {
            agent_id: AgentPreference(
                enabled=bool(value.get("enabled", True)),
                skills_mode=SyncMode(value.get("skills_mode", SyncMode.COPY)),
            )
            for agent_id, value in raw_agents.items()
            if isinstance(value, dict)
        }
        return cls(
            central_skills_path=expand_path(data.get("central_skills_path", "~/agent-skills")),
            agents=agents,
            path=config_path,
        )

    def preference_for(self, agent_id: str) -> AgentPreference:
        return self.agents.get(agent_id, AgentPreference())

    def save(self, path: Path | str | None = None) -> Path:
        config_path = expand_path(path) if path else (self.path or self.default_path())
        config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "central_skills_path": str(self.central_skills_path),
            "agents": {
                key: {"enabled": value.enabled, "skills_mode": value.skills_mode.value}
                for key, value in self.agents.items()
            },
        }
        config_path.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
        self.path = config_path
        return config_path
