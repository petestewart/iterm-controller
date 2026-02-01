"""Blocked tasks widget for Work Mode.

Displays a summary of blocked tasks and their dependencies at the bottom of
the task queue panel.
"""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.widgets import Static

from iterm_controller.models import Plan, Task, TaskStatus
from iterm_controller.task_dependency import TaskDependencyResolver


class BlockedTasksWidget(Static):
    """Displays blocked task summary with dependency chains.

    Shows a compact view of blocked tasks:
        Blocked: 2
          2.2 Create login form ← 2.1 Add auth middleware
          2.3 Session persistence ← 2.1, 2.2

    This widget works alongside TaskQueueWidget to provide a quick overview
    of what tasks are waiting on dependencies.
    """

    DEFAULT_CSS = """
    BlockedTasksWidget {
        height: auto;
        min-height: 3;
        max-height: 10;
        padding: 0 1;
        margin-top: 1;
        border: solid $surface-lighten-1;
        background: $surface;
    }

    BlockedTasksWidget .blocked-header {
        text-style: bold;
        color: $warning;
    }
    """

    def __init__(
        self,
        plan: Plan | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the blocked tasks widget.

        Args:
            plan: Initial plan to display blocked tasks from.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self._plan = plan or Plan()
        self._dependency_resolver = TaskDependencyResolver(self._plan)

    @property
    def plan(self) -> Plan:
        """Get the current plan."""
        return self._plan

    def refresh_plan(self, plan: Plan) -> None:
        """Update the displayed plan.

        Args:
            plan: New plan to display.
        """
        self._plan = plan
        self._dependency_resolver.update_plan(plan)
        self.update(self._render_blocked())

    def is_task_blocked(self, task: Task) -> bool:
        """Check if a task is blocked by incomplete dependencies.

        Delegates to TaskDependencyResolver.

        Args:
            task: The task to check.

        Returns:
            True if the task is blocked, False otherwise.
        """
        return self._dependency_resolver.is_task_blocked(task)

    def get_blocked_tasks(self) -> list[Task]:
        """Get all blocked tasks from the plan.

        Returns:
            List of tasks that have incomplete dependencies.
        """
        blocked = []
        for task in self._plan.all_tasks:
            if task.status in (TaskStatus.PENDING, TaskStatus.BLOCKED):
                if self.is_task_blocked(task):
                    blocked.append(task)
        return blocked

    def get_blocking_task_ids(self, task: Task) -> list[str]:
        """Get IDs of tasks that are blocking this task.

        Delegates to TaskDependencyResolver.

        Args:
            task: The task to check.

        Returns:
            List of task IDs that are blocking this task.
        """
        return self._dependency_resolver.get_blocking_tasks(task)

    def get_dependency_chain(self, task: Task) -> list[tuple[Task, list[str]]]:
        """Get the full dependency chain for a task.

        Delegates to TaskDependencyResolver.

        Args:
            task: The task to get the dependency chain for.

        Returns:
            List of (task, blockers) tuples showing the dependency chain.
        """
        return self._dependency_resolver.get_dependency_chain(task)

    def _render_blocked(self) -> Text:
        """Render the blocked tasks summary.

        Returns:
            Rich Text object containing the blocked tasks view.
        """
        blocked = self.get_blocked_tasks()
        text = Text()

        # Header
        text.append("Blocked", style="bold")
        text.append(f": {len(blocked)}\n", style="dim")

        if not blocked:
            text.append("  No blocked tasks", style="dim italic")
            return text

        # Show each blocked task with its blockers
        for i, task in enumerate(blocked):
            blockers = self.get_blocking_task_ids(task)
            blocker_str = ", ".join(blockers)

            text.append(f"  {task.id}", style="dim")
            text.append(f" {task.title[:25]}", style="dim")
            if len(task.title) > 25:
                text.append("...", style="dim")
            text.append(" ← ", style="yellow")
            text.append(blocker_str, style="dim italic")

            if i < len(blocked) - 1:
                text.append("\n")

        return text

    def render(self) -> Text:
        """Render the widget content.

        Returns:
            Rich Text object to display.
        """
        return self._render_blocked()
