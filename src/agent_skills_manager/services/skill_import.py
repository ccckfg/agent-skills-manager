from __future__ import annotations

from agent_skills_manager.domain.models import (
    InventorySnapshot,
    ItemStatus,
    SyncAction,
    SyncMode,
    SyncPlan,
)
from agent_skills_manager.infrastructure.skill_store import SkillStore


class SkillImportService:
    """Copy unmanaged agent skills into the canonical central directory."""

    def __init__(self, store: SkillStore | None = None) -> None:
        self.store = store or SkillStore()

    def plan(
        self,
        snapshot: InventorySnapshot,
        agent_ids: set[str] | None = None,
    ) -> SyncPlan:
        plan = SyncPlan()
        claimed = set(self.store.children(snapshot.central_skills_path))
        for agent in snapshot.agents:
            if agent_ids and agent.definition.id not in agent_ids:
                continue
            for entry in agent.skills:
                if entry.status is not ItemStatus.UNMANAGED:
                    continue
                if entry.name in claimed:
                    plan.warnings.append(
                        f"Skipped {entry.name} from {agent.definition.display_name}: name already exists."
                    )
                    continue
                claimed.add(entry.name)
                plan.actions.append(
                    SyncAction(
                        agent.definition.id,
                        entry.name,
                        entry.path,
                        snapshot.central_skills_path / entry.name,
                        SyncMode.COPY,
                    )
                )
        return plan

    def execute(self, plan: SyncPlan) -> list[str]:
        imported: list[str] = []
        for action in plan.actions:
            if action.destination.exists() or action.destination.is_symlink():
                raise FileExistsError(f"Refusing to overwrite central skill: {action.destination}")
            self.store.replace(action.source, action.destination, link=False)
            imported.append(action.skill_name)
        return imported
