"""Add content type selection modal for Docs Mode.

Modal dialog for choosing between adding a file or URL reference.
"""

from __future__ import annotations

from enum import Enum

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ContentType(Enum):
    """Type of content to add."""

    FILE = "file"
    BROWSE = "browse"
    URL = "url"


class AddContentTypeModal(ModalScreen[ContentType | None]):
    """Modal for choosing between adding a file or URL reference.

    Returns ContentType.FILE, ContentType.BROWSE, ContentType.URL, or None if cancelled.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("n", "select_file", "New File"),
        Binding("b", "select_browse", "Browse"),
        Binding("u", "select_url", "URL"),
    ]

    DEFAULT_CSS = """
    AddContentTypeModal {
        align: center middle;
    }

    AddContentTypeModal #dialog {
        width: 55;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    AddContentTypeModal #title {
        text-style: bold;
        padding-bottom: 1;
    }

    AddContentTypeModal #description {
        padding-bottom: 1;
        color: $text-muted;
    }

    AddContentTypeModal #options {
        margin-top: 1;
        height: auto;
    }

    AddContentTypeModal .option-button {
        width: 100%;
        margin-bottom: 1;
    }

    AddContentTypeModal #buttons {
        margin-top: 1;
        height: 3;
        align: center middle;
    }

    AddContentTypeModal Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        yield Vertical(
            Static("Add Documentation", id="title"),
            Static("What would you like to add?", id="description"),
            Vertical(
                Button(
                    "📄 [N] New File - Create a markdown file",
                    variant="primary",
                    id="file",
                    classes="option-button",
                ),
                Button(
                    "📁 [B] Browse - Select an existing file",
                    variant="default",
                    id="browse",
                    classes="option-button",
                ),
                Button(
                    "🔗 [U] External URL - Link to external documentation",
                    variant="default",
                    id="url",
                    classes="option-button",
                ),
                id="options",
            ),
            Horizontal(
                Button("Cancel", variant="default", id="cancel"),
                id="buttons",
            ),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button pressed event.
        """
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "file":
            self.dismiss(ContentType.FILE)
        elif event.button.id == "browse":
            self.dismiss(ContentType.BROWSE)
        elif event.button.id == "url":
            self.dismiss(ContentType.URL)

    def action_cancel(self) -> None:
        """Cancel and dismiss."""
        self.dismiss(None)

    def action_select_file(self) -> None:
        """Select file option."""
        self.dismiss(ContentType.FILE)

    def action_select_browse(self) -> None:
        """Select browse option."""
        self.dismiss(ContentType.BROWSE)

    def action_select_url(self) -> None:
        """Select URL option."""
        self.dismiss(ContentType.URL)
