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

    Shows the pattern: [Plan] 1 2 3 4
    with the current mode number highlighted.
    """

    DEFAULT_CSS = """
    ModeIndicatorWidget {
        width: auto;
        height: 1;
        padding: 0 1;
    }
    """

    # Map modes to their key numbers
    MODE_KEYS = {
        WorkflowMode.PLAN: "1",
        WorkflowMode.DOCS: "2",
        WorkflowMode.WORK: "3",
        WorkflowMode.TEST: "4",
    }

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

    def render(self) -> str:
        """Render the mode indicator.

        Format: [Plan] 1 2 3 4
        The current mode is highlighted in the bracketed section,
        and the corresponding number is highlighted.
        """
        if self.current_mode is None:
            return ""

        mode_name = self.current_mode.value.title()
        current_key = self.MODE_KEYS.get(self.current_mode, "")

        parts = []

        # Add the mode name in brackets (highlighted)
        parts.append(f"[bold cyan][{mode_name}][/bold cyan]")

        # Add the shortcuts with current one highlighted
        key_parts = []
        for mode, key in self.MODE_KEYS.items():
            if mode == self.current_mode:
                key_parts.append(f"[bold white on blue] {key} [/bold white on blue]")
            else:
                key_parts.append(f"[dim]{key}[/dim]")

        parts.append(" ".join(key_parts))

        return " ".join(parts)

    def set_mode(self, mode: WorkflowMode) -> None:
        """Update the current mode and refresh display.

        Args:
            mode: The new current mode.
        """
        self.current_mode = mode
        self.refresh()
