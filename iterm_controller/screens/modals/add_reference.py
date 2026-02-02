"""Add external reference modal for Docs Mode.

Modal dialog for adding external URL documentation references.
"""

from __future__ import annotations

import re
import uuid

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from iterm_controller.models import DocReference


class AddReferenceModal(ModalScreen[DocReference | None]):
    """Modal for adding an external URL reference.

    Returns a DocReference if created, or None if cancelled.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    AddReferenceModal {
        align: center middle;
    }

    AddReferenceModal #dialog {
        width: 70;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    AddReferenceModal #title {
        text-style: bold;
        padding-bottom: 1;
    }

    AddReferenceModal .field-label {
        margin-top: 1;
    }

    AddReferenceModal .field-hint {
        color: $text-muted;
        text-style: italic;
    }

    AddReferenceModal Input {
        width: 100%;
        margin-bottom: 1;
    }

    AddReferenceModal #buttons {
        margin-top: 1;
        height: 3;
        align: center middle;
    }

    AddReferenceModal Button {
        margin: 0 1;
    }
    """

    # Basic URL validation pattern
    URL_PATTERN = re.compile(
        r"^https?://"  # http:// or https://
        r"[a-zA-Z0-9]"  # Must start with alphanumeric
        r"[a-zA-Z0-9\-\.]*"  # Followed by alphanumeric, dash, or dot
        r"\.[a-zA-Z]{2,}"  # TLD
        r"(/.*)?$",  # Optional path
        re.IGNORECASE,
    )

    def __init__(
        self,
        existing_reference: DocReference | None = None,
    ) -> None:
        """Initialize the modal.

        Args:
            existing_reference: Optional existing reference to edit.
        """
        super().__init__()
        self._existing = existing_reference

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        title = "Edit Reference" if self._existing else "Add External Reference"
        button_text = "Save" if self._existing else "Add"

        # Pre-fill values if editing
        url_value = self._existing.url if self._existing else ""
        title_value = self._existing.title if self._existing else ""
        category_value = self._existing.category if self._existing else ""
        notes_value = self._existing.notes if self._existing else ""

        yield Vertical(
            Static(title, id="title"),
            Label("URL:", classes="field-label"),
            Input(
                placeholder="https://example.com/docs",
                value=url_value,
                id="url",
            ),
            Label("Title:", classes="field-label"),
            Input(
                placeholder="Documentation Title",
                value=title_value,
                id="title-input",
            ),
            Static("Display name for this reference", classes="field-hint"),
            Label("Category:", classes="field-label"),
            Input(
                placeholder="API Docs, Design, etc. (optional)",
                value=category_value,
                id="category",
            ),
            Static("Used to group related references", classes="field-hint"),
            Label("Notes:", classes="field-label"),
            Input(
                placeholder="Optional notes or description",
                value=notes_value,
                id="notes",
            ),
            Horizontal(
                Button("Cancel", variant="default", id="cancel"),
                Button(button_text, variant="primary", id="add"),
                id="buttons",
            ),
            id="dialog",
        )

    def on_mount(self) -> None:
        """Focus the URL input when mounted."""
        self.query_one("#url", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button pressed event.
        """
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "add":
            self._create_reference()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input - move to next field or submit.

        Args:
            event: The input submitted event.
        """
        if event.input.id == "url":
            self.query_one("#title-input", Input).focus()
        elif event.input.id == "title-input":
            self.query_one("#category", Input).focus()
        elif event.input.id == "category":
            self.query_one("#notes", Input).focus()
        elif event.input.id == "notes":
            self._create_reference()

    def _create_reference(self) -> None:
        """Validate inputs and create the reference."""
        url = self.query_one("#url", Input).value.strip()
        title = self.query_one("#title-input", Input).value.strip()
        category = self.query_one("#category", Input).value.strip()
        notes = self.query_one("#notes", Input).value.strip()

        # Validate URL
        if not url:
            self.notify("Please enter a URL", severity="warning")
            self.query_one("#url", Input).focus()
            return

        # Auto-add https:// if missing protocol
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        if not self.URL_PATTERN.match(url):
            self.notify("Please enter a valid URL", severity="error")
            self.query_one("#url", Input).focus()
            return

        # Validate title
        if not title:
            self.notify("Please enter a title", severity="warning")
            self.query_one("#title-input", Input).focus()
            return

        # Create the reference
        ref_id = self._existing.id if self._existing else str(uuid.uuid4())[:8]

        reference = DocReference(
            id=ref_id,
            title=title,
            url=url,
            category=category,
            notes=notes,
        )

        self.dismiss(reference)

    def action_cancel(self) -> None:
        """Cancel and dismiss."""
        self.dismiss(None)
