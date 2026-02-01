"""Docs Mode screen.

Documentation tree browser for managing project documentation.

See specs/docs-mode.md for full specification.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header, Static

from iterm_controller.models import WorkflowMode
from iterm_controller.screens.mode_screen import ModeScreen


class DocsModeScreen(ModeScreen):
    """Docs Mode screen for documentation management.

    This screen displays a tree view of documentation files:
    - docs/ directory
    - specs/ directory
    - README.md
    - CHANGELOG.md

    Users can navigate, add, edit, and delete documentation files.

    Full implementation in Phase 16.
    """

    CURRENT_MODE = WorkflowMode.DOCS

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            Static("[bold]Docs Mode[/bold]", id="mode-title"),
            Static(
                "[dim]Documentation tree browser.\n\n"
                "This screen will show:\n"
                "  - Tree view of docs/ and specs/\n"
                "  - README.md and CHANGELOG.md\n"
                "  - File add/edit/delete operations\n"
                "  - Markdown preview\n\n"
                "Full implementation coming in Phase 16.[/dim]",
                id="placeholder-content",
            ),
            id="main",
        )
        yield Footer()
