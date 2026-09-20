"""Modal screen for viewing and editing prompt instruction files."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static, TextArea

from agent_skills_manager.tui.constants import (
    CMD_FORCE_QUIT,
    CMD_QUIT,
    CMD_WRITE,
    CMD_WRITE_QUIT,
    CMD_WRITE_QUIT_ALT,
    ID_CLOSE_BUTTON,
    ID_MODE_BUTTON,
    ID_SAVE_BUTTON,
    ID_VIM_TEXT_AREA,
    MSG_SAVE_FAILED,
    MSG_SAVE_SUCCESS,
    MSG_UNKNOWN_COMMAND,
    MSG_UNSAVED_WARNING,
    VimMode,
)
from agent_skills_manager.tui.screens.prompts import PromptViewScreen
from agent_skills_manager.tui.widgets.vim_editor import EditorStatusBar, VimTextArea

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
                    compact=True,
                    classes="quiet-button",
                )
                yield Button(
                    "保存 (:w)",
                    id=ID_SAVE_BUTTON,
                    compact=True,
                    classes="primary-action quiet-button",
                )
                yield Button(
                    "关闭 (:q)",
                    id=ID_CLOSE_BUTTON,
                    compact=True,
                    classes="quiet-button",
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
            cmd_text=editor.command_text,
            message=editor.status_message,
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == ID_MODE_BUTTON:
            editor = self.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)
            editor.toggle_mode()
        elif event.button.id == ID_SAVE_BUTTON:
            self.action_save()
        elif event.button.id == ID_CLOSE_BUTTON:
            self.action_close(force=False)

    def on_vim_text_area_mode_changed(self, event: VimTextArea.ModeChanged) -> None:
        btn = self.query_one(f"#{ID_MODE_BUTTON}", Button)
        btn.label = f"模式: {event.mode.value}"
        self._refresh_status()

    def on_vim_text_area_save_requested(self, event: VimTextArea.SaveRequested) -> None:
        self.action_save()

    def on_vim_text_area_command_executed(self, event: VimTextArea.CommandExecuted) -> None:
        cmd = event.command
        if cmd == CMD_WRITE:
            self.action_save()
        elif cmd == CMD_QUIT:
            self.action_close(force=False)
        elif cmd in (CMD_WRITE_QUIT, CMD_WRITE_QUIT_ALT):
            self.action_save_and_quit()
        elif cmd == CMD_FORCE_QUIT:
            self.dismiss(None)
        else:
            self.notify(MSG_UNKNOWN_COMMAND.format(cmd=cmd), severity="warning")
            self._refresh_status()

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

    def action_close(self, force: bool = False) -> None:
        editor = self.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)
        if not force and editor.is_dirty:
            self.notify(MSG_UNSAVED_WARNING, severity="warning")
            return
        self.dismiss(None)

    def action_handle_escape(self) -> None:
        editor = self.query_one(f"#{ID_VIM_TEXT_AREA}", VimTextArea)
        if editor.mode != VimMode.NORMAL:
            editor.set_mode(VimMode.NORMAL)
        else:
            self.action_close(force=False)
