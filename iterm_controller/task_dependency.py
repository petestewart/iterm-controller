"""Task dependency resolution utility.

Provides centralized logic for checking task blocking status and resolving
dependency chains. Used by task_list, task_queue, and blocked_tasks widgets.
"""

from __future__ import annotations

from iterm_controller.models import Plan, Task, TaskStatus


class TaskDependencyResolver:
    """Resolves task dependencies and blocking status.

    This class provides a shared implementation for dependency checking
    that can be used by multiple widgets. It maintains a task lookup
    dictionary for O(1) task access by ID.

    Example:
        resolver = TaskDependencyResolver(plan)
        if resolver.is_task_blocked(task):
            blockers = resolver.get_blocking_tasks(task)
            print(f"Task {task.id} is blocked by: {blockers}")
    """

    def __init__(self, plan: Plan | None = None) -> None:
        """Initialize the dependency resolver.

        Args:
            plan: Plan to resolve dependencies for. If None, uses an empty plan.
        """
        self._plan = plan or Plan()
        self._task_lookup: dict[str, Task] = {}
        self._rebuild_task_lookup()

    @property
    def plan(self) -> Plan:
        """Get the current plan."""
        return self._plan

    def update_plan(self, plan: Plan) -> None:
        """Update the plan and rebuild the lookup dictionary.

        Args:
            plan: New plan to use for dependency resolution.
        """
        self._plan = plan
        self._rebuild_task_lookup()

    def _rebuild_task_lookup(self) -> None:
        """Rebuild the task lookup dictionary for O(1) access."""
        self._task_lookup = {}
        for task in self._plan.all_tasks:
            self._task_lookup[task.id] = task

    def get_task_by_id(self, task_id: str) -> Task | None:
        """Get a task by its ID.

        Args:
            task_id: The task ID to look up.

        Returns:
            The task if found, None otherwise.
        """
        return self._task_lookup.get(task_id)

    def is_task_blocked(self, task: Task) -> bool:
        """Check if a task is blocked by incomplete dependencies.

        A task is blocked if:
        - Its status is explicitly BLOCKED, OR
        - Any of its dependencies are not complete or skipped

        Args:
            task: The task to check.

        Returns:
            True if the task is blocked, False otherwise.
        """
        # Check if explicitly marked as blocked
        if task.status == TaskStatus.BLOCKED:
            return True

        # No dependencies means not blocked
        if not task.depends:
            return False

        # Check each dependency
        for dep_id in task.depends:
            dep_task = self._task_lookup.get(dep_id)
            if dep_task and dep_task.status not in (
                TaskStatus.COMPLETE,
                TaskStatus.SKIPPED,
            ):
                return True

        return False

    def get_blocking_tasks(self, task: Task) -> list[str]:
        """Get the IDs of tasks that are blocking this task.

        Returns only the direct blockers (incomplete dependencies),
        not the full transitive dependency chain.

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

    def get_dependency_chain(self, task: Task) -> list[tuple[Task, list[str]]]:
        """Get the full dependency chain for a task.

        Recursively builds a list of tasks and their blockers in the
        dependency chain leading to the given task. The chain is ordered
        with root dependencies first.

        Args:
            task: The task to get the dependency chain for.

        Returns:
            List of (task, blockers) tuples showing the dependency chain.
        """
        chain: list[tuple[Task, list[str]]] = []
        visited: set[str] = set()

        def _add_to_chain(t: Task) -> None:
            if t.id in visited:
                return
            visited.add(t.id)

            blockers = self.get_blocking_tasks(t)

            # First add blocking tasks recursively (depth-first)
            for blocker_id in blockers:
                blocker = self._task_lookup.get(blocker_id)
                if blocker:
                    _add_to_chain(blocker)

            # Then add this task
            chain.append((t, blockers))

        _add_to_chain(task)
        return chain

    def get_all_blocked_tasks(self) -> list[Task]:
        """Get all blocked tasks from the plan.

        Returns:
            List of tasks that are blocked by incomplete dependencies.
        """
        return [
            task
            for task in self._plan.all_tasks
            if self.is_task_blocked(task)
        ]

    def get_available_tasks(self) -> list[Task]:
        """Get all pending tasks that are not blocked.

        Returns:
            List of tasks in PENDING state that have no incomplete dependencies.
        """
        return [
            task
            for task in self._plan.all_tasks
            if task.status == TaskStatus.PENDING and not self.is_task_blocked(task)
        ]

    def get_in_progress_tasks(self) -> list[Task]:
        """Get all tasks currently in progress.

        Returns:
            List of tasks in IN_PROGRESS state.
        """
        return [
            task
            for task in self._plan.all_tasks
            if task.status == TaskStatus.IN_PROGRESS
        ]
