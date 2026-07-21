from pathlib import Path

import pytest

from agent_skills_manager.domain.models import (
    AgentDefinition,
    AgentInventory,
    AgentPreference,
    InventorySnapshot,
    McpEntry,
    SkillEntry,
    SyncMode,
)
from agent_skills_manager.tui import AgentSkillsApp


def snapshot() -> InventorySnapshot:
    normal = AgentInventory(
        AgentDefinition("codex", "Codex", {}, {}, "json"),
        True,
        Path("/tmp/codex/skills"),
        Path("/tmp/codex/mcp.json"),
        AgentPreference(),
        [SkillEntry("review", Path("/tmp/review"))],
        [McpEntry("github", Path("/tmp/mcp.json"))],
    )
    antigravity = AgentInventory(
        AgentDefinition("antigravity", "Antigravity", {}, {}, "json", supports_link=False),
        True,
        Path("/tmp/ag/skills"),
        Path("/tmp/ag/mcp.json"),
        AgentPreference(SyncMode.COPY),
    )
    return InventorySnapshot([normal, antigravity], Path("/tmp/central"))


@pytest.mark.asyncio
async def test_inventory_and_detail_navigation() -> None:
    app = AgentSkillsApp(snapshot)
    async with app.run_test() as pilot:
        assert app.query_one("#agents").row_count == 2
        await pilot.press("enter")
        assert app._showing_details
        assert "MCP configurations" in str(app.query_one("#detail").render())
        await pilot.press("escape")
        assert not app._showing_details


@pytest.mark.asyncio
async def test_mode_switch_and_antigravity_copy_only() -> None:
    changed: list[tuple[str, SyncMode]] = []
    app = AgentSkillsApp(
        snapshot,
        mode_change_handler=lambda agent, mode: changed.append((agent.definition.id, mode)),
    )
    async with app.run_test() as pilot:
        await pilot.press("m")
        assert changed == [("codex", SyncMode.LINK)]
        await pilot.press("down", "m")
        assert app.snapshot is not None
        assert app.snapshot.agents[1].preference.skills_mode is SyncMode.COPY
