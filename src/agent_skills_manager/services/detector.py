from __future__ import annotations

from pathlib import Path

from agent_skills_manager.adapters.agent_registry import AgentRegistry
from agent_skills_manager.config.settings import expand_path
from agent_skills_manager.domain.models import AgentDefinition


class AgentDetector:
    def __init__(self, registry: AgentRegistry, system: str | None = None) -> None:
        self.registry, self.system = registry, system

    def paths_for(self, definition: AgentDefinition) -> tuple[Path, Path]:
        return (self._resolve(definition, "skills"), self._resolve(definition, "mcp"))

    def _resolve(self, definition: AgentDefinition, kind: str) -> Path:
        """Prefer the location this machine actually uses, else the documented default."""
        candidates = [
            expand_path(value)
            for value in self.registry.path_candidates(definition, kind, self.system)
        ]
        if not candidates:
            return Path()
        return next((path for path in candidates if path.exists()), candidates[0])

    def installed(self, definition: AgentDefinition) -> bool:
        skills, mcp = self.paths_for(definition)
        return skills.exists() or mcp.exists()
