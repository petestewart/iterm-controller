"""Project browser.

Screen for browsing and selecting projects from configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.events import ScreenResume
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp


class ProjectListScreen(Screen):
    """Browse and select projects.

    Displays a table of all configured projects with their name, path,
    active session count, and status. Users can select a project to
    open its dashboard, create new projects, or delete existing ones.
    """

    BINDINGS = [
        Binding("enter", "open_project", "Open"),
        Binding("n", "new_project", "New Project"),
        Binding("d", "delete_project", "Delete"),
        Binding("r", "refresh", "Refresh"),
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self) -> None:
        """Initialize the screen."""
        super().__init__()
        # Map row keys to project IDs for lookup
        self._row_to_project_id: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            DataTable(id="project-table"),
            Static("", id="empty-message"),
            id="main",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the project table."""
        await self._populate_table()

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle Enter key on DataTable row.

        The DataTable widget intercepts Enter key presses and emits RowSelected
        instead of allowing the screen-level binding to fire. This handler
        bridges the gap by calling the same action.
        """
        await self.action_open_project()

    async def on_screen_resume(self, event: ScreenResume) -> None:
        """Refresh the project list when returning from another screen.

        This ensures the list is up-to-date after creating, editing, or
        deleting projects on other screens.
        """
        await self._populate_table()

    async def _populate_table(self) -> None:
        """Populate the project table with current project data."""
        table = self.query_one("#project-table", DataTable)
        empty_message = self.query_one("#empty-message", Static)

        # Clear existing data
        table.clear(columns=True)
        self._row_to_project_id.clear()

        app: ItermControllerApp = self.app  # type: ignore[assignment]

        if not app.state.projects:
            # Hide table and show empty message
            table.display = False
            empty_message.update(
                "[dim]No projects configured.\n\n"
                "Press [bold]n[/bold] to create a new project.[/dim]"
            )
            empty_message.display = True
            return

        # Show table and hide empty message
        table.display = True
        empty_message.display = False

        table.add_columns("Name", "Path", "Sessions", "Status")
        table.cursor_type = "row"

        for project in app.state.projects.values():
            # Count active sessions for this project
            session_count = len(app.state.get_sessions_for_project(project.id))
            status = "[green]Open[/green]" if project.is_open else "[dim]Closed[/dim]"

            row_key = table.add_row(
                project.name,
                self._truncate_path(project.path),
                str(session_count),
                status,
                key=project.id,
            )
            self._row_to_project_id[str(row_key)] = project.id

    def _truncate_path(self, path: str, max_length: int = 40) -> str:
        """Truncate a path for display, keeping the end visible.

        Args:
            path: The path to truncate.
            max_length: Maximum length before truncation.

        Returns:
            The truncated path with ellipsis if needed.
        """
        if len(path) <= max_length:
            return path
        return "..." + path[-(max_length - 3) :]

    def _get_selected_project_id(self) -> str | None:
        """Get the project ID of the currently selected row.

        Returns:
            The project ID if a valid row is selected, None otherwise.
        """
        table = self.query_one("#project-table", DataTable)

        cursor_coordinate = table.cursor_coordinate
        if cursor_coordinate is None:
            return None

        # Get the CellKey which contains row_key
        try:
            cell_key = table.coordinate_to_cell_key(cursor_coordinate)
            # The row_key.value is the project ID we passed to add_row
            return str(cell_key.row_key.value)
        except Exception:
            return None

    async def action_open_project(self) -> None:
        """Open the selected project in the unified project screen."""
        project_id = self._get_selected_project_id()

        if not project_id:
            self.notify("No project selected", severity="warning")
            return

        app: ItermControllerApp = self.app  # type: ignore[assignment]
        project = app.state.projects.get(project_id)

        if not project:
            self.notify("Project not found", severity="error")
            return

        # Open the project in state
        await app.state.open_project(project_id)

        # Push the unified project screen (replaces the old dashboard + mode screens)
        from iterm_controller.screens.project_screen import ProjectScreen

        self.app.push_screen(ProjectScreen(project_id))

    def action_new_project(self) -> None:
        """Create a new project."""
        from iterm_controller.screens.new_project import NewProjectScreen

        self.app.push_screen(NewProjectScreen())

    def action_delete_project(self) -> None:
        """Delete the selected project."""
        project_id = self._get_selected_project_id()

        if not project_id:
            self.notify("No project selected", severity="warning")
            return

        app: ItermControllerApp = self.app  # type: ignore[assignment]
        project = app.state.projects.get(project_id)

        if not project:
            self.notify("Project not found", severity="error")
            return

        if project.is_open:
            self.notify(
                "Cannot delete an open project. Close it first.",
                severity="error",
            )
            return

        # Show confirmation modal before deleting
        from iterm_controller.screens.modals import DeleteConfirmModal

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                self._do_delete_project(project_id)

        self.app.push_screen(
            DeleteConfirmModal(project.name, "project"),
            on_confirm,
        )

    def _do_delete_project(self, project_id: str) -> None:
        """Actually delete the project after confirmation.

        Args:
            project_id: ID of the project to delete.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        project = app.state.projects.get(project_id)

        if not project:
            return

        # Remove from state
        app.state.remove_project(project_id)

        # Refresh the table
        self.call_later(self._populate_table)
        self.notify(f"Project '{project.name}' deleted")

    async def action_refresh(self) -> None:
        """Refresh the project list."""
        await self._populate_table()
        self.notify("Project list refreshed")
