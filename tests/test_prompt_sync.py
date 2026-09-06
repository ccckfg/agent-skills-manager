import pytest
from pathlib import Path

from agent_skills_manager.adapters.agent_registry import AgentRegistry
from agent_skills_manager.domain.models import PromptStyle
from agent_skills_manager.services.prompt_sync import (
    PromptInventoryService,
    PromptSyncService,
    prompts_file,
)

CONTENT = "Use uv for Python projects\nNo hardcoded config\n"


def registry_with(tmp_path: Path, yaml_text: str) -> AgentRegistry:
    registry_file = tmp_path / "agents.yaml"
    registry_file.write_text("agents:\n" + yaml_text, encoding="utf-8")
    return AgentRegistry.load_default(registry_file)


def single_agent_registry(tmp_path, style="plain"):
    prompt_file = tmp_path / "home" / ".codex" / "AGENTS.md"
    yaml_text = (
        "- id: demo\n"
        "  display_name: Demo\n"
        "  skills_paths: {default: x}\n"
        "  mcp_paths: {default: x}\n"
        "  mcp_format: json\n"
        f"  prompts_paths: {{default: '{prompt_file.as_posix()}'}}\n"
        + (f"  prompt_style: {style}\n" if style != "plain" else "")
    )
    return registry_with(tmp_path, yaml_text), prompt_file


def seed_canonical(tmp_path, content=CONTENT):
    source = prompts_file(tmp_path / "central" / "skills")
    source.parent.mkdir(parents=True)
    source.write_text(content, encoding="utf-8")
    return source


def test_prompt_sync_writes_and_backs_up_existing_file(tmp_path):
    registry, prompt_file = single_agent_registry(tmp_path)
    source = seed_canonical(tmp_path)
    prompt_file.parent.mkdir(parents=True)
    prompt_file.write_text("old content", encoding="utf-8")
    inventory = PromptInventoryService(registry).scan(source)

    service = PromptSyncService()
    plan = service.plan(inventory)
    assert len(plan.actions) == 1 and plan.actions[0].replace is True

    backups = service.execute(
        plan, allowed={prompt_file}, backup_root=source.parents[1] / "backups"
    )

    assert prompt_file.read_text(encoding="utf-8") == CONTENT
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "old content"
    assert backups[0].parent == source.parents[1] / "backups" / "demo"


def test_prompt_status_matches_ignore_line_endings(tmp_path):
    registry, prompt_file = single_agent_registry(tmp_path)
    source = seed_canonical(tmp_path)
    prompt_file.parent.mkdir(parents=True)
    prompt_file.write_bytes(CONTENT.replace("\n", "\r\n").encode("utf-8"))

    inventory = PromptInventoryService(registry).scan(source)

    assert inventory.targets[0].matches is True
    assert PromptSyncService().plan(inventory).has_changes is False


def test_cursor_style_wraps_canonical_content_in_frontmatter(tmp_path):
    registry, prompt_file = single_agent_registry(tmp_path, style="cursor")
    source = seed_canonical(tmp_path)
    inventory = PromptInventoryService(registry).scan(source)

    service = PromptSyncService()
    service.execute(service.plan(inventory), allowed={prompt_file}, backup_root=source.parents[1])

    text = prompt_file.read_text(encoding="utf-8")
    assert text.startswith("---\ndescription: User coding instructions\nalwaysApply: true\n---\n\n")
    assert text.endswith(CONTENT)
    assert inventory.targets[0].style is PromptStyle.CURSOR


def test_two_agents_sharing_one_prompt_file_are_written_once(tmp_path):
    shared = tmp_path / "home" / ".gemini" / "GEMINI.md"
    yaml_text = (
        "- id: first\n"
        "  display_name: First\n"
        "  skills_paths: {default: x}\n"
        "  mcp_paths: {default: x}\n"
        "  mcp_format: json\n"
        f"  prompts_paths: {{default: '{shared.as_posix()}'}}\n"
        "- id: second\n"
        "  display_name: Second\n"
        "  skills_paths: {default: x}\n"
        "  mcp_paths: {default: x}\n"
        "  mcp_format: json\n"
        f"  prompts_paths: {{default: '{shared.as_posix()}'}}\n"
    )
    registry = registry_with(tmp_path, yaml_text)
    source = seed_canonical(tmp_path)
    inventory = PromptInventoryService(registry).scan(source)

    plan = PromptSyncService().plan(inventory)

    assert len(plan.actions) == 1
    assert any("share one prompt file" in warning for warning in plan.warnings)


def test_execute_refuses_a_destination_outside_the_scanned_targets(tmp_path):
    registry, prompt_file = single_agent_registry(tmp_path)
    source = seed_canonical(tmp_path)
    inventory = PromptInventoryService(registry).scan(source)
    plan = PromptSyncService().plan(inventory)

    with pytest.raises(ValueError):
        PromptSyncService().execute(
            plan, allowed={tmp_path / "elsewhere" / "AGENTS.md"}, backup_root=source.parents[1]
        )


def test_plan_without_a_canonical_source_only_warns(tmp_path):
    registry, prompt_file = single_agent_registry(tmp_path)
    source = prompts_file(tmp_path / "central" / "skills")
    inventory = PromptInventoryService(registry).scan(source)

    plan = PromptSyncService().plan(inventory)

    assert not plan.actions
    assert plan.warnings
    assert inventory.source_present is False
