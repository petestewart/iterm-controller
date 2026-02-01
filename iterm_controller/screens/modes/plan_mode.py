"""Plan Mode screen.

Planning artifacts management screen showing PROBLEM.md, PRD.md, specs/, and PLAN.md.

See specs/plan-mode.md for full specification.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header, Static

from iterm_controller.models import WorkflowMode
from iterm_controller.screens.mode_screen import ModeScreen


class PlanModeScreen(ModeScreen):
    """Plan Mode screen for managing planning artifacts.

    This screen displays:
    - PROBLEM.md status and content
    - PRD.md status and content
    - specs/ directory listing
    - PLAN.md status and content

    Users can create missing artifacts, edit existing ones, and preview content.

    Full implementation in Phase 13.
    """

    CURRENT_MODE = WorkflowMode.PLAN

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            Static("[bold]Plan Mode[/bold]", id="mode-title"),
            Static(
                "[dim]Planning artifacts management screen.\n\n"
                "This screen will show:\n"
                "  - PROBLEM.md status\n"
                "  - PRD.md status\n"
                "  - specs/ directory listing\n"
                "  - PLAN.md status\n\n"
                "Full implementation coming in Phase 13.[/dim]",
                id="placeholder-content",
            ),
            id="main",
        )
        yield Footer()
