"""Active work widget for Work Mode.

Displays tasks currently in progress with their assigned sessions and status.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.binding import Binding
from textual.widgets import Static

from iterm_controller.models import AttentionState, ManagedSession, Plan, Task, TaskStatus

if TYPE_CHECKING:
    pass


class ActiveWorkWidget(Static, can_focus=True):
    """Displays tasks currently in progress.

    Shows in-progress tasks with:
    - Task ID and title
    - Assigned session (if linked)
    - Time since started
    - Session attention state (Working/Waiting/Idle)

    Example:
        Active Work
        ┌──────────────────────────────────────┐
        │ ● 1.3 Build API layer                │
        │   Session: claude-main               │
        │   Started: 10 min ago                │
        │   Status: Working                    │
        └──────────────────────────────────────┘
    """

    DEFAULT_CSS = """
    ActiveWorkWidget {
        height: auto;
        min-height: 5;
        padding: 0 1;
        border: solid $surface-lighten-2;
    }

    ActiveWorkWidget:focus {
        border: solid $accent;
    }
    """

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
    ]

    STATUS_ICONS = {
        AttentionState.WAITING: "⧖",
        AttentionState.WORKING: "●",
        AttentionState.IDLE: "○",
    }

    STATUS_COLORS = {
        AttentionState.WAITING: "yellow",
        AttentionState.WORKING: "green",
        AttentionState.IDLE: "dim",
    }

    def __init__(
        self,
        plan: Plan | None = None,
        sessions: dict[str, ManagedSession] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the active work widget.

        Args:
            plan: Initial plan to display tasks from.
            sessions: Dictionary mapping session IDs to sessions.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self._plan = plan or Plan()
        self._sessions = sessions or {}
        self._selected_index: int = 0
        self._active_tasks: list[Task] = []
        self._rebuild_active_tasks()

    @property
    def plan(self) -> Plan:
        """Get the current plan."""
        return self._plan

    @property
    def selected_task(self) -> Task | None:
        """Get the currently selected active task."""
        if 0 <= self._selected_index < len(self._active_tasks):
            return self._active_tasks[self._selected_index]
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
        self._rebuild_active_tasks()
        # Ensure selected index is valid
        if self._selected_index >= len(self._active_tasks):
            self._selected_index = max(0, len(self._active_tasks) - 1)
        self.update(self._render_active())

    def refresh_sessions(self, sessions: dict[str, ManagedSession]) -> None:
        """Update the session dictionary.

        Args:
            sessions: New session dictionary.
        """
        self._sessions = sessions
        self.update(self._render_active())

    def _rebuild_active_tasks(self) -> None:
        """Rebuild the list of in-progress tasks."""
        self._active_tasks = [
            task for task in self._plan.all_tasks
            if task.status == TaskStatus.IN_PROGRESS
        ]

    def get_session_for_task(self, task: Task) -> ManagedSession | None:
        """Get the session linked to a task.

        Looks up the session in two ways:
        1. By task.session_id if set (direct link)
        2. By searching sessions for one whose metadata["task_id"] matches (reverse lookup)

        Args:
            task: The task to look up.

        Returns:
            The linked session, or None if not linked.
        """
        # First try direct lookup via task.session_id
        if task.session_id:
            session = self._sessions.get(task.session_id)
            if session:
                return session

        # Reverse lookup: search sessions for one linked to this task
        for session in self._sessions.values():
            if session.metadata.get("task_id") == task.id:
                return session

        return None

    def select_next(self) -> None:
        """Select the next active task."""
        if self._active_tasks:
            self._selected_index = (self._selected_index + 1) % len(self._active_tasks)
            self.update(self._render_active())

    def select_previous(self) -> None:
        """Select the previous active task."""
        if self._active_tasks:
            self._selected_index = (self._selected_index - 1) % len(self._active_tasks)
            self.update(self._render_active())

    def action_cursor_down(self) -> None:
        """Handle down arrow key."""
        self.select_next()

    def action_cursor_up(self) -> None:
        """Handle up arrow key."""
        self.select_previous()

    def _format_time_ago(self, dt: datetime | None) -> str:
        """Format a datetime as a relative time string.

        Args:
            dt: The datetime to format.

        Returns:
            A human-readable relative time string.
        """
        if not dt:
            return "unknown"

        now = datetime.now()
        diff = now - dt
        seconds = diff.total_seconds()

        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            mins = int(seconds / 60)
            return f"{mins} min ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        else:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days > 1 else ''} ago"

    def _render_task(self, task: Task, is_selected: bool) -> Text:
        """Render a single active task with session info.

        Args:
            task: The task to render.
            is_selected: Whether this task is currently selected.

        Returns:
            Rich Text object for the task.
        """
        session = self.get_session_for_task(task)

        text = Text()

        # Selection indicator
        if is_selected:
            text.append("▸ ", style="bold cyan")
        else:
            text.append("  ")

        # Task with in-progress indicator
        text.append("● ", style="yellow")
        text.append(f"{task.id} {task.title}")
        text.append("\n")

        # Session info (indented)
        indent = "    "
        if session:
            # Session name
            text.append(f"{indent}Session: ")
            text.append(session.template_id, style="cyan")
            text.append("\n")

            # Started time
            text.append(f"{indent}Started: ")
            text.append(self._format_time_ago(session.spawned_at), style="dim")
            text.append("\n")

            # Attention state
            icon = self.STATUS_ICONS.get(session.attention_state, "○")
            color = self.STATUS_COLORS.get(session.attention_state, "dim")
            status = session.attention_state.value.title()
            text.append(f"{indent}Status: ")
            text.append(f"{icon} ", style=color)
            text.append(status, style=color)
        else:
            text.append(f"{indent}Session: ", style="dim")
            text.append("none", style="dim italic")

        return text

    def _render_active(self) -> Text:
        """Render the complete active work panel.

        Returns:
            Rich Text object containing all active tasks.
        """
        text = Text()

        # Header
        text.append("Active Work", style="bold")
        text.append("\n")

        if not self._active_tasks:
            text.append("  No tasks in progress", style="dim italic")
            return text

        # Render each active task
        for i, task in enumerate(self._active_tasks):
            if i > 0:
                text.append("\n")
            is_selected = i == self._selected_index
            text.append_text(self._render_task(task, is_selected))

        return text

    def render(self) -> Text:
        """Render the widget content.

        Returns:
            Rich Text object to display.
        """
        return self._render_active()
