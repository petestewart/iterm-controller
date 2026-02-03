"""Main Textual app class.

This module provides the main iTerm Controller TUI application.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import App
from textual.binding import Binding

from iterm_controller.api import AppAPI
from iterm_controller.screens.mission_control import MissionControlScreen
from iterm_controller.screens.modes import (
    DocsModeScreen,
    PlanModeScreen,
    TestModeScreen,
    WorkModeScreen,
)
from iterm_controller.screens.new_project import NewProjectScreen
from iterm_controller.screens.project_dashboard import ProjectDashboardScreen
from iterm_controller.screens.project_list import ProjectListScreen
from iterm_controller.screens.settings import SettingsScreen
from iterm_controller.services import ScreenFactory, ServiceContainer, screen_factory
from iterm_controller.state import AppState

if TYPE_CHECKING:
    from iterm_controller.screens.modals.quit_confirm import QuitAction


class ItermControllerApp(App):
    """Main iTerm2 Controller TUI application."""

    CSS_PATH = "styles.tcss"
    TITLE = "iTerm Controller"

    SCREENS = {
        "project_list": ProjectListScreen,
        "project_dashboard": ProjectDashboardScreen,
        "new_project": NewProjectScreen,
        "settings": SettingsScreen,
    }

    # Mode screens require a Project argument and are accessed via ProjectDashboard
    # using keys 1-4. They are not registered in SCREENS because they need context.
    # Navigation: ProjectDashboard -> 1/2/3/4 -> Mode Screen -> Esc -> ProjectDashboard
    MODE_SCREENS = {
        "plan": PlanModeScreen,
        "docs": DocsModeScreen,
        "work": WorkModeScreen,
        "test": TestModeScreen,
    }

    BINDINGS = [
        Binding("q", "request_quit", "Quit"),
        Binding("ctrl+c", "request_quit", "Quit", show=False),
        Binding("?", "show_help", "Help"),
        Binding("p", "push_screen('project_list')", "Projects"),
        Binding("s", "go_home", "Sessions"),
        Binding("comma", "push_screen('settings')", "Settings"),
        Binding("h", "go_home", "Home", show=False),
    ]

    def __init__(self) -> None:
        """Initialize the application."""
        super().__init__()
        self.state = AppState()
        self.state.connect_app(self)  # Connect state to app for message posting

        # Create service container with plan manager for ReviewService
        self.services = ServiceContainer.create(
            plan_manager=self.state._plan_manager,  # noqa: SLF001
        )

        # Wire up state managers with services from container
        # This ensures the state managers use the same service instances
        self.state._git_manager.git_service = self.services.git  # noqa: SLF001
        self.state._review_manager.review_service = self.services.reviews  # noqa: SLF001

        # Expose commonly-used services directly for backwards compatibility
        self.iterm = self.services.iterm
        self.github = self.services.github
        self.notifier = self.services.notifier

        # Screen factory for creating modals and screens without circular imports
        self.screen_factory = screen_factory

        # Create API with injected services
        self.api = AppAPI(self, self.services)

    async def on_mount(self) -> None:
        """Initialize services when app starts."""
        # Load configuration
        await self.state.load_config()

        # Apply settings to services
        if self.state.config:
            # Configure skip permissions for Claude sessions
            self.services.spawner.set_skip_permissions(
                self.state.config.settings.dangerously_skip_permissions
            )

        # Load window layouts from config into service container
        if self.state.config and self.state.config.window_layouts:
            self.services.load_layouts(self.state.config.window_layouts)

        # Try to connect to iTerm2 (non-blocking)
        try:
            await self.services.connect_iterm()
        except Exception as e:
            self.notify(f"iTerm2 connection failed: {e}", severity="warning")

        # Initialize GitHub (non-blocking)
        await self.services.initialize_github()

        # Push the initial screen (Mission Control is the main dashboard)
        self.push_screen(MissionControlScreen())

    def action_request_quit(self) -> None:
        """Handle quit with confirmation if sessions active."""
        if self.state.has_active_sessions:
            from iterm_controller.screens.modals.quit_confirm import QuitConfirmModal

            self.push_screen(QuitConfirmModal(), self._on_quit_modal_dismiss)
        else:
            self.call_later(self._cleanup_and_exit)

    def _on_quit_modal_dismiss(self, action: "QuitAction") -> None:
        """Handle the result of the quit confirmation modal.

        Args:
            action: The action chosen by the user.
        """
        self.call_later(self._handle_quit_action, action)

    async def _handle_quit_action(self, action: "QuitAction") -> None:
        """Handle the result of the quit confirmation modal.

        Args:
            action: The action chosen by the user.
        """
        from iterm_controller.screens.modals.quit_confirm import QuitAction

        if action == QuitAction.CANCEL:
            # User cancelled, do nothing
            return

        if action == QuitAction.CLOSE_ALL:
            # Close all sessions, including unmanaged ones
            await self.api.close_all_sessions()
        elif action == QuitAction.CLOSE_MANAGED:
            # Close only managed sessions
            await self.api.close_managed_sessions()
        # LEAVE_RUNNING: just exit without closing sessions

        await self._cleanup_and_exit()

    async def _cleanup_and_exit(self) -> None:
        """Clean up resources and exit the application."""
        # Disconnect from iTerm2
        await self.services.disconnect_iterm()

        # Exit the application
        self.exit()

    def action_show_help(self) -> None:
        """Show help modal with all keyboard shortcuts."""
        from iterm_controller.screens.modals import HelpModal

        self.push_screen(HelpModal())

    def action_go_home(self) -> None:
        """Navigate to the home screen (Mission Control)."""
        # Pop all screens except the base and push Mission Control
        while len(self.screen_stack) > 1:
            self.pop_screen()
        # Push Mission Control if not already there
        if not isinstance(self.screen, MissionControlScreen):
            self.push_screen(MissionControlScreen())
