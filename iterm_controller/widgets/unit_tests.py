"""Unit test results widget for Test Mode.

Displays unit test runner results with pass/fail counts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rich.text import Text
from textual.widgets import Static

# Import models from the parser module
from iterm_controller.test_output_parser import TestResult, UnitTestResults


class UnitTestWidget(Static):
    """Displays unit test runner results.

    Shows:
    - Last run time
    - Pass/fail/skip counts
    - List of failed tests
    - Controls for running tests

    Layout:
        Unit Tests

        Last run: 2 min ago
        Status: ✓ 42 passed
                ✗ 2 failed
                ○ 1 skipped

        Failed:
          test_auth.py::test_timeout
          test_api.py::test_rate_limit

        ┌──────────────────────────┐
        │ [r] Run  [w] Watch  [f]  │
        │     Failed Only          │
        └──────────────────────────┘
    """

    DEFAULT_CSS = """
    UnitTestWidget {
        height: 1fr;
        padding: 0 1;
        border: solid $surface-lighten-2;
    }
    """

    def __init__(
        self,
        results: UnitTestResults | None = None,
        test_command: str = "",
        **kwargs: Any,
    ) -> None:
        """Initialize the unit test widget.

        Args:
            results: Initial test results to display.
            test_command: The detected or configured test command.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self._results = results or UnitTestResults()
        self._test_command = test_command

    def on_mount(self) -> None:
        """Initialize the test results content when mounted."""
        self.update(self._render_results())

    @property
    def results(self) -> UnitTestResults:
        """Get the current test results."""
        return self._results

    @property
    def test_command(self) -> str:
        """Get the test command."""
        return self._test_command

    def refresh_results(self, results: UnitTestResults) -> None:
        """Update the displayed results.

        Args:
            results: New test results to display.
        """
        self._results = results
        self.update(self._render_results())

    def set_test_command(self, command: str) -> None:
        """Set the test command.

        Args:
            command: The test command to use.
        """
        self._test_command = command
        self.update(self._render_results())

    def set_running(self, running: bool) -> None:
        """Set the running state.

        Args:
            running: Whether tests are currently running.
        """
        self._results.is_running = running
        self.update(self._render_results())

    def _format_time_ago(self, dt: datetime) -> str:
        """Format a datetime as a relative time string.

        Args:
            dt: The datetime to format.

        Returns:
            Human-readable relative time string.
        """
        now = datetime.now()
        delta = now - dt
        seconds = delta.total_seconds()

        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            mins = int(seconds // 60)
            return f"{mins} min ago"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        else:
            days = int(seconds // 86400)
            return f"{days} day{'s' if days > 1 else ''} ago"

    def _render_results(self) -> Text:
        """Render the test results.

        Returns:
            Rich Text object containing the test results.
        """
        text = Text()

        # Header
        text.append("Unit Tests\n", style="bold")
        text.append("\n")

        # Running state
        if self._results.is_running:
            text.append("⟳ Running tests...\n", style="yellow")
            text.append("\n")
            return text

        # Last run time
        if self._results.last_run:
            time_ago = self._format_time_ago(self._results.last_run)
            text.append("Last run: ", style="dim")
            text.append(f"{time_ago}\n")
        else:
            text.append("No tests have been run yet\n", style="dim italic")
            text.append("\n")

            # Show detected command if available
            if self._test_command:
                text.append("Detected: ", style="dim")
                text.append(f"{self._test_command}\n", style="cyan")
            else:
                text.append("No test command detected\n", style="dim")

            text.append("\nPress [r] to run tests\n", style="dim")
            return text

        # Status summary
        text.append("Status: ")

        # Passed
        if self._results.passed > 0:
            text.append(f"✓ {self._results.passed} passed", style="green")
        else:
            text.append(f"✓ {self._results.passed} passed", style="dim")
        text.append("\n        ")

        # Failed
        if self._results.failed > 0:
            text.append(f"✗ {self._results.failed} failed", style="red")
        else:
            text.append(f"✗ {self._results.failed} failed", style="dim")
        text.append("\n        ")

        # Skipped
        if self._results.skipped > 0:
            text.append(f"○ {self._results.skipped} skipped", style="yellow")
        else:
            text.append(f"○ {self._results.skipped} skipped", style="dim")
        text.append("\n")

        # Errors (if any)
        if self._results.errors > 0:
            text.append("        ")
            text.append(f"⚠ {self._results.errors} errors", style="red bold")
            text.append("\n")

        text.append("\n")

        # Duration
        if self._results.duration_seconds > 0:
            text.append(f"Duration: {self._results.duration_seconds:.2f}s\n", style="dim")
            text.append("\n")

        # Failed tests list
        if self._results.failed_tests:
            text.append("Failed:\n", style="red bold")
            for test in self._results.failed_tests[:5]:  # Show first 5
                text.append(f"  {test.name}\n", style="red")
            if len(self._results.failed_tests) > 5:
                remaining = len(self._results.failed_tests) - 5
                text.append(f"  ... and {remaining} more\n", style="dim")
            text.append("\n")

        # Command info
        if self._test_command:
            text.append("Command: ", style="dim")
            text.append(f"{self._test_command}\n", style="cyan dim")

        return text

    def render(self) -> Text:
        """Render the widget content.

        Returns:
            Rich Text object to display.
        """
        return self._render_results()
