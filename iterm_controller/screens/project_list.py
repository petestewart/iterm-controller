"""Project browser.

Screen for browsing and selecting projects from configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp


class ProjectListScreen(Screen):
    """Browse and select projects."""

    BINDINGS = [
        Binding("enter", "open_project", "Open"),
        Binding("n", "new_project", "New Project"),
        Binding("d", "delete_project", "Delete"),
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            DataTable(id="project-table"),
            id="main",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the project table."""
        table = self.query_one("#project-table", DataTable)
        table.add_columns("Name", "Path", "Sessions", "Status")
        table.cursor_type = "row"

        app: ItermControllerApp = self.app  # type: ignore[assignment]
        for project in app.state.projects.values():
            table.add_row(
                project.name,
                project.path,
                str(len(project.sessions)),
                "Open" if project.is_open else "Closed",
            )

        if not app.state.projects:
            table.add_row("[dim]No projects configured[/dim]", "", "", "")

    def action_open_project(self) -> None:
        """Open the selected project."""
        table = self.query_one("#project-table", DataTable)
        if table.cursor_row is not None:
            row = table.get_row_at(table.cursor_row)
            if row and row[0]:
                self.notify(f"Would open project: {row[0]}")

    def action_new_project(self) -> None:
        """Create a new project."""
        from iterm_controller.screens.new_project import NewProjectScreen

        self.app.push_screen(NewProjectScreen())

    def action_delete_project(self) -> None:
        """Delete the selected project."""
        self.notify("Delete project: Not implemented yet")
