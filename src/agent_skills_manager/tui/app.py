"""Fast, interactive Agent Skills inventory browser."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any
from webbrowser import open as open_uri

from textual import work
from textual.app import App

from agent_skills_manager.domain.models import AgentInventory, InventorySnapshot, SyncMode
from agent_skills_manager.tui.screens import AgentDetailScreen, DashboardScreen

SnapshotLoader = Callable[[], InventorySnapshot]
SyncHandler = Callable[[AgentInventory], Any]
SkillHandler = Callable[[AgentInventory, tuple[str, ...]], Any]
ModeChangeHandler = Callable[[AgentInventory, SyncMode], Any]


def _default_snapshot_loader() -> InventorySnapshot:
    """Resolve the inventory lazily and use the TUI's fast presence scan."""
    module = import_module("agent_skills_manager.services.inventory")
    loader = getattr(module, "load_inventory")
    return loader(verify_contents=False)


class AgentSkillsApp(App[None]):
    """Browse and manage local Agent Skills without blocking first paint."""

    CSS_PATH = "theme.tcss"
    TITLE = "Agent Skills Manager"
    ENABLE_COMMAND_PALETTE = False

    def __init__(
        self,
        snapshot_loader: SnapshotLoader | None = None,
        sync_handler: SyncHandler | None = None,
        mode_change_handler: ModeChangeHandler | None = None,
        add_handler: SkillHandler | None = None,
        remove_handler: SkillHandler | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.snapshot_loader = snapshot_loader or _default_snapshot_loader
        self.sync_handler = sync_handler
        self.mode_change_handler = mode_change_handler
        self.add_handler = add_handler
        self.remove_handler = remove_handler
        self.snapshot: InventorySnapshot | None = None
        self.dashboard = DashboardScreen()

    def get_default_screen(self) -> DashboardScreen:
        return self.dashboard

    def on_mount(self) -> None:
        self.refresh_inventory(announce=False)

    @work(thread=True, exclusive=True, group="inventory", exit_on_error=False)
    def refresh_inventory(self, announce: bool = True) -> None:
        try:
            snapshot = self.snapshot_loader()
        except Exception as exc:
            self.call_from_thread(self._inventory_failed, str(exc))
            return
        self.call_from_thread(self._apply_snapshot, snapshot, announce)

    def _apply_snapshot(self, snapshot: InventorySnapshot, announce: bool = False) -> None:
        self.snapshot = snapshot
        if self.dashboard.is_mounted:
            self.dashboard.set_snapshot(snapshot)
        if isinstance(self.screen, AgentDetailScreen):
            agent = snapshot.agent(self.screen.agent.definition.id)
            if agent:
                self.screen.set_agent(agent)
        if announce:
            self.notify("清单已刷新")

    def _inventory_failed(self, message: str) -> None:
        if self.dashboard.is_mounted:
            self.dashboard.query_one("#summary").update(f"读取失败：{message}")
        if isinstance(self.screen, AgentDetailScreen):
            self.screen.set_busy(False)
        self.notify(f"无法读取清单：{message}", severity="error")

    def _agent(self, agent_id: str) -> AgentInventory | None:
        return self.snapshot.agent(agent_id) if self.snapshot else None

    def open_agent(self, agent_id: str) -> None:
        agent = self._agent(agent_id)
        if agent:
            self.push_screen(AgentDetailScreen(agent))

    def toggle_mode(self, agent_id: str) -> None:
        agent = self._agent(agent_id)
        if not agent:
            return
        if not agent.definition.supports_link:
            self.notify(f"{agent.definition.display_name} 仅支持 copy 模式", severity="warning")
            return
        mode = SyncMode.LINK if agent.preference.skills_mode is SyncMode.COPY else SyncMode.COPY
        try:
            if self.mode_change_handler:
                self.mode_change_handler(agent, mode)
        except Exception as exc:
            self.notify(f"无法切换模式：{exc}", severity="error")
            return
        agent.preference.skills_mode = mode
        if self.snapshot:
            self._apply_snapshot(self.snapshot)
        self.notify(f"同步模式已切换为 {mode.value}")

    def open_agent_folder(self, agent_id: str) -> None:
        agent = self._agent(agent_id)
        if not agent:
            return
        try:
            open_uri(agent.skills_path.absolute().as_uri())
        except Exception as exc:
            self.notify(f"无法打开目录：{exc}", severity="error")
            return
        self.notify(f"已打开 {agent.skills_path}")

    @work(thread=True, exclusive=True, group="mutation", exit_on_error=False)
    def add_skills(self, agent_id: str, skill_names: tuple[str, ...]) -> None:
        self._run_skill_operation("添加", self.add_handler, agent_id, skill_names)

    @work(thread=True, exclusive=True, group="mutation", exit_on_error=False)
    def remove_skills(self, agent_id: str, skill_names: tuple[str, ...]) -> None:
        self._run_skill_operation("移除", self.remove_handler, agent_id, skill_names)

    def _run_skill_operation(
        self,
        verb: str,
        handler: SkillHandler | None,
        agent_id: str,
        skill_names: tuple[str, ...],
    ) -> None:
        agent = self._agent(agent_id)
        if not agent or not handler:
            self.call_from_thread(self._operation_failed, f"没有可用的{verb}处理器")
            return
        try:
            handler(agent, skill_names)
            snapshot = self.snapshot_loader()
        except Exception as exc:
            self.call_from_thread(self._operation_failed, str(exc))
            return
        self.call_from_thread(self._operation_complete, snapshot, verb, len(skill_names))

    def _operation_complete(
        self,
        snapshot: InventorySnapshot,
        verb: str,
        skill_count: int,
    ) -> None:
        self._apply_snapshot(snapshot)
        self.notify(f"已{verb} {skill_count} 个 Skills")

    def _operation_failed(self, message: str) -> None:
        if isinstance(self.screen, AgentDetailScreen):
            self.screen.set_busy(False)
        self.notify(f"操作失败：{message}", severity="error")


def run_tui(
    snapshot_loader: SnapshotLoader | None = None,
    sync_handler: SyncHandler | None = None,
    mode_change_handler: ModeChangeHandler | None = None,
    add_handler: SkillHandler | None = None,
    remove_handler: SkillHandler | None = None,
) -> None:
    """Launch the interactive application."""
    AgentSkillsApp(
        snapshot_loader,
        sync_handler,
        mode_change_handler,
        add_handler,
        remove_handler,
    ).run()
