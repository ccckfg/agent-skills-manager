from agent_skills_manager.adapters.agent_registry import AgentRegistry
from agent_skills_manager.config.settings import Settings
from agent_skills_manager.domain.models import AgentPreference, SyncMode
from agent_skills_manager.services.inventory import InventoryService
from agent_skills_manager.services.skill_sync import SkillSyncService


def test_sync_copies_and_backs_up_different_managed_skill(tmp_path):
    central, local = tmp_path / "central", tmp_path / "local"
    (central / "skill").mkdir(parents=True)
    (central / "skill" / "SKILL.md").write_text("new")
    (local / "skill").mkdir(parents=True)
    (local / "skill" / "SKILL.md").write_text("old")
    registry_file = tmp_path / "agents.yaml"
    registry_file.write_text(
        "agents:\n- id: demo\n  display_name: Demo\n  skills_paths: {default: '"
        + str(local).replace("\\", "/")
        + "'}\n  mcp_paths: {default: x}\n  mcp_format: json"
    )
    settings = Settings(central, {"demo": AgentPreference(skills_mode=SyncMode.COPY)})
    snapshot = InventoryService(settings, AgentRegistry.load_default(registry_file)).scan()
    service = SkillSyncService()
    backups = service.execute(service.plan(snapshot), central)
    assert (local / "skill" / "SKILL.md").read_text() == "new"
    assert len(backups) == 1 and (backups[0] / "SKILL.md").read_text() == "old"
