"""Work Mode screen.

Task execution and session tracking screen with two-panel layout showing
task queue (pending) and active work (in-progress).

See specs/work-mode.md for full specification.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from iterm_controller.models import (
    ManagedSession,
    Plan,
    SessionTemplate,
    Task,
    TaskStatus,
    WorkflowMode,
)
from iterm_controller.screens.mode_screen import ModeScreen
from iterm_controller.state import (
    SessionClosed,
    SessionSpawned,
    SessionStatusChanged,
)
from iterm_controller.widgets.active_work import ActiveWorkWidget
from iterm_controller.widgets.blocked_tasks import BlockedTasksWidget
from iterm_controller.widgets.mode_indicator import ModeIndicatorWidget
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
        Binding("s", "spawn_session", "Spawn"),
        Binding("u", "unclaim_task", "Unclaim"),
        Binding("d", "mark_done", "Done"),
        Binding("f", "focus_session", "Focus"),
        Binding("v", "view_dependencies", "View Deps"),
        Binding("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    WorkModeScreen {
        layout: vertical;
    }

    WorkModeScreen #mode-indicator {
        dock: top;
        width: 100%;
        height: 1;
        background: $surface;
        padding: 0 1;
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
        height: 2fr;
    }

    WorkModeScreen #blocked-summary {
        height: auto;
        min-height: 3;
        max-height: 8;
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
        yield ModeIndicatorWidget(current_mode=self.CURRENT_MODE, id="mode-indicator")
        yield Container(
            Horizontal(
                Vertical(
                    TaskQueueWidget(id="task-queue"),
                    BlockedTasksWidget(id="blocked-summary"),
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
            # Also update app state for API access
            app.state.set_plan(self.project.id, self._plan)
        else:
            self._plan = Plan()

        # Build session lookup
        self._sessions = {}
        for session in app.state.sessions.values():
            self._sessions[session.id] = session

        # Filter sessions for this project
        project_sessions = [
            s for s in app.state.sessions.values()
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

            # Update blocked tasks summary
            blocked = self.query_one("#blocked-summary", BlockedTasksWidget)
            blocked.refresh_plan(self._plan)

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

        # Count blocked tasks from the blocked summary widget
        blocked_widget = self.query_one("#blocked-summary", BlockedTasksWidget)
        blocked = len(blocked_widget.get_blocked_tasks())

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

        result = await app.api.update_task_status(self.project.id, task.id, new_status)
        if not result.success:
            self.notify(f"Failed to update PLAN.md: {result.error}", severity="error")
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
        self._focus_session(session.id)

    def _focus_session(self, session_id: str) -> None:
        """Focus a session in iTerm2.

        Args:
            session_id: The session ID to focus.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        async def _do_focus() -> None:
            result = await app.api.focus_session(session_id)
            if result.success:
                self.notify("Focused session")
            else:
                self.notify(f"Failed to focus session: {result.error}", severity="error")

        self.call_later(_do_focus)

    def action_refresh(self) -> None:
        """Refresh all data."""

        async def _do_refresh() -> None:
            await self._load_data()
            self.notify("Refreshed")

        self.call_later(_do_refresh)

    def action_spawn_session(self) -> None:
        """Spawn a session for the selected task.

        Opens the script picker modal to select a session template,
        then spawns a session linked to the selected task.
        """
        # Get the selected task from whichever panel is active
        task = self._get_selected_task()

        if not task:
            self.notify("No task selected", severity="warning")
            return

        # Check if task is blocked (only applies to queue tasks)
        if self._active_panel == "queue":
            queue = self.query_one("#task-queue", TaskQueueWidget)
            if queue.is_task_blocked(task):
                blockers = queue.get_blocking_tasks(task)
                self.notify(
                    f"Task is blocked by: {', '.join(blockers)}",
                    severity="warning",
                )
                return

        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Check if connected to iTerm2
        if not app.iterm.is_connected:
            self.notify("Not connected to iTerm2", severity="error")
            return

        # Get session templates from config
        if not app.state.config or not app.state.config.session_templates:
            self.notify("No session templates configured", severity="warning")
            return

        # Show script picker modal to select a template
        from iterm_controller.screens.modals import ScriptPickerModal

        def on_template_selected(template: SessionTemplate | None) -> None:
            if template:
                self._spawn_for_task_async(task, template)

        self.app.push_screen(ScriptPickerModal(), on_template_selected)

    def _get_selected_task(self) -> Task | None:
        """Get the currently selected task from the active panel.

        Returns:
            The selected task, or None if no task is selected.
        """
        if self._active_panel == "queue":
            queue = self.query_one("#task-queue", TaskQueueWidget)
            return queue.selected_task
        else:
            active = self.query_one("#active-work", ActiveWorkWidget)
            return active.selected_task

    def _spawn_for_task_async(self, task: Task, template: SessionTemplate) -> None:
        """Spawn a session for a task asynchronously.

        Args:
            task: The task to spawn a session for.
            template: The session template to use.
        """

        async def _do_spawn() -> None:
            await self._spawn_for_task(task, template)

        self.call_later(_do_spawn)

    async def _spawn_for_task(self, task: Task, template: SessionTemplate) -> None:
        """Spawn a session linked to a task.

        This method:
        1. Spawns a new session using the given template
        2. Links the session to the task (stores task_id in session metadata)
        3. Updates the task's session_id field
        4. Sets the task status to IN_PROGRESS
        5. Optionally sends task context to the session

        Args:
            task: The task to spawn a session for.
            template: The session template to use.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        result = await app.api.spawn_session_with_template(
            self.project, template, task_id=task.id
        )

        if not result.success:
            self.notify(f"Failed to spawn session: {result.error}", severity="error")
            return

        # Set additional task metadata on the session
        if result.session:
            result.session.metadata["task_title"] = task.title

        # Update task with session assignment
        task.session_id = result.spawn_result.session_id if result.spawn_result else ""

        # Set task status to IN_PROGRESS if it was PENDING
        if task.status == TaskStatus.PENDING:
            await self._update_task_status(task, TaskStatus.IN_PROGRESS)
        else:
            # Just update the session_id in PLAN.md
            await self._update_task_session_id(task, task.session_id)

        # Optionally send task context to session
        if task.session_id:
            await self._send_task_context(task.session_id, task)

        self.notify(f"Spawned session for task {task.id}")

        # Reload data to show the updated state
        await self._load_data()

    async def _update_task_session_id(self, task: Task, session_id: str) -> None:
        """Update just the task's session_id in PLAN.md.

        Args:
            task: The task to update.
            session_id: The session ID to assign.
        """
        # Currently, PLAN.md doesn't store session_id directly in the file.
        # The session_id is tracked at runtime. For persistence, the linkage
        # is maintained through the session's metadata which contains task_id.
        # We keep the task's session_id in memory only.
        pass

    async def _send_task_context(self, session_id: str, task: Task) -> None:
        """Send task context to a session.

        Sends the task title and spec reference (if any) to help Claude
        understand what task the session is working on.

        Args:
            session_id: The session ID to send context to.
            task: The task to send context for.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Check if task context should be sent (could be a config option)
        # For now, always send context to help Claude understand the task

        try:
            if not app.iterm.is_connected or not app.iterm.app:
                return

            session = await app.iterm.app.async_get_session_by_id(session_id)
            if not session:
                return

            # Build context message
            lines = [f"# Working on: {task.id} {task.title}"]
            if task.spec_ref:
                lines.append(f"# Spec: {task.spec_ref}")
            if task.scope:
                lines.append(f"# Scope: {task.scope}")

            context_text = "\n".join(lines) + "\n"
            await session.async_send_text(context_text)

        except Exception as e:
            # Don't fail the spawn if context sending fails
            logger.debug("Failed to send task context to session: %s", e)

    # =========================================================================
    # Session Event Handlers
    # =========================================================================

    def on_session_spawned(self, event: SessionSpawned) -> None:
        """Handle session spawned event.

        Updates the display when a new session is spawned.

        Args:
            event: The session spawned event.
        """
        # Only refresh if this session is for our project
        if event.session.project_id == self.project.id:
            self._on_session_changed(event.session)

    def on_session_closed(self, event: SessionClosed) -> None:
        """Handle session closed event.

        Updates the display when a session is closed.

        Args:
            event: The session closed event.
        """
        # Only refresh if this session was for our project
        if event.session.project_id == self.project.id:
            self._on_session_changed(event.session)

    def on_session_status_changed(self, event: SessionStatusChanged) -> None:
        """Handle session status changed event.

        Updates the active work display when a session's attention state changes.
        This keeps the status indicators in sync with session activity.

        Args:
            event: The session status changed event.
        """
        # Only refresh if this session is for our project
        if event.session.project_id == self.project.id:
            self._on_session_changed(event.session)

    def _on_session_changed(self, session: ManagedSession) -> None:
        """Update display when a session changes.

        Refreshes the session dictionary and updates widgets.

        Args:
            session: The session that changed.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Rebuild session lookup with current state
        self._sessions = {}
        for s in app.state.sessions.values():
            self._sessions[s.id] = s

        # Get project sessions for the session list widget
        project_sessions = [
            s for s in app.state.sessions.values()
            if s.project_id == self.project.id
        ]

        # Update widgets
        self._refresh_widgets(project_sessions)

    # =========================================================================
    # Dependency View
    # =========================================================================

    def action_view_dependencies(self) -> None:
        """Show dependency chain for the selected task.

        Opens the DependencyChainModal showing the full dependency chain
        for the currently selected task (if it's blocked).
        """
        task = self._get_selected_task()

        if not task:
            self.notify("No task selected", severity="warning")
            return

        if not self._plan:
            self.notify("No plan loaded", severity="warning")
            return

        # Check if task is blocked - show modal for blocked tasks
        queue = self.query_one("#task-queue", TaskQueueWidget)
        if not queue.is_task_blocked(task):
            self.notify(f"Task {task.id} is not blocked", severity="information")
            return

        # Show dependency chain modal
        from iterm_controller.screens.modals import DependencyChainModal

        self.app.push_screen(DependencyChainModal(task, self._plan))
