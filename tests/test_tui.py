from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from textual.widgets import DataTable

from agent_skills_manager.domain.models import (
    AgentDefinition,
    AgentInventory,
    AgentPreference,
    InventorySnapshot,
    ItemStatus,
    McpEntry,
    SkillEntry,
    SyncMode,
)
from agent_skills_manager.tui import AgentSkillsApp
from agent_skills_manager.tui.screens import AgentDetailScreen, DashboardScreen
from agent_skills_manager.tui.widgets import SkillTree


def snapshot(extra_skills: int = 0) -> InventorySnapshot:
    central = Path("/tmp/central")
    local = Path("/tmp/codex/skills")
    skills = [
        SkillEntry("review", local / "review"),
        SkillEntry("gsd-plan", local / "gsd-plan"),
        SkillEntry("gsd-review", local / "gsd-review", ItemStatus.UNMANAGED),
        SkillEntry("gsd-audit", central / "gsd-audit", ItemStatus.MISSING),
        SkillEntry("gsd-debug", central / "gsd-debug", ItemStatus.MISSING),
        SkillEntry("gsap-core", central / "gsap-core", ItemStatus.MISSING),
        SkillEntry("gsap-react", central / "gsap-react", ItemStatus.MISSING),
        SkillEntry(".system", local / ".system"),
    ]
    skills.extend(
        SkillEntry(f"solo{index:02}", local / f"solo{index:02}") for index in range(extra_skills)
    )
    normal = AgentInventory(
        AgentDefinition("codex", "Codex", {}, {}, "json"),
        True,
        local,
        Path("/tmp/codex/mcp.json"),
        AgentPreference(skills_mode=SyncMode.COPY),
        skills,
        [McpEntry("github", Path("/tmp/mcp.json"))],
    )
    antigravity = AgentInventory(
        AgentDefinition("antigravity", "Antigravity", {}, {}, "json", supports_link=False),
        True,
        Path("/tmp/ag/skills"),
        Path("/tmp/ag/mcp.json"),
        AgentPreference(skills_mode=SyncMode.COPY),
    )
    return InventorySnapshot([normal, antigravity], central)


async def wait_for_inventory(app: AgentSkillsApp, pilot) -> None:
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()


@pytest.mark.asyncio
async def test_inventory_and_two_pane_detail_navigation() -> None:
    app = AgentSkillsApp(snapshot)
    async with app.run_test(size=(120, 32)) as pilot:
        await wait_for_inventory(app, pilot)
        assert isinstance(app.screen, DashboardScreen)
        assert app.screen.query_one("#agents", DataTable).row_count == 2

        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, AgentDetailScreen)
        current = app.screen.query_one("#current-skills", SkillTree)
        missing = app.screen.query_one("#missing-skills", SkillTree)
        assert set(current._entries) == {"review", "gsd-plan", "gsd-review"}
        assert set(missing._entries) == {"gsd-audit", "gsd-debug", "gsap-core", "gsap-react"}
        assert ".system" not in current._entries
        labels = {node.label.plain for node in missing.root.children}
        assert any("gsap-" in label for label in labels)
        assert any("gsd-" in label for label in labels)

        await pilot.press("escape")
        await pilot.pause()
        assert isinstance(app.screen, DashboardScreen)


@pytest.mark.asyncio
async def test_long_skill_tree_scrolls_to_selected_leaf() -> None:
    app = AgentSkillsApp(lambda: snapshot(extra_skills=45))
    async with app.run_test(size=(100, 20)) as pilot:
        await wait_for_inventory(app, pilot)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, AgentDetailScreen)
        tree = app.screen.query_one("#current-skills", SkillTree)

        assert tree.select_skill("solo44")
        await pilot.pause()

        assert tree.selected_skill == "solo44"
        assert tree.max_scroll_y > 0
        assert tree.scroll_y > 0


@pytest.mark.asyncio
async def test_compact_layout_reclaims_rows_and_preserves_selection_on_resize() -> None:
    app = AgentSkillsApp(lambda: snapshot(extra_skills=45))
    async with app.run_test(size=(100, 20)) as pilot:
        await wait_for_inventory(app, pilot)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, AgentDetailScreen)
        assert app.screen.has_class("compact")

        tree = app.screen.query_one("#current-skills", SkillTree)
        button = app.screen.query_one("#remove-skill")
        assert tree.size.height >= 8
        assert button.outer_size.height == 1
        assert app.screen.query_one("#current-selection").outer_size.height == 1
        assert app.screen.query_one("#mcp-strip").outer_size.height == 1

        group = next(node for node in tree.root.children if "gsd-" in node.label.plain)
        tree.move_cursor(group)
        tree.focus()
        await pilot.press("space")
        selected = tree.selected_names
        assert selected

        await pilot.resize_terminal(120, 40)
        await pilot.pause()
        assert not app.screen.has_class("compact")
        assert tree.selected_names == selected
        assert button.outer_size.height == 3


@pytest.mark.asyncio
async def test_space_selects_leaves_and_complete_families() -> None:
    app = AgentSkillsApp(snapshot)
    async with app.run_test(size=(120, 32)) as pilot:
        await wait_for_inventory(app, pilot)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, AgentDetailScreen)
        tree = app.screen.query_one("#missing-skills", SkillTree)
        tree.focus()

        gsap_group = next(node for node in tree.root.children if "gsap-" in node.label.plain)
        tree.move_cursor(gsap_group)
        await pilot.press("space")
        assert set(tree.selected_names) == {"gsap-core", "gsap-react"}
        assert gsap_group.label.plain.startswith("●")
        assert tree._skill_nodes["gsap-core"].label.plain.startswith("●")

        gsd_group = next(node for node in tree.root.children if "gsd-" in node.label.plain)
        tree.move_cursor(gsd_group)
        await pilot.press("space")
        assert set(tree.selected_names) == {
            "gsap-core",
            "gsap-react",
            "gsd-audit",
            "gsd-debug",
        }

        assert tree.select_skill("gsd-audit")
        await pilot.pause()
        await pilot.press("space")
        assert "gsd-audit" not in tree.selected_names
        assert gsd_group.label.plain.startswith("◐")
        assert tree._skill_nodes["gsd-audit"].label.plain.startswith("○")


@pytest.mark.asyncio
async def test_add_and_remove_complete_family_in_one_operation() -> None:
    state = snapshot()
    calls: list[tuple[str, tuple[str, ...]]] = []

    def add(agent: AgentInventory, names: tuple[str, ...]) -> None:
        calls.append(("add", names))
        selected = set(names)
        agent.skills = [
            replace(entry, path=agent.skills_path / entry.name, status=ItemStatus.READY)
            if entry.name in selected
            else entry
            for entry in agent.skills
        ]

    def remove(agent: AgentInventory, names: tuple[str, ...]) -> None:
        calls.append(("remove", names))
        selected = set(names)
        agent.skills = [
            replace(
                entry,
                path=state.central_skills_path / entry.name,
                status=ItemStatus.MISSING,
            )
            if entry.name in selected
            else entry
            for entry in agent.skills
        ]

    app = AgentSkillsApp(lambda: state, add_handler=add, remove_handler=remove)
    async with app.run_test(size=(120, 32)) as pilot:
        await wait_for_inventory(app, pilot)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, AgentDetailScreen)

        missing = app.screen.query_one("#missing-skills", SkillTree)
        group = next(node for node in missing.root.children if "gsap-" in node.label.plain)
        missing.move_cursor(group)
        missing.focus()
        await pilot.press("space")
        assert set(missing.selected_names) == {"gsap-core", "gsap-react"}
        await pilot.press("a", "y")
        await wait_for_inventory(app, pilot)
        assert calls == [("add", ("gsap-core", "gsap-react"))]

        current = app.screen.query_one("#current-skills", SkillTree)
        group = next(node for node in current.root.children if "gsap-" in node.label.plain)
        current.move_cursor(group)
        current.focus()
        await pilot.press("space")
        assert set(current.selected_names) == {"gsap-core", "gsap-react"}
        await pilot.press("d", "y")
        await wait_for_inventory(app, pilot)
        assert calls[-1] == ("remove", ("gsap-core", "gsap-react"))
        missing = app.screen.query_one("#missing-skills", SkillTree)
        assert {"gsap-core", "gsap-react"}.issubset(missing._entries)


@pytest.mark.asyncio
async def test_mode_switch_and_antigravity_copy_only() -> None:
    changed: list[tuple[str, SyncMode]] = []
    app = AgentSkillsApp(
        snapshot,
        mode_change_handler=lambda agent, mode: changed.append((agent.definition.id, mode)),
    )
    async with app.run_test() as pilot:
        await wait_for_inventory(app, pilot)
        await pilot.press("m")
        assert changed == [("codex", SyncMode.LINK)]

        await pilot.press("down", "m")
        assert app.snapshot is not None
        assert app.snapshot.agents[1].preference.skills_mode is SyncMode.COPY
