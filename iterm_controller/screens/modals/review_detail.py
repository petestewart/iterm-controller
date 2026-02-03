"""Review detail modal for showing task review results.

Displays full review output including issues and allows approve/reject/revise actions.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from iterm_controller.models import ReviewResult, Task, TaskReview


class ReviewAction(Enum):
    """Actions that can be taken on a review."""

    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"
    CLOSE = "close"


class ReviewDetailModal(ModalScreen[ReviewAction]):
    """Modal for reviewing completed task and taking action.

    Displays the task information, review result, issues found,
    and allows the user to approve, request changes, or reject.
    Returns the action taken.
    """

    DEFAULT_CSS = """
    ReviewDetailModal {
        align: center middle;
    }

    ReviewDetailModal > Container {
        width: 80;
        height: auto;
        max-height: 40;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }

    ReviewDetailModal .modal-title {
        text-style: bold;
        color: $primary;
        text-align: center;
        margin-bottom: 1;
    }

    ReviewDetailModal .task-id {
        color: $text-muted;
    }

    ReviewDetailModal .task-title {
        text-style: bold;
        margin-bottom: 1;
    }

    ReviewDetailModal .section-header {
        text-style: bold;
        color: $secondary;
        margin-top: 1;
        margin-bottom: 0;
    }

    ReviewDetailModal #review-status {
        padding: 0 1;
        margin-bottom: 1;
    }

    ReviewDetailModal .status-approved {
        color: $success;
    }

    ReviewDetailModal .status-needs-revision {
        color: $warning;
    }

    ReviewDetailModal .status-rejected {
        color: $error;
    }

    ReviewDetailModal .status-pending {
        color: $text-muted;
    }

    ReviewDetailModal #issues-container {
        height: auto;
        max-height: 12;
        border: solid $surface-lighten-1;
        margin-bottom: 1;
        padding: 0 1;
        overflow-y: auto;
    }

    ReviewDetailModal .issue-item {
        margin: 0 0 0 1;
    }

    ReviewDetailModal #summary-container {
        height: auto;
        max-height: 6;
        border: solid $surface-lighten-1;
        margin-bottom: 1;
        padding: 1;
        overflow-y: auto;
    }

    ReviewDetailModal #button-row {
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    ReviewDetailModal #button-row Button {
        margin: 0 1;
        min-width: 14;
    }

    ReviewDetailModal .revision-count {
        color: $text-muted;
        text-align: right;
    }

    ReviewDetailModal .hint {
        color: $text-muted;
        text-align: center;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("a", "approve", "Approve"),
        Binding("c", "request_changes", "Request Changes"),
        Binding("r", "reject", "Reject"),
    ]

    def __init__(
        self,
        review_task: Task,
        review: TaskReview | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the review detail modal.

        Args:
            review_task: The task being reviewed.
            review: The review to display. If None, uses review_task.current_review.
            **kwargs: Additional arguments passed to ModalScreen.
        """
        super().__init__(**kwargs)
        self._review_target = review_task
        self._review = review or review_task.current_review

    @property
    def review_task(self) -> Task:
        """Get the task being reviewed."""
        return self._review_target

    @property
    def review_data(self) -> TaskReview | None:
        """Get the review data."""
        return self._review

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        yield Container(
            Static(f"Review: {self._review_target.id}", classes="modal-title"),
            Static(self._review_target.title, classes="task-title"),
            self._build_review_status(),
            Static("Summary", classes="section-header"),
            ScrollableContainer(
                Static(id="summary-text"),
                id="summary-container",
            ),
            Static("Issues Found", classes="section-header"),
            ScrollableContainer(
                Vertical(id="issues-list"),
                id="issues-container",
            ),
            self._build_revision_info(),
            Horizontal(
                Button("Reject", variant="error", id="reject-btn"),
                Button("Request Changes", variant="warning", id="changes-btn"),
                Button("Approve", variant="success", id="approve-btn"),
                id="button-row",
            ),
            Static("[a] Approve  [c] Changes  [r] Reject  [Esc] Close", classes="hint"),
        )

    def _build_review_status(self) -> Static:
        """Build the review status display."""
        if not self._review:
            return Static(
                "[pending] No review available",
                id="review-status",
                classes="status-pending",
            )

        status_text = self._review.result.value.replace("_", " ").title()
        status_class = f"status-{self._review.result.value.replace('_', '-')}"

        return Static(
            f"[{status_text}]",
            id="review-status",
            classes=status_class,
        )

    def _build_revision_info(self) -> Static:
        """Build the revision count display."""
        if self._review_target.revision_count > 0:
            return Static(
                f"Revision {self._review_target.revision_count} of {self._get_max_revisions()}",
                classes="revision-count",
            )
        return Static("", classes="revision-count")

    def _get_max_revisions(self) -> int:
        """Get the maximum number of revisions allowed."""
        # Default to 3 if not configured
        return 3

    def on_mount(self) -> None:
        """Initialize the modal content."""
        self._populate_summary()
        self._populate_issues()
        self._update_button_states()

    def _populate_summary(self) -> None:
        """Populate the summary text."""
        summary_widget = self.query_one("#summary-text", Static)

        if not self._review:
            summary_widget.update("[dim]No review summary available[/dim]")
            return

        summary_widget.update(self._review.summary or "[dim]No summary provided[/dim]")

    def _populate_issues(self) -> None:
        """Populate the issues list."""
        container = self.query_one("#issues-list", Vertical)

        if not self._review or not self._review.issues:
            container.mount(Static("[dim]No issues found[/dim]"))
            return

        for i, issue in enumerate(self._review.issues, 1):
            container.mount(
                Static(f"{i}. {issue}", classes="issue-item")
            )

    def _update_button_states(self) -> None:
        """Update button states based on review status."""
        # If already approved or rejected, disable action buttons
        if self._review and self._review.result == ReviewResult.REJECTED:
            self.query_one("#approve-btn", Button).disabled = True
            self.query_one("#changes-btn", Button).disabled = True
            self.query_one("#reject-btn", Button).disabled = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button pressed event.
        """
        if event.button.id == "approve-btn":
            self.dismiss(ReviewAction.APPROVE)
        elif event.button.id == "changes-btn":
            self.dismiss(ReviewAction.REQUEST_CHANGES)
        elif event.button.id == "reject-btn":
            self.dismiss(ReviewAction.REJECT)

    def action_close(self) -> None:
        """Close the modal without action."""
        self.dismiss(ReviewAction.CLOSE)

    def action_approve(self) -> None:
        """Approve the task."""
        if self._review and self._review.result == ReviewResult.REJECTED:
            self.notify("Cannot approve a rejected review", severity="warning")
            return
        self.dismiss(ReviewAction.APPROVE)

    def action_request_changes(self) -> None:
        """Request changes to the task."""
        if self._review and self._review.result == ReviewResult.REJECTED:
            self.notify("Cannot request changes on a rejected review", severity="warning")
            return
        self.dismiss(ReviewAction.REQUEST_CHANGES)

    def action_reject(self) -> None:
        """Reject the task."""
        self.dismiss(ReviewAction.REJECT)
