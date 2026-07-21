"""Two-pane Skill management screen for one Agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Resize
from textual.screen import Screen
from textual.widgets import Button, Footer, Static, Tree

from agent_skills_manager.domain.models import AgentInventory, ItemStatus
from agent_skills_manager.tui.layout import DetailLayout, detail_layout
from agent_skills_manager.tui.screens.confirm import ConfirmScreen
from agent_skills_manager.tui.widgets import SkillTree

if TYPE_CHECKING:
    from agent_skills_manager.tui.app import AgentSkillsApp


class AgentDetailScreen(Screen[None]):
    BINDINGS = [
        Binding("a", "add_skill", "添加"),
        Binding("d", "remove_skill", "移除"),
        Binding("delete", "remove_skill", "移除", show=False),
        Binding("m", "toggle_mode", "切换模式"),
        Binding("r", "refresh", "刷新"),
        Binding("o", "open_folder", "打开目录"),
        Binding("escape", "back", "返回"),
        Binding("q", "quit", "退出"),
    ]

    def __init__(self, agent: AgentInventory) -> None:
        super().__init__()
        self.agent = agent
        self._busy = False
        self._layout = DetailLayout.FULL

    @property
    def manager(self) -> AgentSkillsApp:
        return cast("AgentSkillsApp", self.app)

    def compose(self) -> ComposeResult:
        with Horizontal(classes="topbar"):
            yield Static("◆  agent skills manager", classes="brand")
            yield Static(
                self.agent.definition.display_name, id="detail-context", classes="topbar-context"
            )
            yield Button("← Agents", id="back", compact=True, classes="quiet-button")
        with Vertical(id="detail-shell", classes="shell"):
            yield Static("AGENT / SKILLS", classes="eyebrow")
            yield Static(self.agent.definition.display_name, id="agent-title", classes="page-title")
            yield Static(id="agent-meta", classes="muted")
            with Horizontal(id="skill-columns"):
                with Vertical(id="current-pane", classes="skill-pane"):
                    yield Static("当前 Agent  ·  Space 多选", classes="pane-kicker")
                    yield Static(id="current-heading", classes="pane-title")
                    yield SkillTree("当前 Skills", id="current-skills")
                    yield Static(
                        "Space 选中当前项",
                        id="current-selection",
                        classes="selection-info",
                    )
                    yield Button("移除所选", id="remove-skill", compact=True, disabled=True)
                with Vertical(id="missing-pane", classes="skill-pane"):
                    yield Static("中央仓库差异  ·  Space 多选", classes="pane-kicker")
                    yield Static(id="missing-heading", classes="pane-title")
                    yield SkillTree("可添加 Skills", id="missing-skills")
                    yield Static(
                        "Space 选中当前项",
                        id="missing-selection",
                        classes="selection-info",
                    )
                    yield Button("添加所选", id="add-skill", compact=True, disabled=True)
            yield Static(id="mcp-strip")
        yield Footer()

    def on_mount(self) -> None:
        self._set_layout(detail_layout(self.size.height))
        self._render_agent()
        self.query_one("#current-skills", SkillTree).focus()

    def on_resize(self, event: Resize) -> None:
        self._set_layout(detail_layout(event.size.height))

    def _set_layout(self, layout: DetailLayout) -> None:
        changed = layout is not self._layout
        self._layout = layout
        self.set_class(layout is DetailLayout.COMPACT, "compact")
        if changed:
            self.refresh(layout=True)
        if changed and self.is_mounted:
            self._render_heading("current")
            self._render_heading("missing")
            self.query_one("#mcp-strip", Static).update(self._mcp_summary())

    def set_agent(self, agent: AgentInventory) -> None:
        self.agent = agent
        self._busy = False
        if self.is_mounted:
            self._render_agent()

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        if not busy:
            self._render_agent()
            return
        self.query_one("#add-skill", Button).disabled = busy or not self._selected_missing()
        self.query_one("#remove-skill", Button).disabled = busy or not self._selected_current()
        self.query_one("#agent-meta", Static).update("正在应用变更…")

    def _render_agent(self) -> None:
        current = [entry for entry in self.agent.skills if entry.status is not ItemStatus.MISSING]
        missing = [entry for entry in self.agent.skills if entry.status is ItemStatus.MISSING]
        self.query_one("#agent-title", Static).update(self.agent.definition.display_name)
        self.query_one("#detail-context", Static).update(str(self.agent.skills_path))
        self.query_one("#agent-meta", Static).update(
            f"{self._status()}  ·  {self.agent.preference.skills_mode.value} 模式"
            f"  ·  {len(current)} 已有  ·  {len(missing)} 待添加"
        )
        self.query_one("#current-skills", SkillTree).load_entries(
            current, "这个 Agent 还没有 Skill"
        )
        self.query_one("#missing-skills", SkillTree).load_entries(missing, "已经与中央仓库一致")
        self._render_selection("current")
        self._render_selection("missing")
        self.query_one("#mcp-strip", Static).update(self._mcp_summary())

    def _status(self) -> str:
        if not self.agent.installed:
            return "○ 未发现"
        if self.agent.needs_attention:
            return "◆ 待处理"
        return "● 就绪"

    def _mcp_summary(self) -> str:
        names = "  ·  ".join(entry.name for entry in self.agent.mcps) or "未发现 MCP"
        if self._layout is DetailLayout.COMPACT:
            return f"MCP {len(self.agent.mcps)}  ·  {names}"
        errors = f"  ·  {len(self.agent.errors)} 个错误" if self.agent.errors else ""
        return f"MCP  {names}{errors}\n配置  {self.agent.mcp_path}"

    def _selected_current(self) -> tuple[str, ...]:
        return self.query_one("#current-skills", SkillTree).selected_names

    def _selected_missing(self) -> tuple[str, ...]:
        return self.query_one("#missing-skills", SkillTree).selected_names

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        if event.control.id == "current-skills":
            self._render_selection("current")
        elif event.control.id == "missing-skills":
            self._render_selection("missing")

    def on_skill_tree_selection_changed(self, event: SkillTree.SelectionChanged) -> None:
        pane = "current" if event.control.id == "current-skills" else "missing"
        self._render_selection(pane)

    def _render_selection(self, pane: str) -> None:
        tree = self.query_one(f"#{pane}-skills", SkillTree)
        selected = tree.selected_names
        entry = tree.entry(tree.selected_skill)
        if selected:
            text = f"已选择 {len(selected)} 个  ·  Space 可取消  ·  {self._selection_preview(selected)}"
        elif entry:
            text = f"○ 未选  ·  {entry.status.value}  ·  {entry.path}"
        elif tree.highlighted_names:
            text = f"系列共 {len(tree.highlighted_names)} 个  ·  Space 全选  ·  Enter 展开"
        else:
            text = "用方向键定位，Space 选中"
        self.query_one(f"#{pane}-selection", Static).update(text)
        button_id = "#remove-skill" if pane == "current" else "#add-skill"
        button = self.query_one(button_id, Button)
        verb = "移除" if pane == "current" else "添加"
        button.label = f"{verb}所选" + (f"  ·  {len(selected)}" if selected else "")
        button.disabled = self._busy or not selected
        self._render_heading(pane)

    def _render_heading(self, pane: str) -> None:
        tree = self.query_one(f"#{pane}-skills", SkillTree)
        selected = len(tree.selected_names)
        if self._layout is DetailLayout.COMPACT:
            label = "当前 Agent" if pane == "current" else "中央缺少"
            text = f"{label}  ·  {tree.entry_count} Skills"
            if selected:
                text += f"  ·  已选 {selected}"
        else:
            text = (
                f"已有 {tree.entry_count} 个 Skills"
                if pane == "current"
                else f"中央可添加 {tree.entry_count} 个 Skills"
            )
        self.query_one(f"#{pane}-heading", Static).update(text)

    def _selection_preview(self, names: tuple[str, ...]) -> str:
        shown = "、".join(names[:3])
        return shown if len(names) <= 3 else f"{shown} 等"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.action_back()
        elif event.button.id == "add-skill":
            self.action_add_skill()
        elif event.button.id == "remove-skill":
            self.action_remove_skill()

    def action_add_skill(self) -> None:
        names = self._selected_missing()
        if not names or self._busy:
            self.notify("请先在右侧用 Space 选择 Skill", severity="warning")
            return
        self.app.push_screen(
            ConfirmScreen(
                f"添加 {len(names)} 个 Skills",
                f"将 {self._selection_preview(names)} 以 "
                f"{self.agent.preference.skills_mode.value} 模式添加到 "
                f"{self.agent.definition.display_name}。",
                f"确认添加 {len(names)} 个",
            ),
            lambda confirmed: self._confirmed_add(names, confirmed),
        )

    def _confirmed_add(self, names: tuple[str, ...], confirmed: bool | None) -> None:
        if confirmed:
            self.set_busy(True)
            self.manager.add_skills(self.agent.definition.id, names)

    def action_remove_skill(self) -> None:
        names = self._selected_current()
        if not names or self._busy:
            self.notify("请先在左侧用 Space 选择 Skill", severity="warning")
            return
        self.app.push_screen(
            ConfirmScreen(
                f"移除 {len(names)} 个 Skills",
                f"从 {self.agent.definition.display_name} 移除 "
                f"{self._selection_preview(names)}。"
                "文件会移入 ~/.agent/backups，可随时恢复。",
                f"确认移除 {len(names)} 个",
                destructive=True,
            ),
            lambda confirmed: self._confirmed_remove(names, confirmed),
        )

    def _confirmed_remove(self, names: tuple[str, ...], confirmed: bool | None) -> None:
        if confirmed:
            self.set_busy(True)
            self.manager.remove_skills(self.agent.definition.id, names)

    def action_toggle_mode(self) -> None:
        self.manager.toggle_mode(self.agent.definition.id)

    def action_refresh(self) -> None:
        self.set_busy(True)
        self.manager.refresh_inventory()

    def action_open_folder(self) -> None:
        self.manager.open_agent_folder(self.agent.definition.id)

    def action_back(self) -> None:
        if not self._busy:
            self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()
