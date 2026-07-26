import json
from pathlib import Path

import pytest

from agent_skills_manager import cli
from agent_skills_manager.config.settings import Settings
from agent_skills_manager.domain.models import (
    AgentDefinition,
    AgentInventory,
    AgentPreference,
    InventorySnapshot,
    ItemStatus,
    McpEntry,
    SkillEntry,
)


def sample_snapshot(tmp_path: Path, installed: bool = True) -> InventorySnapshot:
    definition = AgentDefinition("codex", "Codex", {}, {}, "toml")
    inventory = AgentInventory(
        definition,
        installed,
        tmp_path / "skills",
        tmp_path / "config.toml",
        AgentPreference(),
        [SkillEntry("review", tmp_path / "skills" / "review")],
        [McpEntry("github", tmp_path / "config.toml")],
    )
    return InventorySnapshot([inventory], tmp_path / "central")


def test_status_json(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "_snapshot", lambda settings, **_: sample_snapshot(tmp_path))
    assert cli.main(["status", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["agents"][0]["id"] == "codex"
    assert payload["agents"][0]["mcps"] == ["github"]
    assert payload["verified"] is False


def test_status_only_hashes_contents_when_verification_is_requested(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    seen: list[bool] = []

    def snapshot(settings, verify_contents: bool = True):
        seen.append(verify_contents)
        return sample_snapshot(tmp_path)

    monkeypatch.setattr(cli, "_snapshot", snapshot)

    assert cli.main(["status"]) == 0
    assert cli.main(["import", "--dry-run"]) == 0
    assert cli.main(["status", "--verify", "--json"]) == 0

    assert seen == [False, False, True]
    assert '"verified": true' in capsys.readouterr().out


def _make_skill(path: Path, content: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(content, encoding="utf-8")


def _tui_handlers(monkeypatch, tmp_path: Path) -> dict:
    """Capture the handlers the real TUI is launched with, without starting it.

    Exercises the wiring in _run_tui against a sandboxed home instead of a stub.
    """
    agent_skills = tmp_path / "codex" / "skills"
    agent_skills.mkdir(parents=True, exist_ok=True)
    registry_file = tmp_path / "agents.yaml"
    registry_file.write_text(
        "agents:\n- id: codex\n  display_name: Codex\n  skills_paths: {default: '"
        + str(agent_skills).replace("\\", "/")
        + "'}\n  mcp_paths: {default: 'x'}\n  mcp_format: json",
        encoding="utf-8",
    )
    load_default = cli.AgentRegistry.load_default
    monkeypatch.setattr(
        cli.AgentRegistry,
        "load_default",
        staticmethod(lambda path=None: load_default(registry_file)),
    )

    captured: dict = {}

    def fake_run_tui(*args) -> None:
        names = ("snapshot", "sync", "set_mode", "add", "remove", "import")
        captured.update(dict(zip(names, args)))

    monkeypatch.setattr("agent_skills_manager.tui.run_tui", fake_run_tui)
    settings = Settings(central_skills_path=tmp_path / "central", path=tmp_path / "settings.yaml")
    assert cli._run_tui(settings) == 0
    return captured


def test_tui_import_handler_copies_an_agent_only_skill_into_the_central_store(
    monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / "central").mkdir()
    _make_skill(tmp_path / "codex" / "skills" / "agent-only", "mine")
    handlers = _tui_handlers(monkeypatch, tmp_path)

    handlers["import"](handlers["snapshot"]().agents[0], ("agent-only",))

    assert (tmp_path / "central" / "agent-only" / "SKILL.md").read_text(encoding="utf-8") == "mine"
    # Importing copies; the agent keeps its own directory.
    assert (tmp_path / "codex" / "skills" / "agent-only" / "SKILL.md").is_file()


def test_tui_import_handler_refuses_a_skill_the_central_store_already_has(
    monkeypatch, tmp_path: Path
) -> None:
    _make_skill(tmp_path / "central" / "shared", "central")
    _make_skill(tmp_path / "codex" / "skills" / "shared", "central")
    handlers = _tui_handlers(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="无法导入"):
        handlers["import"](handlers["snapshot"]().agents[0], ("shared",))


def test_uninstalled_agent_is_not_reported_as_needing_attention(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    """Every central Skill is missing from a host that was never installed."""
    snapshot = sample_snapshot(tmp_path, installed=False)
    snapshot.agents[0].skills = [SkillEntry("review", tmp_path / "review", ItemStatus.MISSING)]
    monkeypatch.setattr(cli, "_snapshot", lambda settings, **_: snapshot)

    assert cli.main(["status"]) == 0

    output = capsys.readouterr().out
    assert "not installed" in output
    assert "attention" not in output
