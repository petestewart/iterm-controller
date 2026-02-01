"""Base class for workflow mode screens.

Provides common navigation bindings and behavior for Plan, Docs, Work, and Test mode screens.
All mode screens inherit from this base class to get consistent 1-4 mode switching and
Esc to return to the project dashboard.

See specs/workflow-modes.md for full specification.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from textual.binding import Binding
from textual.screen import Screen

from iterm_controller.models import WorkflowMode

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp
    from iterm_controller.models import Project

logger = logging.getLogger(__name__)


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

    # Track whether mode command has been triggered for this screen instance
    _mode_command_triggered: bool = False

    def __init__(self, project: Project) -> None:
        """Initialize with project.

        Args:
            project: The project to display in this mode screen.
        """
        super().__init__()
        self.project = project
        self._mode_command_triggered = False

    async def on_mount(self) -> None:
        """Set subtitle to project name when screen mounts.

        Also triggers mode-specific auto mode commands if configured.
        """
        self.sub_title = f"{self.project.name}"
        if self.CURRENT_MODE:
            self.sub_title = f"{self.project.name} - {self.CURRENT_MODE.value.title()} Mode"

        # Trigger mode command if configured (only once per screen instance)
        if self.CURRENT_MODE and not self._mode_command_triggered:
            self._mode_command_triggered = True
            await self._trigger_mode_command()

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

    async def _trigger_mode_command(self) -> None:
        """Trigger mode-specific auto mode command if configured.

        Checks if auto mode is enabled and a command is configured for
        the current mode. If so, shows confirmation (if required) and
        executes the command.

        See specs/auto-mode.md#mode-specific-automation for specification.
        """
        if not self.CURRENT_MODE:
            return

        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Check if auto mode is configured
        if not app.state.config or not app.state.config.auto_mode:
            return

        auto_mode_config = app.state.config.auto_mode
        if not auto_mode_config.enabled:
            logger.debug("Auto mode disabled, skipping mode command trigger")
            return

        # Check if a command is configured for this mode
        command = auto_mode_config.mode_commands.get(self.CURRENT_MODE.value)
        if not command:
            logger.debug(f"No mode command configured for {self.CURRENT_MODE.value}")
            return

        logger.info(f"Triggering mode command for {self.CURRENT_MODE.value}: {command}")

        # Use the AutoAdvanceHandler to handle the mode entry
        from iterm_controller.auto_mode import AutoAdvanceHandler

        handler = AutoAdvanceHandler(
            config=auto_mode_config,
            iterm=app.iterm,
            app=app,
        )

        result = await handler.handle_mode_enter(self.CURRENT_MODE)

        if result:
            if result.success:
                self.notify(f"Running: {command}")
            elif result.error and result.error != "User declined confirmation":
                self.notify(f"Failed to run command: {result.error}", severity="error")

    def _open_in_editor(
        self, path: Path, editor_cmd: str, display_name: str | None = None
    ) -> None:
        """Open a file or directory in the configured editor.

        This is a shared utility method for all mode screens that need to open
        files in an external editor. It handles fallback to macOS `open` command
        if the configured editor is not found.

        Args:
            path: Path to the file or directory to open.
            editor_cmd: The editor command to use (e.g., "code", "cursor").
            display_name: Name to show in notifications. Defaults to path.name.
        """
        if display_name is None:
            display_name = path.name

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
