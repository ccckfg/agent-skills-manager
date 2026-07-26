from pathlib import Path

import pytest

from agent_skills_manager.adapters.agent_registry import AgentRegistry
from agent_skills_manager.config.settings import Settings
from agent_skills_manager.domain.models import (
    AgentDefinition,
    AgentInventory,
    AgentPreference,
    ItemStatus,
    SkillEntry,
)
from agent_skills_manager.infrastructure.skill_store import SkillStore
from agent_skills_manager.services.inventory import InventoryService


def test_inventory_compares_central_skills_and_keeps_unmanaged(tmp_path):
    central, local = tmp_path / "central", tmp_path / "local"
    (central / "skill-a").mkdir(parents=True)
    (central / "skill-a" / "SKILL.md").write_text("new")
    (local / "skill-a").mkdir(parents=True)
    (local / "skill-a" / "SKILL.md").write_text("old")
    (local / "personal").mkdir()
    (local / "personal" / "SKILL.md").write_text("keep")
    (local / ".system").mkdir()
    (local / ".system" / "SKILL.md").write_text("hidden")
    (central / ".internal").mkdir()
    (central / ".internal" / "SKILL.md").write_text("hidden")
    registry_file = tmp_path / "agents.yaml"
    registry_file.write_text(
        "agents:\n- id: demo\n  display_name: Demo\n  skills_paths: {default: '"
        + str(local).replace("\\", "/")
        + "'}\n  mcp_paths: {default: 'x'}\n  mcp_format: json"
    )
    snap = InventoryService(
        Settings(central_skills_path=central), AgentRegistry.load_default(registry_file)
    ).scan()
    statuses = {skill.name: skill.status for skill in snap.agents[0].skills}
    assert statuses == {"skill-a": ItemStatus.DIFFERENT, "personal": ItemStatus.UNMANAGED}


def _inventory(skills):
    return AgentInventory(
        AgentDefinition("demo", "Demo", {}, {}, "json"),
        True,
        Path("/tmp/skills"),
        Path("/tmp/mcp.json"),
        AgentPreference(),
        skills,
    )


def test_missing_skills_are_counted_but_do_not_demand_attention():
    """Not installing a central Skill is a choice, not a problem to resolve."""
    agent = _inventory(
        [
            SkillEntry("here", Path("/tmp/skills/here")),
            SkillEntry("not-here", Path("/tmp/central/not-here"), ItemStatus.MISSING),
            SkillEntry("also-not-here", Path("/tmp/central/x"), ItemStatus.MISSING),
        ]
    )

    assert agent.present_skills == 1
    assert agent.missing_skills == 2
    assert agent.needs_attention is False


@pytest.mark.parametrize(
    "status", [ItemStatus.BROKEN, ItemStatus.UNMANAGED, ItemStatus.DIFFERENT, ItemStatus.ERROR]
)
def test_unresolved_states_still_demand_attention(status):
    agent = _inventory([SkillEntry("one", Path("/tmp/skills/one"), status)])
    assert agent.needs_attention is True


def test_a_read_error_demands_attention_on_its_own():
    agent = _inventory([SkillEntry("one", Path("/tmp/skills/one"))])
    agent.errors.append("Could not read MCP configuration")
    assert agent.needs_attention is True


def test_fast_inventory_scan_skips_content_hashes(tmp_path, monkeypatch):
    central, local = tmp_path / "central", tmp_path / "local"
    (central / "skill-a").mkdir(parents=True)
    (central / "skill-a" / "SKILL.md").write_text("new")
    (local / "skill-a").mkdir(parents=True)
    (local / "skill-a" / "SKILL.md").write_text("old")
    registry_file = tmp_path / "agents.yaml"
    registry_file.write_text(
        "agents:\n- id: demo\n  display_name: Demo\n  skills_paths: {default: '"
        + str(local).replace("\\", "/")
        + "'}\n  mcp_paths: {default: 'x'}\n  mcp_format: json"
    )
    store = SkillStore()

    def fail_digest(_):
        raise AssertionError("fast scan must not hash Skill contents")

    monkeypatch.setattr(store, "digest", fail_digest)
    snapshot = InventoryService(
        Settings(central_skills_path=central),
        AgentRegistry.load_default(registry_file),
        store=store,
    ).scan(verify_contents=False)

    assert snapshot.agents[0].skills[0].status is ItemStatus.READY
