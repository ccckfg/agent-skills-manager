from __future__ import annotations

from pathlib import Path

from agent_skills_manager.adapters.agent_registry import AgentRegistry
from agent_skills_manager.config.settings import expand_path
from agent_skills_manager.domain.models import AgentDefinition


class AgentDetector:
    def __init__(self, registry: AgentRegistry, system: str | None = None) -> None:
        self.registry, self.system = registry, system

    def paths_for(self, definition: AgentDefinition) -> tuple[Path, Path]:
        return (
            expand_path(self.registry.path_for(definition, "skills", self.system)),
            expand_path(self.registry.path_for(definition, "mcp", self.system)),
        )

    def installed(self, definition: AgentDefinition) -> bool:
        skills, mcp = self.paths_for(definition)
        return skills.exists() or mcp.exists()
