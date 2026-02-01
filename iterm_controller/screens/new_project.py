"""Project creation form.

Screen for creating a new project from a template.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp


class NewProjectScreen(Screen):
    """Create a new project from template."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Cancel"),
        Binding("ctrl+s", "save", "Create"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            Vertical(
                Static("Create New Project", id="title", classes="title"),
                Label("Select Template"),
                Select(
                    id="template-select",
                    options=[("default", "Default Template")],
                ),
                Label("Project Name"),
                Input(id="name-input", placeholder="my-project"),
                Label("Path"),
                Input(id="path-input", placeholder="/path/to/project"),
                Label("Git Branch"),
                Input(id="branch-input", placeholder="feature/new-thing"),
                Horizontal(
                    Button("Cancel", variant="default", id="cancel"),
                    Button("Create Project", variant="primary", id="create"),
                    id="buttons",
                ),
                id="form",
            ),
            id="main",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize the form."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Populate template options from config
        if app.state.config and app.state.config.templates:
            select = self.query_one("#template-select", Select)
            options = [(t.id, t.name) for t in app.state.config.templates]
            if options:
                select.set_options(options)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel":
            self.app.pop_screen()
        elif event.button.id == "create":
            await self.action_save()

    async def action_save(self) -> None:
        """Create the project."""
        name = self.query_one("#name-input", Input).value
        path = self.query_one("#path-input", Input).value

        # Validate
        if not name or not path:
            self.notify("Name and path are required", severity="error")
            return

        # TODO: Actually create project
        self.notify(f"Would create project '{name}' at {path}")
        self.app.pop_screen()
