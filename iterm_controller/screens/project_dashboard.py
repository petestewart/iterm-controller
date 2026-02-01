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
