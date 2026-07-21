from agent_skills_manager.adapters.agent_registry import AgentRegistry
from agent_skills_manager.config.settings import Settings
from agent_skills_manager.domain.models import ItemStatus
from agent_skills_manager.services.inventory import InventoryService


def test_inventory_compares_central_skills_and_keeps_unmanaged(tmp_path):
    central, local = tmp_path / "central", tmp_path / "local"
    (central / "skill-a").mkdir(parents=True)
    (central / "skill-a" / "SKILL.md").write_text("new")
    (local / "skill-a").mkdir(parents=True)
    (local / "skill-a" / "SKILL.md").write_text("old")
    (local / "personal").mkdir()
    (local / "personal" / "note").write_text("keep")
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
