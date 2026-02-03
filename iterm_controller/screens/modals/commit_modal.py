"""Commit modal for staging and committing changes.

Displays staged files preview and allows entering a commit message.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class CommitModal(ModalScreen[str | None]):
    """Modal for committing git changes.

    Displays a preview of staged files and a text input for the commit message.
    Returns the commit message on submit, or None if cancelled.
    """

    DEFAULT_CSS = """
    CommitModal {
        align: center middle;
    }

    CommitModal > Container {
        width: 70;
        height: auto;
        max-height: 30;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }

    CommitModal .modal-title {
        text-style: bold;
        color: $primary;
        text-align: center;
        margin-bottom: 1;
    }

    CommitModal #staged-files {
        height: auto;
        max-height: 10;
        border: solid $surface-lighten-1;
        margin-bottom: 1;
        padding: 0 1;
        overflow-y: auto;
    }

    CommitModal #commit-message {
        margin-bottom: 1;
    }

    CommitModal #button-row {
        height: auto;
        align: center middle;
    }

    CommitModal #button-row Button {
        margin: 0 1;
        min-width: 12;
    }

    CommitModal .hint {
        color: $text-muted;
        text-align: center;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+enter", "submit_commit", "Commit", show=False),
    ]

    def __init__(
        self,
        staged_files: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the commit modal.

        Args:
            staged_files: List of staged file paths to display.
            **kwargs: Additional arguments passed to ModalScreen.
        """
        super().__init__(**kwargs)
        self.staged_files = staged_files or []

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        yield Container(
            Static("Commit Changes", classes="modal-title"),
            Static(
                "Staged files:" if self.staged_files else "No files to display",
                classes="hint",
            ),
            Vertical(id="staged-files"),
            Input(
                placeholder="Enter commit message...",
                id="commit-message",
            ),
            Horizontal(
                Button("Cancel", variant="default", id="cancel-btn"),
                Button("Commit", variant="primary", id="commit-btn"),
                id="button-row",
            ),
        )

    def on_mount(self) -> None:
        """Initialize the modal content."""
        self._populate_staged_files()
        # Focus the commit message input
        self.query_one("#commit-message", Input).focus()

    def _populate_staged_files(self) -> None:
        """Populate the staged files container."""
        container = self.query_one("#staged-files", Vertical)

        if not self.staged_files:
            container.mount(Static("[dim]No staged files[/dim]"))
            return

        for file_path in self.staged_files[:10]:  # Limit display
            container.mount(Static(f"  {file_path}"))

        if len(self.staged_files) > 10:
            remaining = len(self.staged_files) - 10
            container.mount(Static(f"  [dim]... and {remaining} more files[/dim]"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button pressed event.
        """
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "commit-btn":
            self._do_commit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key).

        Args:
            event: The input submitted event.
        """
        if event.input.id == "commit-message":
            self._do_commit()

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.dismiss(None)

    def action_submit_commit(self) -> None:
        """Submit the commit."""
        self._do_commit()

    def _do_commit(self) -> None:
        """Validate and submit the commit message."""
        message_input = self.query_one("#commit-message", Input)
        message = message_input.value.strip()

        if not message:
            self.notify("Please enter a commit message", severity="warning")
            message_input.focus()
            return

        self.dismiss(message)
