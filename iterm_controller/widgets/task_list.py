"""Task list widget with phases and dependencies.

Displays tasks from PLAN.md grouped by phases with status indicators
and dependency-based blocked state rendering. Also validates spec
references and shows warnings for missing files/sections.
"""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.widgets import Static

from iterm_controller.models import Phase, Plan, Task, TaskStatus
from iterm_controller.spec_validator import SpecValidationResult, validate_spec_ref
from iterm_controller.state import PlanReloaded, TaskStatusChanged
from iterm_controller.status_display import (
    PHASE_HEADER_WIDTH,
    get_task_color,
    get_task_icon,
)
from iterm_controller.task_dependency import TaskDependencyResolver


class TaskListWidget(Static):
    """Displays tasks with phases and dependencies.

    This widget shows all tasks from a PLAN.md file organized by phase:
    - ✓ Complete: Task is finished
    - ● In Progress: Task is currently being worked on
    - ○ Pending: Task is waiting to be started
    - ⊖ Skipped: Task was skipped
    - ⊘ Blocked: Task is blocked by incomplete dependencies

    Phases are collapsible and show completion progress (e.g., "3/4").
    Blocked tasks are dimmed and show "blocked by X, Y" suffix.

    Example display:
        ▼ Phase 1: Setup                    3/4
          ✓ 1.1 Create package         Done
          ✓ 1.2 Add models             Done
          ● 1.3 Add API           In Progress
          ○ 1.4 Add tests           Pending
        ▼ Phase 2: Features                 0/2
          ⊘ 2.1 Add auth        blocked by 1.3
          ⊘ 2.2 Add login       blocked by 2.1
    """

    DEFAULT_CSS = """
    TaskListWidget {
        height: auto;
        min-height: 3;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        plan: Plan | None = None,
        collapsed_phases: set[str] | None = None,
        project_path: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the task list widget.

        Args:
            plan: Initial plan to display.
            collapsed_phases: Set of phase IDs that should be collapsed.
            project_path: Project root path for spec validation.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self._plan = plan or Plan()
        self._collapsed_phases: set[str] = collapsed_phases or set()
        self._dependency_resolver = TaskDependencyResolver(self._plan)
        self._project_path: str | None = project_path
        self._spec_validations: dict[str, SpecValidationResult] = {}
        # Validate specs if project path is provided
        if self._project_path:
            self._validate_all_specs()

    def on_mount(self) -> None:
        """Initialize the task list content when mounted."""
        self.update(self._render_plan())

    @property
    def plan(self) -> Plan:
        """Get the current plan."""
        return self._plan

    @property
    def project_path(self) -> str | None:
        """Get the project path for spec validation."""
        return self._project_path

    def set_project_path(self, path: str | None) -> None:
        """Set the project path for spec validation.

        Args:
            path: Project root path, or None to disable validation.
        """
        self._project_path = path
        if path:
            self._validate_all_specs()
        else:
            self._spec_validations.clear()
        self.update(self._render_plan())

    def _validate_all_specs(self) -> None:
        """Validate all spec references in the current plan."""
        self._spec_validations.clear()
        if not self._project_path:
            return

        for task in self._plan.all_tasks:
            if task.spec_ref:
                self._spec_validations[task.id] = validate_spec_ref(
                    self._project_path, task.spec_ref
                )

    def get_spec_validation(self, task_id: str) -> SpecValidationResult | None:
        """Get the spec validation result for a task.

        Args:
            task_id: The task ID to look up.

        Returns:
            The validation result, or None if no spec_ref or not validated.
        """
        return self._spec_validations.get(task_id)

    def refresh_plan(self, plan: Plan, project_path: str | None = None) -> None:
        """Update the displayed plan.

        Args:
            plan: New plan to display.
            project_path: Project root path for spec validation. If None,
                uses the previously set project path.
        """
        self._plan = plan
        self._dependency_resolver.update_plan(plan)

        # Update project path if provided
        if project_path is not None:
            self._project_path = project_path

        # Validate specs
        self._validate_all_specs()
        self.update(self._render_plan())

    def toggle_phase(self, phase_id: str) -> None:
        """Toggle collapse state of a phase.

        Args:
            phase_id: The phase ID to toggle.
        """
        if phase_id in self._collapsed_phases:
            self._collapsed_phases.discard(phase_id)
        else:
            self._collapsed_phases.add(phase_id)
        self.update(self._render_plan())

    def is_task_blocked(self, task: Task) -> bool:
        """Check if a task is blocked by incomplete dependencies.

        Delegates to TaskDependencyResolver.

        Args:
            task: The task to check.

        Returns:
            True if the task is blocked, False otherwise.
        """
        return self._dependency_resolver.is_task_blocked(task)

    def get_blocking_tasks(self, task: Task) -> list[str]:
        """Get the IDs of tasks blocking this task.

        Delegates to TaskDependencyResolver.

        Args:
            task: The task to check.

        Returns:
            List of task IDs that are blocking this task.
        """
        return self._dependency_resolver.get_blocking_tasks(task)

    def _get_status_icon(self, status: TaskStatus) -> str:
        """Get the icon for a given task status.

        Args:
            status: The task status.

        Returns:
            Unicode icon representing the status.
        """
        return get_task_icon(status)

    def _get_status_color(self, status: TaskStatus) -> str:
        """Get the color for a given task status.

        Args:
            status: The task status.

        Returns:
            Color name for Rich markup.
        """
        return get_task_color(status)

    def _render_phase_header(self, phase: Phase) -> Text:
        """Render a phase header with completion progress.

        Args:
            phase: The phase to render.

        Returns:
            Rich Text object for the phase header.
        """
        is_collapsed = phase.id in self._collapsed_phases
        collapse_icon = "▶" if is_collapsed else "▼"
        completed, total = phase.completion_count

        text = Text()
        text.append(f"{collapse_icon} ", style="bold")
        text.append(f"{phase.title}", style="bold")

        # Right-align the progress
        progress = f"{completed}/{total}"
        padding = PHASE_HEADER_WIDTH - len(phase.title) - 2  # Account for icon and space
        if padding > 0:
            text.append(" " * padding)
        text.append(progress, style="dim")

        return text

    def _render_task(self, task: Task) -> Text:
        """Render a single task row.

        Args:
            task: The task to render.

        Returns:
            Rich Text object for the task row.
        """
        is_blocked = self.is_task_blocked(task)
        blockers = self.get_blocking_tasks(task) if is_blocked else []

        # Use blocked status if task has incomplete dependencies
        effective_status = TaskStatus.BLOCKED if is_blocked else task.status
        icon = self._get_status_icon(effective_status)
        color = self._get_status_color(effective_status)

        # Check for spec validation issues
        spec_validation = self._spec_validations.get(task.id)
        has_spec_warning = spec_validation is not None and not spec_validation.valid

        text = Text()

        if is_blocked:
            # Render entire task line as dimmed
            text.append(f"  {icon} ", style="dim")
            text.append(f"{task.id} {task.title}", style="dim")
            if blockers:
                blocker_str = ", ".join(blockers)
                text.append(f"  blocked by {blocker_str}", style="dim italic")
        else:
            # Normal rendering
            text.append(f"  {icon} ", style=color)
            text.append(f"{task.id} {task.title}")

            # Add status suffix for in-progress tasks
            if task.status == TaskStatus.IN_PROGRESS:
                text.append("  ", style="default")
                text.append("In Progress", style="yellow")
            elif task.status == TaskStatus.COMPLETE:
                text.append("  ", style="default")
                text.append("Done", style="green")

        # Add spec warning if applicable
        if has_spec_warning and spec_validation:
            text.append("  ")
            text.append("⚠", style="bold yellow")
            text.append(f" ({spec_validation.error_message})", style="dim yellow")

        return text

    def _render_plan(self) -> Text:
        """Render the entire plan with phases and tasks.

        Returns:
            Rich Text object containing all phases and tasks.
        """
        if not self._plan.phases:
            return Text("No tasks", style="dim italic")

        lines: list[Text] = []

        for phase in self._plan.phases:
            # Render phase header
            lines.append(self._render_phase_header(phase))

            # Render tasks if not collapsed
            if phase.id not in self._collapsed_phases:
                for task in phase.tasks:
                    lines.append(self._render_task(task))

        result = Text()
        for i, line in enumerate(lines):
            if i > 0:
                result.append("\n")
            result.append_text(line)

        return result

    def render(self) -> Text:
        """Render the widget content.

        Returns:
            Rich Text object to display.
        """
        return self._render_plan()

    def on_plan_reloaded(self, message: PlanReloaded) -> None:
        """Handle plan reloaded event.

        Args:
            message: The plan reloaded message.
        """
        self.refresh_plan(message.plan)

    def on_task_status_changed(self, message: TaskStatusChanged) -> None:
        """Handle task status changed event.

        Args:
            message: The task status changed message.
        """
        # Just re-render, the plan should have been updated
        self.update(self._render_plan())

    def get_task_by_id(self, task_id: str) -> Task | None:
        """Get a task by its ID.

        Args:
            task_id: The task ID to look up.

        Returns:
            The task if found, None otherwise.
        """
        return self._dependency_resolver.get_task_by_id(task_id)

    def get_pending_tasks(self) -> list[Task]:
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
            task for task in self._plan.all_tasks if task.status == TaskStatus.IN_PROGRESS
        ]

    def get_blocked_tasks(self) -> list[Task]:
        """Get all blocked tasks.

        Returns:
            List of tasks that are blocked by incomplete dependencies.
        """
        return [task for task in self._plan.all_tasks if self.is_task_blocked(task)]

    def get_tasks_with_spec_warnings(self) -> list[tuple[Task, SpecValidationResult]]:
        """Get all tasks that have spec validation warnings.

        Returns:
            List of (task, validation_result) tuples for tasks with invalid spec refs.
        """
        result = []
        for task in self._plan.all_tasks:
            validation = self._spec_validations.get(task.id)
            if validation and not validation.valid:
                result.append((task, validation))
        return result

    def has_spec_warnings(self) -> bool:
        """Check if any tasks have spec validation warnings.

        Returns:
            True if any tasks have invalid spec references.
        """
        return any(
            not v.valid for v in self._spec_validations.values()
        )
