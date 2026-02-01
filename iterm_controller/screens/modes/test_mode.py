"""Test Mode screen.

QA testing and unit test runner screen.

See specs/test-mode.md for full specification.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header, Static

from iterm_controller.models import WorkflowMode
from iterm_controller.screens.mode_screen import ModeScreen


class TestModeScreen(ModeScreen):
    """Test Mode screen for QA and unit testing.

    This screen displays:
    - TEST_PLAN.md steps with status indicators
    - Unit test runner results
    - Test command detection

    Users can run tests, mark QA steps complete, and generate test plans.

    Full implementation in Phase 15.
    """

    CURRENT_MODE = WorkflowMode.TEST

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            Static("[bold]Test Mode[/bold]", id="mode-title"),
            Static(
                "[dim]QA testing and unit test runner.\n\n"
                "This screen will show:\n"
                "  - TEST_PLAN.md steps\n"
                "  - Unit test results\n"
                "  - Test command detection\n"
                "  - Test plan generation\n\n"
                "Full implementation coming in Phase 15.[/dim]",
                id="placeholder-content",
            ),
            id="main",
        )
        yield Footer()
