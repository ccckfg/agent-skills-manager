"""Modal screen for viewing and editing prompt instruction files."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Static, TextArea

from agent_skills_manager.tui.constants import (
    CMD_FORCE_QUIT,
    CMD_QUIT,
    CMD_WRITE,
    CMD_WRITE_QUIT,
    CMD_WRITE_QUIT_ALT,
    ID_CLOSE_BUTTON,
    ID_CMD_INPUT,
    ID_FORCE_QUIT_BUTTON,
    ID_MODE_BUTTON,
    ID_SAVE_BUTTON,
    ID_VIM_TEXT_AREA,
    MSG_SAVE_FAILED,
    MSG_SAVE_SUCCESS,
    MSG_UNKNOWN_COMMAND,
    VimMode,
)
from agent_skills_manager.tui.screens.confirm import ConfirmScreen
from agent_skills_manager.tui.screens.prompts import PromptViewScreen
from agent_skills_manager.tui.widgets.status_bar import EditorStatusBar
from agent_skills_manager.tui.widgets.vim_editor import VimTextArea

SaveHandler = Callable[[Path, str], None]


class PromptEditorScreen(PromptViewScreen):
    """Editor modal with GUI controls and Vim syntax/mode support."""

    BINDINGS = [
        Binding("escape", "handle_escape", "返回/普通模式", priority=True),
        Binding("ctrl+s", "save", "保存", priority=True),
    ]

    def __init__(
        self,
        title: str,
        content: str,
        path: Path | None = None,
        save_handler: SaveHandler | None = None,
    ) -> None:
        super().__init__(title, content)
        self.path = path
        self.save_handler = save_handler

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-editor-shell"):
            with Horizontal(id="prompt-editor-header"):
                yield Static(self.view_title, id="prompt-editor-title")
                yield Button(
                    f"模式: {VimMode.NORMAL.value}",
                    id=ID_MODE_BUTTON,
                    classes="editor-btn",
                )
                yield Button(
                    "保存 (:w)",
                    id=ID_SAVE_BUTTON,
                    classes="editor-btn editor-btn-primary",
                )
                yield Button(
                    "关闭 (:q)",
                    id=ID_CLOSE_BUTTON,
                    classes="editor-btn",
                )
                yield Button(
                    "放弃退出 (:q!)",
                    id=ID_FORCE_QUIT_BUTTON,
                    classes="editor-btn editor-btn-danger",
                )
            yield VimTextArea(self.view_content)
            yield EditorStatusBar()

    def on_mount(self) -> None:
        editor = self.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)
        editor.focus()
        self._refresh_status()

    def _refresh_status(self) -> None:
        editor = self.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)
        status_bar = self.query_one(EditorStatusBar)
        status_bar.update_status(
            mode=editor.mode,
            cursor=editor.cursor_location,
            is_dirty=editor.is_dirty,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == ID_MODE_BUTTON:
            editor = self.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)
            editor.toggle_mode()
        elif event.button.id == ID_SAVE_BUTTON:
            self.action_save()
        elif event.button.id == ID_CLOSE_BUTTON:
            self.action_close(force=False)
        elif event.button.id == ID_FORCE_QUIT_BUTTON:
            self.action_force_quit()

    def on_vim_text_area_mode_changed(self, event: VimTextArea.ModeChanged) -> None:
        btn = self.query_one(f"#{ID_MODE_BUTTON}", Button)
        mode_val = event.mode.value if hasattr(event.mode, "value") else str(event.mode)
        btn.label = f"模式: {mode_val}"
        self._refresh_status()

    def on_vim_text_area_command_mode_requested(
        self, event: VimTextArea.CommandModeRequested
    ) -> None:
        editor = self.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)
        editor.set_mode(VimMode.COMMAND)
        status_bar = self.query_one(EditorStatusBar)
        status_bar.open_command_input()

    def on_vim_text_area_save_requested(self, event: VimTextArea.SaveRequested) -> None:
        self.action_save()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == ID_CMD_INPUT:
            raw_cmd = event.value.strip()
            cmd = raw_cmd[1:] if raw_cmd.startswith(":") else raw_cmd
            self._execute_ex_command(cmd)

    def _execute_ex_command(self, cmd: str) -> None:
        status_bar = self.query_one(EditorStatusBar)
        status_bar.close_command_input()
        editor = self.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)
        editor.set_mode(VimMode.NORMAL)
        editor.focus()

        if cmd == CMD_WRITE:
            self.action_save()
        elif cmd == CMD_QUIT:
            self.action_close(force=False)
        elif cmd in (CMD_WRITE_QUIT, CMD_WRITE_QUIT_ALT):
            self.action_save_and_quit()
        elif cmd == CMD_FORCE_QUIT:
            self.action_force_quit()
        else:
            self.notify(MSG_UNKNOWN_COMMAND.format(cmd=cmd), severity="warning")
            self._refresh_status()

    def on_key(self, event: events.Key) -> None:
        cmd_input = self.query_one(f"#{ID_CMD_INPUT}", Input)
        if cmd_input.has_focus and event.key == "escape":
            event.stop()
            event.prevent_default()
            status_bar = self.query_one(EditorStatusBar)
            status_bar.close_command_input()
            editor = self.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)
            editor.set_mode(VimMode.NORMAL)
            editor.focus()

    def on_text_area_selection_changed(self, event: TextArea.SelectionChanged) -> None:
        self._refresh_status()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        editor = self.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)
        editor.check_dirty()
        self._refresh_status()

    def action_save(self) -> bool:
        if not self.path or not self.save_handler:
            self.notify("没有可用的保存处理器或文件路径", severity="error")
            return False
        editor = self.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)
        try:
            self.save_handler(self.path, editor.text)
            editor.mark_clean()
            self.notify(MSG_SAVE_SUCCESS)
            self._refresh_status()
            return True
        except Exception as exc:
            self.notify(MSG_SAVE_FAILED.format(error=exc), severity="error")
            return False

    def action_save_and_quit(self) -> None:
        if self.action_save():
            self.dismiss(None)

    def action_force_quit(self) -> None:
        self.dismiss(None)

    def action_close(self, force: bool = False) -> None:
        editor = self.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)
        if not force and editor.is_dirty:
            self.app.push_screen(
                ConfirmScreen(
                    "放弃修改并退出？",
                    "当前文件包含未保存的修改。如果退出，这些修改将会丢失。",
                    "放弃并退出",
                ),
                lambda confirmed: self.dismiss(None) if confirmed else None,
            )
            return
        self.dismiss(None)

    def action_handle_escape(self) -> None:
        cmd_input = self.query_one(f"#{ID_CMD_INPUT}", Input)
        if cmd_input.has_focus:
            status_bar = self.query_one(EditorStatusBar)
            status_bar.close_command_input()
            editor = self.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)
            editor.set_mode(VimMode.NORMAL)
            editor.focus()
            return
        editor = self.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)
        if editor.mode != VimMode.NORMAL:
            editor.set_mode(VimMode.NORMAL)
        else:
            self.action_close(force=False)
