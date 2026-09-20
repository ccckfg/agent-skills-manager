"""Vim-enabled text area widget and editor status bar."""

from __future__ import annotations

from typing import ClassVar

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static, TextArea

from agent_skills_manager.tui.constants import (
    ID_CMD_INPUT,
    ID_CURSOR_INFO,
    ID_MODE_BADGE,
    ID_STATUS_BAR,
    ID_STATUS_INFO,
    ID_VIM_TEXT_AREA,
    LABEL_MODIFIED,
    VimMode,
)
from agent_skills_manager.tui.vim_engine import VimEngine, VimResult


class VimTextArea(TextArea):
    """TextArea supporting both mouse GUI interaction and Vim modal editing."""

    DEFAULT_CSS = """
    VimTextArea {
        height: 1fr;
        border: round #46413b;
        background: #201f1c;
    }
    VimTextArea:focus {
        border: round #dd815f;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        *TextArea.BINDINGS,
        Binding("ctrl+s", "save_document", "保存", show=False),
    ]

    mode = reactive(VimMode.NORMAL)
    is_dirty = reactive(False)
    command_text = reactive("")
    status_message = reactive("")

    class ModeChanged(Message):
        def __init__(self, mode: VimMode) -> None:
            super().__init__()
            self.mode = mode

    class CommandExecuted(Message):
        def __init__(self, command: str) -> None:
            super().__init__()
            self.command = command

    class SaveRequested(Message):
        pass

    def __init__(self, initial_text: str = "", **kwargs) -> None:
        super().__init__(text=initial_text, id=ID_VIM_TEXT_AREA, **kwargs)
        self.vim_engine = VimEngine()
        self.initial_content = initial_text
        self.show_line_numbers = True

    def set_mode(self, mode: VimMode) -> None:
        self.mode = mode
        self.vim_engine.set_mode(mode)
        if mode == VimMode.COMMAND:
            self.command_text = ":"
        else:
            self.command_text = ""
        self.post_message(self.ModeChanged(mode))

    def toggle_mode(self) -> None:
        """Toggle between NORMAL and INSERT mode (useful for GUI button click)."""
        new_mode = VimMode.INSERT if self.mode == VimMode.NORMAL else VimMode.NORMAL
        self.set_mode(new_mode)

    def action_save_document(self) -> None:
        self.post_message(self.SaveRequested())

    def mark_clean(self) -> None:
        self.initial_content = self.text
        self.is_dirty = False

    def check_dirty(self) -> None:
        self.is_dirty = self.text != self.initial_content

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "ctrl+s":
            event.stop()
            event.prevent_default()
            self.action_save_document()
            return

        if self.mode == VimMode.COMMAND:
            event.stop()
            event.prevent_default()
            res = self.vim_engine.handle_key(event.key, event.is_printable, event.character)
            if res.action == "exec_command":
                cmd = str(res.param)
                self.set_mode(VimMode.NORMAL)
                self.post_message(self.CommandExecuted(cmd))
            elif res.action == "update_command":
                self.command_text = f":{res.param}"
            elif res.action == "cancel_command":
                self.set_mode(VimMode.NORMAL)
            return

        if self.mode == VimMode.NORMAL:
            res = self.vim_engine.handle_key(event.key, event.is_printable, event.character)
            if res.handled:
                event.stop()
                event.prevent_default()
                self._execute_vim_action(res)
                return

        # In INSERT mode:
        if self.mode == VimMode.INSERT and event.key == "escape":
            event.stop()
            event.prevent_default()
            self.set_mode(VimMode.NORMAL)
            return

        await super()._on_key(event)
        self.check_dirty()

    def _execute_vim_action(self, result: VimResult) -> None:
        act = result.action
        if act == "move_left":
            self.action_cursor_left()
        elif act == "move_right":
            self.action_cursor_right()
        elif act == "move_up":
            self.action_cursor_up()
        elif act == "move_down":
            self.action_cursor_down()
        elif act == "move_word_right":
            self.action_cursor_word_right()
        elif act == "move_word_left":
            self.action_cursor_word_left()
        elif act == "move_line_start":
            self.action_cursor_line_start()
        elif act == "move_line_end":
            self.action_cursor_line_end()
        elif act == "move_doc_start":
            self.move_cursor((0, 0))
        elif act == "move_doc_end":
            last_line = max(0, self.document.line_count - 1)
            line_len = len(self.document.get_line(last_line))
            self.move_cursor((last_line, line_len))
        elif act == "enter_insert":
            self.set_mode(VimMode.INSERT)
        elif act == "enter_insert_append":
            self.action_cursor_right()
            self.set_mode(VimMode.INSERT)
        elif act == "enter_insert_line_start":
            self.action_cursor_line_start()
            self.set_mode(VimMode.INSERT)
        elif act == "enter_insert_line_end":
            self.action_cursor_line_end()
            self.set_mode(VimMode.INSERT)
        elif act == "enter_insert_open_below":
            self.action_cursor_line_end()
            self.insert("\n", self.cursor_location)
            self.set_mode(VimMode.INSERT)
            self.check_dirty()
        elif act == "enter_insert_open_above":
            row, _ = self.cursor_location
            self.insert("\n", (row, 0))
            self.move_cursor((row, 0))
            self.set_mode(VimMode.INSERT)
            self.check_dirty()
        elif act == "enter_command":
            self.set_mode(VimMode.COMMAND)
        elif act == "delete_char":
            self.action_delete_right()
            self.check_dirty()
        elif act == "delete_line":
            row, _ = self.cursor_location
            if row < self.document.line_count:
                self.vim_engine.register = self.document.get_line(row) + "\n"
            self.action_delete_line()
            self.check_dirty()
        elif act == "yank_line":
            row, _ = self.cursor_location
            if row < self.document.line_count:
                self.vim_engine.register = self.document.get_line(row) + "\n"
                self.status_message = "已复制 1 行"
        elif act == "paste_below":
            if self.vim_engine.register:
                row, _ = self.cursor_location
                self.insert(self.vim_engine.register, (row + 1, 0))
                self.move_cursor((row + 1, 0))
                self.check_dirty()
        elif act == "paste_above":
            if self.vim_engine.register:
                row, _ = self.cursor_location
                self.insert(self.vim_engine.register, (row, 0))
                self.move_cursor((row, 0))
                self.check_dirty()
        elif act == "undo":
            self.action_undo()
            self.check_dirty()
        elif act == "redo":
            self.action_redo()
            self.check_dirty()


class EditorStatusBar(Horizontal):
    """Bottom status bar displaying mode, command input, position, and dirty status."""

    DEFAULT_CSS = """
    EditorStatusBar {
        height: 1;
        background: #211f1c;
        padding: 0 1;
        align-vertical: middle;
    }
    .status-left {
        width: auto;
        color: #e69370;
        text-style: bold;
    }
    .status-cmd {
        width: 1fr;
        color: #f1e8dc;
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
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(id=ID_STATUS_BAR, **kwargs)

    def compose(self) -> ComposeResult:
        yield Static("-- NORMAL --", id=ID_MODE_BADGE, classes="status-left")
        yield Static("", id=ID_CMD_INPUT, classes="status-cmd")
        yield Static("", id=ID_STATUS_INFO, classes="status-center")
        yield Static("Ln 1, Col 1", id=ID_CURSOR_INFO, classes="status-right")

    def update_status(
        self,
        mode: VimMode,
        cursor: tuple[int, int],
        is_dirty: bool,
        cmd_text: str = "",
        message: str = "",
    ) -> None:
        badge = self.query_one(f"#{ID_MODE_BADGE}", Static)
        cmd_widget = self.query_one(f"#{ID_CMD_INPUT}", Static)
        info_widget = self.query_one(f"#{ID_STATUS_INFO}", Static)
        cursor_widget = self.query_one(f"#{ID_CURSOR_INFO}", Static)

        if mode == VimMode.COMMAND:
            badge.update(":")
            cmd_widget.update(cmd_text[1:] if cmd_text.startswith(":") else cmd_text)
        else:
            badge.update(f"-- {mode.value} --")
            cmd_widget.update(message)

        dirty_str = f" {LABEL_MODIFIED}" if is_dirty else ""
        info_widget.update(dirty_str)
        cursor_widget.update(f"Ln {cursor[0] + 1}, Col {cursor[1] + 1}")
