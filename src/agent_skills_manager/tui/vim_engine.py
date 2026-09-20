"""Vim state machine and key interpretation logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_skills_manager.tui.constants import VimMode


@dataclass
class VimResult:
    """Outcome of processing a key press."""

    action: str
    param: Any = None
    handled: bool = True


class VimEngine:
    """Decoupled Vim state machine for handling modal editing logic."""

    def __init__(self) -> None:
        self.mode = VimMode.NORMAL
        self.pending_key: str = ""
        self.register: str = ""
        self.command_buffer: str = ""
        self.status_message: str = ""

    def set_mode(self, mode: VimMode) -> None:
        self.mode = mode
        self.pending_key = ""
        if mode != VimMode.COMMAND:
            self.command_buffer = ""

    def handle_key(self, key: str, is_printable: bool, char: str | None = None) -> VimResult:
        """Process a key event and return the corresponding Vim action."""
        if self.mode == VimMode.INSERT:
            return self._handle_insert_mode(key)
        if self.mode == VimMode.COMMAND:
            return self._handle_command_mode(key, is_printable, char)
        return self._handle_normal_mode(key, is_printable, char)

    def _handle_insert_mode(self, key: str) -> VimResult:
        if key == "escape":
            self.set_mode(VimMode.NORMAL)
            return VimResult(action="enter_normal")
        return VimResult(action="none", handled=False)

    def _handle_command_mode(self, key: str, is_printable: bool, char: str | None) -> VimResult:
        if key == "escape":
            self.set_mode(VimMode.NORMAL)
            return VimResult(action="cancel_command")
        if key == "enter":
            cmd = self.command_buffer.strip()
            self.set_mode(VimMode.NORMAL)
            return VimResult(action="exec_command", param=cmd)
        if key == "backspace":
            if not self.command_buffer:
                self.set_mode(VimMode.NORMAL)
                return VimResult(action="cancel_command")
            self.command_buffer = self.command_buffer[:-1]
            return VimResult(action="update_command", param=self.command_buffer)
        if is_printable and char:
            self.command_buffer += char
            return VimResult(action="update_command", param=self.command_buffer)
        return VimResult(action="none", handled=True)

    def _handle_normal_mode(self, key: str, is_printable: bool, char: str | None) -> VimResult:
        effective_char = char or (key if len(key) == 1 else "")

        # Handle pending multi-key sequence (gg, dd, yy)
        if self.pending_key:
            first_key = self.pending_key
            self.pending_key = ""
            if first_key == "g" and effective_char == "g":
                return VimResult(action="move_doc_start")
            if first_key == "d" and effective_char == "d":
                return VimResult(action="delete_line")
            if first_key == "y" and effective_char == "y":
                return VimResult(action="yank_line")
            # Unrecognized sequence, continue as single key
            return VimResult(action="none", handled=True)

        # Single key mappings in normal mode
        if key == "escape":
            self.pending_key = ""
            return VimResult(action="none", handled=True)

        if effective_char in ("g", "d", "y"):
            self.pending_key = effective_char
            return VimResult(action="pending_key", param=effective_char)

        actions: dict[str, VimResult] = {
            # Navigation
            "h": VimResult(action="move_left"),
            "j": VimResult(action="move_down"),
            "k": VimResult(action="move_up"),
            "l": VimResult(action="move_right"),
            "w": VimResult(action="move_word_right"),
            "b": VimResult(action="move_word_left"),
            "0": VimResult(action="move_line_start"),
            "^": VimResult(action="move_line_start"),
            "$": VimResult(action="move_line_end"),
            "G": VimResult(action="move_doc_end"),
            # Mode transitions to Insert
            "i": VimResult(action="enter_insert"),
            "a": VimResult(action="enter_insert_append"),
            "I": VimResult(action="enter_insert_line_start"),
            "A": VimResult(action="enter_insert_line_end"),
            "o": VimResult(action="enter_insert_open_below"),
            "O": VimResult(action="enter_insert_open_above"),
            # Mode transitions to Command
            ":": VimResult(action="enter_command"),
            # Edit actions
            "x": VimResult(action="delete_char"),
            "p": VimResult(action="paste_below"),
            "P": VimResult(action="paste_above"),
            "u": VimResult(action="undo"),
            "ctrl+r": VimResult(action="redo"),
        }

        # Check full key combination first (e.g. ctrl+r)
        if key in actions:
            res = actions[key]
            self._apply_state_change(res)
            return res

        # Check character
        if effective_char in actions:
            res = actions[effective_char]
            self._apply_state_change(res)
            return res

        # Consume other printable keys in normal mode to prevent unintended editing
        if is_printable or len(key) == 1:
            return VimResult(action="none", handled=True)

        return VimResult(action="none", handled=False)

    def _apply_state_change(self, result: VimResult) -> None:
        if result.action.startswith("enter_insert"):
            self.set_mode(VimMode.INSERT)
        elif result.action == "enter_command":
            self.set_mode(VimMode.COMMAND)
            self.command_buffer = ""
