"""Agent overview screen."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Static

from agent_skills_manager.domain.models import AgentInventory, InventorySnapshot, ItemStatus

if TYPE_CHECKING:
    from agent_skills_manager.tui.app import AgentSkillsApp


class DashboardScreen(Screen[None]):
    BINDINGS = [
        Binding("enter", "details", "打开"),
        Binding("m", "toggle_mode", "切换模式"),
        Binding("r", "refresh", "刷新"),
        Binding("o", "open_folder", "打开目录"),
        Binding("q", "quit", "退出"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.snapshot: InventorySnapshot | None = None
        self._agent_ids: list[str] = []
        self._columns_ready = False

    @property
    def manager(self) -> AgentSkillsApp:
        return cast("AgentSkillsApp", self.app)

    def compose(self) -> ComposeResult:
        with Horizontal(classes="topbar"):
            yield Static("◆  agent skills manager", classes="brand")
            yield Static("正在读取中央仓库…", id="central-path", classes="topbar-context")
        with Vertical(id="dashboard-shell", classes="shell"):
            yield Static("AGENTS", classes="eyebrow")
            yield Static("先选择一个 Agent，再进入 Skill 管理", classes="page-title")
            yield Static("正在快速扫描本机配置…", id="summary", classes="muted")
            yield DataTable(id="agents", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#agents", DataTable)
        table.add_columns("Agent", "模式", "已有", "待添加", "MCP", "状态")
        self._columns_ready = True
        if self.manager.snapshot:
            self.set_snapshot(self.manager.snapshot)

    def set_snapshot(self, snapshot: InventorySnapshot) -> None:
        previous = self.selected_agent_id
        self.snapshot = snapshot
        if not self._columns_ready:
            return
        table = self.query_one("#agents", DataTable)
        table.clear()
        self._agent_ids = []
        for agent in snapshot.agents:
            self._agent_ids.append(agent.definition.id)
            present = sum(entry.status is not ItemStatus.MISSING for entry in agent.skills)
            missing = sum(entry.status is ItemStatus.MISSING for entry in agent.skills)
            table.add_row(
                agent.definition.display_name,
                agent.preference.skills_mode.value,
                str(present),
                str(missing),
                str(len(agent.mcps)),
                self._status(agent),
                key=agent.definition.id,
            )
        if previous in self._agent_ids:
            table.move_cursor(row=self._agent_ids.index(previous))
        self.query_one("#central-path", Static).update(str(snapshot.central_skills_path))
        attention = sum(agent.needs_attention for agent in snapshot.agents)
        self.query_one("#summary", Static).update(
            f"{len(snapshot.agents)} 个 Agent  ·  {attention} 个需要处理"
        )
        table.focus()

    @property
    def selected_agent_id(self) -> str | None:
        if not self._agent_ids:
            return None
        row = min(self.query_one("#agents", DataTable).cursor_row, len(self._agent_ids) - 1)
        return self._agent_ids[row]

    def _selected_agent(self) -> AgentInventory | None:
        if not self.snapshot or not self.selected_agent_id:
            return None
        return self.snapshot.agent(self.selected_agent_id)

    def _status(self, agent: AgentInventory) -> str:
        if not agent.installed:
            return "○ 未发现"
        if agent.needs_attention:
            return "◆ 待处理"
        return "● 就绪"

    def action_details(self) -> None:
        if self.selected_agent_id:
            self.manager.open_agent(self.selected_agent_id)

    def on_data_table_row_selected(self, _: DataTable.RowSelected) -> None:
        self.action_details()

    def action_toggle_mode(self) -> None:
        if self.selected_agent_id:
            self.manager.toggle_mode(self.selected_agent_id)

    def action_refresh(self) -> None:
        self.query_one("#summary", Static).update("正在刷新…")
        self.manager.refresh_inventory()

    def action_open_folder(self) -> None:
        if self.selected_agent_id:
            self.manager.open_agent_folder(self.selected_agent_id)

    def action_quit(self) -> None:
        self.app.exit()
