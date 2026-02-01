"""Rename document modal for Docs Mode.

Modal dialog for renaming documentation files.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static


class RenameDocumentModal(ModalScreen[str | None]):
    """Modal for renaming a document.

    Returns the new filename if confirmed, or None if cancelled.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    RenameDocumentModal {
        align: center middle;
    }

    RenameDocumentModal #dialog {
        width: 50;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    RenameDocumentModal #title {
        text-style: bold;
        padding-bottom: 1;
    }

    RenameDocumentModal .field-label {
        margin-top: 1;
    }

    RenameDocumentModal Input {
        width: 100%;
        margin-bottom: 1;
    }

    RenameDocumentModal #buttons {
        margin-top: 1;
        height: 3;
        align: center middle;
    }

    RenameDocumentModal Button {
        margin: 0 1;
    }
    """

    def __init__(self, current_name: str) -> None:
        """Initialize the modal.

        Args:
            current_name: Current filename.
        """
        super().__init__()
        self._current_name = current_name

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        yield Vertical(
            Static("Rename Document", id="title"),
            Label("Current name:", classes="field-label"),
            Static(f"  {self._current_name}", id="current-name"),
            Label("New name:", classes="field-label"),
            Input(value=self._current_name, id="new-name"),
            Horizontal(
                Button("Cancel", variant="default", id="cancel"),
                Button("Rename", variant="primary", id="rename"),
                id="buttons",
            ),
            id="dialog",
        )

    def on_mount(self) -> None:
        """Focus and select the input when mounted."""
        name_input = self.query_one("#new-name", Input)
        name_input.focus()
        # Select just the filename without extension
        if "." in self._current_name:
            dot_index = self._current_name.rfind(".")
            name_input.cursor_position = 0
            name_input.selection_start = 0
            name_input.selection_end = dot_index

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button pressed event.
        """
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "rename":
            self._do_rename()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input.

        Args:
            event: The input submitted event.
        """
        if event.input.id == "new-name":
            self._do_rename()

    def _do_rename(self) -> None:
        """Validate and return the new name."""
        new_name = self.query_one("#new-name", Input).value.strip()

        if not new_name:
            self.notify("Please enter a new name", severity="warning")
            return

        if new_name == self._current_name:
            self.dismiss(None)
            return

        # Basic validation
        invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in invalid_chars:
            if char in new_name:
                self.notify(f"Filename cannot contain '{char}'", severity="error")
                return

        self.dismiss(new_name)

    def action_cancel(self) -> None:
        """Cancel and dismiss."""
        self.dismiss(None)
