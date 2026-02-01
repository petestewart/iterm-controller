"""Main Textual app class.

This module provides the main iTerm Controller TUI application.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import App
from textual.binding import Binding

from iterm_controller.config import load_global_config
from iterm_controller.github import GitHubIntegration
from iterm_controller.iterm_api import ItermController
from iterm_controller.notifications import Notifier
from iterm_controller.screens.new_project import NewProjectScreen
from iterm_controller.screens.project_dashboard import ProjectDashboardScreen
from iterm_controller.screens.project_list import ProjectListScreen
from iterm_controller.screens.settings import SettingsScreen
from iterm_controller.state import AppState

if TYPE_CHECKING:
    pass


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

    BINDINGS = [
        Binding("q", "request_quit", "Quit"),
        Binding("ctrl+c", "request_quit", "Quit", show=False),
        Binding("?", "show_help", "Help"),
        Binding("p", "push_screen('project_list')", "Projects"),
        Binding("s", "push_screen('settings')", "Settings"),
        Binding("h", "go_home", "Home", show=False),
    ]

    def __init__(self) -> None:
        """Initialize the application."""
        super().__init__()
        self.state = AppState()
        self.state.connect_app(self)  # Connect state to app for message posting
        self.iterm = ItermController()
        self.github = GitHubIntegration()
        self.notifier = Notifier()

    async def on_mount(self) -> None:
        """Initialize services when app starts."""
        # Load configuration
        await self.state.load_config()

        # Try to connect to iTerm2 (non-blocking)
        try:
            await self.iterm.connect()
        except Exception as e:
            self.notify(f"iTerm2 connection failed: {e}", severity="warning")

        # Initialize GitHub (non-blocking)
        await self.github.initialize()

        # Push the initial screen
        from iterm_controller.screens.control_room import ControlRoomScreen

        self.push_screen(ControlRoomScreen())

    async def action_request_quit(self) -> None:
        """Handle quit with confirmation if sessions active."""
        if self.state.has_active_sessions:
            from iterm_controller.screens.modals.quit_confirm import (
                QuitAction,
                QuitConfirmModal,
            )

            action = await self.push_screen_wait(QuitConfirmModal())
            await self._handle_quit_action(action)
        else:
            await self._cleanup_and_exit()

    async def _handle_quit_action(self, action: "QuitAction") -> None:
        """Handle the result of the quit confirmation modal.

        Args:
            action: The action chosen by the user.
        """
        from iterm_controller.iterm_api import SessionSpawner, SessionTerminator
        from iterm_controller.screens.modals.quit_confirm import QuitAction

        if action == QuitAction.CANCEL:
            # User cancelled, do nothing
            return

        if action == QuitAction.CLOSE_ALL:
            # Close all sessions, including unmanaged ones
            await self._close_all_sessions()
        elif action == QuitAction.CLOSE_MANAGED:
            # Close only managed sessions
            await self._close_managed_sessions()
        # LEAVE_RUNNING: just exit without closing sessions

        await self._cleanup_and_exit()

    async def _close_all_sessions(self) -> None:
        """Close all sessions (managed and unmanaged)."""
        from iterm_controller.iterm_api import SessionSpawner, SessionTerminator

        if not self.iterm.is_connected or not self.iterm.app:
            return

        terminator = SessionTerminator(self.iterm)

        # Get all sessions from all windows
        for window in self.iterm.app.terminal_windows:
            for tab in window.tabs:
                try:
                    await terminator.close_tab(tab, force=False)
                except Exception as e:
                    self.notify(f"Failed to close tab: {e}", severity="warning")

    async def _close_managed_sessions(self) -> None:
        """Close only sessions managed by this application."""
        from iterm_controller.iterm_api import SessionSpawner, SessionTerminator

        if not self.iterm.is_connected:
            return

        # Get all managed sessions from app state
        managed_sessions = list(self.state.sessions.values())
        if not managed_sessions:
            return

        terminator = SessionTerminator(self.iterm)
        spawner = SessionSpawner(self.iterm)

        # Copy managed sessions to spawner for proper untracking
        for session in managed_sessions:
            spawner.managed_sessions[session.id] = session

        closed, results = await terminator.close_all_managed(
            sessions=managed_sessions,
            spawner=spawner,
            force=False,
        )

        # Update app state
        for result in results:
            if result.success:
                self.state.remove_session(result.session_id)

        if closed < len(managed_sessions):
            self.notify(
                f"Closed {closed}/{len(managed_sessions)} sessions",
                severity="warning",
            )

    async def _cleanup_and_exit(self) -> None:
        """Clean up resources and exit the application."""
        # Disconnect from iTerm2
        await self.iterm.disconnect()

        # Exit the application
        self.exit()

    async def action_show_help(self) -> None:
        """Show help modal with all keyboard shortcuts."""
        from iterm_controller.screens.modals import HelpModal

        await self.push_screen_wait(HelpModal())

    def action_go_home(self) -> None:
        """Navigate to the home screen (Control Room)."""
        from iterm_controller.screens.control_room import ControlRoomScreen

        # Pop all screens except the base and push Control Room
        while len(self.screen_stack) > 1:
            self.pop_screen()
        # Push Control Room if not already there
        if not isinstance(self.screen, ControlRoomScreen):
            self.push_screen(ControlRoomScreen())
