from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from agent_skills_manager.adapters.agent_registry import AgentRegistry
from agent_skills_manager.config.settings import Settings
from agent_skills_manager.domain.models import (
    AgentPreference,
    InventorySnapshot,
    PromptInventory,
    PromptPlan,
    SyncMode,
)
from agent_skills_manager.infrastructure.prompt_store import PromptStore
from agent_skills_manager.services.inventory import InventoryService
from agent_skills_manager.services.prompt_sync import (
    PromptInventoryService,
    PromptSyncService,
    capture_prompt as capture_prompt_file,
    prompts_file,
)
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
    status.add_argument(
        "--verify",
        action="store_true",
        help="Compare file contents instead of only presence and link health",
    )

    for name, description in (
        ("sync", "Synchronize central skills to agents"),
        ("import", "Import unmanaged agent skills into the central directory"),
    ):
        command = commands.add_parser(name, help=description)
        command.add_argument("--agent", action="append", dest="agents")
        command.add_argument("--dry-run", action="store_true")
        command.add_argument("--yes", action="store_true")

    prompts = commands.add_parser("prompts", help="Manage user-level instruction files")
    prompts.add_argument(
        "action", nargs="?", choices=("status", "capture", "sync"), default="status"
    )
    prompts.add_argument("--json", action="store_true", dest="as_json")
    prompts.add_argument("--agent", action="append", dest="agents")
    prompts.add_argument(
        "--from",
        dest="from_agent",
        help="Seed the canonical prompt from this agent's instruction file",
    )
    prompts.add_argument("--dry-run", action="store_true")
    prompts.add_argument("--yes", action="store_true")
    return parser


def _snapshot(settings: Settings, verify_contents: bool = True) -> InventorySnapshot:
    return InventoryService(settings).scan(verify_contents=verify_contents)


def _print_status(
    snapshot: InventorySnapshot,
    as_json: bool = False,
    verified: bool = True,
) -> None:
    rows = [
        {
            "id": agent.definition.id,
            "agent": agent.definition.display_name,
            "installed": agent.installed,
            "mode": agent.preference.skills_mode.value,
            "skills": len(agent.skills),
            "present": agent.present_skills,
            "missing": agent.missing_skills,
            "mcps": [entry.name for entry in agent.mcps],
            "attention": agent.needs_attention,
            "skills_path": str(agent.skills_path),
            "mcp_path": str(agent.mcp_path),
        }
        for agent in snapshot.agents
    ]
    if as_json:
        payload = {
            "central": str(snapshot.central_skills_path),
            "verified": verified,
            "agents": rows,
        }
        print(json.dumps(payload, indent=2))
        return
    print(f"Central skills: {snapshot.central_skills_path}")
    if not verified:
        print("Presence and link health only. Use --verify to compare file contents.")
    print(f"{'Agent':<18} {'Mode':<8} {'Skills':>6} {'Missing':>7} {'MCPs':>5}  Status")
    for row in rows:
        # A host that was never installed reports every central Skill as missing, so
        # absence has to win over attention or nothing is ever "not installed".
        if not row["installed"]:
            status = "not installed"
        else:
            status = "attention" if row["attention"] else "ready"
        print(
            f"{row['agent']:<18} {row['mode']:<8} {row['present']:>6} {row['missing']:>7} "
            f"{len(row['mcps']):>5}  {status}"
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


def _run_prompts(args: argparse.Namespace, settings: Settings) -> int:
    registry = AgentRegistry.load_default()
    store = PromptStore()
    inventory = PromptInventoryService(registry, store).scan(
        prompts_file(settings.central_skills_path)
    )
    targets = inventory.targets
    if args.agents:
        wanted = set(args.agents)
        targets = [item for item in targets if item.agent_id in wanted]

    if args.action == "status":
        _print_prompt_status(inventory, targets, args.as_json)
        return 0
    if args.action == "capture":
        return _capture_prompt(args, targets, settings, store)
    return _sync_prompts(args, inventory, settings, store)


def _print_prompt_status(inventory: PromptInventory, targets, as_json: bool) -> None:
    rows = [
        {
            "id": target.agent_id,
            "agent": target.display_name,
            "path": str(target.path),
            "style": target.style.value,
            "present": target.present,
            "matches": target.matches,
            "attention": target.needs_attention,
        }
        for target in targets
    ]
    if as_json:
        payload = {
            "source": str(inventory.source),
            "source_present": inventory.source_present,
            "agents": rows,
        }
        print(json.dumps(payload, indent=2))
        return
    state = "present" if inventory.source_present else "missing"
    print(f"Canonical prompt: {inventory.source} ({state})")
    if not inventory.source_present:
        print("Seed it with: agent-skills-manager prompts capture --from <agent>")
    print(f"{'Agent':<18} {'Style':<7} {'Status':>10}  Path")
    for row in rows:
        if not inventory.source_present:
            status = "no source"
        elif not row["present"]:
            status = "missing"
        elif row["matches"]:
            status = "ready"
        else:
            status = "different"
        print(f"{row['agent']:<18} {row['style']:<7} {status:>10}  {row['path']}")


def _capture_prompt(
    args: argparse.Namespace,
    targets,
    settings: Settings,
    store: PromptStore,
) -> int:
    origin = next((item for item in targets if item.agent_id == args.from_agent), None)
    if origin is None:
        known = ", ".join(item.agent_id for item in targets) or "none"
        print(f"Error: --from must name an agent that defines a prompt file ({known}).")
        return 1
    source = prompts_file(settings.central_skills_path)
    try:
        backup = capture_prompt_file(
            store,
            source,
            origin.path,
            settings.central_skills_path.parent / "backups" / "prompts",
        )
    except FileNotFoundError:
        print(f"Error: {origin.display_name} has no prompt file at {origin.path}.")
        return 1
    print(f"Captured {origin.path} -> {source}")
    if backup:
        print(f"Backup: {backup}")
    return 0


def _show_prompt_plan(plan: PromptPlan) -> None:
    print("Prompts plan")
    for warning in plan.warnings:
        print(f"Warning: {warning}")
    for action in plan.actions:
        print(
            f"  {action.agent_id}: {action.destination.name} "
            f"[{action.style.value}] {action.source} -> {action.destination}"
        )
    if not plan.actions:
        print("  No changes.")


def _sync_prompts(
    args: argparse.Namespace,
    inventory: PromptInventory,
    settings: Settings,
    store: PromptStore,
) -> int:
    service = PromptSyncService(store)
    selected = set(args.agents) if args.agents else None
    plan = service.plan(inventory, selected)
    _show_prompt_plan(plan)
    if args.dry_run or not plan.has_changes:
        return 0
    if not _confirmed(args.yes):
        print("Cancelled.")
        return 1
    service.execute(
        plan,
        allowed={item.path for item in inventory.targets},
        backup_root=settings.central_skills_path.parent / "backups",
    )
    print(f"Applied {len(plan.actions)} change(s).")
    return 0


def _run_tui(settings: Settings) -> int:
    from agent_skills_manager.tui import run_tui

    inventory = InventoryService(settings)
    synchronizer = SkillSyncService()
    importer = SkillImportService()
    remover = SkillRemovalService()
    prompt_store = PromptStore()
    prompt_scanner = PromptInventoryService(AgentRegistry.load_default(), prompt_store)
    prompt_sync = PromptSyncService(prompt_store)
    prompts_source = prompts_file(settings.central_skills_path)
    prompts_backup_root = settings.central_skills_path.parent / "backups" / "prompts"

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

    def import_skills(agent, skill_names: tuple[str, ...]) -> None:
        snapshot = fast_snapshot()
        requested = set(skill_names)
        plan = importer.plan(snapshot, {agent.definition.id}, requested)
        planned = {action.skill_name for action in plan.actions}
        if unavailable := requested - planned:
            detail = "；".join(plan.warnings) or "它们可能已不在这个 Agent 中"
            raise ValueError(f"无法导入：{', '.join(sorted(unavailable))}（{detail}）")
        importer.execute(plan)

    def remove_skills(agent, skill_names: tuple[str, ...]) -> None:
        remover.remove_many(fast_snapshot(), agent.definition.id, skill_names)

    def set_mode(agent, mode: SyncMode) -> None:
        previous = settings.preference_for(agent.definition.id)
        settings.agents[agent.definition.id] = AgentPreference(previous.enabled, mode)
        settings.save()

    def prompts_loader() -> PromptInventory:
        return prompt_scanner.scan(prompts_source)

    def prompts_planner(selected: set[str] | None) -> PromptPlan:
        return prompt_sync.plan(prompt_scanner.scan(prompts_source), selected)

    def capture_prompt(agent_id: str) -> None:
        target = next(
            (
                item
                for item in prompt_scanner.scan(prompts_source).targets
                if item.agent_id == agent_id
            ),
            None,
        )
        if target is None:
            raise ValueError(f"{agent_id} 没有已登记的提示词文件")
        capture_prompt_file(prompt_store, prompts_source, target.path, prompts_backup_root)

    def sync_prompts(plan: PromptPlan) -> None:
        scan = prompt_scanner.scan(prompts_source)
        prompt_sync.execute(
            plan,
            allowed={item.path for item in scan.targets},
            backup_root=settings.central_skills_path.parent / "backups",
        )

    def prompts_reader(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def prompts_writer(path: Path, content: str) -> None:
        prompt_store.write(path, content)

    run_tui(
        fast_snapshot,
        sync_agent,
        set_mode,
        add_skills,
        remove_skills,
        import_skills,
        prompts_loader,
        prompts_planner,
        capture_prompt,
        sync_prompts,
        prompts_reader,
        prompts_writer,
    )
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
    if args.command == "prompts":
        return _run_prompts(args, settings)
    # Only sync has to prove that two directories hold the same bytes. import looks for
    # Skills the central store has never seen, and status reports presence and link
    # health unless verification is requested, so neither needs to hash every file.
    verify = args.command == "sync" or (args.command == "status" and args.verify)
    snapshot = _snapshot(settings, verify_contents=verify)
    if args.command == "status":
        _print_status(snapshot, args.as_json, verified=args.verify)
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
