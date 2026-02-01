"""Delete confirmation modal.

Modal dialog for confirming file deletion.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class DeleteConfirmModal(ModalScreen[bool]):
    """Modal for confirming deletion of a file.

    Returns True if confirmed, False if cancelled.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm"),
    ]

    DEFAULT_CSS = """
    DeleteConfirmModal {
        align: center middle;
    }

    DeleteConfirmModal #dialog {
        width: 50;
        height: auto;
        border: thick $error;
        background: $surface;
        padding: 1 2;
    }

    DeleteConfirmModal #title {
        text-style: bold;
        color: $error;
        padding-bottom: 1;
    }

    DeleteConfirmModal #message {
        padding-bottom: 1;
    }

    DeleteConfirmModal #item-name {
        text-style: bold;
        padding-bottom: 1;
    }

    DeleteConfirmModal #warning {
        color: $warning;
        padding-bottom: 1;
    }

    DeleteConfirmModal #buttons {
        margin-top: 1;
        height: 3;
        align: center middle;
    }

    DeleteConfirmModal Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        item_name: str,
        item_type: str = "file",
    ) -> None:
        """Initialize the modal.

        Args:
            item_name: Name of the item to delete.
            item_type: Type of item (e.g., "file", "document").
        """
        super().__init__()
        self._item_name = item_name
        self._item_type = item_type

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        yield Vertical(
            Static(f"Delete {self._item_type.title()}", id="title"),
            Static(f"Are you sure you want to delete:", id="message"),
            Static(f"  {self._item_name}", id="item-name"),
            Static("This action cannot be undone.", id="warning"),
            Horizontal(
                Button("Cancel", variant="default", id="cancel"),
                Button("Delete", variant="error", id="delete"),
                id="buttons",
            ),
            id="dialog",
        )

    def on_mount(self) -> None:
        """Focus the cancel button when mounted."""
        self.query_one("#cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button pressed event.
        """
        if event.button.id == "cancel":
            self.dismiss(False)
        elif event.button.id == "delete":
            self.dismiss(True)

    def action_cancel(self) -> None:
        """Cancel and dismiss."""
        self.dismiss(False)

    def action_confirm(self) -> None:
        """Confirm and dismiss."""
        self.dismiss(True)
