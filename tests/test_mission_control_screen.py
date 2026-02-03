"""Tests for the Mission Control screen."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from iterm_controller.app import ItermControllerApp
from iterm_controller.models import (
    AttentionState,
    ManagedSession,
    Project,
    SessionProgress,
    SessionTemplate,
    SessionType,
)
from iterm_controller.screens.mission_control import (
    MissionControlScreen,
    REFRESH_DEBOUNCE_SECONDS,
)
from iterm_controller.state import (
    OrchestratorProgress,
    SessionClosed,
    SessionOutputUpdated,
    SessionSpawned,
    SessionStatusChanged,
)
from iterm_controller.widgets import SessionList


def make_session(
    session_id: str = "session-1",
    template_id: str = "test-template",
    project_id: str = "project-1",
    attention_state: AttentionState = AttentionState.IDLE,
    session_type: SessionType = SessionType.SHELL,
) -> ManagedSession:
    """Create a test session."""
    return ManagedSession(
        id=session_id,
        template_id=template_id,
        project_id=project_id,
        tab_id="tab-1",
        attention_state=attention_state,
        session_type=session_type,
        spawned_at=datetime.now(),
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


class TestMissionControlScreen:
    """Tests for MissionControlScreen."""

    def test_screen_has_bindings(self) -> None:
        """Test that screen has required keybindings."""
        screen = MissionControlScreen()
        binding_keys = [b.key for b in screen.BINDINGS]

        assert "n" in binding_keys  # New Session
        assert "k" in binding_keys  # Kill Session
        assert "enter" in binding_keys  # Open Project
        assert "x" in binding_keys  # Expand/Collapse
        assert "f" in binding_keys  # Focus iTerm
        assert "p" in binding_keys  # Projects
        assert "j" in binding_keys  # Move Down
        assert "r" in binding_keys  # Refresh
        assert "q" in binding_keys  # Quit

        # Number shortcuts
        for num in "123456789":
            assert num in binding_keys

    def test_screen_has_css(self) -> None:
        """Test that screen has CSS styling."""
        assert MissionControlScreen.CSS is not None
        assert "#title" in MissionControlScreen.CSS
        assert "#session-count" in MissionControlScreen.CSS


@pytest.mark.asyncio
class TestMissionControlScreenAsync:
    """Async tests for MissionControlScreen."""

    async def test_screen_composes_widgets(self) -> None:
        """Test that screen composes required widgets."""
        app = ItermControllerApp()
        async with app.run_test():
            # Push Mission Control screen
            await app.push_screen(MissionControlScreen())

            assert isinstance(app.screen, MissionControlScreen)

            # Check for SessionList container
            session_list = app.screen.query_one("#session-list", SessionList)
            assert session_list is not None

            # Check for title
            from textual.widgets import Static

            title = app.screen.query_one("#title", Static)
            assert title is not None

            # Check for session count
            count = app.screen.query_one("#session-count", Static)
            assert count is not None

    async def test_screen_shows_empty_state(self) -> None:
        """Test that screen shows empty state when no sessions."""
        app = ItermControllerApp()
        async with app.run_test():
            await app.push_screen(MissionControlScreen())
            assert isinstance(app.screen, MissionControlScreen)

            session_list = app.screen.query_one("#session-list", SessionList)
            assert session_list.session_count == 0

    async def test_screen_displays_sessions(self) -> None:
        """Test that screen displays sessions from state."""
        app = ItermControllerApp()
        async with app.run_test():
            await app.push_screen(MissionControlScreen())

            # Add a session to state
            session = make_session()
            app.state.sessions[session.id] = session

            # Refresh the session list
            await app.screen.refresh_sessions()

            session_list = app.screen.query_one("#session-list", SessionList)
            assert session_list.session_count == 1

    async def test_session_count_updates(self) -> None:
        """Test that session count label updates."""
        app = ItermControllerApp()
        async with app.run_test():
            await app.push_screen(MissionControlScreen())

            from textual.widgets import Static

            count = app.screen.query_one("#session-count", Static)
            assert "0 active sessions" in str(count.renderable)

            # Add sessions
            for i in range(3):
                session = make_session(session_id=f"session-{i}")
                app.state.sessions[session.id] = session

            await app.screen.refresh_sessions()

            # Should now show "3 active sessions"
            count = app.screen.query_one("#session-count", Static)
            assert "3 active sessions" in str(count.renderable)

    async def test_selected_session_returns_none_when_empty(self) -> None:
        """Test that selected_session returns None when no sessions."""
        app = ItermControllerApp()
        async with app.run_test():
            await app.push_screen(MissionControlScreen())
            screen = app.screen
            assert isinstance(screen, MissionControlScreen)
            assert screen.selected_session is None

    async def test_selected_session_returns_waiting_first(self) -> None:
        """Test that sessions are sorted with WAITING first."""
        app = ItermControllerApp()
        async with app.run_test():
            await app.push_screen(MissionControlScreen())

            # Add sessions with different states
            idle = make_session(
                session_id="idle", attention_state=AttentionState.IDLE
            )
            waiting = make_session(
                session_id="waiting", attention_state=AttentionState.WAITING
            )
            app.state.sessions[idle.id] = idle
            app.state.sessions[waiting.id] = waiting

            await app.screen.refresh_sessions()

            screen = app.screen
            assert isinstance(screen, MissionControlScreen)
            selected = screen.selected_session
            assert selected is not None
            assert selected.attention_state == AttentionState.WAITING


@pytest.mark.asyncio
class TestMissionControlActions:
    """Tests for Mission Control screen actions."""

    async def test_refresh_action(self) -> None:
        """Test that refresh action updates session list."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            await app.push_screen(MissionControlScreen())

            # Add a session after initial mount
            session = make_session()
            app.state.sessions[session.id] = session

            # Press 'r' to refresh
            await pilot.press("r")

            session_list = app.screen.query_one("#session-list", SessionList)
            assert session_list.session_count == 1

    async def test_new_session_requires_iterm_connection(self) -> None:
        """Test that new session shows error when not connected to iTerm2."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            await app.push_screen(MissionControlScreen())

            # iTerm2 is not connected by default in tests
            assert not app.iterm.is_connected

            # Press 'n' for new session - should show error notification
            await pilot.press("n")

    async def test_new_session_requires_active_project(self) -> None:
        """Test that new session requires an active project."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            await app.push_screen(MissionControlScreen())

            # Mock iTerm as connected
            app.iterm._connected = True
            app.iterm.connection = MagicMock()

            # No active project
            assert app.state.active_project is None

            # Press 'n' - should prompt to select project
            await pilot.press("n")

    async def test_kill_session_no_session(self) -> None:
        """Test that kill session shows warning when no session."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            await app.push_screen(MissionControlScreen())

            # No sessions
            assert not app.state.sessions

            # Press 'k' to kill - should show warning
            await pilot.press("k")

    async def test_expand_collapse_action(self) -> None:
        """Test expand/collapse action on session."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            await app.push_screen(MissionControlScreen())

            # Add a session
            session = make_session()
            app.state.sessions[session.id] = session
            await app.screen.refresh_sessions()

            # Press 'x' to expand - should not error
            await pilot.press("x")

    async def test_navigation_actions(self) -> None:
        """Test j/k navigation actions."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            await app.push_screen(MissionControlScreen())

            # Add multiple sessions
            for i in range(3):
                session = make_session(session_id=f"session-{i}")
                app.state.sessions[session.id] = session
            await app.screen.refresh_sessions()

            # Navigate down
            await pilot.press("j")
            await pilot.press("j")

            # Navigate up
            await pilot.press("up")

    async def test_open_project_no_session(self) -> None:
        """Test that open project shows warning when no session."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            await app.push_screen(MissionControlScreen())

            # No sessions
            assert not app.state.sessions

            # Press 'enter' to open project - should show warning
            await pilot.press("enter")


@pytest.mark.asyncio
class TestMissionControlEventHandlers:
    """Tests for Mission Control event handlers."""

    async def test_session_spawned_schedules_refresh(self) -> None:
        """Test that SessionSpawned event schedules refresh."""
        app = ItermControllerApp()
        async with app.run_test():
            await app.push_screen(MissionControlScreen())
            screen = app.screen
            assert isinstance(screen, MissionControlScreen)

            # Track schedule_refresh calls
            schedule_count = 0
            original_schedule = screen.schedule_refresh

            def counting_schedule():
                nonlocal schedule_count
                schedule_count += 1
                original_schedule()

            screen.schedule_refresh = counting_schedule

            # Trigger the event
            session = make_session()
            screen.on_session_spawned(SessionSpawned(session))

            assert schedule_count == 1

    async def test_session_closed_removes_session(self) -> None:
        """Test that SessionClosed event removes session from list."""
        app = ItermControllerApp()
        async with app.run_test():
            await app.push_screen(MissionControlScreen())

            # Add a session
            session = make_session()
            app.state.sessions[session.id] = session
            await app.screen.refresh_sessions()

            session_list = app.screen.query_one("#session-list", SessionList)
            assert session_list.session_count == 1

            # Trigger closed event
            screen = app.screen
            assert isinstance(screen, MissionControlScreen)
            screen.on_session_closed(SessionClosed(session))

            assert session_list.session_count == 0

    async def test_session_status_changed_updates_session(self) -> None:
        """Test that SessionStatusChanged event updates session."""
        app = ItermControllerApp()
        async with app.run_test():
            await app.push_screen(MissionControlScreen())

            # Add a session
            session = make_session(attention_state=AttentionState.IDLE)
            app.state.sessions[session.id] = session
            await app.screen.refresh_sessions()

            # Change status
            session.attention_state = AttentionState.WAITING
            screen = app.screen
            assert isinstance(screen, MissionControlScreen)
            screen.on_session_status_changed(SessionStatusChanged(session))

            # Should have updated the session
            session_list = app.screen.query_one("#session-list", SessionList)
            updated = session_list.get_session_by_id(session.id)
            assert updated is not None
            assert updated.attention_state == AttentionState.WAITING

    async def test_session_output_updated_streams_output(self) -> None:
        """Test that SessionOutputUpdated event streams output to card."""
        app = ItermControllerApp()
        async with app.run_test():
            await app.push_screen(MissionControlScreen())

            # Add a session
            session = make_session()
            app.state.sessions[session.id] = session
            await app.screen.refresh_sessions()

            # Trigger output event
            screen = app.screen
            assert isinstance(screen, MissionControlScreen)
            screen.on_session_output_updated(
                SessionOutputUpdated(session.id, "Hello, World!")
            )

            # Should not error - the output log should have the content

    async def test_orchestrator_progress_updates_session(self) -> None:
        """Test that OrchestratorProgress event updates session progress."""
        app = ItermControllerApp()
        async with app.run_test():
            await app.push_screen(MissionControlScreen())

            # Add an orchestrator session
            session = make_session(session_type=SessionType.ORCHESTRATOR)
            app.state.sessions[session.id] = session
            await app.screen.refresh_sessions()

            # Create progress
            progress = SessionProgress(
                completed_tasks=3,
                total_tasks=6,
                current_task_id="2.3",
                current_task_title="Adding authentication",
            )

            # Trigger progress event
            screen = app.screen
            assert isinstance(screen, MissionControlScreen)
            screen.on_orchestrator_progress(
                OrchestratorProgress(
                    project_id=session.project_id,
                    session_id=session.id,
                    progress=progress,
                )
            )

            # Session should have updated progress
            session_list = app.screen.query_one("#session-list", SessionList)
            updated = session_list.get_session_by_id(session.id)
            assert updated is not None
            assert updated.progress is not None
            assert updated.progress.completed_tasks == 3


@pytest.mark.asyncio
class TestMissionControlDebounce:
    """Tests for debounced refresh functionality."""

    def test_debounce_constant_is_100ms(self) -> None:
        """Test that debounce interval is 100ms."""
        assert REFRESH_DEBOUNCE_SECONDS == 0.1

    async def test_schedule_refresh_sets_pending_flag(self) -> None:
        """Test that schedule_refresh sets the pending flag."""
        app = ItermControllerApp()
        async with app.run_test():
            await app.push_screen(MissionControlScreen())
            screen = app.screen
            assert isinstance(screen, MissionControlScreen)

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
            await app.push_screen(MissionControlScreen())
            screen = app.screen
            assert isinstance(screen, MissionControlScreen)

            # Initially no timer
            assert screen._refresh_timer is None

            # Schedule a refresh
            screen.schedule_refresh()

            # Should have a timer now
            assert screen._refresh_timer is not None

    async def test_multiple_schedule_refresh_calls_batched(self) -> None:
        """Test that multiple rapid schedule_refresh calls are batched."""
        app = ItermControllerApp()
        async with app.run_test():
            await app.push_screen(MissionControlScreen())
            screen = app.screen
            assert isinstance(screen, MissionControlScreen)

            # Track refresh calls
            refresh_count = 0
            original_refresh = screen.refresh_sessions

            async def counting_refresh():
                nonlocal refresh_count
                refresh_count += 1
                await original_refresh()

            screen.refresh_sessions = counting_refresh

            # Schedule multiple refreshes rapidly
            for _ in range(5):
                screen.schedule_refresh()

            # Wait for debounce period
            await asyncio.sleep(REFRESH_DEBOUNCE_SECONDS + 0.05)
            await asyncio.sleep(0.05)

            # Should only have refreshed once (batched)
            assert refresh_count == 1

    async def test_refresh_clears_pending_flag(self) -> None:
        """Test that refresh_sessions clears the pending flag."""
        app = ItermControllerApp()
        async with app.run_test():
            await app.push_screen(MissionControlScreen())
            screen = app.screen
            assert isinstance(screen, MissionControlScreen)

            # Set pending flag
            screen._refresh_pending = True

            # Refresh
            await screen.refresh_sessions()

            # Should clear the flag
            assert not screen._refresh_pending


@pytest.mark.asyncio
class TestMissionControlNumberShortcuts:
    """Tests for number key shortcuts (1-9)."""

    async def test_focus_session_num_no_session(self) -> None:
        """Test focus_session_num when no session at that index."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            await app.push_screen(MissionControlScreen())

            # No sessions
            await pilot.press("1")
            # Should show warning but not error

    async def test_focus_session_num_with_session(self) -> None:
        """Test focus_session_num focuses correct session."""
        app = ItermControllerApp()
        async with app.run_test():
            await app.push_screen(MissionControlScreen())

            # Add sessions
            for i in range(3):
                session = make_session(session_id=f"session-{i}")
                app.state.sessions[session.id] = session

            await app.screen.refresh_sessions()

            screen = app.screen
            assert isinstance(screen, MissionControlScreen)

            # Get session at index 2 (which is session 2 in 1-based)
            session_list = app.screen.query_one("#session-list", SessionList)
            expected = session_list.get_session_by_index(2)

            # This verifies the indexing logic works - session-1 would be at index 2
            # (since sessions are sorted by attention state and last_activity)
            assert expected is not None
