from pathlib import Path
from typing import Iterable, Optional, Set

from .models import Action, AgentInventory, Plan
from .store import child_directories, replace


def _selected(agent_id: str, selected: Optional[Set[str]]) -> bool:
    return not selected or agent_id in selected


def plan_import(
    central: Path,
    inventories: Iterable[AgentInventory],
    selected: Optional[Set[str]] = None,
) -> Plan:
    plan = Plan("import")
    claimed = set(child_directories(central))
    for agent in inventories:
        if not _selected(agent.profile.id, selected):
            continue
        for skill in agent.skills:
            if skill.status != "unmanaged":
                continue
            if skill.name in claimed:
                plan.warnings.append(
                    "Skipped {} from {}: name already exists.".format(
                        skill.name, agent.profile.display_name
                    )
                )
                continue
            claimed.add(skill.name)
            plan.actions.append(
                Action(
                    agent.profile.id,
                    skill.name,
                    skill.path,
                    central / skill.name,
                    "copy",
                )
            )
    return plan


def plan_sync(
    central: Path,
    inventories: Iterable[AgentInventory],
    mode: str,
    selected: Optional[Set[str]] = None,
) -> Plan:
    plan = Plan("sync")
    sources = child_directories(central)
    for agent in inventories:
        if not _selected(agent.profile.id, selected):
            continue
        agent_mode = mode
        if mode == "link" and not agent.profile.supports_link:
            agent_mode = "copy"
            plan.warnings.append(
                "{} does not support links; using copy.".format(agent.profile.display_name)
            )
        for skill in agent.skills:
            source = sources.get(skill.name)
            if not source:
                continue
            if skill.status == "ready":
                link_matches = skill.is_link and skill.path.resolve() == source.resolve()
                mode_matches = link_matches if agent_mode == "link" else not skill.is_link
                if mode_matches:
                    continue
            elif skill.status not in {"missing", "different", "broken"}:
                continue
            plan.actions.append(
                Action(
                    agent.profile.id,
                    skill.name,
                    source,
                    agent.profile.skills_path / skill.name,
                    agent_mode,
                    replace=skill.status != "missing",
                )
            )
    return plan


def apply_import(plan: Plan) -> None:
    for action in plan.actions:
        if action.destination.exists() or action.destination.is_symlink():
            raise FileExistsError(
                "Refusing to overwrite central Skill: {}".format(action.destination)
            )
        replace(action.source, action.destination, "copy")
    plan.applied = True


def apply_sync(plan: Plan, central: Path) -> None:
    root = central.resolve()
    for action in plan.actions:
        source = action.source.resolve()
        if root != source and root not in source.parents:
            raise ValueError("Refusing source outside central directory: {}".format(source))
        if action.destination.name != action.skill_name:
            raise ValueError("Unsafe destination: {}".format(action.destination))
        if (action.destination.exists() or action.destination.is_symlink()) and not action.replace:
            raise FileExistsError(
                "Refusing to overwrite unmanaged Skill: {}".format(action.destination)
            )
        backup_root = central.parent / "backups" / action.agent_id
        old = replace(source, action.destination, action.mode, backup_root)
        if old:
            plan.backups.append(old)
    plan.applied = True
