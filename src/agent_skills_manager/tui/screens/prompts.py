"""Cross-agent management screen for user-level instruction files."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, DataTable, Footer, Static, TextArea

from agent_skills_manager.domain.models import PromptInventory, PromptTarget

if TYPE_CHECKING:
    from agent_skills_manager.tui.app import AgentSkillsApp

# Matches the disabled-control colour in theme.tcss.
ABSENT_STYLE = "#69635c"


class PromptsScreen(Screen[None]):
    BINDINGS = [
        Binding("s", "sync_all", "同步全部"),
        Binding("t", "sync_one", "同步此项"),
        Binding("c", "capture", "采集为标准"),
        Binding("v", "view_host", "查看/编辑"),
        Binding("b", "view_canonical", "编辑标准"),
        Binding("r", "refresh", "刷新"),
        Binding("escape", "back", "返回"),
        Binding("q", "quit", "退出"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.inventory: PromptInventory | None = None
        self._agent_ids: list[str] = []
        self._columns_ready = False

    @property
    def manager(self) -> AgentSkillsApp:
        return cast("AgentSkillsApp", self.app)

    def compose(self) -> ComposeResult:
        with Horizontal(classes="topbar"):
            yield Static("◆  agent skills manager", classes="brand")
            yield Static("prompts", id="prompts-context", classes="topbar-context")
            yield Button("← Agents", id="back", compact=True, classes="quiet-button")
        with Vertical(id="prompts-shell", classes="shell"):
            yield Static("PROMPTS", classes="eyebrow")
            yield Static("用户级系统提示词", classes="page-title")
            yield Static("正在读取各 Agent 的指令文件…", id="prompts-summary", classes="muted")
            yield DataTable(id="prompts", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#prompts", DataTable)
        table.add_columns("Agent", "指令文件", "状态")
        self._columns_ready = True
        if self.inventory:
            self.set_inventory(self.inventory)
        table.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.action_back()

    def set_inventory(self, inventory: PromptInventory | None) -> None:
        previous = self.selected_agent_id
        self.inventory = inventory
        if not self._columns_ready:
            return
        table = self.query_one("#prompts", DataTable)
        table.clear()
        self._agent_ids = []
        if inventory is None:
            return
        for target in inventory.targets:
            self._agent_ids.append(target.agent_id)
            cells = [
                target.display_name,
                str(target.path),
                self._status(inventory, target),
            ]
            if not inventory.source_present:
                cells = [Text(cell, style=ABSENT_STYLE) for cell in cells]
            table.add_row(*cells, key=target.agent_id)
        if previous in self._agent_ids:
            table.move_cursor(row=self._agent_ids.index(previous))
        state = "已创建" if inventory.source_present else "未创建"
        differing = sum(target.needs_attention for target in inventory.targets)
        self.query_one("#prompts-summary", Static).update(
            f"标准文件  {inventory.source}（{state}）  ·  {differing} 个待同步"
        )
        table.focus()

    @property
    def selected_agent_id(self) -> str | None:
        if not self._agent_ids:
            return None
        row = min(self.query_one("#prompts", DataTable).cursor_row, len(self._agent_ids) - 1)
        return self._agent_ids[row]

    def _selected_target(self) -> PromptTarget | None:
        if not self.inventory or not self.selected_agent_id:
            return None
        return next(
            (
                target
                for target in self.inventory.targets
                if target.agent_id == self.selected_agent_id
            ),
            None,
        )

    @staticmethod
    def _status(inventory: PromptInventory, target: PromptTarget) -> str:
        if not inventory.source_present:
            return "○ 无标准文件"
        if not target.present:
            return "○ 未创建"
        if target.matches:
            return "● 一致"
        return "◆ 待同步"

    def action_sync_all(self) -> None:
        self.manager.sync_prompts_flow()

    def action_sync_one(self) -> None:
        target = self._selected_target()
        if not target:
            self.notify("请先选择一个 Agent", severity="warning")
            return
        self.manager.sync_prompts_flow({target.agent_id})

    def action_capture(self) -> None:
        target = self._selected_target()
        if not target:
            self.notify("请先选择一个 Agent", severity="warning")
            return
        self.manager.capture_prompt_flow(target)

    def action_view_host(self) -> None:
        target = self._selected_target()
        if not target:
            self.notify("请先选择一个 Agent", severity="warning")
            return
        self.manager.open_prompt_viewer(target)

    def action_view_canonical(self) -> None:
        self.manager.open_canonical_viewer()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.action_view_host()

    def action_refresh(self) -> None:
        self.query_one("#prompts-summary", Static).update("正在刷新…")
        self.manager.refresh_prompts()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()


class PromptViewScreen(ModalScreen[None]):
    """Read-only viewer for one instruction file."""

    BINDINGS = [Binding("escape", "close", "返回")]

    def __init__(self, title: str, content: str) -> None:
        super().__init__()
        self.view_title = title
        self.view_content = content

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-view"):
            yield Static(self.view_title, id="prompt-view-title")
            yield TextArea(
                self.view_content,
                id="prompt-view-text",
                read_only=True,
                soft_wrap=True,
            )

    def on_mount(self) -> None:
        self.query_one("#prompt-view-text", TextArea).focus()

    def action_close(self) -> None:
        self.dismiss(None)
