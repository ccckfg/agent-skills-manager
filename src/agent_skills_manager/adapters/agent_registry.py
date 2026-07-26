from __future__ import annotations

import platform
from pathlib import Path

import yaml

from agent_skills_manager.domain.models import AgentDefinition


class AgentRegistry:
    def __init__(self, definitions: list[AgentDefinition]) -> None:
        self._definitions = definitions

    @classmethod
    def load_default(cls, path: Path | str | None = None) -> "AgentRegistry":
        source = Path(path) if path else Path(__file__).parents[1] / "resources" / "agents.yaml"
        data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
        definitions = []
        for item in data.get("agents", []):
            definitions.append(
                AgentDefinition(
                    id=item["id"],
                    display_name=item["display_name"],
                    skills_paths=item.get("skills_paths", {}),
                    mcp_paths=item.get("mcp_paths", {}),
                    mcp_format=item.get("mcp_format", "json"),
                    supports_link=bool(item.get("supports_link", True)),
                )
            )
        return cls(definitions)

    def all(self) -> list[AgentDefinition]:
        return list(self._definitions)

    def get(self, agent_id: str) -> AgentDefinition | None:
        return next((item for item in self._definitions if item.id == agent_id), None)

    def path_candidates(
        self,
        definition: AgentDefinition,
        kind: str,
        system: str | None = None,
    ) -> list[str]:
        """Return every documented location for one kind, most preferred first.

        Several agents renamed or relocated their directory between releases, so a
        definition may list more than one path. The detector keeps the first entry
        that exists on this machine and falls back to the preferred one.
        """
        key = (system or platform.system()).lower()
        paths = definition.skills_paths if kind == "skills" else definition.mcp_paths
        value = paths.get(key, paths.get("default", ""))
        if isinstance(value, str):
            return [value] if value else []
        return [item for item in value if item]

    def path_for(self, definition: AgentDefinition, kind: str, system: str | None = None) -> str:
        candidates = self.path_candidates(definition, kind, system)
        return candidates[0] if candidates else ""
