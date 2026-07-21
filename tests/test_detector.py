from agent_skills_manager.adapters.agent_registry import AgentRegistry
from agent_skills_manager.services.detector import AgentDetector


def test_default_registry_has_all_supported_agents():
    registry = AgentRegistry.load_default()
    assert {item.id for item in registry.all()} == {"claude-code", "codex", "cursor", "antigravity"}
    assert registry.get("antigravity").supports_link is False


def test_detector_expands_default_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    definition = AgentRegistry.load_default().get("codex")
    skills, mcp = AgentDetector(AgentRegistry([definition])).paths_for(definition)
    assert skills == tmp_path / ".codex" / "skills"
    assert mcp.name == "config.toml"
