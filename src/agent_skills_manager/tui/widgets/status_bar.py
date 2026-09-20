"""Status bar widget with mode badge, file status, cursor position, and command input."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Static

from agent_skills_manager.tui.constants import (
    ID_CMD_INPUT,
    ID_CURSOR_INFO,
    ID_MODE_BADGE,
    ID_STATUS_BAR,
    ID_STATUS_INFO,
    LABEL_MODIFIED,
    VimMode,
)


class EditorStatusBar(Horizontal):
    """Bottom status bar with normal status info and togglable command input."""

    DEFAULT_CSS = """
    EditorStatusBar {
        height: 1;
        background: #211f1c;
        padding: 0 1;
        align-vertical: middle;
    }
    #status-normal-container {
        width: 1fr;
        height: 1;
        align-vertical: middle;
    }
    .status-left {
        width: auto;
        color: #e69370;
        text-style: bold;
    }
    .status-center {
        width: 1fr;
        color: #9f988e;
        content-align: center middle;
    }
    .status-right {
        width: auto;
        color: #9f988e;
        content-align: right middle;
    }
    #editor-cmd-input {
        width: 1fr;
        height: 1;
        border: none;
        background: #1c1a17;
        color: #f1e8dc;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(id=ID_STATUS_BAR, **kwargs)

    def compose(self) -> ComposeResult:
        with Horizontal(id="status-normal-container"):
            yield Static("-- NORMAL --", id=ID_MODE_BADGE, classes="status-left")
            yield Static("", id=ID_STATUS_INFO, classes="status-center")
            yield Static("Ln 1, Col 1", id=ID_CURSOR_INFO, classes="status-right")
        cmd_input = Input(id=ID_CMD_INPUT, placeholder="输入命令: :w(保存) :q(退出) :q!(强制退出)")
        cmd_input.display = False
        yield cmd_input

    def update_status(
        self,
        mode: VimMode,
        cursor: tuple[int, int],
        is_dirty: bool,
    ) -> None:
        badge = self.query_one(f"#{ID_MODE_BADGE}", Static)
        info_widget = self.query_one(f"#{ID_STATUS_INFO}", Static)
        cursor_widget = self.query_one(f"#{ID_CURSOR_INFO}", Static)

        badge.update(f"-- {mode.value} --")
        dirty_str = f" {LABEL_MODIFIED}" if is_dirty else ""
        info_widget.update(dirty_str)
        cursor_widget.update(f"Ln {cursor[0] + 1}, Col {cursor[1] + 1}")

    def open_command_input(self) -> None:
        normal = self.query_one("#status-normal-container", Horizontal)
        cmd_input = self.query_one(f"#{ID_CMD_INPUT}", Input)
        normal.display = False
        cmd_input.display = True
        cmd_input.value = ":"
        cmd_input.cursor_position = 1
        cmd_input.focus()

    def close_command_input(self) -> None:
        normal = self.query_one("#status-normal-container", Horizontal)
        cmd_input = self.query_one(f"#{ID_CMD_INPUT}", Input)
        cmd_input.display = False
        normal.display = True
