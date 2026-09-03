import json
from pathlib import Path

import yaml

from agent_skills_manager.adapters.agent_registry import AgentRegistry
from agent_skills_manager.services.detector import AgentDetector

PROFILES = (
    Path(__file__).parents[1] / "skill" / "agent-skills-manager" / "scripts" / "agent_profiles.json"
)
AGENTS_YAML = (
    Path(__file__).parents[1] / "src" / "agent_skills_manager" / "resources" / "agents.yaml"
)

EXPECTED_AGENTS = {
    "claude-code",
    "codex",
    "cursor",
    "antigravity",
    "gemini-cli",
    "copilot-cli",
    "windsurf",
    "opencode",
    "kiro",
    "pi",
    "droid",
    "qoder",
    "qoder-cn",
    "trae",
    "trae-cn",
    "codebuddy",
    "kimi-code",
    "iflow",
    "qwen-code",
    "lingma",
    "mimo-code",
    "agents-shared",
}


def test_default_registry_has_all_supported_agents():
    registry = AgentRegistry.load_default()
    assert {item.id for item in registry.all()} == EXPECTED_AGENTS
    assert registry.get("antigravity").supports_link is False
    assert registry.get("qoder").supports_link is True


def test_portable_profiles_match_the_installed_registry():
    """The bundled Skill and the optional app must describe the same agents."""
    expected = yaml.safe_load(AGENTS_YAML.read_text(encoding="utf-8"))["agents"]
    actual = json.loads(PROFILES.read_text(encoding="utf-8"))["agents"]

    def normalize(items):
        return {
            item["id"]: (
                item["display_name"],
                item["skills_paths"],
                item["mcp_paths"],
                item["mcp_format"],
                item.get("supports_link", True),
            )
            for item in items
        }

    assert normalize(actual) == normalize(expected)


def test_detector_expands_default_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    definition = AgentRegistry.load_default().get("codex")
    skills, mcp = AgentDetector(AgentRegistry([definition])).paths_for(definition)
    assert skills == tmp_path / ".codex" / "skills"
    assert mcp.name == "config.toml"


def test_droid_reads_the_factory_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    definition = AgentRegistry.load_default().get("droid")

    skills, mcp = AgentDetector(AgentRegistry([definition])).paths_for(definition)

    assert skills == tmp_path / ".factory" / "skills"
    assert mcp == tmp_path / ".factory" / "mcp.json"


def test_antigravity_uses_gemini_config_skills(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    definition = AgentRegistry.load_default().get("antigravity")

    skills, _ = AgentDetector(AgentRegistry([definition])).paths_for(definition)

    assert skills == tmp_path / ".gemini" / "config" / "skills"


def test_detector_prefers_the_candidate_that_exists(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    definition = AgentRegistry.load_default().get("antigravity")
    relocated = tmp_path / ".gemini" / "antigravity" / "skills"
    relocated.mkdir(parents=True)

    skills, _ = AgentDetector(AgentRegistry([definition])).paths_for(definition)

    assert skills == relocated


def test_codebuddy_falls_back_to_the_recommended_mcp_path(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    definition = AgentRegistry.load_default().get("codebuddy")
    registry = AgentRegistry([definition])

    _, mcp = AgentDetector(registry).paths_for(definition)
    assert mcp == tmp_path / ".codebuddy" / ".mcp.json"

    legacy = tmp_path / ".codebuddy" / "mcp.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("{}", encoding="utf-8")
    _, mcp = AgentDetector(registry).paths_for(definition)
    assert mcp == legacy


def test_windows_only_paths_do_not_leak_into_other_systems(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    definition = AgentRegistry.load_default().get("mimo-code")
    registry = AgentRegistry([definition])

    assert "%LOCALAPPDATA%" in " ".join(registry.path_candidates(definition, "skills", "Windows"))
    assert registry.path_candidates(definition, "skills", "Darwin") == ["~/.config/mimocode/skills"]
