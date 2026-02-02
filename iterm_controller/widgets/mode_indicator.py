"""Mode indicator widget for workflow mode screens.

This widget displays the current workflow mode and shortcuts 1-4
in a horizontal bar, with the current mode highlighted.

See specs/workflow-modes.md#mode-indicator for specification.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.widgets import Static

from iterm_controller.models import WorkflowMode


class ModeIndicatorWidget(Static):
    """Displays current mode and navigation shortcuts.

    Shows the pattern: 1 Plan  2 Docs  3 Work  4 Test
    with the current mode highlighted.
    """

    DEFAULT_CSS = """
    ModeIndicatorWidget {
        width: auto;
        height: 1;
        padding: 0 1;
    }
    """

    # Map modes to their key numbers and labels
    MODE_INFO = [
        (WorkflowMode.PLAN, "1", "Plan"),
        (WorkflowMode.DOCS, "2", "Docs"),
        (WorkflowMode.WORK, "3", "Work"),
        (WorkflowMode.TEST, "4", "Test"),
    ]

    def __init__(
        self,
        current_mode: WorkflowMode | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the mode indicator.

        Args:
            current_mode: The currently active workflow mode.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self.current_mode = current_mode

    def on_mount(self) -> None:
        """Initialize the mode indicator content when mounted."""
        self.update(self.render())

    def render(self) -> str:
        """Render the mode indicator.

        Format: 1 Plan  2 Docs  3 Work  4 Test
        The current mode is highlighted.
        """
        if self.current_mode is None:
            return ""

        parts = []

        # Add each mode with key and label
        for mode, key, label in self.MODE_INFO:
            if mode == self.current_mode:
                # Highlight current mode
                parts.append(f"[bold white on blue] {key} {label} [/bold white on blue]")
            else:
                # Dim non-current modes
                parts.append(f"[dim]{key} {label}[/dim]")

        return "  ".join(parts)

    def set_mode(self, mode: WorkflowMode) -> None:
        """Update the current mode and refresh display.

        Args:
            mode: The new current mode.
        """
        self.current_mode = mode
        self.refresh()
