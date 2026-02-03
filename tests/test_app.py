"""Tests for the main Textual app."""

import pytest

from iterm_controller.app import ItermControllerApp
from iterm_controller.state import AppState


class TestItermControllerApp:
    """Tests for ItermControllerApp."""

    def test_app_initialization(self) -> None:
        """Test that app initializes with required components."""
        app = ItermControllerApp()

        # Check that all components are initialized
        assert app.state is not None
        assert isinstance(app.state, AppState)
        assert app.iterm is not None
        assert app.github is not None
        assert app.notifier is not None

    def test_app_has_bindings(self) -> None:
        """Test that app has required keybindings."""
        app = ItermControllerApp()

        # Get binding keys
        binding_keys = [b.key for b in app.BINDINGS]

        # Check required bindings exist
        assert "q" in binding_keys
        assert "?" in binding_keys
        assert "p" in binding_keys
        assert "s" in binding_keys  # Sessions
        assert "comma" in binding_keys  # Settings

    def test_app_has_css_path(self) -> None:
        """Test that app has CSS_PATH configured."""
        assert ItermControllerApp.CSS_PATH == "styles.tcss"

    def test_app_has_title(self) -> None:
        """Test that app has TITLE configured."""
        assert ItermControllerApp.TITLE == "iTerm Controller"


@pytest.mark.asyncio
class TestItermControllerAppAsync:
    """Async tests for ItermControllerApp."""

    async def test_app_mounts_without_error(self) -> None:
        """Test that app can be mounted."""
        app = ItermControllerApp()
        async with app.run_test():
            # App should mount without crashing
            assert app.state.config is not None

    async def test_app_shows_mission_control_on_start(self) -> None:
        """Test that Mission Control screen is shown on start."""
        app = ItermControllerApp()
        async with app.run_test():
            # Check that we're on the Mission Control screen
            from iterm_controller.screens.mission_control import MissionControlScreen

            assert isinstance(app.screen, MissionControlScreen)

    async def test_app_navigation_to_project_list(self) -> None:
        """Test navigation to project list screen."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            # Press 'p' to go to project list
            await pilot.press("p")

            from iterm_controller.screens.project_list import ProjectListScreen

            assert isinstance(app.screen, ProjectListScreen)

    async def test_app_navigation_to_settings(self) -> None:
        """Test navigation to settings screen."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            # Press comma to go to settings
            await pilot.press("comma")

            from iterm_controller.screens.settings import SettingsScreen

            assert isinstance(app.screen, SettingsScreen)

    async def test_app_navigation_to_sessions(self) -> None:
        """Test navigation to sessions/Mission Control screen."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            # First go to another screen
            await pilot.press("p")
            from iterm_controller.screens.project_list import ProjectListScreen

            assert isinstance(app.screen, ProjectListScreen)

            # Press 's' to go back to sessions/Mission Control
            await pilot.press("s")

            from iterm_controller.screens.mission_control import MissionControlScreen

            assert isinstance(app.screen, MissionControlScreen)

    async def test_app_escape_returns_from_screen(self) -> None:
        """Test that escape returns from pushed screens."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            from iterm_controller.screens.mission_control import MissionControlScreen
            from iterm_controller.screens.project_list import ProjectListScreen

            # Go to project list
            await pilot.press("p")
            assert isinstance(app.screen, ProjectListScreen)

            # Press escape to return
            await pilot.press("escape")
            assert isinstance(app.screen, MissionControlScreen)

    async def test_app_quit_without_sessions_exits(self) -> None:
        """Test that quitting without active sessions exits immediately."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            # Ensure no active sessions
            assert not app.state.has_active_sessions

            # Press 'q' to quit - should exit immediately
            await pilot.press("q")

            # App should be exiting
            # Note: The test framework may not fully exit, but we verify no modal shown
            from iterm_controller.screens.modals.quit_confirm import QuitConfirmModal

            assert not isinstance(app.screen, QuitConfirmModal)
