"""Add Document modal for Docs Mode.

Modal dialog for creating new documentation files.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from iterm_controller.security import PathTraversalError, validate_filename


class AddDocumentModal(ModalScreen[dict | None]):
    """Modal for adding a new document.

    Returns a dict with 'path' and optional 'content' if created,
    or None if cancelled.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    AddDocumentModal {
        align: center middle;
    }

    AddDocumentModal #dialog {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    AddDocumentModal #title {
        text-style: bold;
        padding-bottom: 1;
    }

    AddDocumentModal .field-label {
        margin-top: 1;
    }

    AddDocumentModal Input, AddDocumentModal Select {
        width: 100%;
        margin-bottom: 1;
    }

    AddDocumentModal #buttons {
        margin-top: 1;
        height: 3;
        align: center middle;
    }

    AddDocumentModal Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        project_path: str,
        default_directory: str | None = None,
    ) -> None:
        """Initialize the modal.

        Args:
            project_path: Path to the project root.
            default_directory: Default directory for the new document.
        """
        super().__init__()
        self._project_path = Path(project_path)
        self._default_directory = default_directory or project_path

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        # Get available directories
        directories = self._get_directories()

        yield Vertical(
            Static("Add Document", id="title"),
            Label("Location:", classes="field-label"),
            Select(
                [(d, d) for d in directories],
                value=self._get_relative_default(),
                id="location",
            ),
            Label("Filename:", classes="field-label"),
            Input(placeholder="new-document.md", id="filename"),
            Horizontal(
                Button("Cancel", variant="default", id="cancel"),
                Button("Create", variant="primary", id="create"),
                id="buttons",
            ),
            id="dialog",
        )

    def _get_directories(self) -> list[str]:
        """Get list of available directories for documents.

        Returns:
            List of directory paths relative to project root.
        """
        directories = ["."]

        # Standard doc directories
        for dir_name in ["docs", "specs", "documentation"]:
            dir_path = self._project_path / dir_name
            if dir_path.exists():
                directories.append(dir_name)
                # Include subdirectories
                for subdir in dir_path.rglob("*"):
                    if subdir.is_dir() and not subdir.name.startswith("."):
                        try:
                            rel_path = subdir.relative_to(self._project_path)
                            directories.append(str(rel_path))
                        except ValueError as e:
                            logger.debug(
                                "Subdir '%s' not relative to project: %s", subdir, e
                            )

        return sorted(directories)

    def _get_relative_default(self) -> str:
        """Get the default directory as a relative path.

        Returns:
            Relative path string.
        """
        try:
            default_path = Path(self._default_directory)
            rel_path = default_path.relative_to(self._project_path)
            return str(rel_path) if str(rel_path) != "." else "."
        except ValueError:
            return "."

    def on_mount(self) -> None:
        """Focus the filename input when mounted."""
        self.query_one("#filename", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button pressed event.
        """
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "create":
            self._create_document()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input.

        Args:
            event: The input submitted event.
        """
        if event.input.id == "filename":
            self._create_document()

    def _create_document(self) -> None:
        """Create the document and dismiss."""
        filename_input = self.query_one("#filename", Input)
        location_select = self.query_one("#location", Select)

        filename = filename_input.value.strip()

        if not filename:
            self.notify("Please enter a filename", severity="warning")
            return

        # Validate filename to prevent path traversal
        # Don't allow subdirectories in filename - location selector handles that
        try:
            filename = validate_filename(filename, allow_subdirs=False)
        except PathTraversalError as e:
            self.notify(
                f"Invalid filename: {e.args[0]}",
                severity="error",
            )
            return
        except ValueError as e:
            self.notify(str(e), severity="error")
            return

        # Ensure .md extension
        if not filename.endswith(".md"):
            filename = f"{filename}.md"

        # Build full path
        location = location_select.value
        if location and location != ".":
            full_path = self._project_path / location / filename
        else:
            full_path = self._project_path / filename

        # Check if file already exists
        if full_path.exists():
            self.notify(f"{filename} already exists", severity="error")
            return

        self.dismiss({"path": str(full_path), "content": ""})

    def action_cancel(self) -> None:
        """Cancel and dismiss."""
        self.dismiss(None)
