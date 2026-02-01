"""Single project view.

Dashboard for a single project with tasks, sessions, and workflow status.

Layout:
┌────────────────────────────────────────────────────────────────┐
│ my-project                                         [?] Help    │
├────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────┬──────────────────────────────┐ │
│ │ Tasks              Progress │ GitHub                       │ │
│ │ ▼ Phase 1           3/4     │ Branch: feature/auth         │ │
│ │   ✓ 1.1 Setup          Done │ ↑2 ↓0 from main              │ │
│ │   ✓ 1.2 Models         Done │                              │ │
│ │   ● 1.3 API      In Progress│ PR #42: Add auth             │ │
│ │   ○ 1.4 Tests       Pending │ ● Checks passing             │ │
│ │ ▼ Phase 2           0/3     │ 2 reviews pending            │ │
│ │   ⊘ 2.1 Auth      blocked   │                              │ │
│ │   ⊘ 2.2 Login     blocked   │                              │ │
│ ├─────────────────────────────┼──────────────────────────────┤ │
│ │ Sessions                    │ Health                       │ │
│ │ ● API Server       Working  │ API ● Web ● DB ○             │ │
│ │ ⧖ Claude           Waiting  │                              │ │
│ │ ○ Tests            Idle     │                              │ │
│ └─────────────────────────────┴──────────────────────────────┘ │
│                                                                │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ Planning ✓ → [Execute] → Review → PR → Done                │ │
│ └────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────┤
│ t Toggle  s Spawn  r Script  d Docs  g GitHub  Esc Back        │
└────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from iterm_controller.models import ManagedSession, WorkflowMode
from iterm_controller.state import (
    HealthStatusChanged,
    PlanReloaded,
    SessionClosed,
    SessionSpawned,
    SessionStatusChanged,
    TaskStatusChanged,
    WorkflowStageChanged,
)
from iterm_controller.widgets import (
    HealthStatusWidget,
    SessionListWidget,
    TaskListWidget,
    TaskProgressWidget,
    WorkflowBarWidget,
)

if TYPE_CHECKING:
    from pathlib import Path

    from iterm_controller.app import ItermControllerApp
    from iterm_controller.models import SessionTemplate


class ProjectDashboardScreen(Screen):
    """Dashboard for a single project.

    This screen provides a comprehensive view of a single project including:
    - Task list from PLAN.md with phases and dependencies
    - Task progress statistics
    - Active sessions with status indicators
    - GitHub integration status (branch, PR info)
    - Health check status
    - Workflow stage progression bar

    Users can toggle task status, spawn new sessions, run scripts,
    access documentation, and view GitHub actions.
    """

    BINDINGS = [
        Binding("t", "toggle_task", "Toggle Task"),
        Binding("s", "spawn_session", "Spawn"),
        Binding("r", "run_script", "Run Script"),
        Binding("d", "open_docs", "Docs"),
        Binding("g", "github_actions", "GitHub"),
        Binding("f", "focus_session", "Focus"),
        Binding("k", "kill_session", "Kill"),
        Binding("a", "toggle_auto_mode", "Auto Mode"),
        Binding("1", "enter_mode('plan')", "Plan"),
        Binding("2", "enter_mode('docs')", "Docs Mode"),
        Binding("3", "enter_mode('work')", "Work"),
        Binding("4", "enter_mode('test')", "Test"),
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, project_id: str) -> None:
        """Initialize with project ID.

        Args:
            project_id: ID of the project to display.
        """
        super().__init__()
        self.project_id = project_id

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            Horizontal(
                Vertical(
                    Horizontal(
                        Static("Tasks", id="tasks-header", classes="section-header"),
                        TaskProgressWidget(id="task-progress"),
                        id="tasks-header-row",
                    ),
                    TaskListWidget(id="tasks"),
                    Static("Sessions", id="sessions-header", classes="section-header"),
                    SessionListWidget(id="sessions", show_project=False),
                    id="left-panel",
                ),
                Vertical(
                    Static("GitHub", id="github-header", classes="section-header"),
                    Static("[dim]Not connected[/dim]", id="github-panel"),
                    Static("Health", id="health-header", classes="section-header"),
                    HealthStatusWidget(id="health-panel"),
                    id="right-panel",
                ),
                id="panels",
            ),
            WorkflowBarWidget(id="workflow-bar"),
            id="main",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Load project data when screen mounts."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        project = app.state.projects.get(self.project_id)

        if project:
            self.sub_title = project.name
            # Load initial data
            await self._refresh_all()
        else:
            self.notify("Project not found", severity="error")

    async def _refresh_all(self) -> None:
        """Refresh all display elements."""
        await self._refresh_tasks()
        await self._refresh_sessions()
        await self._refresh_health()
        await self._refresh_workflow()

    # =========================================================================
    # Actions
    # =========================================================================

    def action_toggle_task(self) -> None:
        """Toggle the selected task status.

        Cycles through: Pending → In Progress → Complete → Pending
        """
        # Get task list widget to find current selection
        task_widget = self.query_one("#tasks", TaskListWidget)
        in_progress = task_widget.get_in_progress_tasks()

        if in_progress:
            # Mark first in-progress task as complete
            task = in_progress[0]
            self.notify(f"Task toggle for {task.id}: Not fully implemented yet")
        else:
            # Find first pending task to start
            pending = task_widget.get_pending_tasks()
            if pending:
                task = pending[0]
                self.notify(f"Task toggle for {task.id}: Not fully implemented yet")
            else:
                self.notify("No tasks to toggle", severity="warning")

    def action_spawn_session(self) -> None:
        """Spawn a new session for this project."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Check if connected to iTerm2
        if not app.iterm.is_connected:
            self.notify("Not connected to iTerm2", severity="error")
            return

        # Get session templates from config
        if not app.state.config or not app.state.config.session_templates:
            self.notify("No session templates configured", severity="warning")
            return

        # Get project
        project = app.state.projects.get(self.project_id)
        if not project:
            self.notify("Project not found", severity="error")
            return

        # Show script picker modal to select a template
        from iterm_controller.screens.modals import ScriptPickerModal

        self.app.push_screen(ScriptPickerModal(), self._on_spawn_template_selected)

    async def _on_spawn_template_selected(self, template: "SessionTemplate | None") -> None:
        """Handle template selection from spawn session modal.

        Args:
            template: The selected template, or None if cancelled.
        """
        await self._spawn_session_from_template(template, "Spawned session")

    def action_run_script(self) -> None:
        """Show script picker modal and run selected script."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Check if connected to iTerm2
        if not app.iterm.is_connected:
            self.notify("Not connected to iTerm2", severity="error")
            return

        # Get session templates from config
        if not app.state.config or not app.state.config.session_templates:
            self.notify("No session templates configured", severity="warning")
            return

        # Get project
        project = app.state.projects.get(self.project_id)
        if not project:
            self.notify("Project not found", severity="error")
            return

        # Show script picker modal to select a template
        from iterm_controller.screens.modals import ScriptPickerModal

        self.app.push_screen(ScriptPickerModal(), self._on_run_script_template_selected)

    async def _on_run_script_template_selected(self, template: "SessionTemplate | None") -> None:
        """Handle template selection from run script modal.

        Args:
            template: The selected template, or None if cancelled.
        """
        await self._spawn_session_from_template(template, "Running script")

    async def _spawn_session_from_template(
        self, template: "SessionTemplate | None", success_prefix: str
    ) -> None:
        """Spawn a session from a selected template.

        Args:
            template: The selected template, or None if cancelled.
            success_prefix: Prefix for success notification (e.g., "Spawned session", "Running script").
        """
        if template is None:
            # User cancelled
            return

        app: ItermControllerApp = self.app  # type: ignore[assignment]
        project = app.state.projects.get(self.project_id)

        if not project:
            self.notify("Project not found", severity="error")
            return

        try:
            from iterm_controller.iterm_api import SessionSpawner

            spawner = SessionSpawner(app.iterm)
            result = await spawner.spawn_session(template, project)

            if result.success:
                # Add session to state
                managed = spawner.get_session(result.session_id)
                if managed:
                    app.state.add_session(managed)
                self.notify(f"{success_prefix}: {template.name}")
            else:
                self.notify(f"Failed: {result.error}", severity="error")
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    def action_open_docs(self) -> None:
        """Show docs picker modal."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Get project
        project = app.state.projects.get(self.project_id)
        if not project:
            self.notify("Project not found", severity="error")
            return

        from iterm_controller.screens.modals import DocsPickerModal

        self.app.push_screen(DocsPickerModal(project.path), self._on_docs_selected)

    def _on_docs_selected(self, doc_path: "Path | None") -> None:
        """Handle doc selection from docs picker modal.

        Args:
            doc_path: The selected document path, or None if cancelled.
        """
        if doc_path:
            self.notify(f"Opened: {doc_path.name}")

    def action_github_actions(self) -> None:
        """Show GitHub actions modal."""
        self.notify("GitHub actions: Not implemented yet")

    def action_enter_mode(self, mode: str) -> None:
        """Navigate to a workflow mode screen.

        This action is triggered by pressing 1-4 keys to switch between
        Plan, Docs, Work, and Test modes.

        Args:
            mode: The mode to enter ('plan', 'docs', 'work', or 'test').
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        project = app.state.projects.get(self.project_id)

        if not project:
            self.notify("Project not found", severity="error")
            return

        try:
            workflow_mode = WorkflowMode(mode)
        except ValueError:
            self.notify(f"Invalid mode: {mode}", severity="error")
            return

        # Update project's last_mode
        project.last_mode = workflow_mode

        # Push the appropriate mode screen
        mode_screen_map = {
            WorkflowMode.PLAN: "PlanModeScreen",
            WorkflowMode.DOCS: "DocsModeScreen",
            WorkflowMode.WORK: "WorkModeScreen",
            WorkflowMode.TEST: "TestModeScreen",
        }

        screen_name = mode_screen_map.get(workflow_mode)

        # Mode screens are not yet implemented (Phase 13-16)
        # For now, show a notification
        self.notify(f"Entering {workflow_mode.value.title()} Mode (screen not yet implemented)")

    async def action_toggle_auto_mode(self) -> None:
        """Toggle auto mode enabled/disabled or open config modal."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        if not app.state.config:
            self.notify("No configuration loaded", severity="error")
            return

        # Toggle auto mode
        auto_mode = app.state.config.auto_mode
        auto_mode.enabled = not auto_mode.enabled

        # Save config
        from iterm_controller.config import save_global_config

        save_global_config(app.state.config)

        status = "enabled" if auto_mode.enabled else "disabled"
        self.notify(f"Auto mode {status}")

    async def action_focus_session(self) -> None:
        """Focus the first WAITING session (or first session if none waiting)."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        session = self._get_selected_session()

        if not session:
            self.notify("No session to focus", severity="warning")
            return

        if not app.iterm.is_connected:
            self.notify("Not connected to iTerm2", severity="error")
            return

        try:
            iterm_session = await app.iterm.app.async_get_session_by_id(session.id)
            if not iterm_session:
                self.notify(f"Session not found: {session.template_id}", severity="error")
                return

            await iterm_session.async_activate()
            self.notify(f"Focused session: {session.template_id}")
        except Exception as e:
            self.notify(f"Error focusing session: {e}", severity="error")

    async def action_kill_session(self) -> None:
        """Kill the selected session."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        session = self._get_selected_session()

        if not session:
            self.notify("No session to kill", severity="warning")
            return

        if not app.iterm.is_connected:
            self.notify("Not connected to iTerm2", severity="error")
            return

        try:
            from iterm_controller.iterm_api import SessionTerminator

            terminator = SessionTerminator(app.iterm)

            iterm_session = await app.iterm.app.async_get_session_by_id(session.id)
            if not iterm_session:
                app.state.remove_session(session.id)
                self.notify(f"Session already closed: {session.template_id}")
                return

            result = await terminator.close_session(iterm_session)

            if result.success:
                app.state.remove_session(session.id)
                if result.force_required:
                    self.notify(f"Force-closed session: {session.template_id}")
                else:
                    self.notify(f"Closed session: {session.template_id}")
            else:
                self.notify(f"Failed to close session: {result.error}", severity="error")
        except Exception as e:
            self.notify(f"Error closing session: {e}", severity="error")

    def _get_selected_session(self) -> ManagedSession | None:
        """Get the currently selected session.

        Prioritizes WAITING sessions, then returns the first session.

        Returns:
            The selected session, or None if no sessions exist.
        """
        session_widget = self.query_one("#sessions", SessionListWidget)
        waiting = session_widget.get_waiting_sessions()
        if waiting:
            return waiting[0]
        if session_widget.sessions:
            return session_widget.sessions[0]
        return None

    # =========================================================================
    # State Event Handlers
    # =========================================================================

    def on_session_spawned(self, event: SessionSpawned) -> None:
        """Handle session spawned event."""
        if event.session.project_id == self.project_id:
            self.call_later(self._refresh_sessions)

    def on_session_closed(self, event: SessionClosed) -> None:
        """Handle session closed event."""
        if event.session.project_id == self.project_id:
            self.call_later(self._refresh_sessions)

    def on_session_status_changed(self, event: SessionStatusChanged) -> None:
        """Handle session status change event."""
        if event.session.project_id == self.project_id:
            self.call_later(self._refresh_sessions)

    def on_plan_reloaded(self, event: PlanReloaded) -> None:
        """Handle plan reloaded event."""
        if event.project_id == self.project_id:
            app: ItermControllerApp = self.app  # type: ignore[assignment]
            project = app.state.projects.get(self.project_id)

            # Update task list widget directly with project path for spec validation
            task_widget = self.query_one("#tasks", TaskListWidget)
            project_path = project.path if project else None
            task_widget.refresh_plan(event.plan, project_path=project_path)

            # Update progress widget
            progress_widget = self.query_one("#task-progress", TaskProgressWidget)
            progress_widget.refresh_plan(event.plan)

    def on_task_status_changed(self, event: TaskStatusChanged) -> None:
        """Handle task status change event."""
        if event.project_id == self.project_id:
            self.call_later(self._refresh_tasks)

    def on_health_status_changed(self, event: HealthStatusChanged) -> None:
        """Handle health status change event."""
        if event.project_id == self.project_id:
            self.call_later(self._refresh_health)

    def on_workflow_stage_changed(self, event: WorkflowStageChanged) -> None:
        """Handle workflow stage change event."""
        if event.project_id == self.project_id:
            # Update workflow bar widget directly
            workflow_widget = self.query_one("#workflow-bar", WorkflowBarWidget)
            from iterm_controller.models import WorkflowStage

            try:
                stage = WorkflowStage(event.stage)
                workflow_widget.set_stage(stage)
            except ValueError:
                pass

    # =========================================================================
    # Refresh Methods
    # =========================================================================

    async def _refresh_sessions(self) -> None:
        """Refresh the session list display."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        sessions = app.state.get_sessions_for_project(self.project_id)

        session_widget = self.query_one("#sessions", SessionListWidget)
        session_widget.refresh_sessions(sessions)

    async def _refresh_tasks(self) -> None:
        """Refresh the task list display."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        plan = app.state.get_plan(self.project_id)
        project = app.state.projects.get(self.project_id)

        task_widget = self.query_one("#tasks", TaskListWidget)
        progress_widget = self.query_one("#task-progress", TaskProgressWidget)

        if plan:
            project_path = project.path if project else None
            task_widget.refresh_plan(plan, project_path=project_path)
            progress_widget.refresh_plan(plan)

    async def _refresh_health(self) -> None:
        """Refresh the health status display."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        statuses = app.state.get_health_statuses(self.project_id)

        health_widget = self.query_one("#health-panel", HealthStatusWidget)
        health_widget.set_statuses(statuses)

    async def _refresh_workflow(self) -> None:
        """Refresh the workflow bar display."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        project = app.state.projects.get(self.project_id)

        if project:
            workflow_widget = self.query_one("#workflow-bar", WorkflowBarWidget)
            workflow_widget.update_state(project.workflow_state)
