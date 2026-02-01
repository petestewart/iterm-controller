"""Base class for workflow mode screens.

Provides common navigation bindings and behavior for Plan, Docs, Work, and Test mode screens.
All mode screens inherit from this base class to get consistent 1-4 mode switching and
Esc to return to the project dashboard.

See specs/workflow-modes.md for full specification.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.binding import Binding
from textual.screen import Screen

from iterm_controller.models import WorkflowMode

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp
    from iterm_controller.models import Project


class ModeScreen(Screen):
    """Base class for workflow mode screens.

    All mode screens share common navigation bindings:
    - 1: Switch to Plan Mode
    - 2: Switch to Docs Mode
    - 3: Switch to Work Mode
    - 4: Switch to Test Mode
    - Esc: Return to Project Dashboard

    Subclasses should:
    - Set CURRENT_MODE to indicate which mode they represent
    - Override compose() to build their UI
    - Override on_mount() to load data (calling super().on_mount() first)
    """

    BINDINGS = [
        Binding("1", "switch_mode('plan')", "Plan"),
        Binding("2", "switch_mode('docs')", "Docs"),
        Binding("3", "switch_mode('work')", "Work"),
        Binding("4", "switch_mode('test')", "Test"),
        Binding("escape", "back_to_dashboard", "Back"),
    ]

    # Subclasses should override this to indicate their mode
    CURRENT_MODE: WorkflowMode | None = None

    def __init__(self, project: Project) -> None:
        """Initialize with project.

        Args:
            project: The project to display in this mode screen.
        """
        super().__init__()
        self.project = project

    async def on_mount(self) -> None:
        """Set subtitle to project name when screen mounts."""
        self.sub_title = f"{self.project.name}"
        if self.CURRENT_MODE:
            self.sub_title = f"{self.project.name} - {self.CURRENT_MODE.value.title()} Mode"

    def action_switch_mode(self, mode: str) -> None:
        """Switch to another workflow mode.

        Updates the project's last_mode and pushes the appropriate mode screen.
        If already in the target mode, does nothing.

        Args:
            mode: The mode to switch to ('plan', 'docs', 'work', or 'test').
        """
        try:
            workflow_mode = WorkflowMode(mode)
        except ValueError:
            self.notify(f"Invalid mode: {mode}", severity="error")
            return

        # Don't switch if already in this mode
        if self.CURRENT_MODE == workflow_mode:
            return

        # Update project's last_mode
        self.project.last_mode = workflow_mode

        # Save project state
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        app.state.update_project(self.project)

        # Get the appropriate screen class
        screen = self._get_mode_screen(workflow_mode)
        if screen:
            # Replace current screen with new mode screen
            self.app.switch_screen(screen)
        else:
            self.notify(f"{workflow_mode.value.title()} Mode not yet implemented")

    def _get_mode_screen(self, mode: WorkflowMode) -> Screen | None:
        """Get the screen instance for a workflow mode.

        Args:
            mode: The workflow mode.

        Returns:
            The screen instance, or None if not yet implemented.
        """
        # Import mode screens here to avoid circular imports
        # These will be implemented in Phase 13-16
        from iterm_controller.screens.modes import (
            DocsModeScreen,
            PlanModeScreen,
            TestModeScreen,
            WorkModeScreen,
        )

        mode_screen_map = {
            WorkflowMode.PLAN: PlanModeScreen,
            WorkflowMode.DOCS: DocsModeScreen,
            WorkflowMode.WORK: WorkModeScreen,
            WorkflowMode.TEST: TestModeScreen,
        }

        screen_class = mode_screen_map.get(mode)
        if screen_class:
            return screen_class(self.project)
        return None

    def action_back_to_dashboard(self) -> None:
        """Return to the project dashboard."""
        self.app.pop_screen()
