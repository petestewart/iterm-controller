"""Dependency chain modal.

Displays the full dependency chain for a blocked task in a modal dialog.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from iterm_controller.models import Plan, Task, TaskStatus


class DependencyChainModal(ModalScreen[None]):
    """Modal showing the full dependency chain for a blocked task.

    Displays:
        ┌────────────────────────────────────────────────────────────────┐
        │ Task Dependencies: 2.3 Session persistence                     │
        ├────────────────────────────────────────────────────────────────┤
        │ This task is blocked by:                                       │
        │                                                                │
        │   ○ 2.1 Add auth middleware (pending)                          │
        │     └─ No blockers                                             │
        │   ⊘ 2.2 Create login form (blocked)                            │
        │     └─ Blocked by: 2.1                                         │
        │                                                                │
        │ [Press Esc to close]                                           │
        └────────────────────────────────────────────────────────────────┘
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close", show=False),
    ]

    CSS = """
    DependencyChainModal {
        align: center middle;
    }

    DependencyChainModal > Container {
        width: 70;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $warning;
        padding: 1 2;
    }

    DependencyChainModal #title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid $warning;
    }

    DependencyChainModal #subtitle {
        color: $text-muted;
        margin-top: 1;
    }

    DependencyChainModal .task-row {
        padding-left: 2;
        margin-top: 1;
    }

    DependencyChainModal .task-available {
        color: $text;
    }

    DependencyChainModal .task-blocked {
        color: $text-muted;
    }

    DependencyChainModal .task-detail {
        padding-left: 4;
        color: $text-muted;
    }

    DependencyChainModal #footer {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
        padding-top: 1;
        border-top: solid $warning;
    }
    """

    def __init__(self, task: Task, plan: Plan) -> None:
        """Initialize the modal.

        Args:
            task: The blocked task to show dependencies for.
            plan: The plan containing all tasks.
        """
        super().__init__()
        self._task = task
        self._plan = plan
        self._task_lookup = {t.id: t for t in plan.all_tasks}

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        yield Container(
            Static(f"Task Dependencies: {self._task.id}", id="title"),
            Static(f"{self._task.title}", id="subtitle"),
            VerticalScroll(
                Static("This task is blocked by:", classes="section-title"),
                *self._build_chain_display(),
                id="content",
            ),
            Static("[bold]Press Esc to close[/bold]", id="footer"),
            id="dialog",
        )

    def _build_chain_display(self) -> list[Static]:
        """Build the dependency chain display widgets.

        Returns:
            List of Static widgets showing the chain.
        """
        widgets: list[Static] = []

        # Get direct blockers
        chain = self._get_dependency_chain(self._task)

        # Filter out the task itself from the chain (it's the last entry)
        dependencies = [
            (dep_task, blockers) for dep_task, blockers in chain
            if dep_task.id != self._task.id
        ]

        if not dependencies:
            widgets.append(Static("  No blockers - task is available!", classes="task-row"))
            return widgets

        # Display each dependency in the chain
        for dep_task, blockers in dependencies:
            is_blocked = len(blockers) > 0
            status_text = self._get_status_text(dep_task)

            if is_blocked:
                icon = "⊘"
                style_class = "task-blocked"
            else:
                icon = "○"
                style_class = "task-available"

            widgets.append(
                Static(f"{icon} {dep_task.id} {dep_task.title} ({status_text})", classes=f"task-row {style_class}")
            )

            # Show what this task is blocked by
            if blockers:
                blocker_str = ", ".join(blockers)
                widgets.append(Static(f"└─ Blocked by: {blocker_str}", classes="task-detail"))
            else:
                widgets.append(Static("└─ No blockers", classes="task-detail"))

        return widgets

    def _get_dependency_chain(self, task: Task) -> list[tuple[Task, list[str]]]:
        """Get the dependency chain for a task.

        Args:
            task: The task to get dependencies for.

        Returns:
            List of (task, blockers) tuples.
        """
        chain: list[tuple[Task, list[str]]] = []
        visited: set[str] = set()

        def _add_to_chain(t: Task) -> None:
            if t.id in visited:
                return
            visited.add(t.id)

            blockers = self._get_blocking_task_ids(t)

            # First add blocking tasks recursively
            for blocker_id in blockers:
                blocker = self._task_lookup.get(blocker_id)
                if blocker:
                    _add_to_chain(blocker)

            # Then add this task
            chain.append((t, blockers))

        _add_to_chain(task)
        return chain

    def _get_blocking_task_ids(self, task: Task) -> list[str]:
        """Get IDs of incomplete dependencies for a task.

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

    def _get_status_text(self, task: Task) -> str:
        """Get a human-readable status text for a task.

        Args:
            task: The task to get status for.

        Returns:
            Status text like "pending", "in progress", etc.
        """
        status_map = {
            TaskStatus.PENDING: "pending",
            TaskStatus.IN_PROGRESS: "in progress",
            TaskStatus.COMPLETE: "complete",
            TaskStatus.SKIPPED: "skipped",
            TaskStatus.BLOCKED: "blocked",
        }
        return status_map.get(task.status, "unknown")

    def action_dismiss(self) -> None:
        """Dismiss the modal."""
        self.dismiss(None)
