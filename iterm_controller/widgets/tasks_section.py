"""Tasks section widget for Project Screen.

Displays collapsible section showing tasks organized by phases with
review status indicators.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Static

from iterm_controller.models import Phase, Plan, Task, TaskStatus
from iterm_controller.status_display import (
    PHASE_HEADER_WIDTH,
    get_task_color,
    get_task_icon,
)
from iterm_controller.task_dependency import TaskDependencyResolver

if TYPE_CHECKING:
    from iterm_controller.models import Project


class TaskRow(Static):
    """Single task row with status and review indicators.

    Displays a task with:
    - Status icon (○ pending, ● in progress, ✓ complete, ⊖ skipped, ⊘ blocked)
    - Task ID and title
    - Review indicator (←REVIEW) for awaiting_review status
    - Blocked indicator with blocking task IDs for blocked tasks

    Example display:
        ✓ 1.1 Create project
        ● 1.2 Add models  In Progress
        ⏳ 1.3 Add API  ←REVIEW
        [dim]⊘ 2.1 Add auth  blocked by 1.2, 1.3[/dim]
    """

    DEFAULT_CSS = """
    TaskRow {
        height: auto;
        padding: 0;
    }

    TaskRow.selected {
        background: $primary-darken-2;
    }
    """

    class TaskSelected(Message):
        """Posted when a task is selected."""

        def __init__(self, task: Task) -> None:
            super().__init__()
            self.task = task

    def __init__(
        self,
        task: Task,
        is_blocked: bool = False,
        blocking_tasks: list[str] | None = None,
        is_selected: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the task row.

        Args:
            task: Task to display.
            is_blocked: Whether the task is blocked.
            blocking_tasks: List of task IDs blocking this task.
            is_selected: Whether this task is selected.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self._task = task
        self._is_blocked = is_blocked
        self._blocking_tasks = blocking_tasks or []
        self._is_selected = is_selected

    @property
    def task(self) -> Task:
        """Get the task."""
        return self._task

    def render(self) -> Text:
        """Render task with appropriate status icon and indicators."""
        text = Text()

        # Selection indicator
        if self._is_selected:
            text.append("> ", style="bold cyan")
        else:
            text.append("  ")

        if self._is_blocked:
            # Render entire task line as dimmed
            icon = get_task_icon(TaskStatus.BLOCKED)
            text.append(f"{icon} ", style="dim")
            text.append(f"{self._task.id} {self._task.title}", style="dim")
            if self._blocking_tasks:
                blocker_str = ", ".join(self._blocking_tasks)
                text.append(f"  blocked by {blocker_str}", style="dim italic")
        else:
            # Normal rendering
            icon = self._get_status_icon()
            color = get_task_color(self._task.status)
            text.append(f"{icon} ", style=color)
            text.append(f"{self._task.id} {self._task.title}")

            # Add review indicator for awaiting_review status
            review_indicator = self._get_review_indicator()
            if review_indicator:
                text.append(review_indicator, style="cyan bold")

            # Add status suffix for in-progress tasks
            if self._task.status == TaskStatus.IN_PROGRESS:
                text.append("  ", style="default")
                text.append("In Progress", style="yellow")
            elif self._task.status == TaskStatus.COMPLETE:
                text.append("  ", style="default")
                text.append("Done", style="green")

        return text

    def _get_status_icon(self) -> str:
        """Get status icon based on task state."""
        if self._task.status == TaskStatus.AWAITING_REVIEW:
            return "⏳"
        return get_task_icon(self._task.status)

    def _get_review_indicator(self) -> str:
        """Get review indicator if task is awaiting review."""
        if self._task.status == TaskStatus.AWAITING_REVIEW:
            return " ←REVIEW"
        return ""


class TasksSection(Static):
    """Tasks section with collapsible phases.

    Displays a collapsible section showing tasks organized by phases:
    - Phase headers with completion counts (e.g., "Phase 1: Setup [2/3]")
    - Collapsible/expandable phases
    - Task rows with status icons
    - Review indicators for tasks awaiting review
    - Dimmed blocked tasks with "blocked by" suffix

    Example display:
        -- Tasks ------------------------------------------
        > ▼ Phase 1: Setup                           [2/3]
            ✓ 1.1 Create project
            ✓ 1.2 Setup deps
            ○ 1.3 Configure DB
          ▶ Phase 2: Core                            [0/4]
    """

    DEFAULT_CSS = """
    TasksSection {
        height: auto;
        min-height: 6;
        padding: 0 1;
        border: solid $surface-lighten-1;
        margin-bottom: 1;
    }

    TasksSection .section-header {
        color: $text;
        text-style: bold;
        margin-bottom: 1;
    }

    TasksSection .section-header-collapsed {
        color: $text-muted;
        text-style: bold;
        margin-bottom: 0;
    }

    TasksSection #task-list-container {
        height: auto;
        padding-left: 1;
    }
    """

    class PhaseToggled(Message):
        """Posted when a phase is toggled."""

        def __init__(self, phase_id: str, collapsed: bool) -> None:
            super().__init__()
            self.phase_id = phase_id
            self.collapsed = collapsed

    class TaskSelected(Message):
        """Posted when a task is selected."""

        def __init__(self, task: Task) -> None:
            super().__init__()
            self.task = task

    def __init__(
        self,
        project: Project | None = None,
        collapsed: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the tasks section widget.

        Args:
            project: Project containing plan with tasks.
            collapsed: Whether to start collapsed.
            **kwargs: Additional arguments passed to Static.
        """
        # Initialize instance attributes before calling super().__init__
        # because Textual's Static may call refresh() during initialization
        self._project = project
        self._collapsed = collapsed
        self._collapsed_phases: set[str] = set()
        self._selected_index = 0
        self._plan: Plan | None = None
        self._dependency_resolver = TaskDependencyResolver()
        super().__init__(**kwargs)

    @property
    def project(self) -> Project | None:
        """Get the current project."""
        return self._project

    @property
    def collapsed(self) -> bool:
        """Get collapsed state."""
        return self._collapsed

    @property
    def plan(self) -> Plan | None:
        """Get the current plan."""
        return self._plan

    @property
    def selected_task(self) -> Task | None:
        """Get the currently selected task."""
        if not self._plan or self._collapsed:
            return None
        items = self._get_selectable_items()
        if 0 <= self._selected_index < len(items):
            item = items[self._selected_index]
            if isinstance(item, Task):
                return item
        return None

    def _get_selectable_items(self) -> list[Phase | Task]:
        """Get list of selectable items (phases and tasks).

        Returns flattened list of phases and their visible tasks.
        """
        items: list[Phase | Task] = []
        if not self._plan:
            return items

        for phase in self._plan.phases:
            items.append(phase)
            if phase.id not in self._collapsed_phases:
                items.extend(phase.tasks)
        return items

    def set_project(self, project: Project) -> None:
        """Set the project and refresh tasks.

        Args:
            project: Project containing plan with tasks.
        """
        self._project = project
        self.refresh_tasks()

    def set_plan(self, plan: Plan) -> None:
        """Set the plan directly and refresh display.

        Args:
            plan: Plan to display.
        """
        self._plan = plan
        self._dependency_resolver.update_plan(plan)
        self.refresh()

    def toggle_collapsed(self) -> None:
        """Toggle section collapsed state."""
        self._collapsed = not self._collapsed
        self.refresh()

    def toggle_phase(self, phase_id: str) -> None:
        """Toggle phase collapse state.

        Args:
            phase_id: The phase ID to toggle.
        """
        if phase_id in self._collapsed_phases:
            self._collapsed_phases.discard(phase_id)
            collapsed = False
        else:
            self._collapsed_phases.add(phase_id)
            collapsed = True
        self.post_message(self.PhaseToggled(phase_id, collapsed))
        self.refresh()

    def refresh_tasks(self) -> None:
        """Load plan from project and refresh display."""
        # In real implementation, load plan from project
        # For now, just refresh
        self.refresh()

    def select_next(self) -> None:
        """Select the next item."""
        if self._collapsed:
            return
        items = self._get_selectable_items()
        if items:
            self._selected_index = min(self._selected_index + 1, len(items) - 1)
            self.refresh()

    def select_previous(self) -> None:
        """Select the previous item."""
        if self._collapsed:
            return
        if self._selected_index > 0:
            self._selected_index -= 1
            self.refresh()

    def action_toggle_selected(self) -> None:
        """Toggle the selected item (phase collapse or task selection)."""
        if not self._plan or self._collapsed:
            return
        items = self._get_selectable_items()
        if 0 <= self._selected_index < len(items):
            item = items[self._selected_index]
            if isinstance(item, Phase):
                self.toggle_phase(item.id)
            elif isinstance(item, Task):
                self.post_message(self.TaskSelected(item))

    def compose(self) -> "ComposeResult":  # type: ignore[name-defined]
        """Compose the widget content."""
        from textual.app import ComposeResult

        # Section header
        collapse_icon = ">" if self._collapsed else "v"
        header_class = "section-header-collapsed" if self._collapsed else "section-header"
        yield Static(f"{collapse_icon} Tasks", classes=header_class, id="section-header")

        if not self._collapsed:
            # Pre-create the content Static to avoid remove/mount cycles
            yield Vertical(
                Static("", id="task-content"),
                id="task-list-container",
            )

    def on_mount(self) -> None:
        """Initialize when mounted."""
        self.refresh()

    def _render_phase_header(self, phase: Phase, is_selected: bool) -> Text:
        """Render a phase header with completion progress.

        Args:
            phase: The phase to render.
            is_selected: Whether this phase is selected.

        Returns:
            Rich Text object for the phase header.
        """
        is_phase_collapsed = phase.id in self._collapsed_phases
        collapse_icon = "▶" if is_phase_collapsed else "▼"
        completed, total = phase.completion_count

        text = Text()

        # Selection indicator
        if is_selected:
            text.append("> ", style="bold cyan")
        else:
            text.append("  ")

        # Collapse icon and title
        text.append(f"{collapse_icon} ", style="bold")
        text.append(f"{phase.title}", style="bold")

        # Right-align the progress
        progress = f"[{completed}/{total}]"
        padding = PHASE_HEADER_WIDTH - len(phase.title) - 4  # Account for icon, space, selection
        if padding > 0:
            text.append(" " * padding)
        text.append(progress, style="dim")

        return text

    def _render_task(self, task: Task, is_selected: bool) -> Text:
        """Render a single task row.

        Args:
            task: The task to render.
            is_selected: Whether this task is selected.

        Returns:
            Rich Text object for the task row.
        """
        is_blocked = self._dependency_resolver.is_task_blocked(task)
        blocking_tasks = self._dependency_resolver.get_blocking_tasks(task) if is_blocked else []

        text = Text()

        # Selection indicator
        if is_selected:
            text.append(">   ", style="bold cyan")
        else:
            text.append("    ")

        if is_blocked:
            # Render entire task line as dimmed
            icon = get_task_icon(TaskStatus.BLOCKED)
            text.append(f"{icon} ", style="dim")
            text.append(f"{task.id} {task.title}", style="dim")
            if blocking_tasks:
                blocker_str = ", ".join(blocking_tasks)
                text.append(f"  blocked by {blocker_str}", style="dim italic")
        else:
            # Normal rendering
            if task.status == TaskStatus.AWAITING_REVIEW:
                icon = "⏳"
            else:
                icon = get_task_icon(task.status)
            color = get_task_color(task.status)
            text.append(f"{icon} ", style=color)
            text.append(f"{task.id} {task.title}")

            # Add review indicator for awaiting_review status
            if task.status == TaskStatus.AWAITING_REVIEW:
                text.append(" ←REVIEW", style="cyan bold")

            # Add status suffix for in-progress tasks
            if task.status == TaskStatus.IN_PROGRESS:
                text.append("  ", style="default")
                text.append("In Progress", style="yellow")
            elif task.status == TaskStatus.COMPLETE:
                text.append("  ", style="default")
                text.append("Done", style="green")

        return text

    def _build_task_content(self) -> Text:
        """Build the task list content text."""
        if not self._plan:
            return Text("[dim]No plan loaded[/dim]")

        if not self._plan.phases:
            return Text("[dim]No tasks[/dim]")

        # Build content
        lines: list[Text] = []
        items = self._get_selectable_items()

        for idx, item in enumerate(items):
            is_selected = idx == self._selected_index
            if isinstance(item, Phase):
                lines.append(self._render_phase_header(item, is_selected))
            elif isinstance(item, Task):
                lines.append(self._render_task(item, is_selected))

        # Combine into single content
        content = Text()
        for i, line in enumerate(lines):
            if i > 0:
                content.append("\n")
            content.append_text(line)

        return content

    def _update_task_display(self) -> None:
        """Update the task content using update() to avoid DOM thrashing."""
        try:
            content_widget = self.query_one("#task-content", Static)
            content_widget.update(self._build_task_content())
        except Exception:
            pass

    def refresh(self, *args: Any, **kwargs: Any) -> None:
        """Override refresh to update task display."""
        # Update section header
        try:
            header = self.query_one("#section-header", Static)
            collapse_icon = ">" if self._collapsed else "v"
            header.update(f"{collapse_icon} Tasks")
            header.set_class(self._collapsed, "section-header-collapsed")
            header.set_class(not self._collapsed, "section-header")
        except Exception:
            pass

        # Update tasks if not collapsed
        if not self._collapsed:
            self._update_task_display()

        super().refresh(*args, **kwargs)

    # Event handlers for state changes
    def on_plan_reloaded(self, message: Any) -> None:
        """Handle plan reloaded event.

        Args:
            message: The plan reloaded message (PlanReloaded).
        """
        if hasattr(message, "plan"):
            self.set_plan(message.plan)

    def on_task_status_changed(self, message: Any) -> None:
        """Handle task status changed event.

        Args:
            message: The task status changed message.
        """
        self.refresh()

    # Helper methods for external access
    def get_completed_count(self) -> tuple[int, int]:
        """Get overall completion count.

        Returns:
            Tuple of (completed, total) tasks.
        """
        if not self._plan:
            return 0, 0
        completed = sum(
            1 for task in self._plan.all_tasks
            if task.status in (TaskStatus.COMPLETE, TaskStatus.SKIPPED)
        )
        return completed, len(self._plan.all_tasks)

    def get_awaiting_review_tasks(self) -> list[Task]:
        """Get all tasks awaiting review.

        Returns:
            List of tasks in AWAITING_REVIEW status.
        """
        if not self._plan:
            return []
        return [
            task for task in self._plan.all_tasks
            if task.status == TaskStatus.AWAITING_REVIEW
        ]
