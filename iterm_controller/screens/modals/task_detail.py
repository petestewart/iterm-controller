"""Task detail modal for showing full task information.

Displays task details including status, dependencies, scope, acceptance criteria,
and review history.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from iterm_controller.models import Task, TaskReview, TaskStatus


class TaskDetailModal(ModalScreen[None]):
    """Modal for showing full task details.

    Displays the task information including title, status, description,
    dependencies, scope, acceptance criteria, and review history.
    """

    DEFAULT_CSS = """
    TaskDetailModal {
        align: center middle;
    }

    TaskDetailModal > Container {
        width: 75;
        height: auto;
        max-height: 35;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }

    TaskDetailModal .modal-title {
        text-style: bold;
        color: $primary;
        text-align: center;
        margin-bottom: 1;
    }

    TaskDetailModal .task-title {
        text-style: bold;
        margin-bottom: 1;
    }

    TaskDetailModal .section-header {
        text-style: bold;
        color: $secondary;
        margin-top: 1;
        margin-bottom: 0;
    }

    TaskDetailModal .task-status {
        padding: 0 1;
    }

    TaskDetailModal .status-pending {
        color: $text-muted;
    }

    TaskDetailModal .status-in-progress {
        color: $warning;
    }

    TaskDetailModal .status-complete {
        color: $success;
    }

    TaskDetailModal .status-blocked {
        color: $error;
    }

    TaskDetailModal .status-awaiting-review {
        color: $warning;
    }

    TaskDetailModal .status-skipped {
        color: $text-muted;
    }

    TaskDetailModal .task-deps {
        color: $text-muted;
        margin-bottom: 1;
    }

    TaskDetailModal #content-container {
        height: auto;
        max-height: 15;
        border: solid $surface-lighten-1;
        margin-bottom: 1;
        padding: 0 1;
        overflow-y: auto;
    }

    TaskDetailModal .content-section {
        margin-bottom: 1;
    }

    TaskDetailModal .content-label {
        color: $text-muted;
        text-style: italic;
    }

    TaskDetailModal #review-history {
        height: auto;
        max-height: 8;
        border: solid $surface-lighten-1;
        margin-bottom: 1;
        padding: 0 1;
        overflow-y: auto;
    }

    TaskDetailModal .review-item {
        margin: 0 0 1 0;
    }

    TaskDetailModal .review-passed {
        color: $success;
    }

    TaskDetailModal .review-failed {
        color: $error;
    }

    TaskDetailModal .review-pending {
        color: $text-muted;
    }

    TaskDetailModal #button-row {
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    TaskDetailModal #button-row Button {
        min-width: 12;
    }

    TaskDetailModal .hint {
        color: $text-muted;
        text-align: center;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("enter", "close", "Close"),
    ]

    def __init__(
        self,
        detail_task: Task,
        **kwargs: Any,
    ) -> None:
        """Initialize the task detail modal.

        Args:
            detail_task: The task to display details for.
            **kwargs: Additional arguments passed to ModalScreen.
        """
        super().__init__(**kwargs)
        self._detail_task = detail_task

    @property
    def detail_task(self) -> Task:
        """Get the task being displayed."""
        return self._detail_task

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        yield Container(
            Static(f"Task: {self._detail_task.id}", classes="modal-title"),
            Static(self._detail_task.title, classes="task-title"),
            self._build_status_display(),
            self._build_dependencies_display(),
            Static("Details", classes="section-header"),
            ScrollableContainer(
                Vertical(id="content-sections"),
                id="content-container",
            ),
            self._build_review_section(),
            Horizontal(
                Button("Close", variant="default", id="close-btn"),
                id="button-row",
            ),
            Static("[Enter] or [Esc] to close", classes="hint"),
        )

    def _build_status_display(self) -> Static:
        """Build the status display with appropriate styling."""
        status = self._detail_task.status
        status_text = status.value.replace("_", " ").title()
        status_class = f"status-{status.value.replace('_', '-')}"

        return Static(
            f"Status: {status_text}",
            classes=f"task-status {status_class}",
        )

    def _build_dependencies_display(self) -> Static:
        """Build the dependencies display."""
        deps = self._detail_task.depends
        if deps:
            deps_text = ", ".join(deps)
        else:
            deps_text = "None"

        return Static(
            f"Dependencies: {deps_text}",
            classes="task-deps",
        )

    def _build_review_section(self) -> Container:
        """Build the review history section."""
        return Container(
            Static("Review History", classes="section-header"),
            ScrollableContainer(
                Vertical(id="review-list"),
                id="review-history",
            ),
        )

    def on_mount(self) -> None:
        """Initialize the modal content."""
        self._populate_content_sections()
        self._populate_review_history()

    def _populate_content_sections(self) -> None:
        """Populate the content sections (scope, acceptance, notes)."""
        container = self.query_one("#content-sections", Vertical)

        # Scope section
        if self._detail_task.scope:
            container.mount(Static("Scope:", classes="content-label"))
            container.mount(
                Static(self._detail_task.scope, classes="content-section")
            )

        # Acceptance criteria section
        if self._detail_task.acceptance:
            container.mount(Static("Acceptance:", classes="content-label"))
            container.mount(
                Static(self._detail_task.acceptance, classes="content-section")
            )

        # Spec reference
        if self._detail_task.spec_ref:
            container.mount(Static("Spec Reference:", classes="content-label"))
            container.mount(
                Static(self._detail_task.spec_ref, classes="content-section")
            )

        # Notes section
        if self._detail_task.notes:
            container.mount(Static("Notes:", classes="content-label"))
            for note in self._detail_task.notes:
                container.mount(Static(f"  • {note}", classes="content-section"))

        # If nothing to show
        if not any([
            self._detail_task.scope,
            self._detail_task.acceptance,
            self._detail_task.spec_ref,
            self._detail_task.notes,
        ]):
            container.mount(Static("[dim]No additional details[/dim]"))

    def _populate_review_history(self) -> None:
        """Populate the review history list."""
        container = self.query_one("#review-list", Vertical)

        reviews = self._detail_task.review_history
        current_review = self._detail_task.current_review

        # Add current review if it exists
        if current_review and current_review not in reviews:
            reviews = [current_review] + list(reviews)

        if not reviews:
            container.mount(Static("[dim]No reviews yet[/dim]"))
            return

        for review in reviews:
            result_class = self._get_review_result_class(review)
            result_text = review.result.value.replace("_", " ").title()
            container.mount(
                Static(
                    f"Attempt {review.attempt}: {result_text} - {review.summary[:50]}...",
                    classes=f"review-item {result_class}",
                )
            )

    def _get_review_result_class(self, review: TaskReview) -> str:
        """Get CSS class for review result."""
        from iterm_controller.models import ReviewResult

        if review.result == ReviewResult.APPROVED:
            return "review-passed"
        elif review.result in (ReviewResult.REJECTED, ReviewResult.NEEDS_REVISION):
            return "review-failed"
        else:
            return "review-pending"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button pressed event.
        """
        if event.button.id == "close-btn":
            self.dismiss(None)

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss(None)
