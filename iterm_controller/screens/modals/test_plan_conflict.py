"""TEST_PLAN.md external edit resolution modal.

Shows detected changes and prompts user to reload or keep current version.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static

if TYPE_CHECKING:
    from ...models import TestPlan
    from ...test_plan_watcher import TestStepChange


class TestPlanConflictModal(ModalScreen[str]):
    """Modal for resolving TEST_PLAN.md conflicts.

    Displays detected changes between the in-memory test plan and the
    externally modified file. User can choose to:
    - Reload: Accept external changes
    - Keep: Keep current in-memory version
    - Decide later: Dismiss modal without action
    """

    DEFAULT_CSS = """
    TestPlanConflictModal {
        align: center middle;
    }

    TestPlanConflictModal > Container {
        width: 60;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $warning;
        padding: 1 2;
    }

    TestPlanConflictModal .modal-title {
        text-align: center;
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }

    TestPlanConflictModal .modal-description {
        margin-bottom: 1;
    }

    TestPlanConflictModal .changes-header {
        text-style: bold;
        margin-top: 1;
    }

    TestPlanConflictModal .change-item {
        margin-left: 2;
        color: $text-muted;
    }

    TestPlanConflictModal .more-changes {
        margin-left: 2;
        color: $text-disabled;
        text-style: italic;
    }

    TestPlanConflictModal .button-row {
        margin-top: 2;
        align: center middle;
    }

    TestPlanConflictModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("r", "reload", "Reload from file", show=True),
        Binding("k", "keep", "Keep current", show=True),
        Binding("escape", "dismiss", "Decide later", show=True),
    ]

    # Maximum number of changes to display
    MAX_DISPLAYED_CHANGES = 10

    def __init__(
        self,
        current_plan: TestPlan,
        new_plan: TestPlan,
        changes: list[TestStepChange],
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the conflict modal.

        Args:
            current_plan: The current in-memory test plan
            new_plan: The newly parsed test plan from disk
            changes: List of detected changes between versions
            name: Optional widget name
            id: Optional widget id
            classes: Optional CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self.current_plan = current_plan
        self.new_plan = new_plan
        self.changes = changes

    def compose(self) -> ComposeResult:
        """Compose the modal content."""
        with Container():
            yield Static("TEST_PLAN.md Changed", classes="modal-title")
            yield Static(
                "The test plan file was modified externally.",
                classes="modal-description",
            )

            yield Static("Changes detected:", classes="changes-header")

            # Display changes (limited to MAX_DISPLAYED_CHANGES)
            displayed_changes = self.changes[: self.MAX_DISPLAYED_CHANGES]
            for change in displayed_changes:
                yield Static(f"• {change}", classes="change-item")

            # Show count of remaining changes if any
            remaining = len(self.changes) - self.MAX_DISPLAYED_CHANGES
            if remaining > 0:
                yield Static(
                    f"... and {remaining} more change(s)",
                    classes="more-changes",
                )

            with Horizontal(classes="button-row"):
                yield Button("[R] Reload", id="reload", variant="primary")
                yield Button("[K] Keep current", id="keep", variant="default")
                yield Button("[Esc] Later", id="dismiss", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "reload":
            self.action_reload()
        elif event.button.id == "keep":
            self.action_keep()
        elif event.button.id == "dismiss":
            self.action_dismiss()

    def action_reload(self) -> None:
        """Accept external changes and reload from file."""
        self.dismiss("reload")

    def action_keep(self) -> None:
        """Keep current in-memory version and discard external changes."""
        self.dismiss("keep")

    def action_dismiss(self) -> None:
        """Dismiss modal without action (decide later)."""
        self.dismiss("later")
