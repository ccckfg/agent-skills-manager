from pathlib import Path

from agent_skills_manager.domain.models import (
    AgentDefinition,
    AgentInventory,
    AgentPreference,
    InventorySnapshot,
    ItemStatus,
    SkillEntry,
)
from agent_skills_manager.services.skill_import import SkillImportService


def test_import_unmanaged_skill_without_overwrite(tmp_path: Path) -> None:
    central = tmp_path / "central"
    source = tmp_path / "codex" / "review"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("review", encoding="utf-8")
    definition = AgentDefinition("codex", "Codex", {}, {}, "toml")
    agent = AgentInventory(
        definition,
        True,
        source.parent,
        tmp_path / "config.toml",
        AgentPreference(),
        [SkillEntry("review", source, ItemStatus.UNMANAGED)],
    )
    snapshot = InventorySnapshot([agent], central)

    service = SkillImportService()
    plan = service.plan(snapshot)
    assert [action.skill_name for action in plan.actions] == ["review"]
    assert service.execute(plan) == ["review"]
    assert (central / "review" / "SKILL.md").read_text(encoding="utf-8") == "review"

    repeated = service.plan(snapshot)
    assert not repeated.actions
    assert "already exists" in repeated.warnings[0]
