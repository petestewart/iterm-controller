"""Work Mode screen.

Task execution and session tracking screen.

See specs/work-mode.md for full specification.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header, Static

from iterm_controller.models import WorkflowMode
from iterm_controller.screens.mode_screen import ModeScreen


class WorkModeScreen(ModeScreen):
    """Work Mode screen for task execution.

    This screen displays:
    - Task queue (pending tasks)
    - Active work (in-progress tasks with linked sessions)
    - Session status indicators

    Users can claim tasks, spawn sessions, and track work progress.

    Full implementation in Phase 14.
    """

    CURRENT_MODE = WorkflowMode.WORK

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            Static("[bold]Work Mode[/bold]", id="mode-title"),
            Static(
                "[dim]Task execution and session tracking.\n\n"
                "This screen will show:\n"
                "  - Task queue (pending tasks)\n"
                "  - Active work (in-progress tasks)\n"
                "  - Task-session linking\n"
                "  - Session status indicators\n\n"
                "Full implementation coming in Phase 14.[/dim]",
                id="placeholder-content",
            ),
            id="main",
        )
        yield Footer()
