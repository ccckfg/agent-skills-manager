"""Small confirmation surface for filesystem changes."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "cancel", "取消"),
        Binding("n", "cancel", "取消", show=False),
        Binding("y", "confirm", "确认", show=False),
    ]

    def __init__(
        self,
        title: str,
        message: str,
        confirm_label: str,
        *,
        destructive: bool = False,
    ) -> None:
        super().__init__()
        self.dialog_title = title
        self.message = message
        self.confirm_label = confirm_label
        self.destructive = destructive

    def compose(self) -> ComposeResult:
        with Grid(id="confirm-dialog"):
            yield Static(self.dialog_title, id="confirm-title")
            yield Static(self.message, id="confirm-message")
            yield Button("取消", id="cancel", compact=True)
            yield Button(
                self.confirm_label,
                id="confirm",
                classes="destructive" if self.destructive else "primary-action",
                compact=True,
            )

    def on_mount(self) -> None:
        self.query_one("#cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)
