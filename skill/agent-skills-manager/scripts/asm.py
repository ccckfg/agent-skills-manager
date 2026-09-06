#!/usr/bin/env python3
"""Portable, dependency-free entry point bundled with the Skill."""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Set

sys.dont_write_bytecode = True

from asm_lib.diffing import compare  # noqa: E402
from asm_lib.inventory import scan  # noqa: E402
from asm_lib.models import AgentDifference, AgentInventory, Plan  # noqa: E402
from asm_lib.operations import apply_import, apply_sync, plan_import, plan_sync  # noqa: E402
from asm_lib.paths import central_path, load_profiles  # noqa: E402
from asm_lib.prompts import (  # noqa: E402
    apply_prompts,
    capture_prompt,
    load_targets,
    plan_prompts,
    prompts_file,
    scan_prompts,
)


VERSION = "0.4.1"
TUI_INSTALL = "uv tool install git+https://github.com/ccckfg/agent-skills-manager.git"


def _add_common(parser: argparse.ArgumentParser, agent_ids: List[str]) -> None:
    parser.add_argument("--central", help="Override the central Skills directory")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--agent", action="append", choices=agent_ids, dest="agents")


def _parser(agent_ids: List[str]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asm.py")
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser("status", help="Read Skills and MCP inventory")
    _add_common(status, agent_ids)
    status.add_argument(
        "--verify",
        action="store_true",
        help="Compare file contents instead of only presence and link health",
    )

    difference = commands.add_parser("diff", help="Compare central and agent Skills")
    _add_common(difference, agent_ids)
    difference.add_argument("--skill", action="append", dest="skills")
    difference.add_argument(
        "--all", action="store_true", dest="include_identical", help="Include identical Skills"
    )

    importer = commands.add_parser("import", help="Copy unmanaged Skills to the central store")
    _add_common(importer, agent_ids)
    importer.add_argument("--apply", action="store_true", help="Execute the displayed plan")

    sync = commands.add_parser("sync", help="Synchronize central Skills to agents")
    _add_common(sync, agent_ids)
    sync.add_argument("--mode", choices=("copy", "link"), default="copy")
    sync.add_argument("--apply", action="store_true", help="Execute the displayed plan")

    prompts = commands.add_parser("prompts", help="Manage user-level instruction files")
    _add_common(prompts, agent_ids)
    prompts.add_argument(
        "action", nargs="?", choices=("status", "capture", "sync"), default="status"
    )
    prompts.add_argument(
        "--from",
        dest="from_agent",
        metavar="AGENT_ID",
        help="Seed the canonical prompt from this agent's instruction file",
    )
    prompts.add_argument("--apply", action="store_true", help="Execute the displayed sync plan")

    doctor = commands.add_parser("doctor", help="Check the portable Skill runtime")
    doctor.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _selected(values: Optional[List[str]]) -> Optional[Set[str]]:
    return set(values) if values else None


def _status_payload(central: Path, inventories: List[AgentInventory], verified: bool) -> dict:
    return {
        "central": str(central),
        "verified": verified,
        "agents": [inventory.as_dict() for inventory in inventories],
    }


def _print_status(
    central: Path,
    inventories: List[AgentInventory],
    as_json: bool,
    verified: bool,
) -> None:
    payload = _status_payload(central, inventories, verified)
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    print("Central Skills: {}".format(central))
    if not verified:
        print("Presence and link health only. Use --verify or diff to compare file contents.")
    print("{:<18} {:>7} {:>8} {:>6}  {}".format("Agent", "Skills", "Missing", "MCPs", "Status"))
    for agent in inventories:
        state = "attention" if agent.needs_attention else "ready"
        if not agent.installed:
            state = "not installed"
        print(
            "{:<18} {:>7} {:>8} {:>6}  {}".format(
                agent.profile.display_name,
                agent.present_skills,
                agent.missing_skills,
                len(agent.mcps),
                state,
            )
        )
    print("\nOptional TUI: {}".format(TUI_INSTALL))


def _print_diff(
    central: Path,
    differences: List[AgentDifference],
    as_json: bool,
    include_identical: bool,
) -> None:
    payload = {
        "central": str(central),
        "agents": [item.as_dict(include_identical) for item in differences],
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    symbols = {"missing": "-", "extra": "+", "different": "~", "identical": "="}
    file_symbols = {
        "only-central": "-",
        "only-agent": "+",
        "modified": "~",
        "type-changed": "!",
    }
    print("Central Skills: {}".format(central))
    for difference in differences:
        summary = difference.summary
        print(
            "{}: {} different, {} missing, {} extra, {} identical".format(
                difference.profile.display_name,
                summary["different"],
                summary["missing"],
                summary["extra"],
                summary["identical"],
            )
        )
        visible = (
            difference.skills
            if include_identical
            else [item for item in difference.skills if item.status != "identical"]
        )
        for skill in visible:
            print("  {} {} [{}]".format(symbols[skill.status], skill.name, skill.status))
            for item in skill.files:
                print("    {} {} [{}]".format(file_symbols[item.status], item.path, item.status))
        if not visible:
            print("  No differences.")


def _print_plan(plan: Plan, as_json: bool) -> None:
    if as_json:
        print(json.dumps(plan.as_dict(), indent=2, ensure_ascii=False))
        return
    print("{} plan{}".format(plan.operation.title(), " (applied)" if plan.applied else ""))
    for warning in plan.warnings:
        print("Warning: {}".format(warning))
    for action in plan.actions:
        print(
            "  {}: {} [{}] {} -> {}".format(
                action.agent_id,
                action.skill_name,
                action.mode,
                action.source,
                action.destination,
            )
        )
    if not plan.actions:
        print("  No changes.")
    for old in plan.backups:
        print("Backup: {}".format(old))
    if plan.actions and not plan.applied:
        print("Plan only. Re-run with --apply after explicit user confirmation.")


def _print_prompt_status(source, source_present, targets, as_json: bool) -> None:
    payload = {
        "source": str(source),
        "source_present": source_present,
        "agents": [target.as_dict() for target in targets],
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    state = "present" if source_present else "missing"
    print("Canonical prompt: {} ({})".format(source, state))
    if not source_present:
        print("Seed it with: prompts capture --from <agent-id>")
    print("{:<18} {:<7} {:>10}  {}".format("Agent", "Style", "Status", "Path"))
    for target in targets:
        if not source_present:
            status = "no source"
        elif not target.present:
            status = "missing"
        elif target.matches:
            status = "ready"
        else:
            status = "different"
        print(
            "{:<18} {:<7} {:>10}  {}".format(target.display_name, target.style, status, target.path)
        )


def _prompts(args, profiles, central: Path) -> int:
    source = prompts_file(central)
    targets = load_targets(profiles)
    warnings = []
    if args.agents:
        known = {item.id for item in targets}
        undefined = [agent_id for agent_id in args.agents if agent_id not in known]
        if undefined:
            warnings.append(
                "No user-level prompt file is defined for: {}".format(", ".join(undefined))
            )
    if args.action == "status":
        scanned = scan_prompts(source, targets)
        _print_prompt_status(source, source.is_file(), scanned, args.as_json)
        return 0
    if args.action == "capture":
        return _capture_prompt(args, source, targets, central)
    plan = plan_prompts(source, targets, set(args.agents) if args.agents else None)
    plan.warnings.extend(warnings)
    if args.apply:
        apply_prompts(plan, source, [item.path for item in targets], central.parent / "backups")
    _print_plan(plan, args.as_json)
    return 0


def _capture_prompt(args, source: Path, targets, central: Path) -> int:
    origin = next((item for item in targets if item.id == args.from_agent), None)
    if origin is None:
        known = ", ".join(item.id for item in targets) or "none"
        print("Error: --from must name an agent that defines a prompt file ({}).".format(known))
        return 1
    if not origin.path.is_file():
        print(
            "Error: {} has no prompt file at {}. Nothing to capture.".format(
                origin.display_name, origin.path
            )
        )
        return 1
    old = capture_prompt(origin.path, source, central.parent / "backups" / "prompts")
    payload = {
        "source": str(source),
        "captured_from": origin.id,
        "backup": str(old) if old else None,
    }
    if args.as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    print("Captured {} -> {}".format(origin.path, source))
    if old:
        print("Backup: {}".format(old))
    return 0


def _doctor(as_json: bool) -> None:
    payload = {
        "ok": sys.version_info >= (3, 9),
        "python": sys.version.split()[0],
        "script": str(Path(__file__).resolve()),
        "tui_installed": False,
        "tui_install": TUI_INSTALL,
    }
    try:
        import shutil

        payload["tui_installed"] = shutil.which("agent-skills-manager") is not None
    except OSError:
        pass
    if as_json:
        print(json.dumps(payload, indent=2))
    else:
        for key, value in payload.items():
            print("{}: {}".format(key, value))


def main(argv: Optional[List[str]] = None) -> int:
    script_dir = Path(__file__).resolve().parent
    profiles = load_profiles(script_dir / "agent_profiles.json")
    args = _parser([profile.id for profile in profiles]).parse_args(argv)
    if args.command == "doctor":
        _doctor(args.as_json)
        return 0
    central = central_path(args.central)
    requested_agents = getattr(args, "agents", None)
    if requested_agents:
        requested_ids = set(requested_agents)
        profiles = [profile for profile in profiles if profile.id in requested_ids]
    if args.command == "prompts":
        return _prompts(args, profiles, central)
    if args.command == "diff":
        skill_names = set(args.skills) if args.skills else None
        differences = compare(central, profiles, skill_names)
        _print_diff(central, differences, args.as_json, args.include_identical)
        return 0
    # Only sync has to prove that two directories hold the same bytes. status reports
    # presence and link health unless --verify is requested, and import only looks for
    # Skills the central store has never seen, so neither needs to hash every file.
    if args.command == "sync":
        compare_contents = args.mode != "link"
        trust_links = args.mode == "copy"
    else:
        compare_contents = args.command == "status" and args.verify
        trust_links = False
    inventories = scan(
        central,
        profiles,
        compare_contents=compare_contents,
        trust_links=trust_links,
    )
    if args.command == "status":
        _print_status(central, inventories, args.as_json, compare_contents)
        return 0
    selected = _selected(args.agents)
    if args.command == "import":
        plan = plan_import(central, inventories, selected)
        if args.apply:
            central.mkdir(parents=True, exist_ok=True)
            apply_import(plan)
    else:
        plan = plan_sync(central, inventories, args.mode, selected)
        if args.apply:
            apply_sync(plan, central)
    _print_plan(plan, args.as_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
