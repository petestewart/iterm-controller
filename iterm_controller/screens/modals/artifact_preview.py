"""Artifact preview modal for viewing markdown files inline.

Shows artifact content in a scrollable markdown viewer with option to edit.

See specs/plan-mode.md#inline-preview for specification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Markdown, Static

# Result type for the modal
ArtifactPreviewResult = Literal["edit", "agent", "close"]


class ArtifactPreviewModal(ModalScreen[ArtifactPreviewResult]):
    """Modal for previewing artifact content inline.

    Displays the markdown content of an artifact file with options to:
    - Edit: Open in external editor (returns "edit")
    - Close: Dismiss modal (returns "close")
    """

    DEFAULT_CSS = """
    ArtifactPreviewModal {
        align: center middle;
    }

    ArtifactPreviewModal > Container {
        width: 80%;
        height: 80%;
        max-width: 100;
        background: $surface;
        border: thick $primary;
        padding: 0;
    }

    ArtifactPreviewModal #header {
        dock: top;
        height: 3;
        padding: 0 2;
        background: $primary;
        color: $text;
    }

    ArtifactPreviewModal #header-row {
        height: 100%;
        align: center middle;
    }

    ArtifactPreviewModal #title {
        text-style: bold;
    }

    ArtifactPreviewModal #edit-hint {
        dock: right;
        color: $text-muted;
    }

    ArtifactPreviewModal #content {
        padding: 1 2;
        height: 1fr;
        overflow-y: auto;
    }

    ArtifactPreviewModal #content Markdown {
        margin: 0;
        padding: 0;
    }

    ArtifactPreviewModal #footer {
        dock: bottom;
        height: 3;
        padding: 0 2;
        background: $surface-darken-1;
    }

    ArtifactPreviewModal #footer-row {
        height: 100%;
        align: center middle;
    }

    ArtifactPreviewModal Button {
        margin: 0 1;
    }

    ArtifactPreviewModal #empty-message {
        text-align: center;
        color: $text-muted;
        padding: 2;
    }
    """

    BINDINGS = [
        Binding("e", "edit", "Edit"),
        Binding("a", "agent", "Agent"),
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close", show=False),
    ]

    def __init__(
        self,
        artifact_name: str,
        artifact_path: Path,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the preview modal.

        Args:
            artifact_name: Display name for the artifact (e.g., "PRD.md")
            artifact_path: Full path to the artifact file
            name: Optional widget name
            id: Optional widget id
            classes: Optional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.artifact_name = artifact_name
        self.artifact_path = artifact_path
        self._content: str = ""

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        # Load content
        self._load_content()

        with Container():
            # Header with title and edit hint
            with Container(id="header"):
                with Horizontal(id="header-row"):
                    yield Static(f"{self.artifact_name} Preview", id="title")
                    yield Static("[e] Edit  [a] Agent", id="edit-hint")

            # Content area with markdown viewer
            with Container(id="content"):
                if self._content:
                    yield Markdown(self._content, id="markdown")
                else:
                    yield Static(
                        "File is empty or could not be read.",
                        id="empty-message",
                    )

            # Footer with buttons
            with Container(id="footer"):
                with Horizontal(id="footer-row"):
                    yield Button("[E] Edit", id="edit", variant="primary")
                    yield Button("[A] Agent", id="agent", variant="success")
                    yield Button("[Esc] Close", id="close", variant="default")

    def _load_content(self) -> None:
        """Load content from the artifact file."""
        try:
            if self.artifact_path.exists():
                self._content = self.artifact_path.read_text(encoding="utf-8")
            else:
                self._content = ""
        except Exception:
            self._content = ""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "edit":
            self.action_edit()
        elif event.button.id == "agent":
            self.action_agent()
        elif event.button.id == "close":
            self.action_close()

    def action_edit(self) -> None:
        """Request to edit the artifact in external editor."""
        self.dismiss("edit")

    def action_agent(self) -> None:
        """Request to collaborate with an agent on the artifact."""
        self.dismiss("agent")

    def action_close(self) -> None:
        """Close the preview modal."""
        self.dismiss("close")
