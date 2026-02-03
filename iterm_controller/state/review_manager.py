"""Review state manager.

Manages review state for tasks with event dispatch.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from iterm_controller.models import (
    ReviewResult,
    TaskReview,
)
from iterm_controller.state.events import (
    ReviewCompleted,
    ReviewFailed,
    ReviewStarted,
)

if TYPE_CHECKING:
    from textual.app import App

    from iterm_controller.review_service import ReviewService

logger = logging.getLogger(__name__)


class ReviewStateManager:
    """Manages review state for tasks.

    Tracks active reviews and provides methods to start, complete, and
    query review status. Posts events to the Textual app for UI updates.

    This manager coordinates between the ReviewService (which handles the
    actual review execution) and the app state (which UI components observe).

    Attributes:
        active_reviews: Dictionary of currently running reviews by task ID.
        review_service: Optional ReviewService for running reviews.
    """

    def __init__(self, review_service: ReviewService | None = None) -> None:
        """Initialize the review state manager.

        Args:
            review_service: The ReviewService to use for running reviews.
                           If None, reviews cannot be started but state
                           can still be tracked.
        """
        self.review_service = review_service
        self.active_reviews: dict[str, TaskReview] = {}
        self._app: App | None = None

    def connect_app(self, app: App) -> None:
        """Connect to a Textual App for message posting.

        Args:
            app: The Textual App instance.
        """
        self._app = app

    def _post_message(self, message: Any) -> None:
        """Post a message to the connected Textual app."""
        if self._app is not None:
            self._app.post_message(message)

    def _get_project(self, project_id: str) -> Any:
        """Get a project by ID from the app state.

        Args:
            project_id: The project ID.

        Returns:
            The project if found, None otherwise.
        """
        if self._app is None:
            logger.warning("No app connected, cannot get project")
            return None

        if not hasattr(self._app, "state"):
            logger.warning("App has no state attribute")
            return None

        return self._app.state.projects.get(project_id)

    def _get_task(self, project_id: str, task_id: str) -> Any:
        """Get a task by ID from the app state.

        Args:
            project_id: The project ID.
            task_id: The task ID.

        Returns:
            The task if found, None otherwise.
        """
        if self._app is None:
            logger.warning("No app connected, cannot get task")
            return None

        if not hasattr(self._app, "state"):
            logger.warning("App has no state attribute")
            return None

        plan = self._app.state.get_plan(project_id)
        if plan is None:
            logger.warning("No plan found for project %s", project_id)
            return None

        return plan.get_task(task_id)

    async def start_review(
        self,
        project_id: str,
        task_id: str,
    ) -> TaskReview | None:
        """Start a new review for a task.

        Builds review context and runs the review using the ReviewService.
        Posts ReviewStarted, then ReviewCompleted or ReviewFailed when done.

        Args:
            project_id: The project ID.
            task_id: The task ID to review.

        Returns:
            The TaskReview result, or None if the review couldn't be started.
        """
        if self.review_service is None:
            logger.error("No ReviewService configured, cannot start review")
            return None

        project = self._get_project(project_id)
        if project is None:
            logger.error("Project %s not found", project_id)
            return None

        task = self._get_task(project_id, task_id)
        if task is None:
            logger.error("Task %s not found in project %s", task_id, project_id)
            return None

        # Check if already reviewing
        if task_id in self.active_reviews:
            logger.warning("Review already in progress for task %s", task_id)
            return self.active_reviews[task_id]

        # Post review started event
        self._post_message(ReviewStarted(task_id, project_id))
        logger.info("Starting review for task %s in project %s", task_id, project_id)

        try:
            # Build context and run review
            context = await self.review_service.build_review_context(project, task)
            review = await self.review_service.run_review(project, task, context)

            # Track as active during review
            self.active_reviews[task_id] = review

            # Handle the result
            await self._handle_review_result(task_id, review)

            return review

        except Exception as e:
            logger.error("Review failed for task %s: %s", task_id, e)

            # Create a failed review record
            from datetime import datetime

            from iterm_controller.review_service import generate_id

            failed_review = TaskReview(
                id=generate_id(),
                task_id=task_id,
                attempt=task.revision_count + 1 if task else 1,
                result=ReviewResult.NEEDS_REVISION,
                issues=[str(e)],
                summary=f"Review failed: {e}",
                blocking=False,
                reviewed_at=datetime.now(),
                reviewer_command="",
            )
            self.active_reviews[task_id] = failed_review
            self._post_message(ReviewFailed(task_id, failed_review))
            del self.active_reviews[task_id]

            return failed_review

    async def _handle_review_result(
        self,
        task_id: str,
        review: TaskReview,
    ) -> None:
        """Handle a completed review result.

        Posts appropriate events based on the review result.

        Args:
            task_id: The task ID.
            review: The completed review.
        """
        if review.result == ReviewResult.APPROVED:
            self._post_message(ReviewCompleted(task_id, review.result, review))
            logger.info("Review approved for task %s", task_id)

        elif review.result == ReviewResult.REJECTED:
            # Rejected reviews need human intervention
            self._post_message(ReviewFailed(task_id, review))
            logger.warning("Review rejected for task %s: %s", task_id, review.summary)

        elif review.result == ReviewResult.NEEDS_REVISION:
            # Check if we've hit max revisions (blocking)
            if review.blocking:
                self._post_message(ReviewFailed(task_id, review))
                logger.warning(
                    "Review blocked for task %s after max attempts", task_id
                )
            else:
                self._post_message(ReviewCompleted(task_id, review.result, review))
                logger.info(
                    "Review needs revision for task %s (attempt %d)",
                    task_id,
                    review.attempt,
                )

        else:
            # For pending or other states, just complete
            self._post_message(ReviewCompleted(task_id, review.result, review))

        # Clean up active review
        self.active_reviews.pop(task_id, None)

    def get_active_review(self, task_id: str) -> TaskReview | None:
        """Get the active review for a task.

        Args:
            task_id: The task ID.

        Returns:
            The active TaskReview if one exists, None otherwise.
        """
        return self.active_reviews.get(task_id)

    def get_all_active_reviews(self) -> list[TaskReview]:
        """Get all currently active reviews.

        Returns:
            List of all active TaskReview objects.
        """
        return list(self.active_reviews.values())

    def is_reviewing(self, task_id: str) -> bool:
        """Check if a task is currently being reviewed.

        Args:
            task_id: The task ID.

        Returns:
            True if a review is in progress.
        """
        return task_id in self.active_reviews

    def clear(self) -> None:
        """Clear all active reviews.

        This is typically called when shutting down or resetting state.
        """
        self.active_reviews.clear()

    def clear_for_project(self, project_id: str) -> None:
        """Clear active reviews for a specific project.

        Args:
            project_id: The project ID.
        """
        # We need to check which reviews belong to the project
        # Since we only have task_id, we'd need to look up each task
        # For now, this is a best-effort clear based on task lookups
        to_remove = []
        for task_id in self.active_reviews:
            task = self._get_task(project_id, task_id)
            if task is not None:
                to_remove.append(task_id)

        for task_id in to_remove:
            del self.active_reviews[task_id]

    def get_review_count(self) -> int:
        """Get the number of active reviews.

        Returns:
            The number of currently active reviews.
        """
        return len(self.active_reviews)
