from __future__ import annotations

from pathlib import Path

from agent_skills_manager.domain.models import (
    InventorySnapshot,
    ItemStatus,
    SyncAction,
    SyncMode,
    SyncPlan,
)
from agent_skills_manager.infrastructure.skill_store import SkillStore


class SkillSyncService:
    def __init__(self, store: SkillStore | None = None) -> None:
        self.store = store or SkillStore()

    def plan(self, snapshot: InventorySnapshot, agent_ids: set[str] | None = None) -> SyncPlan:
        plan = SyncPlan()
        sources = self.store.children(snapshot.central_skills_path)
        for agent in snapshot.agents:
            if agent_ids and agent.definition.id not in agent_ids:
                continue
            if not agent.preference.enabled:
                continue
            mode = agent.preference.skills_mode
            if mode is SyncMode.LINK and not agent.definition.supports_link:
                plan.warnings.append(
                    f"{agent.definition.display_name} does not support links; using copy."
                )
                mode = SyncMode.COPY
            for entry in agent.skills:
                if entry.status not in {
                    ItemStatus.MISSING,
                    ItemStatus.DIFFERENT,
                    ItemStatus.BROKEN,
                }:
                    continue
                source = sources.get(entry.name)
                if source is None:
                    continue
                plan.actions.append(
                    SyncAction(
                        agent.definition.id,
                        entry.name,
                        source,
                        agent.skills_path / entry.name,
                        mode,
                        replace=entry.status is not ItemStatus.MISSING,
                    )
                )
        return plan

    def execute(self, plan: SyncPlan, central_skills_path: Path | None = None) -> list[Path]:
        backups: list[Path] = []
        root = central_skills_path.resolve() if central_skills_path else None
        for action in plan.actions:
            if root and root not in action.source.resolve().parents:
                raise ValueError(
                    f"Refusing source outside central skills directory: {action.source}"
                )
            if action.destination.name != action.skill_name:
                raise ValueError(f"Unsafe destination: {action.destination}")
            if (
                action.destination.exists() or action.destination.is_symlink()
            ) and not action.replace:
                raise FileExistsError(
                    f"Refusing to overwrite unmanaged skill: {action.destination}"
                )
            backup = self.store.replace(
                action.source, action.destination, action.mode is SyncMode.LINK
            )
            if backup:
                backups.append(backup)
        return backups
