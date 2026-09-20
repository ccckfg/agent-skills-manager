"""Fast, interactive Agent Skills inventory browser."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import Any
from webbrowser import open as open_uri

from textual import work
from textual.app import App

from agent_skills_manager.domain.models import (
    AgentInventory,
    InventorySnapshot,
    PromptInventory,
    PromptPlan,
    PromptTarget,
    SyncMode,
)
from agent_skills_manager.tui.screens import (
    AgentDetailScreen,
    DashboardScreen,
    PromptEditorScreen,
    PromptsScreen,
)
from agent_skills_manager.tui.screens.confirm import ConfirmScreen

SnapshotLoader = Callable[[], InventorySnapshot]
SyncHandler = Callable[[AgentInventory], Any]
SkillHandler = Callable[[AgentInventory, tuple[str, ...]], Any]
ModeChangeHandler = Callable[[AgentInventory, SyncMode], Any]
PromptsLoader = Callable[[], PromptInventory]
PromptsPlanner = Callable[[set[str] | None], PromptPlan]
PromptsCaptureHandler = Callable[[str], Any]
PromptsSyncHandler = Callable[[PromptPlan], Any]
PromptsReader = Callable[[Path], str]
PromptsWriter = Callable[[Path, str], None]


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
        import_handler: SkillHandler | None = None,
        prompts_loader: PromptsLoader | None = None,
        prompts_planner: PromptsPlanner | None = None,
        prompts_capture_handler: PromptsCaptureHandler | None = None,
        prompts_sync_handler: PromptsSyncHandler | None = None,
        prompts_reader: PromptsReader | None = None,
        prompts_writer: PromptsWriter | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.snapshot_loader = snapshot_loader or _default_snapshot_loader
        self.sync_handler = sync_handler
        self.mode_change_handler = mode_change_handler
        self.add_handler = add_handler
        self.remove_handler = remove_handler
        self.import_handler = import_handler
        self.prompts_loader = prompts_loader
        self.prompts_planner = prompts_planner
        self.prompts_capture_handler = prompts_capture_handler
        self.prompts_sync_handler = prompts_sync_handler
        self.prompts_reader = prompts_reader
        self.prompts_writer = prompts_writer
        self.snapshot: InventorySnapshot | None = None
        self.prompts_inventory: PromptInventory | None = None
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

    def open_prompts(self) -> None:
        self.push_screen(PromptsScreen())
        self.refresh_prompts()

    def open_prompt_viewer(self, target: PromptTarget) -> None:
        """Open an editor/viewer for one host's instruction file."""
        self._open_prompt_viewer(target.display_name, target.path, target.present)

    def open_canonical_viewer(self) -> None:
        inventory = self.prompts_inventory
        if inventory is None:
            self.notify("提示词清单尚未就绪", severity="warning")
            return
        self._open_prompt_viewer("标准文件", inventory.source, inventory.source_present)

    def save_prompt(self, path: Path, content: str) -> None:
        """Save prompt file and refresh prompt inventory."""
        if self.prompts_writer:
            self.prompts_writer(path, content)
        else:
            from agent_skills_manager.infrastructure.prompt_store import PromptStore

            PromptStore().write(path, content)
        self.refresh_prompts()

    def _open_prompt_viewer(self, label: str, path: Path, exists: bool) -> None:
        if not self.prompts_reader:
            self.notify("没有可用的提示词读取处理器", severity="error")
            return
        if exists:
            try:
                content = self.prompts_reader(path)
            except Exception as exc:
                self.notify(f"无法读取 {path}：{exc}", severity="error")
                return
            if not content:
                content = "（文件是空的）"
        else:
            content = "（该文件还不存在）"
        self.push_screen(
            PromptEditorScreen(
                f"{label} · {path}",
                content,
                path=path,
                save_handler=self.save_prompt,
            )
        )

    @work(thread=True, exclusive=True, group="prompts", exit_on_error=False)
    def refresh_prompts(self, announce: bool = False) -> None:
        """Scan prompt files in the background; prompt files are small, always compare."""
        if not self.prompts_loader:
            return
        try:
            inventory = self.prompts_loader()
        except Exception as exc:
            self.call_from_thread(self._operation_failed, f"无法读取提示词清单：{exc}")
            return
        self.call_from_thread(self._apply_prompts, inventory, announce)

    def _apply_prompts(self, inventory: PromptInventory, announce: bool = False) -> None:
        self.prompts_inventory = inventory
        if isinstance(self.screen, PromptsScreen):
            self.screen.set_inventory(inventory)
        if announce:
            self.notify("提示词清单已刷新")

    def sync_prompts_flow(self, selected: set[str] | None = None) -> None:
        """Plan in the foreground, confirm, then let the worker apply the plan.

        `selected` narrows the plan to a single host's prompt file.
        """
        if not self.prompts_planner or not self.prompts_sync_handler:
            self.notify("没有可用的提示词同步处理器", severity="error")
            return
        try:
            plan = self.prompts_planner(selected)
        except Exception as exc:
            self.notify(f"无法生成同步计划：{exc}", severity="error")
            return
        for warning in plan.warnings:
            self.notify(warning, severity="warning")
        if not plan.has_changes:
            if not plan.warnings:
                scope = "选中主机已与标准一致" if selected else "所有提示词文件均已一致"
                self.notify(scope)
            return
        listing = self._destination_preview(plan)
        scope_note = "只把标准内容写入选中主机的" if selected else "将把标准内容写入"
        self.push_screen(
            ConfirmScreen(
                f"同步 {len(plan.actions)} 个提示词文件",
                f"{scope_note} {listing}。被替换的文件会先备份到 ~/.agentskillsbank/backups/<agent>/。",
                f"确认同步 {len(plan.actions)} 个",
            ),
            lambda confirmed: self.sync_prompts(plan) if confirmed else None,
        )

    @staticmethod
    def _destination_preview(plan: PromptPlan) -> str:
        shown = [action.destination.name for action in plan.actions[:3]]
        listing = "、".join(shown)
        if len(plan.actions) > len(shown):
            listing += f" 等 {len(plan.actions)} 个文件"
        return listing

    @work(thread=True, exclusive=True, group="mutation", exit_on_error=False)
    def sync_prompts(self, plan: PromptPlan) -> None:
        if not self.prompts_sync_handler:
            self.call_from_thread(self._operation_failed, "没有可用的提示词同步处理器")
            return
        try:
            self.prompts_sync_handler(plan)
            inventory = self.prompts_loader()
        except Exception as exc:
            self.call_from_thread(self._operation_failed, str(exc))
            return
        self.call_from_thread(
            self._prompts_done, inventory, f"已同步 {len(plan.actions)} 个提示词文件"
        )

    def capture_prompt_flow(self, target: PromptTarget) -> None:
        if not self.prompts_capture_handler:
            self.notify("没有可用的采集处理器", severity="error")
            return
        if not target.present:
            self.notify(f"{target.display_name} 没有可采集的指令文件", severity="warning")
            return
        self.push_screen(
            ConfirmScreen(
                "采集标准提示词",
                f"用 {target.display_name} 的指令文件内容初始化标准文件。"
                "已有的标准文件会先备份到 ~/.agentskillsbank/backups/prompts/。",
                "确认采集",
            ),
            lambda confirmed: self.capture_prompt(target.agent_id) if confirmed else None,
        )

    @work(thread=True, exclusive=True, group="mutation", exit_on_error=False)
    def capture_prompt(self, agent_id: str) -> None:
        if not self.prompts_capture_handler:
            self.call_from_thread(self._operation_failed, "没有可用的采集处理器")
            return
        try:
            self.prompts_capture_handler(agent_id)
            inventory = self.prompts_loader()
        except Exception as exc:
            self.call_from_thread(self._operation_failed, str(exc))
            return
        self.call_from_thread(self._prompts_done, inventory, "标准提示词已更新")

    def _prompts_done(self, inventory: PromptInventory, message: str) -> None:
        self._apply_prompts(inventory)
        self.notify(message)

    @work(thread=True, exclusive=True, group="mutation", exit_on_error=False)
    def add_skills(self, agent_id: str, skill_names: tuple[str, ...]) -> None:
        self._run_skill_operation("添加", self.add_handler, agent_id, skill_names)

    @work(thread=True, exclusive=True, group="mutation", exit_on_error=False)
    def remove_skills(self, agent_id: str, skill_names: tuple[str, ...]) -> None:
        self._run_skill_operation("移除", self.remove_handler, agent_id, skill_names)

    @work(thread=True, exclusive=True, group="mutation", exit_on_error=False)
    def import_skills(self, agent_id: str, skill_names: tuple[str, ...]) -> None:
        self._run_skill_operation("导入", self.import_handler, agent_id, skill_names)

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
    import_handler: SkillHandler | None = None,
    prompts_loader: PromptsLoader | None = None,
    prompts_planner: PromptsPlanner | None = None,
    prompts_capture_handler: PromptsCaptureHandler | None = None,
    prompts_sync_handler: PromptsSyncHandler | None = None,
    prompts_reader: PromptsReader | None = None,
    prompts_writer: PromptsWriter | None = None,
) -> None:
    """Launch the interactive application."""
    AgentSkillsApp(
        snapshot_loader,
        sync_handler,
        mode_change_handler,
        add_handler,
        remove_handler,
        import_handler,
        prompts_loader,
        prompts_planner,
        prompts_capture_handler,
        prompts_sync_handler,
        prompts_reader,
        prompts_writer,
    ).run()
