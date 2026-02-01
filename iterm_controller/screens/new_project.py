"""Project creation form.

Screen for creating a new project from a template.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static

from iterm_controller.config import save_global_config
from iterm_controller.templates import SetupScriptError, TemplateRunner

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp
    from iterm_controller.models import ProjectTemplate


class NewProjectScreen(Screen):
    """Create a new project from template.

    Allows users to create a new project by selecting a template, entering
    a name and path, and optionally specifying a git branch. The screen
    handles template setup scripts, initial session spawning, and git
    branch creation.
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Cancel"),
        Binding("ctrl+s", "save", "Create"),
    ]

    def __init__(self) -> None:
        """Initialize the screen."""
        super().__init__()
        self._creating = False  # Prevent double-submission

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            Vertical(
                Static("Create New Project", id="title", classes="title"),
                Label("Select Template"),
                Select(
                    id="template-select",
                    options=[],
                    prompt="Choose a template...",
                ),
                Label("Project Name"),
                Input(id="name-input", placeholder="my-project"),
                Label("Path"),
                Input(id="path-input", placeholder="/path/to/project"),
                Label("Git Branch (optional)"),
                Input(id="branch-input", placeholder="feature/new-thing"),
                Label("Jira Ticket (optional)"),
                Input(id="jira-input", placeholder="PROJ-123"),
                Static("", id="status-message", classes="status"),
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
        """Initialize the form with template options."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Populate template options from config
        select = self.query_one("#template-select", Select)
        options: list[tuple[str, str]] = []

        if app.state.config and app.state.config.templates:
            options = [(t.id, t.name) for t in app.state.config.templates]

        # Always add a "No Template" option for creating empty projects
        options.insert(0, ("", "(No template - empty project)"))
        select.set_options(options)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel":
            self.app.pop_screen()
        elif event.button.id == "create":
            await self.action_save()

    def _get_template(self, template_id: str) -> ProjectTemplate | None:
        """Get template by ID from config.

        Args:
            template_id: The template ID to look up.

        Returns:
            The template if found, None otherwise.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        if not app.state.config or not app.state.config.templates:
            return None
        for t in app.state.config.templates:
            if t.id == template_id:
                return t
        return None

    def _update_status(self, message: str, is_error: bool = False) -> None:
        """Update the status message display.

        Args:
            message: The message to display.
            is_error: If True, display as an error.
        """
        status = self.query_one("#status-message", Static)
        if is_error:
            status.update(f"[red]{message}[/red]")
        else:
            status.update(f"[dim]{message}[/dim]")

    def _set_form_enabled(self, enabled: bool) -> None:
        """Enable or disable form inputs during project creation.

        Args:
            enabled: If True, enable form inputs; otherwise disable.
        """
        self.query_one("#name-input", Input).disabled = not enabled
        self.query_one("#path-input", Input).disabled = not enabled
        self.query_one("#branch-input", Input).disabled = not enabled
        self.query_one("#jira-input", Input).disabled = not enabled
        self.query_one("#template-select", Select).disabled = not enabled
        self.query_one("#create", Button).disabled = not enabled

    async def action_save(self) -> None:
        """Create the project from form values."""
        if self._creating:
            return  # Prevent double-submission

        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Get form values
        name = self.query_one("#name-input", Input).value.strip()
        path_value = self.query_one("#path-input", Input).value.strip()
        branch = self.query_one("#branch-input", Input).value.strip()
        jira_ticket = self.query_one("#jira-input", Input).value.strip() or None
        template_select = self.query_one("#template-select", Select)
        template_id = str(template_select.value) if template_select.value else ""

        # Validate required fields
        if not name:
            self._update_status("Project name is required", is_error=True)
            self.query_one("#name-input", Input).focus()
            return

        if not path_value:
            self._update_status("Project path is required", is_error=True)
            self.query_one("#path-input", Input).focus()
            return

        # Expand path (handle ~ for home directory)
        project_path = Path(os.path.expanduser(path_value)).resolve()

        # Check if path already exists with content
        if project_path.exists() and any(project_path.iterdir()):
            self._update_status(
                f"Directory {project_path} already exists and is not empty",
                is_error=True,
            )
            return

        # Check if project name already exists in config
        if name in app.state.projects:
            self._update_status(
                f"A project named '{name}' already exists",
                is_error=True,
            )
            return

        self._creating = True
        self._set_form_enabled(False)

        try:
            # Get template if selected
            template = self._get_template(template_id) if template_id else None

            # Form values for template variable substitution
            form_values = {
                "name": name,
                "path": str(project_path),
                "branch": branch,
                "jira_ticket": jira_ticket,
            }

            if template:
                self._update_status("Running setup from template...")
                await self._create_from_template(
                    template, str(project_path), form_values, branch
                )
            else:
                self._update_status("Creating project directory...")
                await self._create_empty_project(name, str(project_path), branch, jira_ticket)

            self.notify(f"Project '{name}' created successfully!", severity="information")
            self.app.pop_screen()

        except SetupScriptError as e:
            self._update_status(f"Setup script failed: {e}", is_error=True)
            self.notify(f"Setup script failed: {e}", severity="error")
        except OSError as e:
            self._update_status(f"File system error: {e}", is_error=True)
            self.notify(f"Failed to create project: {e}", severity="error")
        except Exception as e:
            self._update_status(f"Unexpected error: {e}", is_error=True)
            self.notify(f"Failed to create project: {e}", severity="error")
        finally:
            self._creating = False
            self._set_form_enabled(True)

    async def _create_from_template(
        self,
        template: ProjectTemplate,
        project_path: str,
        form_values: dict[str, str],
        branch: str,
    ) -> None:
        """Create a project from a template.

        Args:
            template: The template to use.
            project_path: Path where the project should be created.
            form_values: Form values for variable substitution.
            branch: Optional git branch to create.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Use TemplateRunner to create the project
        runner = TemplateRunner()
        project = await runner.create_from_template(template, project_path, form_values)

        # Create git branch if specified
        if branch:
            self._update_status(f"Creating git branch '{branch}'...")
            await self._create_git_branch(project_path, branch)

        # Add project to state
        app.state.projects[project.id] = project

        # Save to config
        self._update_status("Saving configuration...")
        await self._save_project_to_config(project)

        # Spawn initial sessions if template specifies them
        if template.initial_sessions:
            self._update_status("Spawning initial sessions...")
            await self._spawn_initial_sessions(project, template)

    async def _create_empty_project(
        self, name: str, project_path: str, branch: str, jira_ticket: str | None
    ) -> None:
        """Create an empty project without a template.

        Args:
            name: The project name.
            project_path: Path where the project should be created.
            branch: Optional git branch to create.
            jira_ticket: Optional Jira ticket number.
        """
        from iterm_controller.models import Project

        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Create directory
        path = Path(project_path)
        path.mkdir(parents=True, exist_ok=True)

        # Create project object
        project = Project(
            id=name,
            name=name,
            path=str(path.resolve()),
            jira_ticket=jira_ticket,
        )

        # Create git branch if specified
        if branch:
            self._update_status(f"Creating git branch '{branch}'...")
            await self._create_git_branch(project_path, branch)

        # Add project to state
        app.state.projects[project.id] = project

        # Save to config
        self._update_status("Saving configuration...")
        await self._save_project_to_config(project)

    async def _create_git_branch(self, project_path: str, branch: str) -> None:
        """Create and checkout a git branch.

        If the directory is not a git repository, initialize one first.

        Args:
            project_path: The project directory.
            branch: The branch name to create.
        """
        path = Path(project_path)

        # Check if it's a git repository
        git_dir = path / ".git"
        if not git_dir.exists():
            # Initialize git repo
            process = await asyncio.create_subprocess_exec(
                "git", "init",
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()

        # Create and checkout branch
        process = await asyncio.create_subprocess_exec(
            "git", "checkout", "-b", branch,
            cwd=path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        # If branch already exists, try to just checkout
        if process.returncode != 0:
            process = await asyncio.create_subprocess_exec(
                "git", "checkout", branch,
                cwd=path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()

    async def _save_project_to_config(self, project: Project) -> None:
        """Save the project to the global configuration.

        Args:
            project: The project to save.
        """
        from iterm_controller.models import Project as ProjectModel

        app: ItermControllerApp = self.app  # type: ignore[assignment]

        if app.state.config:
            # Add project to config's project list
            # Check if it already exists and update, otherwise append
            existing_idx = None
            for i, p in enumerate(app.state.config.projects):
                if p.id == project.id:
                    existing_idx = i
                    break

            if existing_idx is not None:
                app.state.config.projects[existing_idx] = project
            else:
                app.state.config.projects.append(project)

            # Save to disk
            save_global_config(app.state.config)

    async def _spawn_initial_sessions(
        self, project: Project, template: ProjectTemplate
    ) -> None:
        """Spawn initial sessions defined in the template.

        Args:
            project: The project to spawn sessions for.
            template: The template containing session definitions.
        """
        from iterm_controller.iterm_api import SessionSpawner

        app: ItermControllerApp = self.app  # type: ignore[assignment]

        if not app.iterm.is_connected:
            self.notify("iTerm2 not connected, skipping session spawn", severity="warning")
            return

        # Build session template lookup
        session_templates = {}
        if app.state.config:
            for st in app.state.config.session_templates:
                session_templates[st.id] = st

        spawner = SessionSpawner(app.iterm)

        for session_id in template.initial_sessions:
            session_template = session_templates.get(session_id)
            if session_template:
                result = await spawner.spawn_session(session_template, project)
                if result.success:
                    # Add to app state
                    managed = spawner.get_session(result.session_id)
                    if managed:
                        app.state.add_session(managed)
            else:
                self.notify(
                    f"Session template '{session_id}' not found",
                    severity="warning",
                )
