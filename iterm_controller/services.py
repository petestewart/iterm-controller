"""Service container for dependency injection.

This module provides a ServiceContainer that holds all injectable services,
enabling screens and other components to access services via the app rather
than instantiating them directly.

Services are initialized eagerly when the container is created, but the
actual iTerm2 connection is deferred until connect() is called.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from textual.screen import ModalScreen, Screen

from iterm_controller.git_service import GitService
from iterm_controller.github import GitHubIntegration
from iterm_controller.iterm import (
    FocusWatcher,
    ItermController,
    SessionSpawner,
    SessionTerminator,
    WindowLayoutManager,
    WindowLayoutSpawner,
)
from iterm_controller.models import WorkflowMode, WorkflowStage
from iterm_controller.notifications import Notifier
from iterm_controller.review_service import ReviewService

# Import all screens and modals in services.py - this is the single place where
# they are imported to avoid circular dependencies elsewhere
from iterm_controller.screens.modals.mode_command import ModeCommandModal
from iterm_controller.screens.modals.stage_advance import StageAdvanceModal
from iterm_controller.screens.modes.test_mode import TestModeScreen
from iterm_controller.script_service import ScriptService

if TYPE_CHECKING:
    from iterm_controller.models import Project, WindowLayout
    from iterm_controller.state.plan_manager import PlanStateManager

logger = logging.getLogger(__name__)


@dataclass
class ServiceContainer:
    """Container for all injectable services.

    This container holds references to all services that screens and other
    components need. Instead of screens instantiating services directly,
    they access them via the app's service container.

    Services are created during container initialization but remain
    disconnected until the async initialization methods are called.

    Attributes:
        iterm: The iTerm2 connection controller.
        spawner: Service for creating terminal sessions.
        terminator: Service for closing terminal sessions.
        layout_manager: Service for managing window layouts.
        layout_spawner: Service for spawning window layouts.
        github: GitHub integration service.
        notifier: macOS notification service.
        scripts: Script execution service.
        git: Git operations service.
        reviews: Review pipeline service.
    """

    iterm: ItermController
    spawner: SessionSpawner
    terminator: SessionTerminator
    layout_manager: WindowLayoutManager
    layout_spawner: WindowLayoutSpawner
    focus_watcher: FocusWatcher
    github: GitHubIntegration
    notifier: Notifier
    scripts: ScriptService
    git: GitService
    reviews: ReviewService

    @classmethod
    def create(cls, plan_manager: PlanStateManager | None = None) -> ServiceContainer:
        """Create a new service container with all services initialized.

        The services are created but not yet connected. Call the async
        initialization methods (connect_iterm, initialize_github, etc.)
        to complete setup.

        Args:
            plan_manager: Optional PlanStateManager for ReviewService.
                         If not provided, ReviewService will have limited
                         functionality (cannot update task status).

        Returns:
            A new ServiceContainer with all services.
        """
        # Create the core iTerm2 controller
        iterm = ItermController()

        # Create dependent services
        spawner = SessionSpawner(iterm)
        terminator = SessionTerminator(iterm)
        layout_manager = WindowLayoutManager(iterm)
        layout_spawner = WindowLayoutSpawner(iterm, spawner)
        focus_watcher = FocusWatcher(iterm)

        # Create integration services
        github = GitHubIntegration()
        notifier = Notifier()
        scripts = ScriptService(spawner)

        # Create git service
        git = GitService()

        # Create review service (needs spawner, git, and plan manager)
        # Import here to avoid circular import issues with PlanStateManager
        reviews = ReviewService(
            session_spawner=spawner,
            git_service=git,
            plan_manager=plan_manager,  # type: ignore[arg-type]
            notifier=notifier,
        )

        return cls(
            iterm=iterm,
            spawner=spawner,
            terminator=terminator,
            layout_manager=layout_manager,
            layout_spawner=layout_spawner,
            focus_watcher=focus_watcher,
            github=github,
            notifier=notifier,
            scripts=scripts,
            git=git,
            reviews=reviews,
        )

    async def connect_iterm(self) -> None:
        """Connect to iTerm2.

        Raises:
            Exception: If the connection fails.
        """
        await self.iterm.connect()

    async def disconnect_iterm(self) -> None:
        """Disconnect from iTerm2."""
        # Stop focus watcher before disconnecting
        await self.focus_watcher.stop()
        await self.iterm.disconnect()

    async def start_focus_watcher(
        self, on_tab_focused: Callable[[], None] | None = None
    ) -> None:
        """Start the focus watcher to monitor tab selection changes.

        Args:
            on_tab_focused: Callback to invoke when the TUI's tab becomes active.
        """
        if on_tab_focused:
            self.focus_watcher.on_tab_focused = on_tab_focused
        await self.focus_watcher.start()

    async def stop_focus_watcher(self) -> None:
        """Stop the focus watcher."""
        await self.focus_watcher.stop()

    async def initialize_github(self) -> None:
        """Initialize the GitHub integration."""
        await self.github.initialize()

    def load_layouts(self, layouts: list[WindowLayout]) -> None:
        """Load window layouts into the layout manager.

        Args:
            layouts: The window layouts to load.
        """
        self.layout_manager.load_from_config(layouts)

    @property
    def is_connected(self) -> bool:
        """Check if connected to iTerm2."""
        return self.iterm.is_connected


class ScreenFactory:
    """Factory for creating screens and modals without circular imports.

    This factory is the single point where screen/modal classes are
    instantiated. By centralizing these imports in services.py, we avoid
    circular imports between auto_mode.py, mode_screen.py, and the
    screens/modals packages.

    The factory implements ScreenFactoryProtocol from ports.py.
    """

    # Map of workflow mode names to screen classes
    # Plan, Docs, and Work modes were removed in task 27.9.3
    _mode_screen_map: dict[str, type[Screen]] = {
        "test": TestModeScreen,
    }

    def create_mode_command_modal(
        self, mode: str, command: str
    ) -> ModalScreen[bool]:
        """Create a modal for confirming mode command execution.

        Args:
            mode: The workflow mode name ('plan', 'docs', 'work', 'test').
            command: The command that will be executed.

        Returns:
            A ModeCommandModal that returns True if confirmed, False if cancelled.
        """
        try:
            workflow_mode = WorkflowMode(mode)
        except ValueError:
            # Default to PLAN if invalid mode
            workflow_mode = WorkflowMode.PLAN

        return ModeCommandModal(workflow_mode, command)

    def create_stage_advance_modal(
        self, stage: str, command: str
    ) -> ModalScreen[bool]:
        """Create a modal for confirming stage advancement.

        Args:
            stage: The workflow stage name.
            command: The command that will be executed.

        Returns:
            A StageAdvanceModal that returns True if confirmed, False if cancelled.
        """
        try:
            workflow_stage = WorkflowStage(stage)
        except ValueError:
            # Default to PLANNING if invalid stage
            workflow_stage = WorkflowStage.PLANNING

        return StageAdvanceModal(workflow_stage, command)

    def create_mode_screen(
        self, mode: str, project: Project
    ) -> Screen | None:
        """Create a screen for a workflow mode.

        Args:
            mode: The workflow mode name ('plan', 'docs', 'work', 'test').
            project: The project to display in the mode screen.

        Returns:
            The screen instance, or None if the mode is invalid.
        """
        screen_class = self._mode_screen_map.get(mode)
        if screen_class:
            return screen_class(project)
        return None


# Create a singleton instance for use across the app
screen_factory = ScreenFactory()
