from agent_skills_manager.adapters.agent_registry import AgentRegistry
from agent_skills_manager.config.settings import Settings
from agent_skills_manager.domain.models import AgentPreference, SyncMode
from agent_skills_manager.infrastructure.skill_store import SkillStore
from agent_skills_manager.services.inventory import InventoryService
from agent_skills_manager.services.skill_removal import SkillRemovalService
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
    assert backups[0].parent == central.parent / "backups" / "demo"


def test_sync_plan_can_target_one_selected_skill(tmp_path):
    central, local = tmp_path / "central", tmp_path / "local"
    for name in ("one", "two"):
        (central / name).mkdir(parents=True)
        (central / name / "SKILL.md").write_text(name)
    registry_file = tmp_path / "agents.yaml"
    registry_file.write_text(
        "agents:\n- id: demo\n  display_name: Demo\n  skills_paths: {default: '"
        + str(local).replace("\\", "/")
        + "'}\n  mcp_paths: {default: x}\n  mcp_format: json"
    )
    settings = Settings(central, {"demo": AgentPreference(skills_mode=SyncMode.COPY)})
    snapshot = InventoryService(settings, AgentRegistry.load_default(registry_file)).scan()

    plan = SkillSyncService().plan(snapshot, {"demo"}, {"two"})

    assert [action.skill_name for action in plan.actions] == ["two"]


def test_link_mode_uses_a_real_link_or_windows_junction(tmp_path):
    central, local = tmp_path / "central", tmp_path / "local"
    (central / "linked").mkdir(parents=True)
    (central / "linked" / "SKILL.md").write_text("linked")
    registry_file = tmp_path / "agents.yaml"
    registry_file.write_text(
        "agents:\n- id: demo\n  display_name: Demo\n  skills_paths: {default: '"
        + str(local).replace("\\", "/")
        + "'}\n  mcp_paths: {default: x}\n  mcp_format: json"
    )
    snapshot = InventoryService(
        Settings(central, {"demo": AgentPreference(skills_mode=SyncMode.LINK)}),
        AgentRegistry.load_default(registry_file),
    ).scan()

    service = SkillSyncService()
    service.execute(service.plan(snapshot), central)

    destination = local / "linked"
    assert SkillStore().is_link(destination)
    assert SkillStore().points_to(destination, central / "linked")

    refreshed = InventoryService(
        Settings(central, {"demo": AgentPreference(skills_mode=SyncMode.LINK)}),
        AgentRegistry.load_default(registry_file),
    ).scan(verify_contents=False)
    backup = SkillRemovalService().remove(refreshed, "demo", "linked")
    assert not destination.exists()
    assert SkillStore().is_link(backup)
    assert SkillStore().points_to(backup, central / "linked")
