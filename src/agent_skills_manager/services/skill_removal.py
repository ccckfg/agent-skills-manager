"""Safe removal of one Skill from one Agent."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from agent_skills_manager.domain.models import AgentInventory, InventorySnapshot, ItemStatus
from agent_skills_manager.infrastructure.skill_store import SkillStore


class SkillRemovalService:
    """Move an Agent Skill to the central backup area instead of deleting it."""

    def __init__(self, store: SkillStore | None = None) -> None:
        self.store = store or SkillStore()

    def remove(
        self,
        snapshot: InventorySnapshot,
        agent_id: str,
        skill_name: str,
    ) -> Path:
        return self.remove_many(snapshot, agent_id, (skill_name,))[0]

    def remove_many(
        self,
        snapshot: InventorySnapshot,
        agent_id: str,
        skill_names: Iterable[str],
    ) -> list[Path]:
        names = tuple(dict.fromkeys(skill_names))
        if not names:
            raise ValueError("No Skills were selected")
        agent = snapshot.agent(agent_id)
        if agent is None:
            raise ValueError(f"Unknown Agent: {agent_id}")

        # Validate the complete batch before moving the first directory.
        destinations = [self._destination(agent, name) for name in names]
        backup_root = snapshot.central_skills_path.parent / "backups" / agent_id
        return [self.store.backup(destination, backup_root) for destination in destinations]

    def _destination(self, agent: AgentInventory, skill_name: str) -> Path:
        if not skill_name or skill_name.startswith(".") or Path(skill_name).name != skill_name:
            raise ValueError(f"Unsafe Skill name: {skill_name!r}")
        entry = next((item for item in agent.skills if item.name == skill_name), None)
        if entry is None or entry.status is ItemStatus.MISSING:
            raise FileNotFoundError(
                f"Skill is not installed for {agent.definition.id}: {skill_name}"
            )

        destination = (agent.skills_path / skill_name).absolute()
        if destination.parent != agent.skills_path.absolute():
            raise ValueError(f"Unsafe Skill destination: {destination}")
        if not destination.exists() and not self.store.is_link(destination):
            raise FileNotFoundError(destination)
        return destination
