"""Work Mode screen.

Task execution and session tracking screen with two-panel layout showing
task queue (pending) and active work (in-progress).

See specs/work-mode.md for full specification.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from iterm_controller.models import (
    ManagedSession,
    Plan,
    Task,
    TaskStatus,
    WorkflowMode,
)
from iterm_controller.screens.mode_screen import ModeScreen
from iterm_controller.widgets.active_work import ActiveWorkWidget
from iterm_controller.widgets.session_list import SessionListWidget
from iterm_controller.widgets.task_queue import TaskQueueWidget

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp
    from iterm_controller.models import Project


class WorkModeScreen(ModeScreen):
    """Work Mode screen for task execution.

    This screen displays:
    - Task queue (pending tasks that can be claimed)
    - Active work (in-progress tasks with linked sessions)
    - Session status indicators at the bottom

    Users can claim tasks, spawn sessions, and track work progress.

    Layout:
        ┌─────────────────────────────┬──────────────────────────────┐
        │ Task Queue           5 left │ Active Work                  │
        │ ○ 2.1 Add auth middleware   │ ● 1.3 Build API layer        │
        │ ⊘ 2.2 Create login form     │   Session: claude-main       │
        │ ⊘ 2.3 Session persistence   │   Started: 10 min ago        │
        └─────────────────────────────┴──────────────────────────────┘
        │ Sessions                                                   │
        │ ● claude-main    Task 1.3    Working                       │
        └────────────────────────────────────────────────────────────┘
    """

    CURRENT_MODE = WorkflowMode.WORK

    BINDINGS = [
        *ModeScreen.BINDINGS,
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("tab", "switch_panel", "Switch Panel"),
        Binding("c", "claim_task", "Claim"),
        Binding("u", "unclaim_task", "Unclaim"),
        Binding("d", "mark_done", "Done"),
        Binding("f", "focus_session", "Focus"),
        Binding("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    WorkModeScreen {
        layout: vertical;
    }

    WorkModeScreen #main {
        height: 1fr;
        padding: 1;
    }

    WorkModeScreen #panels {
        height: 1fr;
    }

    WorkModeScreen #left-panel {
        width: 1fr;
        height: 1fr;
        padding-right: 1;
    }

    WorkModeScreen #right-panel {
        width: 1fr;
        height: 1fr;
    }

    WorkModeScreen #task-queue {
        height: 1fr;
    }

    WorkModeScreen #active-work {
        height: 1fr;
    }

    WorkModeScreen #sessions-container {
        dock: bottom;
        height: auto;
        min-height: 5;
        max-height: 10;
        padding-top: 1;
    }

    WorkModeScreen #sessions-title {
        text-style: bold;
        padding-bottom: 0;
    }

    WorkModeScreen #progress-bar {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $surface;
    }

    WorkModeScreen SessionListWidget {
        height: auto;
        min-height: 3;
    }
    """

    # Track which panel is focused: "queue" or "active"
    _active_panel: str = "queue"

    def __init__(self, project: Project) -> None:
        """Initialize the Work Mode screen.

        Args:
            project: The project to display.
        """
        super().__init__(project)
        self._plan: Plan | None = None
        self._sessions: dict[str, ManagedSession] = {}

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            Horizontal(
                Vertical(
                    TaskQueueWidget(id="task-queue"),
                    id="left-panel",
                ),
                Vertical(
                    ActiveWorkWidget(id="active-work"),
                    id="right-panel",
                ),
                id="panels",
            ),
            Vertical(
                Static("Sessions", id="sessions-title"),
                SessionListWidget(show_project=False, id="sessions"),
                id="sessions-container",
            ),
            Static(id="progress-bar"),
            id="main",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Load data when screen mounts."""
        await super().on_mount()
        await self._load_data()
        self._update_progress_bar()
        # Focus the task queue by default
        self.query_one("#task-queue", TaskQueueWidget).focus()

    async def _load_data(self) -> None:
        """Load plan and session data."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Load plan from project
        plan_path = self.project.full_plan_path
        if plan_path.exists():
            from iterm_controller.plan_parser import PlanParser
            parser = PlanParser()
            self._plan = parser.parse_file(plan_path)
        else:
            self._plan = Plan()

        # Build session lookup
        self._sessions = {}
        for session in app.state.sessions:
            self._sessions[session.id] = session

        # Filter sessions for this project
        project_sessions = [
            s for s in app.state.sessions
            if s.project_id == self.project.id
        ]

        # Update widgets
        self._refresh_widgets(project_sessions)

    def _refresh_widgets(self, sessions: list[ManagedSession] | None = None) -> None:
        """Refresh all widgets with current data.

        Args:
            sessions: Optional list of sessions to display.
        """
        if self._plan:
            # Update task queue
            queue = self.query_one("#task-queue", TaskQueueWidget)
            queue.refresh_plan(self._plan)

            # Update active work
            active = self.query_one("#active-work", ActiveWorkWidget)
            active.refresh_plan(self._plan)
            active.refresh_sessions(self._sessions)

        # Update session list
        if sessions is not None:
            session_widget = self.query_one("#sessions", SessionListWidget)
            session_widget.refresh_sessions(sessions)

        self._update_progress_bar()

    def _update_progress_bar(self) -> None:
        """Update the progress bar text."""
        if not self._plan:
            return

        all_tasks = self._plan.all_tasks
        total = len(all_tasks)
        if total == 0:
            return

        complete = sum(
            1 for t in all_tasks
            if t.status in (TaskStatus.COMPLETE, TaskStatus.SKIPPED)
        )
        in_progress = sum(
            1 for t in all_tasks
            if t.status == TaskStatus.IN_PROGRESS
        )

        # Count blocked tasks
        queue = self.query_one("#task-queue", TaskQueueWidget)
        blocked = len(queue.get_blocked_tasks())

        percent = (complete / total) * 100

        progress_text = (
            f"Progress: {complete}/{total} complete ({percent:.0f}%)  |  "
            f"{in_progress} in progress  |  {blocked} blocked"
        )

        progress_bar = self.query_one("#progress-bar", Static)
        progress_bar.update(progress_text)

    def action_switch_panel(self) -> None:
        """Switch focus between queue and active work panels."""
        if self._active_panel == "queue":
            self._active_panel = "active"
            self.query_one("#active-work", ActiveWorkWidget).focus()
        else:
            self._active_panel = "queue"
            self.query_one("#task-queue", TaskQueueWidget).focus()

    def action_cursor_down(self) -> None:
        """Move cursor down in active panel."""
        if self._active_panel == "queue":
            queue = self.query_one("#task-queue", TaskQueueWidget)
            queue.select_next()
        else:
            active = self.query_one("#active-work", ActiveWorkWidget)
            active.select_next()

    def action_cursor_up(self) -> None:
        """Move cursor up in active panel."""
        if self._active_panel == "queue":
            queue = self.query_one("#task-queue", TaskQueueWidget)
            queue.select_previous()
        else:
            active = self.query_one("#active-work", ActiveWorkWidget)
            active.select_previous()

    async def action_claim_task(self) -> None:
        """Claim the selected task from the queue."""
        queue = self.query_one("#task-queue", TaskQueueWidget)
        task = queue.selected_task

        if not task:
            self.notify("No task selected", severity="warning")
            return

        if queue.is_task_blocked(task):
            blockers = queue.get_blocking_tasks(task)
            self.notify(
                f"Task is blocked by: {', '.join(blockers)}",
                severity="warning",
            )
            return

        # Update task status to in_progress
        await self._update_task_status(task, TaskStatus.IN_PROGRESS)
        self.notify(f"Claimed task {task.id}")

    async def action_unclaim_task(self) -> None:
        """Unclaim the selected active task."""
        active = self.query_one("#active-work", ActiveWorkWidget)
        task = active.selected_task

        if not task:
            self.notify("No active task selected", severity="warning")
            return

        # Update task status back to pending
        await self._update_task_status(task, TaskStatus.PENDING)
        self.notify(f"Unclaimed task {task.id}")

    async def action_mark_done(self) -> None:
        """Mark the selected active task as complete."""
        active = self.query_one("#active-work", ActiveWorkWidget)
        task = active.selected_task

        if not task:
            self.notify("No active task selected", severity="warning")
            return

        # Update task status to complete
        await self._update_task_status(task, TaskStatus.COMPLETE)
        self.notify(f"Completed task {task.id}")

    async def _update_task_status(self, task: Task, new_status: TaskStatus) -> None:
        """Update a task's status in PLAN.md.

        Args:
            task: The task to update.
            new_status: The new status to set.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Update in-memory task
        task.status = new_status

        # Write to PLAN.md
        plan_path = self.project.full_plan_path
        if plan_path.exists():
            from iterm_controller.plan_parser import PlanUpdater
            updater = PlanUpdater()
            try:
                updater.update_task_status_in_file(
                    plan_path,
                    task.id,
                    new_status,
                )
            except Exception as e:
                self.notify(f"Failed to update PLAN.md: {e}", severity="error")
                return

        # Reload data and refresh
        await self._load_data()

        # Post task status changed event
        from iterm_controller.state import TaskStatusChanged
        self.post_message(TaskStatusChanged(task.id, self.project.id))

    def action_focus_session(self) -> None:
        """Focus the session linked to the selected active task."""
        active = self.query_one("#active-work", ActiveWorkWidget)
        task = active.selected_task

        if not task:
            self.notify("No active task selected", severity="warning")
            return

        session = active.get_session_for_task(task)
        if not session:
            self.notify(f"Task {task.id} has no linked session", severity="warning")
            return

        # Focus session in iTerm2
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        if app.iterm.is_connected:
            self._focus_session(session.id)
        else:
            self.notify("Not connected to iTerm2", severity="error")

    def _focus_session(self, session_id: str) -> None:
        """Focus a session in iTerm2.

        Args:
            session_id: The session ID to focus.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        async def _do_focus() -> None:
            try:
                await app.iterm.focus_session(session_id)
                self.notify("Focused session")
            except Exception as e:
                self.notify(f"Failed to focus session: {e}", severity="error")

        self.call_later(_do_focus)

    def action_refresh(self) -> None:
        """Refresh all data."""

        async def _do_refresh() -> None:
            await self._load_data()
            self.notify("Refreshed")

        self.call_later(_do_refresh)
