"""Review service for automatic task reviews.

This module provides the ReviewService which orchestrates the review pipeline:
1. Build context (task definition, git diff, test results)
2. Run configurable review command
3. Parse output into structured result
4. Handle result (update task status, notify)

See specs/review-service.md for full specification.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from iterm_controller.exceptions import ItermControllerError
from iterm_controller.models import (
    ManagedSession,
    Project,
    ReviewConfig,
    ReviewContextConfig,
    ReviewResult,
    SessionTemplate,
    SessionType,
    Task,
    TaskReview,
    TaskStatus,
)

if TYPE_CHECKING:
    from iterm_controller.git_service import GitService
    from iterm_controller.iterm.spawner import SessionSpawner
    from iterm_controller.notifications import Notifier
    from iterm_controller.state.plan_manager import PlanStateManager


logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class ReviewError(ItermControllerError):
    """Base exception for review errors."""


class ReviewContextError(ReviewError):
    """Raised when building review context fails."""


class ReviewCommandError(ReviewError):
    """Raised when the review command fails."""


class ReviewParseError(ReviewError):
    """Raised when parsing review output fails."""


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class ReviewContext:
    """Context provided to the reviewer.

    Contains all the information needed for the review command to evaluate
    whether a task was completed correctly.

    Attributes:
        task_id: The ID of the task being reviewed.
        task_definition: Formatted task title, scope, and acceptance criteria.
        git_diff: Git diff of changes since base branch.
        test_results: Output from running tests, if included.
        lint_results: Output from running linter, if included.
        session_log: Session output log (usually too verbose).
    """

    task_id: str
    task_definition: str | None = None
    git_diff: str | None = None
    test_results: str | None = None
    lint_results: str | None = None
    session_log: str | None = None


@dataclass
class ParsedReviewResult:
    """Structured result extracted from review output.

    This is the normalized output from parsing the free-form review
    command output.

    Attributes:
        result: Review verdict (APPROVED, NEEDS_REVISION, REJECTED).
        issues: List of specific issues found.
        summary: Brief summary (1-2 sentences).
        blocking: If True, needs human intervention regardless of attempt count.
    """

    result: ReviewResult
    issues: list[str] = field(default_factory=list)
    summary: str = ""
    blocking: bool = False


def generate_id() -> str:
    """Generate a unique ID for reviews."""
    return str(uuid.uuid4())[:8]


# =============================================================================
# Review Service
# =============================================================================


class ReviewService:
    """Orchestrates the review pipeline for completed tasks.

    The review pipeline:
    1. Build context (task definition, git diff, test results)
    2. Run configurable review command in a session
    3. Parse output via subagent for structured result
    4. Handle result (update task status, notify user)

    Attributes:
        session_spawner: Service for spawning review sessions.
        git_service: Service for git operations.
        plan_manager: Manager for updating task status.
        notifier: Optional notifier for sending alerts.
    """

    # Patterns for detecting review results in output
    _APPROVED_PATTERNS = [
        r"\bapproved\b",
        r"\bpasses?\b(?:\s+(?:all|the))?\s+(?:review|tests?)",
        r"\blgtm\b",
        r"\ball\s+good\b",
    ]

    _NEEDS_REVISION_PATTERNS = [
        r"\bneeds?\s+(?:revision|changes?|work)\b",
        r"\brequires?\s+(?:changes?|updates?|fixes?)\b",
        r"\bplease\s+(?:fix|update|change)\b",
    ]

    _REJECTED_PATTERNS = [
        r"\brejected\b",
        r"\bblocking\s+issue\b",
        r"\bcritical\s+(?:error|problem|issue)\b",
        r"\bcannot\s+(?:approve|pass)\b",
    ]

    def __init__(
        self,
        session_spawner: SessionSpawner,
        git_service: GitService,
        plan_manager: PlanStateManager,
        notifier: Notifier | None = None,
    ) -> None:
        """Initialize the review service.

        Args:
            session_spawner: Service for spawning sessions.
            git_service: Service for git operations.
            plan_manager: Manager for updating task status.
            notifier: Optional notifier for alerts.
        """
        self.session_spawner = session_spawner
        self.git_service = git_service
        self.plan_manager = plan_manager
        self.notifier = notifier

        # Track active reviews
        self._active_reviews: dict[str, TaskReview] = {}

    # =========================================================================
    # Public API
    # =========================================================================

    async def build_review_context(
        self,
        project: Project,
        task: Task,
        config: ReviewContextConfig | None = None,
    ) -> ReviewContext:
        """Gather all context needed for review.

        Builds a ReviewContext containing task definition, git diff,
        test results, and other relevant information based on the
        configuration.

        Args:
            project: The project containing the task.
            task: The task to review.
            config: Optional config specifying what context to include.
                    Defaults to including task definition, git diff, and tests.

        Returns:
            ReviewContext with requested context sections populated.

        Raises:
            ReviewContextError: If building context fails.
        """
        config = config or ReviewContextConfig()
        context = ReviewContext(task_id=task.id)

        try:
            if config.include_task_definition:
                context.task_definition = self._format_task_definition(task)

            if config.include_git_diff:
                try:
                    base_branch = (
                        project.git_config.default_branch
                        if project.git_config
                        else "main"
                    )
                    context.git_diff = await self.git_service.get_diff(
                        Path(project.path),
                        base_branch=base_branch,
                    )
                except Exception as e:
                    logger.warning(f"Failed to get git diff for review: {e}")
                    context.git_diff = f"[Error getting diff: {e}]"

            if config.include_test_results:
                context.test_results = await self._run_tests(project)

            if config.include_lint_results:
                context.lint_results = await self._run_lint(project)

        except Exception as e:
            raise ReviewContextError(
                f"Failed to build review context: {e}",
                context={"task_id": task.id, "project_id": project.id},
                cause=e,
            ) from e

        return context

    async def run_review(
        self,
        project: Project,
        task: Task,
        context: ReviewContext,
    ) -> TaskReview:
        """Run the full review pipeline.

        Executes the review command with the provided context, parses
        the output, creates a review record, and handles the result
        (updating task status and sending notifications).

        Args:
            project: The project containing the task.
            task: The task to review.
            context: Pre-built review context.

        Returns:
            TaskReview with result, issues, and summary.

        Raises:
            ReviewError: If the review fails.
        """
        config = project.review_config or ReviewConfig()

        # Create pending review record
        review = TaskReview(
            id=generate_id(),
            task_id=task.id,
            attempt=task.revision_count + 1,
            result=ReviewResult.PENDING,
            issues=[],
            summary="",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command=config.command,
            raw_output=None,
        )
        self._active_reviews[task.id] = review

        try:
            # Run the review command and get output
            raw_output = await self._run_review_command(
                project=project,
                task=task,
                context=context,
                command=config.command,
                model=config.model,
            )
            review.raw_output = raw_output

            # Parse the output into structured result
            parsed = await self._parse_review_output(raw_output, task)

            # Update review record with parsed results
            review.result = parsed.result
            review.issues = parsed.issues
            review.summary = parsed.summary
            review.blocking = parsed.blocking

            # Handle the result (update task status, notify)
            await self._handle_review_result(project, task, review, config)

        except Exception as e:
            logger.error(f"Review failed for task {task.id}: {e}")
            review.result = ReviewResult.NEEDS_REVISION
            review.summary = f"Review failed: {e}"
            raise ReviewError(
                f"Review failed for task {task.id}",
                context={"task_id": task.id, "project_id": project.id},
                cause=e,
            ) from e
        finally:
            self._active_reviews.pop(task.id, None)

        return review

    def get_active_review(self, task_id: str) -> TaskReview | None:
        """Get the currently active review for a task.

        Args:
            task_id: The task ID to look up.

        Returns:
            The active TaskReview if one exists, None otherwise.
        """
        return self._active_reviews.get(task_id)

    def is_review_in_progress(self, task_id: str) -> bool:
        """Check if a review is currently in progress for a task.

        Args:
            task_id: The task ID to check.

        Returns:
            True if a review is in progress.
        """
        return task_id in self._active_reviews

    # =========================================================================
    # Review Command Execution
    # =========================================================================

    async def _run_review_command(
        self,
        project: Project,
        task: Task,
        context: ReviewContext,
        command: str,
        model: str | None,
    ) -> str:
        """Execute the review slash command.

        Spawns a review session, sends the formatted context as input,
        and waits for the review to complete.

        Args:
            project: Project context.
            task: Task being reviewed.
            context: Review context with diff, tests, etc.
            command: Slash command to run (e.g., "/review-task").
            model: Optional model override.

        Returns:
            Raw output from the review command.

        Raises:
            ReviewCommandError: If the review command fails.
        """
        # Format the review prompt with context
        prompt = self._format_review_prompt(task, context)

        try:
            # Build the full command string
            # Format: claude <command> with context piped in or as argument
            full_command = f"claude {command}"
            if model:
                full_command = f"claude --model {model} {command}"

            # Create session template for the review
            template = SessionTemplate(
                id=f"review-{task.id}",
                name=f"Review: {task.title[:30]}",
                command=full_command,
                working_dir=project.path,
            )

            # Get project window for spawning in same window
            window = await self._get_project_window(project)

            # Spawn the review session
            result = await self.session_spawner.spawn_session(
                template=template,
                project=project,
                window=window,
            )

            if not result.success:
                raise ReviewCommandError(
                    f"Failed to spawn review session: {result.error}",
                    context={"task_id": task.id},
                )

            # Get the managed session
            session = self.session_spawner.get_session(result.session_id)
            if session:
                session.session_type = SessionType.REVIEW
                session.task_id = task.id

            # In a real implementation, we would:
            # 1. Send the prompt to the session
            # 2. Monitor output for completion markers
            # 3. Capture and return the review output
            #
            # For now, we'll simulate waiting for output
            # The actual implementation would use the session monitor
            # to capture output and detect when the review is complete.

            # Wait a reasonable time for review (this is a placeholder)
            await asyncio.sleep(0.1)

            # Return placeholder - in production this would be captured output
            logger.info(f"Review session spawned for task {task.id}")
            return f"[Review session spawned - output capture not yet implemented]\n\nContext:\n{prompt}"

        except ReviewCommandError:
            raise
        except Exception as e:
            raise ReviewCommandError(
                f"Failed to run review command: {e}",
                context={"task_id": task.id, "command": command},
                cause=e,
            ) from e

    async def _get_project_window(self, project: Project) -> Any:
        """Get the iTerm2 window for a project's sessions.

        Looks for an existing session for the project and uses its window.
        This ensures review sessions spawn as tabs in the same window.

        Args:
            project: The project to find a window for.

        Returns:
            The iTerm2 window if found, None otherwise.
        """
        # Look for existing sessions in this project
        project_sessions = self.session_spawner.get_sessions_for_project(project.id)

        if not project_sessions:
            return None

        # Get the window from an existing session
        for session in project_sessions:
            if session.window_id:
                app = self.session_spawner.controller.app
                if app:
                    for window in app.windows:
                        if window.window_id == session.window_id:
                            return window
                break

        return None

    # =========================================================================
    # Output Parsing
    # =========================================================================

    async def _parse_review_output(
        self,
        raw_output: str,
        task: Task,
    ) -> ParsedReviewResult:
        """Parse review output to extract structured result.

        Uses pattern matching to determine the review result and extract
        issues. In the future, this could use a parser subagent for more
        sophisticated interpretation.

        Args:
            raw_output: Free-form review output.
            task: The reviewed task.

        Returns:
            ParsedReviewResult with structured data.
        """
        output_lower = raw_output.lower()

        # Determine result based on patterns
        result = self._detect_result(output_lower)

        # Extract issues (look for bullet points, numbered items, or "issue:" patterns)
        issues = self._extract_issues(raw_output)

        # Extract summary (first paragraph or sentence)
        summary = self._extract_summary(raw_output)

        # Check for blocking indicators
        blocking = self._detect_blocking(output_lower)

        return ParsedReviewResult(
            result=result,
            issues=issues,
            summary=summary,
            blocking=blocking,
        )

    def _detect_result(self, output_lower: str) -> ReviewResult:
        """Detect the review result from output text.

        Checks for approval, revision, or rejection patterns.
        Defaults to NEEDS_REVISION if unclear.

        Args:
            output_lower: Lowercase output text.

        Returns:
            Detected ReviewResult.
        """
        # Check for rejection first (highest priority)
        for pattern in self._REJECTED_PATTERNS:
            if re.search(pattern, output_lower):
                return ReviewResult.REJECTED

        # Check for needs revision
        for pattern in self._NEEDS_REVISION_PATTERNS:
            if re.search(pattern, output_lower):
                return ReviewResult.NEEDS_REVISION

        # Check for approval
        for pattern in self._APPROVED_PATTERNS:
            if re.search(pattern, output_lower):
                return ReviewResult.APPROVED

        # Default to needs revision if unclear
        return ReviewResult.NEEDS_REVISION

    def _extract_issues(self, output: str) -> list[str]:
        """Extract issues from review output.

        Looks for bullet points, numbered items, and "issue:" patterns.

        Args:
            output: Raw review output.

        Returns:
            List of issue descriptions.
        """
        issues: list[str] = []

        # Match bullet points: - text, * text, • text
        bullet_pattern = r"^[\s]*[-*•]\s+(.+?)$"
        for match in re.finditer(bullet_pattern, output, re.MULTILINE):
            issue = match.group(1).strip()
            if issue and len(issue) > 10:  # Skip very short items
                issues.append(issue)

        # Match numbered items: 1. text, 1) text
        numbered_pattern = r"^[\s]*\d+[.)]\s+(.+?)$"
        for match in re.finditer(numbered_pattern, output, re.MULTILINE):
            issue = match.group(1).strip()
            if issue and len(issue) > 10:
                issues.append(issue)

        # Match "Issue:" or "Problem:" patterns
        issue_pattern = r"(?:issue|problem|error|bug|fix|todo):\s*(.+?)(?:\n|$)"
        for match in re.finditer(issue_pattern, output, re.IGNORECASE):
            issue = match.group(1).strip()
            if issue:
                issues.append(issue)

        # Deduplicate while preserving order
        seen = set()
        unique_issues = []
        for issue in issues:
            if issue not in seen:
                seen.add(issue)
                unique_issues.append(issue)

        return unique_issues[:10]  # Limit to 10 issues

    def _extract_summary(self, output: str) -> str:
        """Extract a summary from review output.

        Takes the first paragraph or sentence that looks like a summary.

        Args:
            output: Raw review output.

        Returns:
            Summary text (1-2 sentences).
        """
        # Skip any leading whitespace or headers
        lines = output.strip().split("\n")

        summary_lines = []
        for line in lines:
            line = line.strip()

            # Skip empty lines, headers, and code blocks
            if not line or line.startswith("#") or line.startswith("```"):
                if summary_lines:
                    break
                continue

            # Skip bullet points and numbered items
            if re.match(r"^[-*•\d]", line):
                continue

            summary_lines.append(line)

            # Stop after ~200 characters
            if sum(len(l) for l in summary_lines) > 200:
                break

        summary = " ".join(summary_lines)

        # Truncate if too long
        if len(summary) > 300:
            summary = summary[:297] + "..."

        return summary

    def _detect_blocking(self, output_lower: str) -> bool:
        """Detect if the review indicates a blocking issue.

        Blocking issues require human intervention regardless of
        the number of revision attempts.

        Args:
            output_lower: Lowercase output text.

        Returns:
            True if blocking, False otherwise.
        """
        blocking_patterns = [
            r"\bblocking\b",
            r"\bsecurity\s+(?:issue|vulnerability|risk)\b",
            r"\bdata\s+(?:loss|corruption)\b",
            r"\bbreaking\s+change\b",
            r"\brequires?\s+human\b",
            r"\bmanual\s+intervention\b",
            r"\barchitectural\s+(?:issue|problem)\b",
        ]

        for pattern in blocking_patterns:
            if re.search(pattern, output_lower):
                return True

        return False

    # =========================================================================
    # Result Handling
    # =========================================================================

    async def _handle_review_result(
        self,
        project: Project,
        task: Task,
        review: TaskReview,
        config: ReviewConfig,
    ) -> None:
        """Update task status and notify based on review result.

        Handles the three possible outcomes:
        - APPROVED: Mark task as complete
        - NEEDS_REVISION: Send back for revision or block if max attempts reached
        - REJECTED: Block task and notify (blocking issue)

        Args:
            project: Project context.
            task: Reviewed task.
            review: The review result.
            config: Review configuration.
        """
        if review.result == ReviewResult.APPROVED:
            # Task completed successfully
            self.plan_manager.update_task_status(project.id, task.id)
            # Note: The actual status change would be done by the caller
            # after updating the task object. This just notifies.
            logger.info(f"Task {task.id} approved by review")

        elif review.result == ReviewResult.NEEDS_REVISION:
            if review.attempt >= config.max_revisions:
                # Max revisions reached - need human intervention
                self.plan_manager.update_task_status(project.id, task.id)
                logger.warning(
                    f"Task {task.id} blocked after {review.attempt} failed reviews"
                )

                if self.notifier:
                    await self.notifier.notify(
                        title=f"Review Failed: {task.title[:30]}",
                        message=f"Task needs human review after {review.attempt} attempts",
                        sound="Basso",
                    )
            else:
                # Send back for revision
                self.plan_manager.update_task_status(project.id, task.id)
                logger.info(
                    f"Task {task.id} needs revision (attempt {review.attempt}/{config.max_revisions})"
                )

        elif review.result == ReviewResult.REJECTED:
            # Blocking issue - needs human regardless of attempt count
            self.plan_manager.update_task_status(project.id, task.id)
            logger.warning(f"Task {task.id} rejected: {review.summary}")

            if self.notifier:
                await self.notifier.notify(
                    title=f"Review Rejected: {task.title[:30]}",
                    message=f"Blocking issue: {review.summary[:100]}",
                    sound="Basso",
                )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _format_task_definition(self, task: Task) -> str:
        """Format task definition for review context.

        Creates a markdown-formatted representation of the task
        including title, scope, and acceptance criteria.

        Args:
            task: The task to format.

        Returns:
            Formatted task definition.
        """
        parts = [f"# Task {task.id}: {task.title}"]

        if task.scope:
            parts.append(f"\n## Scope\n{task.scope}")

        if task.acceptance:
            parts.append(f"\n## Acceptance Criteria\n{task.acceptance}")

        if task.notes:
            parts.append(f"\n## Notes\n" + "\n".join(f"- {n}" for n in task.notes))

        return "\n".join(parts)

    def _format_review_prompt(
        self,
        task: Task,
        context: ReviewContext,
    ) -> str:
        """Format the complete prompt for the review command.

        Combines all context sections into a single review prompt.

        Args:
            task: The task being reviewed.
            context: Review context with diff, tests, etc.

        Returns:
            Complete formatted prompt.
        """
        sections = []

        if context.task_definition:
            sections.append(context.task_definition)

        if context.git_diff:
            sections.append(f"## Git Diff\n```diff\n{context.git_diff}\n```")

        if context.test_results:
            sections.append(f"## Test Results\n```\n{context.test_results}\n```")

        if context.lint_results:
            sections.append(f"## Lint Results\n```\n{context.lint_results}\n```")

        return "\n\n".join(sections)

    async def _run_tests(self, project: Project) -> str | None:
        """Run tests and capture output.

        Attempts to detect and run the project's test command.

        Args:
            project: The project to test.

        Returns:
            Test output, or None if tests couldn't be run.
        """
        # Detect test command based on project structure
        project_path = Path(project.path)

        test_commands = []

        # Python projects
        if (project_path / "pytest.ini").exists() or (
            project_path / "pyproject.toml"
        ).exists():
            test_commands.append("pytest -v --tb=short")

        # Node.js projects
        if (project_path / "package.json").exists():
            test_commands.append("npm test")

        # Make-based projects
        if (project_path / "Makefile").exists():
            test_commands.append("make test")

        if not test_commands:
            return None

        # Try each test command
        for cmd in test_commands:
            try:
                result = await asyncio.create_subprocess_shell(
                    cmd,
                    cwd=project_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                stdout, _ = await asyncio.wait_for(
                    result.communicate(),
                    timeout=120,  # 2 minute timeout
                )
                return stdout.decode(errors="replace")
            except asyncio.TimeoutError:
                return "[Test timeout after 2 minutes]"
            except Exception as e:
                logger.debug(f"Test command '{cmd}' failed: {e}")
                continue

        return None

    async def _run_lint(self, project: Project) -> str | None:
        """Run linter and capture output.

        Attempts to detect and run the project's lint command.

        Args:
            project: The project to lint.

        Returns:
            Lint output, or None if linting couldn't be run.
        """
        project_path = Path(project.path)

        lint_commands = []

        # Python projects
        if (project_path / "pyproject.toml").exists():
            lint_commands.append("ruff check .")

        # Node.js projects
        if (project_path / "package.json").exists():
            lint_commands.append("npm run lint")

        if not lint_commands:
            return None

        # Try each lint command
        for cmd in lint_commands:
            try:
                result = await asyncio.create_subprocess_shell(
                    cmd,
                    cwd=project_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                stdout, _ = await asyncio.wait_for(
                    result.communicate(),
                    timeout=60,  # 1 minute timeout
                )
                return stdout.decode(errors="replace")
            except asyncio.TimeoutError:
                return "[Lint timeout after 1 minute]"
            except Exception as e:
                logger.debug(f"Lint command '{cmd}' failed: {e}")
                continue

        return None


# =============================================================================
# Review State Manager
# =============================================================================


class ReviewStateManager:
    """Manages review state for tasks.

    Tracks active reviews and provides methods to start, complete, and
    query review status. Posts events to the Textual app for UI updates.

    Attributes:
        active_reviews: Dictionary of currently running reviews by task ID.
    """

    def __init__(self) -> None:
        """Initialize the review state manager."""
        self.active_reviews: dict[str, TaskReview] = {}
        self._app: Any = None

    def connect_app(self, app: Any) -> None:
        """Connect to a Textual App for message posting.

        Args:
            app: The Textual App instance.
        """
        self._app = app

    def _post_message(self, message: Any) -> None:
        """Post a message to the connected Textual app."""
        if self._app is not None:
            self._app.post_message(message)

    async def start_review(
        self,
        task_id: str,
        project_id: str,
    ) -> TaskReview:
        """Start a new review for a task.

        Creates a pending review record and emits a ReviewStarted event.

        Args:
            task_id: The task ID.
            project_id: The project ID.

        Returns:
            The pending TaskReview.
        """
        review = TaskReview(
            id=generate_id(),
            task_id=task_id,
            attempt=1,
            result=ReviewResult.PENDING,
            issues=[],
            summary="",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="",
        )
        self.active_reviews[task_id] = review

        # Note: Event posting would go here when events are implemented
        logger.info(f"Started review for task {task_id}")

        return review

    async def complete_review(
        self,
        task_id: str,
        result: ParsedReviewResult,
    ) -> None:
        """Complete an active review with the parsed result.

        Updates the review with results and emits ReviewCompleted
        or ReviewFailed event.

        Args:
            task_id: The task ID.
            result: The parsed review result.
        """
        review = self.active_reviews.get(task_id)
        if not review:
            logger.warning(f"No active review found for task {task_id}")
            return

        review.result = result.result
        review.issues = result.issues
        review.summary = result.summary
        review.blocking = result.blocking

        # Note: Event posting would go here when events are implemented
        logger.info(f"Completed review for task {task_id}: {result.result.value}")

        del self.active_reviews[task_id]

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
        """Clear all active reviews."""
        self.active_reviews.clear()
