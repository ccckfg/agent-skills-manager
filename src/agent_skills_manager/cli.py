from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from agent_skills_manager.adapters.agent_registry import AgentRegistry
from agent_skills_manager.config.settings import Settings
from agent_skills_manager.domain.models import AgentPreference, InventorySnapshot, SyncMode
from agent_skills_manager.services.inventory import InventoryService
from agent_skills_manager.services.skill_import import SkillImportService
from agent_skills_manager.services.skill_removal import SkillRemovalService
from agent_skills_manager.services.skill_sync import SkillSyncService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-skills-manager")
    parser.add_argument("--config", help="Use a custom settings YAML file")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("tui", help="Open the interactive interface")
    commands.add_parser("init", help="Create settings and the central skills directory")

    status = commands.add_parser("status", help="Print the current inventory")
    status.add_argument("--json", action="store_true", dest="as_json")

    for name, description in (
        ("sync", "Synchronize central skills to agents"),
        ("import", "Import unmanaged agent skills into the central directory"),
    ):
        command = commands.add_parser(name, help=description)
        command.add_argument("--agent", action="append", dest="agents")
        command.add_argument("--dry-run", action="store_true")
        command.add_argument("--yes", action="store_true")
    return parser


def _snapshot(settings: Settings) -> InventorySnapshot:
    return InventoryService(settings).scan()


def _print_status(snapshot: InventorySnapshot, as_json: bool = False) -> None:
    rows = [
        {
            "id": agent.definition.id,
            "agent": agent.definition.display_name,
            "installed": agent.installed,
            "mode": agent.preference.skills_mode.value,
            "skills": len(agent.skills),
            "mcps": [entry.name for entry in agent.mcps],
            "attention": agent.needs_attention,
            "skills_path": str(agent.skills_path),
            "mcp_path": str(agent.mcp_path),
        }
        for agent in snapshot.agents
    ]
    if as_json:
        print(json.dumps({"central": str(snapshot.central_skills_path), "agents": rows}, indent=2))
        return
    print(f"Central skills: {snapshot.central_skills_path}")
    print(f"{'Agent':<18} {'Mode':<8} {'Skills':>6} {'MCPs':>5}  Status")
    for row in rows:
        status = (
            "attention" if row["attention"] else ("ready" if row["installed"] else "not installed")
        )
        print(
            f"{row['agent']:<18} {row['mode']:<8} {row['skills']:>6} {len(row['mcps']):>5}  {status}"
        )


def _show_plan(title: str, actions: list, warnings: list[str]) -> None:
    print(title)
    for warning in warnings:
        print(f"Warning: {warning}")
    for action in actions:
        print(
            f"  {action.agent_id}: {action.skill_name} "
            f"[{action.mode.value}] {action.source} -> {action.destination}"
        )
    if not actions:
        print("  No changes.")


def _confirmed(assume_yes: bool) -> bool:
    return assume_yes or input("Apply this plan? [y/N] ").strip().lower() in {"y", "yes"}


def _run_tui(settings: Settings) -> int:
    from agent_skills_manager.tui import run_tui

    inventory = InventoryService(settings)
    synchronizer = SkillSyncService()
    remover = SkillRemovalService()

    def fast_snapshot() -> InventorySnapshot:
        return inventory.scan(verify_contents=False)

    def sync_agent(agent) -> None:
        snapshot = inventory.scan()
        plan = synchronizer.plan(snapshot, {agent.definition.id})
        synchronizer.execute(plan, snapshot.central_skills_path)

    def add_skills(agent, skill_names: tuple[str, ...]) -> None:
        snapshot = fast_snapshot()
        requested = set(skill_names)
        plan = synchronizer.plan(snapshot, {agent.definition.id}, requested)
        planned = {action.skill_name for action in plan.actions}
        if unavailable := requested - planned:
            raise ValueError(f"No add action is available for: {', '.join(sorted(unavailable))}")
        synchronizer.execute(plan, snapshot.central_skills_path)

    def remove_skills(agent, skill_names: tuple[str, ...]) -> None:
        remover.remove_many(fast_snapshot(), agent.definition.id, skill_names)

    def set_mode(agent, mode: SyncMode) -> None:
        previous = settings.preference_for(agent.definition.id)
        settings.agents[agent.definition.id] = AgentPreference(previous.enabled, mode)
        settings.save()

    run_tui(fast_snapshot, sync_agent, set_mode, add_skills, remove_skills)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = Settings.load(args.config)
    if args.command in {None, "tui"}:
        return _run_tui(settings)
    if args.command == "init":
        settings.central_skills_path.mkdir(parents=True, exist_ok=True)
        for definition in AgentRegistry.load_default().all():
            settings.agents.setdefault(definition.id, AgentPreference())
        path = settings.save()
        print(f"Settings: {path}\nCentral skills: {settings.central_skills_path}")
        return 0
    snapshot = _snapshot(settings)
    if args.command == "status":
        _print_status(snapshot, args.as_json)
        return 0
    agent_ids = set(args.agents) if args.agents else None
    service = SkillSyncService() if args.command == "sync" else SkillImportService()
    plan = service.plan(snapshot, agent_ids)
    _show_plan(args.command.title() + " plan", plan.actions, plan.warnings)
    if args.dry_run or not plan.has_changes:
        return 0
    if not _confirmed(args.yes):
        print("Cancelled.")
        return 1
    if args.command == "sync":
        service.execute(plan, snapshot.central_skills_path)
    else:
        service.execute(plan)
    print(f"Applied {len(plan.actions)} change(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
