# Review Service

## Overview

The ReviewService orchestrates automatic code review when tasks are completed. It builds context, runs a configurable review slash command, parses the output via a subagent, and handles the result (approve, request revision, or reject).

## Pipeline Flow

```
+----------------+      +----------------+      +----------------+
|    Context     |      |    /review     |      |    /parse-     |
|    Builder     | ---> |    (config)    | ---> |    review      |
|                |      |                |      |    (parser)    |
+----------------+      +----------------+      +----------------+
       |                      |                       |
       v                      v                       v
Task definition         Free-form review        Structured JSON
+ git diff              analysis output         {approved, issues, ...}
+ test results
```

## ReviewService Class

```python
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .session_spawner import SessionSpawner
    from .git_service import GitService
    from .plan_manager import PlanStateManager
    from .notifications import Notifier

class ReviewService:
    """Orchestrates the review pipeline for completed tasks."""

    def __init__(
        self,
        session_spawner: "SessionSpawner",
        git_service: "GitService",
        plan_manager: "PlanStateManager",
        notifier: "Notifier | None" = None
    ):
        self.session_spawner = session_spawner
        self.git_service = git_service
        self.plan_manager = plan_manager
        self.notifier = notifier

    async def build_review_context(
        self,
        project: "Project",
        task: "Task",
        config: "ReviewContextConfig | None" = None
    ) -> "ReviewContext":
        """Gather all context needed for review.

        Args:
            project: The project containing the task
            task: The task to review
            config: Optional config specifying what context to include

        Returns:
            ReviewContext with task definition, git diff, test results, etc.
        """
        config = config or ReviewContextConfig()
        context = ReviewContext(task_id=task.id)

        if config.include_task_definition:
            context.task_definition = self._format_task_definition(task)

        if config.include_git_diff:
            context.git_diff = await self.git_service.get_diff(
                project.path,
                base_branch=project.git_config.default_branch if project.git_config else "main"
            )

        if config.include_test_results:
            context.test_results = await self._run_tests(project)

        if config.include_lint_results:
            context.lint_results = await self._run_lint(project)

        return context

    async def run_review(
        self,
        project: "Project",
        task: "Task",
        context: "ReviewContext"
    ) -> "TaskReview":
        """Run the full review pipeline.

        Args:
            project: The project containing the task
            task: The task to review
            context: Pre-built review context

        Returns:
            TaskReview with result and issues
        """
        config = project.review_config or ReviewConfig()

        # Run the review command
        raw_output = await self._run_review_command(
            project=project,
            task=task,
            context=context,
            command=config.command,
            model=config.model
        )

        # Parse the output into structured result
        parsed = await self._parse_review_output(raw_output, task)

        # Create the review record
        review = TaskReview(
            id=generate_id(),
            task_id=task.id,
            attempt=task.revision_count + 1,
            result=parsed.result,
            issues=parsed.issues,
            summary=parsed.summary,
            blocking=parsed.blocking,
            reviewed_at=datetime.now(),
            reviewer_command=config.command,
            raw_output=raw_output
        )

        # Handle the result
        await self._handle_review_result(project, task, review, config)

        return review

    async def _run_review_command(
        self,
        project: "Project",
        task: "Task",
        context: "ReviewContext",
        command: str,
        model: str | None
    ) -> str:
        """Execute the review slash command.

        Args:
            project: Project context
            task: Task being reviewed
            context: Review context with diff, tests, etc.
            command: Slash command to run (e.g., "/review-task")
            model: Optional model override

        Returns:
            Raw output from the review command
        """
        # Format the prompt with context
        prompt = self._format_review_prompt(task, context)

        # Spawn a review session
        session = await self.session_spawner.spawn_review_session(
            project=project,
            command=command,
            prompt=prompt,
            model=model
        )

        # Wait for completion and capture output
        output = await session.wait_for_completion()
        return output

    async def _parse_review_output(
        self,
        raw_output: str,
        task: "Task"
    ) -> "ParsedReviewResult":
        """Run the parser subagent to extract structured result.

        Args:
            raw_output: Free-form review output
            task: The reviewed task

        Returns:
            ParsedReviewResult with structured data
        """
        # Run a lightweight parsing command
        parser_prompt = f"""
        Parse the following review output and extract:
        - result: APPROVED, NEEDS_REVISION, or REJECTED
        - issues: List of specific issues found
        - summary: Brief summary (1-2 sentences)
        - blocking: True if needs human intervention regardless of attempt count

        Review output:
        {raw_output}
        """

        # Use a fast model for parsing
        result = await self.session_spawner.run_parser(
            command="/parse-review",
            prompt=parser_prompt
        )

        return ParsedReviewResult(
            result=ReviewResult(result.get("result", "needs_revision")),
            issues=result.get("issues", []),
            summary=result.get("summary", ""),
            blocking=result.get("blocking", False)
        )

    async def _handle_review_result(
        self,
        project: "Project",
        task: "Task",
        review: "TaskReview",
        config: "ReviewConfig"
    ) -> None:
        """Update task status and notify based on review result.

        Args:
            project: Project context
            task: Reviewed task
            review: The review result
            config: Review configuration
        """
        if review.result == ReviewResult.APPROVED:
            await self.plan_manager.update_task_status(
                project.id, task.id, TaskStatus.COMPLETE
            )

        elif review.result == ReviewResult.NEEDS_REVISION:
            if review.attempt >= config.max_revisions:
                # Max revisions reached - need human
                await self.plan_manager.update_task_status(
                    project.id, task.id, TaskStatus.BLOCKED
                )
                if self.notifier:
                    await self.notifier.notify_with_sound(
                        title=f"Review Failed: {task.title}",
                        message=f"Task needs human review after {review.attempt} attempts",
                        sound="Basso"
                    )
            else:
                # Send back for revision
                await self.plan_manager.update_task_revision(
                    project.id, task.id, review
                )

        elif review.result == ReviewResult.REJECTED:
            # Blocking issue - needs human regardless of attempt count
            await self.plan_manager.update_task_status(
                project.id, task.id, TaskStatus.BLOCKED
            )
            if self.notifier:
                await self.notifier.notify_with_sound(
                    title=f"Review Rejected: {task.title}",
                    message=f"Blocking issue found: {review.summary}",
                    sound="Basso"
                )

    def _format_task_definition(self, task: "Task") -> str:
        """Format task definition for review context."""
        parts = [f"# Task {task.id}: {task.title}"]
        if task.scope:
            parts.append(f"\n## Scope\n{task.scope}")
        if task.acceptance:
            parts.append(f"\n## Acceptance Criteria\n{task.acceptance}")
        return "\n".join(parts)

    def _format_review_prompt(
        self,
        task: "Task",
        context: "ReviewContext"
    ) -> str:
        """Format the complete prompt for the review command."""
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
```

## Context Building

ReviewContext includes data based on ReviewContextConfig:

```python
@dataclass
class ReviewContext:
    """Context provided to the reviewer."""
    task_id: str
    task_definition: str | None = None   # Task title, scope, acceptance criteria
    git_diff: str | None = None          # Changes since base branch
    test_results: str | None = None      # Test output if run
    lint_results: str | None = None      # Lint output if run
    session_log: str | None = None       # Session output (often too verbose)

@dataclass
class ReviewContextConfig:
    """What context to provide to the reviewer."""
    include_task_definition: bool = True
    include_git_diff: bool = True
    include_test_results: bool = True
    include_lint_results: bool = False
    include_session_log: bool = False    # Usually too verbose
```

Default configuration includes task_definition + git_diff + test_results.

## Review Command

The configured slash command (default: `/review-task`) receives the context and produces a free-form review. The command can output whatever format it wants - human-readable analysis is fine.

```python
# Example review command invocation
await session_spawner.spawn_review_session(
    project=project,
    command="/review-task",
    prompt=formatted_context,
    model="claude-sonnet"  # Optional model override
)
```

## Parser Subagent

A separate lightweight command (`/parse-review`) reads the review output and extracts structured data:

```python
@dataclass
class ParsedReviewResult:
    """Structured result extracted from review output."""
    result: ReviewResult      # APPROVED, NEEDS_REVISION, REJECTED
    issues: list[str]         # Specific issues found
    summary: str              # Brief summary
    blocking: bool            # If true, needs human regardless of attempt count
```

This separation lets the review command focus on quality analysis while the parser normalizes output.

## Result Handling

```python
async def _handle_review_result(self, project, task, review, config):
    """Handle review result by updating task status."""

    if review.result == ReviewResult.APPROVED:
        # Task completed successfully
        await self.plan_manager.update_task_status(
            project.id, task.id, TaskStatus.COMPLETE
        )

    elif review.result == ReviewResult.NEEDS_REVISION:
        if review.attempt >= config.max_revisions:
            # Max revisions reached - need human intervention
            await self.plan_manager.update_task_status(
                project.id, task.id, TaskStatus.BLOCKED
            )
            if self.notifier:
                await self.notifier.notify_with_sound(
                    title=f"Review Failed: {task.title}",
                    message=f"Task needs human review after {review.attempt} attempts",
                    sound="Basso"
                )
        else:
            # Send back for revision - worker will pick it up again
            await self.plan_manager.update_task_revision(
                project.id, task.id, review
            )

    elif review.result == ReviewResult.REJECTED:
        # Blocking issue - needs human regardless of attempt count
        await self.plan_manager.update_task_status(
            project.id, task.id, TaskStatus.BLOCKED
        )
        if self.notifier:
            await self.notifier.notify_with_sound(
                title=f"Review Rejected: {task.title}",
                message=f"Blocking issue found: {review.summary}",
                sound="Basso"
            )
```

## Review Triggers

Configurable via `ReviewConfig.trigger`:

| Trigger | Description |
|---------|-------------|
| `script_completion` | Review runs when orchestrator script finishes a task |
| `session_idle` | Review runs when session goes idle after working |
| `explicit` | Only run when manually triggered |

## Configuration

```python
@dataclass
class ReviewConfig:
    """Review settings for a project."""
    enabled: bool = True
    command: str = "/review-task"      # Slash command to run
    model: str | None = None           # Override model for review
    max_revisions: int = 3             # Pause after N failed reviews
    trigger: str = "script_completion"
    context: ReviewContextConfig | None = None
```

## ReviewStateManager

```python
class ReviewStateManager:
    """Manages review state for tasks."""

    def __init__(self):
        self.active_reviews: dict[str, TaskReview] = {}  # task_id -> current review

    async def start_review(
        self,
        task_id: str,
        project_id: str
    ) -> TaskReview:
        """Start a new review for a task.

        Posts ReviewStarted message to state.
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
            reviewer_command=""
        )
        self.active_reviews[task_id] = review

        self.state.emit(
            StateEvent.REVIEW_STARTED,
            task_id=task_id,
            project_id=project_id,
            review=review
        )

        return review

    async def complete_review(
        self,
        task_id: str,
        result: ParsedReviewResult
    ) -> None:
        """Complete an active review with the parsed result.

        Posts ReviewCompleted or ReviewFailed message to state.
        """
        review = self.active_reviews.get(task_id)
        if not review:
            return

        review.result = result.result
        review.issues = result.issues
        review.summary = result.summary
        review.blocking = result.blocking

        event = (
            StateEvent.REVIEW_COMPLETED
            if result.result == ReviewResult.APPROVED
            else StateEvent.REVIEW_FAILED
        )

        self.state.emit(event, task_id=task_id, review=review)

        del self.active_reviews[task_id]
```

## Task Status Flow

```
PENDING --> IN_PROGRESS --> AWAITING_REVIEW --> COMPLETE
                 |                |
                 |                v
                 |          [Review runs]
                 |                |
                 |          +-----+-----+
                 |          v           v
                 |      APPROVED   NEEDS_REVISION
                 |          |           |
                 |          v           v
                 |      COMPLETE   (back to worker or BLOCKED after max)
```

## Integration Example

```python
class TaskCompletionHandler:
    """Handles task completion and triggers reviews."""

    def __init__(
        self,
        review_service: ReviewService,
        review_state: ReviewStateManager
    ):
        self.review_service = review_service
        self.review_state = review_state

    async def on_task_completed(
        self,
        project: Project,
        task: Task
    ):
        """Called when a task is marked complete by worker."""
        config = project.review_config or ReviewConfig()

        if not config.enabled:
            # Reviews disabled - mark as complete
            await self.plan_manager.update_task_status(
                project.id, task.id, TaskStatus.COMPLETE
            )
            return

        # Update to awaiting review
        await self.plan_manager.update_task_status(
            project.id, task.id, TaskStatus.AWAITING_REVIEW
        )

        # Start tracking
        await self.review_state.start_review(task.id, project.id)

        # Build context and run review
        context = await self.review_service.build_review_context(
            project, task, config.context
        )
        review = await self.review_service.run_review(project, task, context)

        # Complete tracking
        await self.review_state.complete_review(task.id, ParsedReviewResult(
            result=review.result,
            issues=review.issues,
            summary=review.summary,
            blocking=review.blocking
        ))
```
