"""Tests for the Control Room screen."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iterm_controller.app import ItermControllerApp
from iterm_controller.models import (
    AppConfig,
    AppSettings,
    AttentionState,
    ManagedSession,
    Project,
    SessionTemplate,
)
from iterm_controller.screens.control_room import (
    ControlRoomScreen,
    REFRESH_DEBOUNCE_SECONDS,
)
from iterm_controller.widgets import SessionListWidget, WorkflowBarWidget


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


def make_project(
    project_id: str = "project-1",
    name: str = "Test Project",
    path: str = "/tmp/test-project",
) -> Project:
    """Create a test project."""
    return Project(
        id=project_id,
        name=name,
        path=path,
    )


def make_session_template(
    template_id: str = "test-template",
    name: str = "Test Template",
    command: str = "echo hello",
) -> SessionTemplate:
    """Create a test session template."""
    return SessionTemplate(
        id=template_id,
        name=name,
        command=command,
    )


class TestControlRoomScreen:
    """Tests for ControlRoomScreen."""

    def test_screen_has_bindings(self) -> None:
        """Test that screen has required keybindings."""
        screen = ControlRoomScreen()
        binding_keys = [b.key for b in screen.BINDINGS]

        assert "n" in binding_keys  # New Session
        assert "k" in binding_keys  # Kill Session
        assert "enter" in binding_keys  # Focus
        assert "p" in binding_keys  # Projects
        assert "r" in binding_keys  # Refresh


@pytest.mark.asyncio
class TestControlRoomScreenAsync:
    """Async tests for ControlRoomScreen.

    Note: Since the app now starts on MissionControlScreen, these tests
    explicitly push ControlRoomScreen to test its functionality.
    """

    async def test_screen_composes_widgets(self) -> None:
        """Test that screen composes required widgets."""
        app = ItermControllerApp()
        async with app.run_test():
            # Push Control Room screen (app now starts on MissionControl)
            app.push_screen(ControlRoomScreen())
            await asyncio.sleep(0.1)  # Let screen mount

            assert isinstance(app.screen, ControlRoomScreen)

            # Check for SessionListWidget
            session_widget = app.screen.query_one("#sessions", SessionListWidget)
            assert session_widget is not None

            # Check for WorkflowBarWidget
            workflow_widget = app.screen.query_one("#workflow", WorkflowBarWidget)
            assert workflow_widget is not None

    async def test_screen_shows_no_sessions_message(self) -> None:
        """Test that screen shows message when no sessions."""
        app = ItermControllerApp()
        async with app.run_test():
            # Push Control Room screen (app now starts on MissionControl)
            app.push_screen(ControlRoomScreen())
            await asyncio.sleep(0.1)  # Let screen mount

            assert isinstance(app.screen, ControlRoomScreen)

            widget = app.screen.query_one("#sessions", SessionListWidget)
            assert widget.sessions == []

    async def test_screen_displays_sessions(self) -> None:
        """Test that screen displays sessions from state."""
        app = ItermControllerApp()
        async with app.run_test():
            # Push Control Room screen (app now starts on MissionControl)
            app.push_screen(ControlRoomScreen())
            await asyncio.sleep(0.1)  # Let screen mount

            # Add a session to state
            session = make_session()
            app.state.sessions[session.id] = session

            # Refresh the session list
            await app.screen.refresh_sessions()

            widget = app.screen.query_one("#sessions", SessionListWidget)
            assert len(widget.sessions) == 1
            assert widget.sessions[0].id == session.id

    async def test_selected_session_returns_waiting_first(self) -> None:
        """Test that selected_session prioritizes WAITING sessions."""
        app = ItermControllerApp()
        async with app.run_test():
            # Push Control Room screen (app now starts on MissionControl)
            app.push_screen(ControlRoomScreen())
            await asyncio.sleep(0.1)  # Let screen mount

            # Add sessions with different states
            idle = make_session(session_id="idle", attention_state=AttentionState.IDLE)
            waiting = make_session(
                session_id="waiting", attention_state=AttentionState.WAITING
            )
            app.state.sessions[idle.id] = idle
            app.state.sessions[waiting.id] = waiting

            await app.screen.refresh_sessions()

            # Should return the WAITING session
            screen = app.screen
            assert isinstance(screen, ControlRoomScreen)
            selected = screen.selected_session
            assert selected is not None
            assert selected.attention_state == AttentionState.WAITING

    async def test_selected_session_returns_none_when_empty(self) -> None:
        """Test that selected_session returns None when no sessions."""
        app = ItermControllerApp()
        async with app.run_test():
            # Push Control Room screen (app now starts on MissionControl)
            app.push_screen(ControlRoomScreen())
            await asyncio.sleep(0.1)  # Let screen mount

            screen = app.screen
            assert isinstance(screen, ControlRoomScreen)
            assert screen.selected_session is None

    async def test_refresh_action(self) -> None:
        """Test that refresh action updates session list."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            # Push Control Room screen (app now starts on MissionControl)
            app.push_screen(ControlRoomScreen())
            await asyncio.sleep(0.1)  # Let screen mount

            # Add a session after initial mount
            session = make_session()
            app.state.sessions[session.id] = session

            # Press 'r' to refresh
            await pilot.press("r")

            widget = app.screen.query_one("#sessions", SessionListWidget)
            assert len(widget.sessions) == 1


@pytest.mark.asyncio
class TestNewSessionAction:
    """Tests for the new session action."""

    async def test_new_session_requires_iterm_connection(self) -> None:
        """Test that new session shows error when not connected to iTerm2."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            # iTerm2 is not connected by default in tests
            assert not app.iterm.is_connected

            # Press 'n' for new session
            await pilot.press("n")

            # Should show error notification (we can't easily check the notification,
            # but the action should complete without error)

    async def test_new_session_requires_active_project(self) -> None:
        """Test that new session requires an active project."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            # Mock iTerm as connected
            app.iterm._connected = True
            app.iterm.connection = MagicMock()

            # No active project
            assert app.state.active_project is None

            # Press 'n' - should prompt to select project
            await pilot.press("n")


@pytest.mark.asyncio
class TestKillSessionAction:
    """Tests for the kill session action."""

    async def test_kill_session_no_session(self) -> None:
        """Test that kill session shows warning when no session."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            # No sessions
            assert not app.state.sessions

            # Press 'k' to kill
            await pilot.press("k")

            # Should show warning (no error)


@pytest.mark.asyncio
class TestFocusSessionAction:
    """Tests for the focus session action."""

    async def test_focus_session_no_session(self) -> None:
        """Test that focus session shows warning when no session."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            # No sessions
            assert not app.state.sessions

            # Press 'enter' to focus
            await pilot.press("enter")

            # Should show warning (no error)


@pytest.mark.asyncio
class TestEventHandlers:
    """Tests for event handler methods.

    Note: Since the app now starts on MissionControlScreen, these tests
    explicitly push ControlRoomScreen to test its functionality.
    """

    async def test_session_spawned_event_refreshes_list(self) -> None:
        """Test that SessionSpawned event refreshes the session list."""
        app = ItermControllerApp()
        async with app.run_test():
            # Push Control Room screen (app now starts on MissionControl)
            app.push_screen(ControlRoomScreen())
            await asyncio.sleep(0.1)  # Let screen mount

            session = make_session()

            # Add session through state (which posts the event)
            app.state.add_session(session)

            # Give the event time to process
            await app.screen.refresh_sessions()

            widget = app.screen.query_one("#sessions", SessionListWidget)
            assert len(widget.sessions) == 1

    async def test_session_closed_event_refreshes_list(self) -> None:
        """Test that SessionClosed event refreshes the session list."""
        app = ItermControllerApp()
        async with app.run_test():
            # Push Control Room screen (app now starts on MissionControl)
            app.push_screen(ControlRoomScreen())
            await asyncio.sleep(0.1)  # Let screen mount

            session = make_session()
            app.state.add_session(session)
            await app.screen.refresh_sessions()

            widget = app.screen.query_one("#sessions", SessionListWidget)
            assert len(widget.sessions) == 1

            # Remove session through state
            app.state.remove_session(session.id)
            await app.screen.refresh_sessions()

            assert len(widget.sessions) == 0

    async def test_session_status_changed_event_refreshes_list(self) -> None:
        """Test that SessionStatusChanged event refreshes the session list."""
        app = ItermControllerApp()
        async with app.run_test():
            # Push Control Room screen (app now starts on MissionControl)
            app.push_screen(ControlRoomScreen())
            await asyncio.sleep(0.1)  # Let screen mount

            session = make_session(attention_state=AttentionState.IDLE)
            app.state.add_session(session)
            await app.screen.refresh_sessions()

            widget = app.screen.query_one("#sessions", SessionListWidget)
            assert widget.sessions[0].attention_state == AttentionState.IDLE

            # Update session status through state
            app.state.update_session_status(session.id, attention_state=AttentionState.WAITING)
            await app.screen.refresh_sessions()

            assert widget.sessions[0].attention_state == AttentionState.WAITING


@pytest.mark.asyncio
class TestDebounceRefresh:
    """Tests for the debounced refresh functionality.

    Note: Since the app now starts on MissionControlScreen, these tests
    explicitly push ControlRoomScreen to test its functionality.
    """

    def test_debounce_constant_is_100ms(self) -> None:
        """Test that debounce interval is 100ms."""
        assert REFRESH_DEBOUNCE_SECONDS == 0.1

    async def test_schedule_refresh_sets_pending_flag(self) -> None:
        """Test that schedule_refresh sets the pending flag."""
        app = ItermControllerApp()
        async with app.run_test():
            # Push Control Room screen (app now starts on MissionControl)
            app.push_screen(ControlRoomScreen())
            await asyncio.sleep(0.1)  # Let screen mount

            screen = app.screen
            assert isinstance(screen, ControlRoomScreen)

            # Initially not pending
            assert not screen._refresh_pending

            # Schedule a refresh
            screen.schedule_refresh()

            # Should now be pending
            assert screen._refresh_pending

    async def test_schedule_refresh_creates_timer(self) -> None:
        """Test that schedule_refresh creates a timer."""
        app = ItermControllerApp()
        async with app.run_test():
            # Push Control Room screen (app now starts on MissionControl)
            app.push_screen(ControlRoomScreen())
            await asyncio.sleep(0.1)  # Let screen mount

            screen = app.screen
            assert isinstance(screen, ControlRoomScreen)

            # Initially no timer
            assert screen._refresh_timer is None

            # Schedule a refresh
            screen.schedule_refresh()

            # Should have a timer now
            assert screen._refresh_timer is not None

    async def test_multiple_schedule_refresh_calls_batched(self) -> None:
        """Test that multiple rapid schedule_refresh calls are batched into one refresh."""
        app = ItermControllerApp()
        async with app.run_test():
            # Push Control Room screen (app now starts on MissionControl)
            app.push_screen(ControlRoomScreen())
            await asyncio.sleep(0.1)  # Let screen mount

            screen = app.screen
            assert isinstance(screen, ControlRoomScreen)

            # Track refresh calls
            refresh_count = 0
            original_refresh = screen.refresh_sessions

            async def counting_refresh():
                nonlocal refresh_count
                refresh_count += 1
                await original_refresh()

            screen.refresh_sessions = counting_refresh

            # Schedule multiple refreshes rapidly
            screen.schedule_refresh()
            screen.schedule_refresh()
            screen.schedule_refresh()
            screen.schedule_refresh()
            screen.schedule_refresh()

            # Wait for debounce period to elapse
            await asyncio.sleep(REFRESH_DEBOUNCE_SECONDS + 0.05)

            # Give the event loop time to process the callback
            await asyncio.sleep(0.05)

            # Should only have refreshed once (batched)
            assert refresh_count == 1

    async def test_refresh_clears_pending_flag(self) -> None:
        """Test that refresh_sessions clears the pending flag."""
        app = ItermControllerApp()
        async with app.run_test():
            # Push Control Room screen (app now starts on MissionControl)
            app.push_screen(ControlRoomScreen())
            await asyncio.sleep(0.1)  # Let screen mount

            screen = app.screen
            assert isinstance(screen, ControlRoomScreen)

            # Set pending flag
            screen._refresh_pending = True

            # Refresh
            await screen.refresh_sessions()

            # Should clear the flag
            assert not screen._refresh_pending

    async def test_event_handler_calls_schedule_refresh(self) -> None:
        """Test that event handlers call schedule_refresh instead of direct refresh."""
        app = ItermControllerApp()
        async with app.run_test():
            from iterm_controller.state import SessionSpawned

            # Push Control Room screen (app now starts on MissionControl)
            app.push_screen(ControlRoomScreen())
            await asyncio.sleep(0.1)  # Let screen mount

            screen = app.screen
            assert isinstance(screen, ControlRoomScreen)

            # Track schedule_refresh calls
            schedule_count = 0
            original_schedule = screen.schedule_refresh

            def counting_schedule():
                nonlocal schedule_count
                schedule_count += 1
                original_schedule()

            screen.schedule_refresh = counting_schedule

            # Directly call the event handler (simulating the event)
            session = make_session()
            screen.on_session_spawned(SessionSpawned(session))

            # Should have called schedule_refresh
            assert schedule_count == 1

    async def test_status_change_event_handler_calls_schedule_refresh(self) -> None:
        """Test that status change event handler calls schedule_refresh."""
        app = ItermControllerApp()
        async with app.run_test():
            from iterm_controller.state import SessionStatusChanged

            # Push Control Room screen (app now starts on MissionControl)
            app.push_screen(ControlRoomScreen())
            await asyncio.sleep(0.1)  # Let screen mount

            screen = app.screen
            assert isinstance(screen, ControlRoomScreen)

            # Track schedule_refresh calls
            schedule_count = 0
            original_schedule = screen.schedule_refresh

            def counting_schedule():
                nonlocal schedule_count
                schedule_count += 1
                original_schedule()

            screen.schedule_refresh = counting_schedule

            # Directly call the event handler (simulating the event)
            screen.on_session_status_changed(SessionStatusChanged("session-1"))

            # Should have called schedule_refresh
            assert schedule_count == 1

    async def test_closed_event_handler_calls_schedule_refresh(self) -> None:
        """Test that closed event handler calls schedule_refresh."""
        app = ItermControllerApp()
        async with app.run_test():
            from iterm_controller.state import SessionClosed

            # Push Control Room screen (app now starts on MissionControl)
            app.push_screen(ControlRoomScreen())
            await asyncio.sleep(0.1)  # Let screen mount

            screen = app.screen
            assert isinstance(screen, ControlRoomScreen)

            # Track schedule_refresh calls
            schedule_count = 0
            original_schedule = screen.schedule_refresh

            def counting_schedule():
                nonlocal schedule_count
                schedule_count += 1
                original_schedule()

            screen.schedule_refresh = counting_schedule

            # Directly call the event handler (simulating the event)
            screen.on_session_closed(SessionClosed("session-1"))

            # Should have called schedule_refresh
            assert schedule_count == 1
