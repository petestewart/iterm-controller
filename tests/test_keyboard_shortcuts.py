"""Tests for keyboard shortcuts across the application."""

import pytest

from iterm_controller.app import ItermControllerApp
from iterm_controller.models import AttentionState, ManagedSession
from iterm_controller.screens.control_room import ControlRoomScreen
from iterm_controller.screens.mission_control import MissionControlScreen
from iterm_controller.screens.modals import HelpModal
from iterm_controller.screens.project_dashboard import ProjectDashboardScreen
from iterm_controller.screens.project_list import ProjectListScreen
from iterm_controller.screens.settings import SettingsScreen


def make_session(
    session_id: str = "session-1",
    template_id: str = "test-template",
    project_id: str = "project-1",
    attention_state: AttentionState = AttentionState.IDLE,
) -> ManagedSession:
    """Create a test session."""
    return ManagedSession(
        id=session_id,
        template_id=template_id,
        project_id=project_id,
        tab_id="tab-1",
        attention_state=attention_state,
    )


class TestGlobalShortcuts:
    """Tests for global keyboard shortcuts defined in the app."""

    def test_app_has_global_bindings(self) -> None:
        """Test that app has all required global keybindings."""
        app = ItermControllerApp()
        binding_keys = [b.key for b in app.BINDINGS]

        # Core navigation
        assert "q" in binding_keys  # Quit
        assert "ctrl+c" in binding_keys  # Quit immediate
        assert "?" in binding_keys  # Help
        assert "p" in binding_keys  # Projects
        assert "s" in binding_keys  # Sessions/Control Room
        assert "comma" in binding_keys  # Settings
        assert "h" in binding_keys  # Home


class TestControlRoomShortcuts:
    """Tests for Control Room screen shortcuts."""

    def test_control_room_has_bindings(self) -> None:
        """Test that control room has all required keybindings."""
        screen = ControlRoomScreen()
        binding_keys = [b.key for b in screen.BINDINGS]

        # Core actions
        assert "n" in binding_keys  # New session
        assert "k" in binding_keys  # Kill session
        assert "enter" in binding_keys  # Focus session
        assert "r" in binding_keys  # Refresh

        # Number shortcuts for quick access
        for i in range(1, 10):
            assert str(i) in binding_keys


class TestProjectDashboardShortcuts:
    """Tests for Project Dashboard screen shortcuts."""

    def test_project_dashboard_has_bindings(self) -> None:
        """Test that project dashboard has all required keybindings."""
        screen = ProjectDashboardScreen(project_id="test")
        binding_keys = [b.key for b in screen.BINDINGS]

        assert "t" in binding_keys  # Toggle task
        assert "s" in binding_keys  # Spawn session
        assert "r" in binding_keys  # Run script
        assert "d" in binding_keys  # Docs
        assert "g" in binding_keys  # GitHub
        assert "f" in binding_keys  # Focus
        assert "k" in binding_keys  # Kill
        assert "a" in binding_keys  # Auto mode
        assert "escape" in binding_keys  # Back


class TestProjectListShortcuts:
    """Tests for Project List screen shortcuts."""

    def test_project_list_has_bindings(self) -> None:
        """Test that project list has all required keybindings."""
        screen = ProjectListScreen()
        binding_keys = [b.key for b in screen.BINDINGS]

        assert "enter" in binding_keys  # Open
        assert "n" in binding_keys  # New
        assert "d" in binding_keys  # Delete
        assert "r" in binding_keys  # Refresh
        assert "escape" in binding_keys  # Back


class TestSettingsShortcuts:
    """Tests for Settings screen shortcuts."""

    def test_settings_has_bindings(self) -> None:
        """Test that settings has all required keybindings."""
        screen = SettingsScreen()
        binding_keys = [b.key for b in screen.BINDINGS]

        assert "ctrl+s" in binding_keys  # Save
        assert "escape" in binding_keys  # Back


class TestHelpModal:
    """Tests for the Help modal."""

    def test_help_modal_has_bindings(self) -> None:
        """Test that help modal has dismiss bindings."""
        modal = HelpModal()
        binding_keys = [b.key for b in modal.BINDINGS]

        assert "escape" in binding_keys  # Dismiss
        assert "q" in binding_keys  # Also dismiss
        assert "?" in binding_keys  # Also dismiss

    def test_help_modal_has_all_shortcut_sections(self) -> None:
        """Test that help modal documents all major sections."""
        expected_sections = [
            "Global",
            "Control Room",
            "Project List",
            "Project Dashboard",
            "Settings",
            "Modals",
        ]

        for section in expected_sections:
            assert section in HelpModal.SHORTCUTS


class TestHelpModalActions:
    """Tests for HelpModal action methods."""

    def test_action_show_help_is_sync(self) -> None:
        """Test that action_show_help is not async (fix for NoActiveWorker error)."""
        import asyncio

        from iterm_controller.app import ItermControllerApp

        # The action_show_help method should be synchronous
        # If it were async with push_screen_wait, it would require a worker context
        app = ItermControllerApp()
        method = app.action_show_help
        assert not asyncio.iscoroutinefunction(method), (
            "action_show_help should be sync to avoid NoActiveWorker error"
        )

    def test_action_dismiss_dismisses_modal(self) -> None:
        """Test that action_dismiss dismisses the modal."""
        modal = HelpModal()

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_dismiss()

        assert dismissed_with == [None]

    def test_help_modal_compose_returns_widgets(self) -> None:
        """Test that compose returns widgets."""
        modal = HelpModal()
        widgets = list(modal.compose())
        assert len(widgets) > 0

    def test_help_modal_binding_actions(self) -> None:
        """Test that bindings have correct actions."""
        modal = HelpModal()
        bindings = {b.key: b.action for b in modal.BINDINGS}

        assert bindings["escape"] == "dismiss"
        assert bindings["q"] == "dismiss"
        assert bindings["?"] == "dismiss"


@pytest.mark.asyncio
class TestShortcutNavigation:
    """Async tests for keyboard navigation."""

    async def test_navigation_to_projects(self) -> None:
        """Test that p navigates to project list."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            await pilot.press("p")
            assert isinstance(app.screen, ProjectListScreen)

    async def test_navigation_to_settings(self) -> None:
        """Test that comma navigates to settings."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            await pilot.press("comma")
            assert isinstance(app.screen, SettingsScreen)

    async def test_escape_returns_from_project_list(self) -> None:
        """Test that escape returns from project list."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            await pilot.press("p")
            assert isinstance(app.screen, ProjectListScreen)

            await pilot.press("escape")
            assert isinstance(app.screen, MissionControlScreen)

    async def test_escape_returns_from_settings(self) -> None:
        """Test that escape returns from settings."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            await pilot.press("comma")
            assert isinstance(app.screen, SettingsScreen)

            await pilot.press("escape")
            assert isinstance(app.screen, MissionControlScreen)

    async def test_sessions_shortcut_navigates_to_mission_control(self) -> None:
        """Test that s navigates to sessions (Mission Control)."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            # Start on Mission Control
            assert isinstance(app.screen, MissionControlScreen)

            # Navigate to project list first
            await pilot.press("p")
            assert isinstance(app.screen, ProjectListScreen)

            # Press s to go back to sessions (Mission Control)
            await pilot.press("s")
            assert isinstance(app.screen, MissionControlScreen)


@pytest.mark.asyncio
class TestNumberShortcuts:
    """Tests for number shortcuts in Control Room."""

    async def test_number_shortcut_no_sessions(self) -> None:
        """Test that number shortcuts show warning when no sessions."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            # No sessions exist
            assert not app.state.sessions

            # Press '1' - should not crash
            await pilot.press("1")

    async def test_number_shortcuts_exist_1_through_9(self) -> None:
        """Test that number shortcuts 1-9 are defined."""
        screen = ControlRoomScreen()
        bindings = {b.key: b.action for b in screen.BINDINGS}

        for i in range(1, 10):
            assert str(i) in bindings
            assert f"focus_session_num({i})" in bindings[str(i)]
