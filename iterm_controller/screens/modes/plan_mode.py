"""Plan Mode screen.

Planning artifacts management screen showing PROBLEM.md, PRD.md, specs/, and PLAN.md.

See specs/plan-mode.md for full specification.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Footer, Header, Static

from iterm_controller.models import SessionTemplate, WorkflowMode
from iterm_controller.screens.mode_screen import ModeScreen
from iterm_controller.screens.modals.artifact_preview import ArtifactPreviewModal
from iterm_controller.security import get_safe_editor_command
from iterm_controller.widgets.artifact_list import ArtifactListWidget
from iterm_controller.widgets.mode_indicator import ModeIndicatorWidget
from iterm_controller.widgets.workflow_bar import WorkflowBarWidget

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp
    from iterm_controller.models import Project


# Claude commands for creating planning artifacts
# See specs/plan-mode.md#create-artifact-commands
ARTIFACT_COMMANDS = {
    "PROBLEM.md": "claude /problem-statement",
    "PRD.md": "claude /prd",
    "specs/": "claude /specs",
    "PLAN.md": "claude /plan",
}

# Editor command mapping (mirrors docs_picker.py)
EDITOR_COMMANDS = {
    "vscode": "code",
    "code": "code",
    "cursor": "cursor",
    "vim": "vim",
    "nvim": "nvim",
    "neovim": "nvim",
    "subl": "subl",
    "sublime": "subl",
    "atom": "atom",
    "nano": "nano",
    "emacs": "emacs",
}


class PlanModeScreen(ModeScreen):
    """Plan Mode screen for managing planning artifacts.

    This screen displays:
    - PROBLEM.md status and content
    - PRD.md status and content
    - specs/ directory listing
    - PLAN.md status and content

    Users can create missing artifacts, edit existing ones, and preview content.
    """

    CURRENT_MODE = WorkflowMode.PLAN

    BINDINGS = [
        *ModeScreen.BINDINGS,
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("enter", "view_artifact", "View"),
        Binding("e", "edit_artifact", "Edit"),
        Binding("c", "create_artifact", "Create"),
        Binding("s", "spawn_planning", "Spawn"),
        Binding("r", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    PlanModeScreen {
        layout: vertical;
    }

    PlanModeScreen #mode-indicator {
        dock: top;
        width: 100%;
        height: 1;
        background: $surface;
        padding: 0 1;
    }

    PlanModeScreen #main {
        height: 1fr;
        padding: 1;
    }

    PlanModeScreen #artifacts-container {
        height: 1fr;
    }

    PlanModeScreen #artifacts-title {
        dock: top;
        text-style: bold;
        padding: 0 0 1 0;
    }

    PlanModeScreen #workflow-container {
        dock: bottom;
        height: auto;
        padding-top: 1;
    }

    PlanModeScreen #workflow-label {
        text-style: bold;
        padding-bottom: 0;
    }

    PlanModeScreen #workflow-bar {
        padding-left: 0;
    }

    PlanModeScreen ArtifactListWidget {
        height: auto;
        min-height: 8;
    }
    """

    def __init__(self, project: Project) -> None:
        """Initialize the Plan Mode screen.

        Args:
            project: The project to display.
        """
        super().__init__(project)

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield ModeIndicatorWidget(current_mode=self.CURRENT_MODE, id="mode-indicator")
        yield Container(
            Vertical(
                Static("Planning Artifacts", id="artifacts-title"),
                ArtifactListWidget(project=self.project, id="artifacts"),
                id="artifacts-container",
            ),
            Vertical(
                Static("Workflow Stage:", id="workflow-label"),
                WorkflowBarWidget(
                    workflow_state=self.project.workflow_state,
                    id="workflow-bar",
                ),
                id="workflow-container",
            ),
            id="main",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Load artifact status when screen mounts."""
        await super().on_mount()
        self._refresh_artifacts()

    def _refresh_artifacts(self) -> None:
        """Refresh artifact status display."""
        artifact_widget = self.query_one("#artifacts", ArtifactListWidget)
        artifact_widget.refresh_status()

    def action_cursor_down(self) -> None:
        """Move cursor down in artifact list."""
        artifact_widget = self.query_one("#artifacts", ArtifactListWidget)
        artifact_widget.select_next()

    def action_cursor_up(self) -> None:
        """Move cursor up in artifact list."""
        artifact_widget = self.query_one("#artifacts", ArtifactListWidget)
        artifact_widget.select_previous()

    def action_view_artifact(self) -> None:
        """View the selected artifact (inline preview).

        Opens a preview modal showing the artifact content.
        For directories (specs/), toggles expansion instead.
        """
        artifact_widget = self.query_one("#artifacts", ArtifactListWidget)
        selected = artifact_widget.selected_artifact
        if not selected:
            self.notify("No artifact selected", severity="warning")
            return

        # For specs/, toggle expansion
        if selected == "specs/":
            artifact_widget.toggle_specs_expanded()
            return

        # Get the path and check if it exists
        path = artifact_widget.get_selected_path()
        if not path:
            return

        if not path.exists():
            self.notify(f"{selected} does not exist", severity="warning")
            return

        # For directories (like individual spec files shown under specs/),
        # just open in editor since we can't preview a directory
        if path.is_dir():
            self.action_edit_artifact()
            return

        # Open preview modal for files
        def handle_preview_result(result: str | None) -> None:
            """Handle the result from the preview modal."""
            if result == "edit":
                # User wants to edit - trigger edit action
                self.action_edit_artifact()

        self.app.push_screen(
            ArtifactPreviewModal(
                artifact_name=selected,
                artifact_path=path,
            ),
            handle_preview_result,
        )

    def action_edit_artifact(self) -> None:
        """Edit the selected artifact in configured editor.

        Opens the selected file in the configured IDE (default: vscode).
        For directories like specs/, opens the directory in the editor.
        """
        artifact_widget = self.query_one("#artifacts", ArtifactListWidget)
        selected = artifact_widget.selected_artifact
        if not selected:
            self.notify("No artifact selected", severity="warning")
            return

        path = artifact_widget.get_selected_path()
        if not path:
            return

        if not path.exists():
            self.notify(f"{selected} does not exist. Use 'c' to create it.", severity="warning")
            return

        # Get configured editor
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        ide = "code"  # default to VS Code
        if app.state.config and app.state.config.settings:
            ide = app.state.config.settings.default_ide

        # Get editor command - validated against allowlist
        editor_cmd = EDITOR_COMMANDS.get(ide.lower())
        if editor_cmd:
            # Validate the command from the mapping
            editor_cmd = get_safe_editor_command(editor_cmd, fallback="open")
        else:
            # Try to validate the IDE setting directly (might be a command)
            editor_cmd = get_safe_editor_command(ide, fallback="open")

        # Open file/directory in editor
        self._open_in_editor(path, editor_cmd, selected)

    def action_create_artifact(self) -> None:
        """Create a missing artifact using Claude.

        Spawns a new iTerm2 session with the appropriate Claude command
        for creating the selected artifact type.
        """
        artifact_widget = self.query_one("#artifacts", ArtifactListWidget)
        selected = artifact_widget.selected_artifact
        if not selected:
            self.notify("No artifact selected", severity="warning")
            return

        path = artifact_widget.get_selected_path()
        if not path:
            return

        if path.exists():
            self.notify(f"{selected} already exists. Use 'e' to edit.", severity="warning")
            return

        # Get the artifact name (for spec files, use the parent directory key)
        artifact_key = selected
        if selected.startswith("specs/") and selected != "specs/":
            artifact_key = "specs/"

        # Get the Claude command for this artifact
        command = ARTIFACT_COMMANDS.get(artifact_key)
        if not command:
            self.notify(f"No create command configured for {selected}", severity="warning")
            return

        # Spawn session with Claude command
        self._spawn_claude_session(command, f"Create {artifact_key}")

    def action_spawn_planning(self) -> None:
        """Spawn a planning session.

        Spawns a new iTerm2 session with a generic planning command.
        Uses the auto mode planning command if configured, otherwise
        spawns a claude session ready for planning work.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Check if auto mode has a configured planning command
        command = "claude"  # Default to plain claude session
        if app.state.config and app.state.config.auto_mode:
            stage_cmd = app.state.config.auto_mode.stage_commands.get("planning")
            if stage_cmd:
                command = stage_cmd

        self._spawn_claude_session(command, "Planning Session")

    def action_refresh(self) -> None:
        """Refresh artifact status."""
        self._refresh_artifacts()
        self.notify("Artifacts refreshed")

    def _open_in_editor(self, path: Path, editor_cmd: str, display_name: str) -> None:
        """Open a file or directory in the configured editor.

        Args:
            path: Path to the file or directory to open.
            editor_cmd: The editor command to use.
            display_name: Name to show in notifications.
        """

        async def _do_open() -> None:
            try:
                cmd = [editor_cmd, str(path)]
                await asyncio.to_thread(
                    subprocess.Popen,
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.notify(f"Opened {display_name} in {editor_cmd}")
            except FileNotFoundError:
                # Editor not found, try macOS open command
                try:
                    await asyncio.to_thread(
                        subprocess.Popen,
                        ["open", str(path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    self.notify(f"Opened {display_name}")
                except Exception as e:
                    self.notify(f"Failed to open {display_name}: {e}", severity="error")
            except Exception as e:
                self.notify(f"Failed to open {display_name}: {e}", severity="error")

        self.call_later(_do_open)

    def _spawn_claude_session(self, command: str, session_name: str) -> None:
        """Spawn a new iTerm2 session with a Claude command.

        Args:
            command: The command to run (e.g., "claude /prd").
            session_name: Display name for the session.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Check if connected to iTerm2
        if not app.iterm.is_connected:
            self.notify("Not connected to iTerm2", severity="error")
            return

        # Create a temporary session template for this command
        template = SessionTemplate(
            id=f"plan-mode-{session_name.lower().replace(' ', '-')}",
            name=session_name,
            command=command,
            working_dir=self.project.path,
        )

        async def _do_spawn() -> None:
            result = await app.api.spawn_session_with_template(self.project, template)
            if result.success:
                self.notify(f"Spawned: {session_name}")
                # Refresh artifacts after spawning (in case it creates files)
                self._refresh_artifacts()
            else:
                self.notify(f"Failed to spawn session: {result.error}", severity="error")

        self.call_later(_do_spawn)
