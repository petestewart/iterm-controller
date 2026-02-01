"""Task queue widget for Work Mode.

Displays pending tasks that can be claimed, ordered by phase and availability.
Blocked tasks are shown with dimmed styling and blocked-by information.
"""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.binding import Binding
from textual.widgets import Static

from iterm_controller.models import Plan, Task, TaskStatus


class TaskQueueWidget(Static, can_focus=True):
    """Displays pending tasks that can be claimed.

    Shows available tasks (no blockers) and blocked tasks separately:
    - Available: ○ icon, can be selected for claiming
    - Blocked: ⊘ icon, dimmed, shows "blocked by X, Y"

    Tasks are ordered by:
    1. Phase order
    2. Dependencies (available before blocked)
    3. Task ID
    """

    DEFAULT_CSS = """
    TaskQueueWidget {
        height: auto;
        min-height: 5;
        padding: 0 1;
        border: solid $surface-lighten-2;
    }

    TaskQueueWidget:focus {
        border: solid $accent;
    }

    TaskQueueWidget .title {
        text-style: bold;
        padding-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
    ]

    def __init__(
        self,
        plan: Plan | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the task queue widget.

        Args:
            plan: Initial plan to display tasks from.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self._plan = plan or Plan()
        self._task_lookup: dict[str, Task] = {}
        self._selected_index: int = 0
        self._visible_tasks: list[Task] = []
        self._rebuild_task_lookup()
        self._rebuild_visible_tasks()

    @property
    def plan(self) -> Plan:
        """Get the current plan."""
        return self._plan

    @property
    def selected_task(self) -> Task | None:
        """Get the currently selected task."""
        if 0 <= self._selected_index < len(self._visible_tasks):
            return self._visible_tasks[self._selected_index]
        return None

    @property
    def selected_index(self) -> int:
        """Get the current selection index."""
        return self._selected_index

    def refresh_plan(self, plan: Plan) -> None:
        """Update the displayed plan.

        Args:
            plan: New plan to display.
        """
        self._plan = plan
        self._rebuild_task_lookup()
        self._rebuild_visible_tasks()
        # Ensure selected index is valid
        if self._selected_index >= len(self._visible_tasks):
            self._selected_index = max(0, len(self._visible_tasks) - 1)
        self.update(self._render_queue())

    def _rebuild_task_lookup(self) -> None:
        """Rebuild the task lookup dictionary for dependency resolution."""
        self._task_lookup = {}
        for task in self._plan.all_tasks:
            self._task_lookup[task.id] = task

    def _rebuild_visible_tasks(self) -> None:
        """Rebuild the list of visible (pending and blocked) tasks."""
        self._visible_tasks = []
        for task in self._plan.all_tasks:
            if task.status in (TaskStatus.PENDING, TaskStatus.BLOCKED):
                self._visible_tasks.append(task)

    def is_task_blocked(self, task: Task) -> bool:
        """Check if a task is blocked by incomplete dependencies.

        Args:
            task: The task to check.

        Returns:
            True if the task is blocked, False otherwise.
        """
        if task.status == TaskStatus.BLOCKED:
            return True
        if not task.depends:
            return False
        for dep_id in task.depends:
            dep_task = self._task_lookup.get(dep_id)
            if dep_task and dep_task.status not in (
                TaskStatus.COMPLETE,
                TaskStatus.SKIPPED,
            ):
                return True
        return False

    def get_blocking_tasks(self, task: Task) -> list[str]:
        """Get the IDs of tasks blocking this task.

        Args:
            task: The task to check.

        Returns:
            List of task IDs that are blocking this task.
        """
        blockers = []
        for dep_id in task.depends:
            dep_task = self._task_lookup.get(dep_id)
            if dep_task and dep_task.status not in (
                TaskStatus.COMPLETE,
                TaskStatus.SKIPPED,
            ):
                blockers.append(dep_id)
        return blockers

    def get_available_tasks(self) -> list[Task]:
        """Get tasks that are available to claim (not blocked).

        Returns:
            List of pending tasks that have no incomplete dependencies.
        """
        return [t for t in self._visible_tasks if not self.is_task_blocked(t)]

    def get_blocked_tasks(self) -> list[Task]:
        """Get tasks that are blocked by dependencies.

        Returns:
            List of pending tasks that have incomplete dependencies.
        """
        return [t for t in self._visible_tasks if self.is_task_blocked(t)]

    def select_next(self) -> None:
        """Select the next task in the queue."""
        if self._visible_tasks:
            self._selected_index = (self._selected_index + 1) % len(self._visible_tasks)
            self.update(self._render_queue())

    def select_previous(self) -> None:
        """Select the previous task in the queue."""
        if self._visible_tasks:
            self._selected_index = (self._selected_index - 1) % len(self._visible_tasks)
            self.update(self._render_queue())

    def action_cursor_down(self) -> None:
        """Handle down arrow key."""
        self.select_next()

    def action_cursor_up(self) -> None:
        """Handle up arrow key."""
        self.select_previous()

    def _render_task(self, task: Task, is_selected: bool) -> Text:
        """Render a single task row.

        Args:
            task: The task to render.
            is_selected: Whether this task is currently selected.

        Returns:
            Rich Text object for the task row.
        """
        is_blocked = self.is_task_blocked(task)
        blockers = self.get_blocking_tasks(task) if is_blocked else []

        text = Text()

        # Selection indicator
        if is_selected:
            text.append("▸ ", style="bold cyan")
        else:
            text.append("  ")

        if is_blocked:
            # Render as dimmed/blocked
            text.append("⊘ ", style="dim")
            text.append(f"{task.id} {task.title}", style="dim")
            if blockers:
                blocker_str = ", ".join(blockers)
                text.append(f"  blocked by {blocker_str}", style="dim italic")
        else:
            # Render as available
            text.append("○ ", style="white")
            text.append(f"{task.id} {task.title}")

        return text

    def _render_queue(self) -> Text:
        """Render the complete task queue.

        Returns:
            Rich Text object containing the queue header and tasks.
        """
        available = self.get_available_tasks()
        blocked = self.get_blocked_tasks()
        total = len(self._visible_tasks)

        text = Text()

        # Header with count
        text.append("Task Queue", style="bold")
        text.append(f"  {total} left", style="dim")
        text.append("\n")

        if not self._visible_tasks:
            text.append("  No pending tasks", style="dim italic")
            return text

        # Render available tasks first, then blocked
        all_tasks = available + blocked
        for i, task in enumerate(all_tasks):
            # Find original index for selection
            orig_index = self._visible_tasks.index(task)
            is_selected = orig_index == self._selected_index
            text.append_text(self._render_task(task, is_selected))
            if i < len(all_tasks) - 1:
                text.append("\n")

        return text

    def render(self) -> Text:
        """Render the widget content.

        Returns:
            Rich Text object to display.
        """
        return self._render_queue()
