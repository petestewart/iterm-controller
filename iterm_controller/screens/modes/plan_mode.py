"""Plan Mode screen.

Planning artifacts management screen showing PROBLEM.md, PRD.md, specs/, and PLAN.md.

See specs/plan-mode.md for full specification.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Footer, Header, Static

from iterm_controller.models import WorkflowMode
from iterm_controller.screens.mode_screen import ModeScreen
from iterm_controller.widgets.artifact_list import ArtifactListWidget
from iterm_controller.widgets.workflow_bar import WorkflowBarWidget

if TYPE_CHECKING:
    from iterm_controller.models import Project


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
        Implementation deferred to Phase 13 task: "Add inline artifact preview".
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

        if path.exists():
            self.notify(f"Preview: {selected} (inline preview coming in Phase 13)")
        else:
            self.notify(f"{selected} does not exist", severity="warning")

    def action_edit_artifact(self) -> None:
        """Edit the selected artifact in configured editor.

        Implementation deferred to Phase 13 task: "Add create/edit actions for artifacts".
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

        # TODO: Open in configured editor (Phase 13)
        self.notify(f"Edit: {selected} (editor integration coming in Phase 13)")

    def action_create_artifact(self) -> None:
        """Create a missing artifact using Claude.

        Implementation deferred to Phase 13 task: "Add create/edit actions for artifacts".
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

        # TODO: Launch Claude command (Phase 13)
        self.notify(f"Create: {selected} (Claude integration coming in Phase 13)")

    def action_spawn_planning(self) -> None:
        """Spawn a planning session.

        Implementation deferred to Phase 13 task: "Integrate with Auto Mode planning commands".
        """
        # TODO: Spawn session with planning command (Phase 13)
        self.notify("Spawn planning session (coming in Phase 13)")

    def action_refresh(self) -> None:
        """Refresh artifact status."""
        self._refresh_artifacts()
        self.notify("Artifacts refreshed")
