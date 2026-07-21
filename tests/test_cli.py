import json
from pathlib import Path

from agent_skills_manager import cli
from agent_skills_manager.domain.models import (
    AgentDefinition,
    AgentInventory,
    AgentPreference,
    InventorySnapshot,
    McpEntry,
    SkillEntry,
)


def sample_snapshot(tmp_path: Path) -> InventorySnapshot:
    definition = AgentDefinition("codex", "Codex", {}, {}, "toml")
    inventory = AgentInventory(
        definition,
        True,
        tmp_path / "skills",
        tmp_path / "config.toml",
        AgentPreference(),
        [SkillEntry("review", tmp_path / "skills" / "review")],
        [McpEntry("github", tmp_path / "config.toml")],
    )
    return InventorySnapshot([inventory], tmp_path / "central")


def test_status_json(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "_snapshot", lambda settings: sample_snapshot(tmp_path))
    assert cli.main(["status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["agents"][0]["id"] == "codex"
    assert payload["agents"][0]["mcps"] == ["github"]
