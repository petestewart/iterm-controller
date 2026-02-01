"""Single project view.

Dashboard for a single project with tasks, sessions, and workflow status.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from iterm_controller.state import (
    HealthStatusChanged,
    PlanReloaded,
    SessionClosed,
    SessionSpawned,
    SessionStatusChanged,
    TaskStatusChanged,
    WorkflowStageChanged,
)

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp


class ProjectDashboardScreen(Screen):
    """Dashboard for a single project."""

    BINDINGS = [
        Binding("t", "toggle_task", "Toggle Task"),
        Binding("s", "spawn_session", "Spawn"),
        Binding("r", "run_script", "Run Script"),
        Binding("d", "open_docs", "Docs"),
        Binding("g", "github_actions", "GitHub"),
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
                    Static("Tasks", id="tasks-header", classes="section-header"),
                    Static("[dim]No tasks loaded[/dim]", id="tasks-list"),
                    Static("Sessions", id="sessions-header", classes="section-header"),
                    Static("[dim]No sessions[/dim]", id="sessions-list"),
                    id="left-panel",
                ),
                Vertical(
                    Static("GitHub", id="github-header", classes="section-header"),
                    Static("[dim]Not connected[/dim]", id="github-panel"),
                    Static("Health", id="health-header", classes="section-header"),
                    Static("[dim]No health checks[/dim]", id="health-panel"),
                    id="right-panel",
                ),
                id="panels",
            ),
            Static(
                "[dim]Planning → Execute → Review → PR → Done[/dim]",
                id="workflow-bar",
            ),
            id="main",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Load project data when screen mounts."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        project = app.state.projects.get(self.project_id)

        if project:
            self.sub_title = project.name
        else:
            self.notify("Project not found", severity="error")

    def action_toggle_task(self) -> None:
        """Toggle the selected task status."""
        self.notify("Toggle task: Not implemented yet")

    def action_spawn_session(self) -> None:
        """Spawn a new session."""
        self.notify("Spawn session: Not implemented yet")

    def action_run_script(self) -> None:
        """Show script picker modal."""
        self.notify("Run script: Not implemented yet")

    def action_open_docs(self) -> None:
        """Show docs picker modal."""
        self.notify("Open docs: Not implemented yet")

    def action_github_actions(self) -> None:
        """Show GitHub actions modal."""
        self.notify("GitHub actions: Not implemented yet")

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
            self.call_later(self._refresh_tasks)

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
            self.call_later(self._refresh_workflow)

    # =========================================================================
    # Refresh Methods
    # =========================================================================

    async def _refresh_sessions(self) -> None:
        """Refresh the session list display."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        sessions = app.state.get_sessions_for_project(self.project_id)
        sessions_list = self.query_one("#sessions-list", Static)

        if sessions:
            lines = []
            for session in sessions:
                icon = {
                    "waiting": "[yellow]⧖[/yellow]",
                    "working": "[green]●[/green]",
                    "idle": "[dim]○[/dim]",
                }.get(session.attention_state.value, "○")
                lines.append(f"{icon} {session.template_id}")
            sessions_list.update("\n".join(lines))
        else:
            sessions_list.update("[dim]No sessions[/dim]")

    async def _refresh_tasks(self) -> None:
        """Refresh the task list display."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        plan = app.state.get_plan(self.project_id)
        tasks_list = self.query_one("#tasks-list", Static)

        if plan and plan.all_tasks:
            lines = []
            for task in plan.all_tasks:
                status_icon = {
                    "pending": "[dim]○[/dim]",
                    "in_progress": "[yellow]⧖[/yellow]",
                    "complete": "[green]✓[/green]",
                    "skipped": "[dim]⊘[/dim]",
                    "blocked": "[red]⊘[/red]",
                }.get(task.status.value, "○")
                lines.append(f"{status_icon} {task.id} {task.title}")
            tasks_list.update("\n".join(lines))
        else:
            tasks_list.update("[dim]No tasks loaded[/dim]")

    async def _refresh_health(self) -> None:
        """Refresh the health status display."""
        # Placeholder - will be implemented with health check widget
        pass

    async def _refresh_workflow(self) -> None:
        """Refresh the workflow bar display."""
        # Placeholder - will be implemented with workflow bar widget
        pass
