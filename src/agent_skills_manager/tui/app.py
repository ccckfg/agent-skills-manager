"""Interactive inventory browser built with Textual."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any
from webbrowser import open as open_uri

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import DataTable, Footer, Header, Static

from agent_skills_manager.domain.models import (
    AgentInventory,
    InventorySnapshot,
    SyncMode,
)

SnapshotLoader = Callable[[], InventorySnapshot]
SyncHandler = Callable[[AgentInventory], Any]
ModeChangeHandler = Callable[[AgentInventory, SyncMode], Any]


def _default_snapshot_loader() -> InventorySnapshot:
    """Resolve the core loader lazily so this package stays UI-only."""
    module = import_module("agent_skills_manager.services.inventory")
    loader = getattr(module, "load_inventory")
    return loader()


class AgentSkillsApp(App[None]):
    """Browse local agent skills and MCP configurations."""

    CSS = """
    Screen { background: #111827; color: #e5e7eb; }
    Header { background: #182235; color: #f8fafc; }
    Footer { background: #182235; color: #cbd5e1; }
    #content { height: 1fr; padding: 1 2; }
    #summary { color: #94a3b8; margin-bottom: 1; }
    DataTable { height: 1fr; background: #172033; }
    DataTable > .datatable--header { background: #22304a; color: #93c5fd; }
    #detail { height: 1fr; background: #172033; border: round #334155; padding: 1 2; overflow: auto; }
    .hidden { display: none; }
    """

    BINDINGS = [
        ("enter", "details", "Details"),
        ("s", "sync", "Sync"),
        ("m", "toggle_mode", "Mode"),
        ("r", "refresh", "Refresh"),
        ("o", "open_folder", "Open"),
        ("escape", "back", "Back"),
        ("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        snapshot_loader: SnapshotLoader | None = None,
        sync_handler: SyncHandler | None = None,
        mode_change_handler: ModeChangeHandler | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.snapshot_loader = snapshot_loader or _default_snapshot_loader
        self.sync_handler = sync_handler
        self.mode_change_handler = mode_change_handler
        self.snapshot: InventorySnapshot | None = None
        self._agent_ids: list[str] = []
        self._showing_details = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="content"):
            yield Static("Loading inventory…", id="summary")
            yield DataTable(id="agents", cursor_type="row")
            yield Static(id="detail", classes="hidden")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#agents", DataTable)
        table.add_columns("Agent", "Mode", "Skills", "MCPs", "Status")
        self.action_refresh()

    def _selected_agent(self) -> AgentInventory | None:
        if not self.snapshot or not self._agent_ids:
            return None
        row = min(self.query_one("#agents", DataTable).cursor_row, len(self._agent_ids) - 1)
        return self.snapshot.agent(self._agent_ids[row])

    def _status(self, agent: AgentInventory) -> str:
        if not agent.installed:
            return "Not installed"
        if agent.needs_attention:
            return "Needs attention"
        return "Ready"

    def _render_table(self) -> None:
        assert self.snapshot is not None
        table = self.query_one("#agents", DataTable)
        table.clear()
        self._agent_ids = []
        for agent in self.snapshot.agents:
            self._agent_ids.append(agent.definition.id)
            table.add_row(
                agent.definition.display_name,
                agent.preference.skills_mode.value.title(),
                str(len(agent.skills)),
                str(len(agent.mcps)),
                self._status(agent),
            )
        self.query_one("#summary", Static).update(
            f"{len(self.snapshot.agents)} agents · central skills: {self.snapshot.central_skills_path}"
        )

    def _render_detail(self, agent: AgentInventory) -> None:
        skills = (
            "\n".join(
                f"  • {entry.name} — {entry.status.value}{' (link)' if entry.is_link else ''}"
                for entry in agent.skills
            )
            or "  None"
        )
        mcps = (
            "\n".join(f"  • {entry.name} — {entry.config_path}" for entry in agent.mcps) or "  None"
        )
        errors = "\n".join(f"  • {message}" for message in agent.errors) or "  None"
        self.query_one("#detail", Static).update(
            f"[b]{agent.definition.display_name}[/b]\n"
            f"Status: {self._status(agent)}\nMode: {agent.preference.skills_mode.value.title()}\n\n"
            f"[b]Skills[/b]\n{skills}\n\n[b]MCP configurations[/b]\n{mcps}\n\n[b]Errors[/b]\n{errors}"
        )

    def action_refresh(self) -> None:
        try:
            self.snapshot = self.snapshot_loader()
        except Exception as exc:  # User-facing failure keeps the app usable.
            self.notify(f"Could not load inventory: {exc}", severity="error")
            return
        self._render_table()
        if self._showing_details and (agent := self._selected_agent()):
            self._render_detail(agent)
        self.notify("Inventory refreshed")

    def action_details(self) -> None:
        agent = self._selected_agent()
        if not agent:
            return
        self._showing_details = True
        self.query_one("#agents", DataTable).add_class("hidden")
        detail = self.query_one("#detail", Static)
        detail.remove_class("hidden")
        self._render_detail(agent)

    def on_data_table_row_selected(self, _: DataTable.RowSelected) -> None:
        """Open a row when Enter is handled by the focused data table."""
        self.action_details()

    def action_back(self) -> None:
        if not self._showing_details:
            return
        self._showing_details = False
        self.query_one("#detail", Static).add_class("hidden")
        self.query_one("#agents", DataTable).remove_class("hidden")

    def action_sync(self) -> None:
        agent = self._selected_agent()
        if not agent or not self.sync_handler:
            self.notify("No sync handler is configured", severity="warning")
            return
        self.sync_handler(agent)
        self.notify(f"Sync requested for {agent.definition.display_name}")
        self.action_refresh()

    def action_toggle_mode(self) -> None:
        agent = self._selected_agent()
        if not agent:
            return
        if not agent.definition.supports_link:
            self.notify(
                f"{agent.definition.display_name} only supports Copy mode", severity="warning"
            )
            return
        mode = SyncMode.LINK if agent.preference.skills_mode is SyncMode.COPY else SyncMode.COPY
        if self.mode_change_handler:
            self.mode_change_handler(agent, mode)
        agent.preference.skills_mode = mode
        self._render_table()
        if self._showing_details:
            self._render_detail(agent)
        self.notify(f"Mode set to {mode.value.title()}")

    def action_open_folder(self) -> None:
        agent = self._selected_agent()
        if not agent:
            return
        open_uri(agent.skills_path.resolve().as_uri())
        self.notify(f"Opened {agent.skills_path}")


def run_tui(
    snapshot_loader: SnapshotLoader | None = None,
    sync_handler: SyncHandler | None = None,
    mode_change_handler: ModeChangeHandler | None = None,
) -> None:
    """Launch the interactive application."""
    AgentSkillsApp(snapshot_loader, sync_handler, mode_change_handler).run()
