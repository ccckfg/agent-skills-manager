from pathlib import Path

import pytest

from agent_skills_manager.domain.models import (
    AgentDefinition,
    AgentInventory,
    AgentPreference,
    InventorySnapshot,
    ItemStatus,
    SkillEntry,
)
from agent_skills_manager.services.skill_removal import SkillRemovalService


def _snapshot(tmp_path: Path, status: ItemStatus = ItemStatus.READY) -> InventorySnapshot:
    central = tmp_path / ".agent" / "skills"
    local = tmp_path / ".codex" / "skills"
    skill = local / "review"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("review", encoding="utf-8")
    agent = AgentInventory(
        AgentDefinition("codex", "Codex", {}, {}, "toml"),
        True,
        local,
        tmp_path / ".codex" / "config.toml",
        AgentPreference(),
        [SkillEntry("review", skill, status)],
    )
    return InventorySnapshot([agent], central)


def test_remove_moves_skill_to_central_backup_area(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)

    backup = SkillRemovalService().remove(snapshot, "codex", "review")

    assert not (snapshot.agents[0].skills_path / "review").exists()
    assert backup.parent == snapshot.central_skills_path.parent / "backups" / "codex"
    assert (backup / "SKILL.md").read_text(encoding="utf-8") == "review"


def test_remove_allows_unmanaged_skill_because_it_is_recoverable(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path, ItemStatus.UNMANAGED)

    backup = SkillRemovalService().remove(snapshot, "codex", "review")

    assert backup.exists()


def test_remove_many_moves_every_selected_skill(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)
    local = snapshot.agents[0].skills_path
    second = local / "format"
    second.mkdir()
    (second / "SKILL.md").write_text("format", encoding="utf-8")
    snapshot.agents[0].skills.append(SkillEntry("format", second))

    backups = SkillRemovalService().remove_many(snapshot, "codex", ("review", "format"))

    assert len(backups) == 2
    assert not (local / "review").exists()
    assert not (local / "format").exists()
    assert all(path.parent.name == "codex" for path in backups)


def test_remove_many_validates_full_batch_before_moving_anything(tmp_path: Path) -> None:
    snapshot = _snapshot(tmp_path)

    with pytest.raises(FileNotFoundError):
        SkillRemovalService().remove_many(snapshot, "codex", ("review", "missing"))

    assert (snapshot.agents[0].skills_path / "review").exists()


@pytest.mark.parametrize("skill_name", [".system", "../escape", "folder/review", ""])
def test_remove_rejects_unsafe_names(tmp_path: Path, skill_name: str) -> None:
    snapshot = _snapshot(tmp_path)

    with pytest.raises(ValueError):
        SkillRemovalService().remove(snapshot, "codex", skill_name)

    assert (snapshot.agents[0].skills_path / "review").exists()
