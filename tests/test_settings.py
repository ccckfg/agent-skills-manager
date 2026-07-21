from agent_skills_manager.config.settings import Settings, expand_path
from agent_skills_manager.domain.models import AgentPreference, SyncMode


def test_default_central_skills_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    settings = Settings.load(tmp_path / "missing-settings.yaml")

    assert settings.central_skills_path == tmp_path / ".agent" / "skills"


def test_settings_round_trip_expands_home(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    path = tmp_path / "settings.yaml"
    settings = Settings.load(path)
    settings.central_skills_path = expand_path("%USERPROFILE%/central")
    settings.agents["codex"] = AgentPreference(False, SyncMode.LINK)
    settings.save()
    loaded = Settings.load(path)
    assert loaded.central_skills_path == tmp_path / "central"
    assert loaded.preference_for("codex").skills_mode is SyncMode.LINK
