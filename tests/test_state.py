"""Tests for the AppState module."""

import pytest

from iterm_controller.models import AttentionState, ManagedSession, Project
from iterm_controller.state import AppState, StateEvent


class TestAppState:
    """Tests for AppState."""

    def test_state_initialization(self) -> None:
        """Test that state initializes with empty collections."""
        state = AppState()

        assert state.projects == {}
        assert state.sessions == {}
        assert state.active_project_id is None
        assert state.config is None

    def test_has_active_sessions_false_when_empty(self) -> None:
        """Test has_active_sessions returns False when no sessions."""
        state = AppState()
        assert not state.has_active_sessions

    def test_has_active_sessions_true_when_active(self) -> None:
        """Test has_active_sessions returns True when active session exists."""
        state = AppState()
        session = ManagedSession(
            id="session-1",
            template_id="test",
            project_id="project-1",
            tab_id="tab-1",
            is_active=True,
        )
        state.sessions["session-1"] = session
        assert state.has_active_sessions

    def test_has_active_sessions_false_when_all_inactive(self) -> None:
        """Test has_active_sessions returns False when all sessions inactive."""
        state = AppState()
        session = ManagedSession(
            id="session-1",
            template_id="test",
            project_id="project-1",
            tab_id="tab-1",
            is_active=False,
        )
        state.sessions["session-1"] = session
        assert not state.has_active_sessions

    def test_active_project_none_when_no_active(self) -> None:
        """Test active_project returns None when no project active."""
        state = AppState()
        assert state.active_project is None

    def test_active_project_returns_correct_project(self) -> None:
        """Test active_project returns the correct project."""
        state = AppState()
        project = Project(id="project-1", name="Test Project", path="/test")
        state.projects["project-1"] = project
        state.active_project_id = "project-1"

        assert state.active_project == project

    def test_add_session(self) -> None:
        """Test adding a session to state."""
        state = AppState()
        session = ManagedSession(
            id="session-1",
            template_id="test",
            project_id="project-1",
            tab_id="tab-1",
        )

        state.add_session(session)

        assert "session-1" in state.sessions
        assert state.sessions["session-1"] == session

    def test_remove_session(self) -> None:
        """Test removing a session from state."""
        state = AppState()
        session = ManagedSession(
            id="session-1",
            template_id="test",
            project_id="project-1",
            tab_id="tab-1",
        )
        state.sessions["session-1"] = session

        state.remove_session("session-1")

        assert "session-1" not in state.sessions

    def test_remove_nonexistent_session_no_error(self) -> None:
        """Test removing nonexistent session doesn't raise error."""
        state = AppState()
        state.remove_session("nonexistent")  # Should not raise

    def test_update_session_status(self) -> None:
        """Test updating session status."""
        state = AppState()
        session = ManagedSession(
            id="session-1",
            template_id="test",
            project_id="project-1",
            tab_id="tab-1",
            attention_state=AttentionState.IDLE,
        )
        state.sessions["session-1"] = session

        state.update_session_status(
            "session-1",
            attention_state=AttentionState.WAITING,
        )

        assert state.sessions["session-1"].attention_state == AttentionState.WAITING

    def test_get_sessions_for_project(self) -> None:
        """Test getting sessions for a specific project."""
        state = AppState()

        # Add sessions for different projects
        session1 = ManagedSession(
            id="s1", template_id="t1", project_id="p1", tab_id="t1"
        )
        session2 = ManagedSession(
            id="s2", template_id="t2", project_id="p1", tab_id="t2"
        )
        session3 = ManagedSession(
            id="s3", template_id="t3", project_id="p2", tab_id="t3"
        )

        state.sessions["s1"] = session1
        state.sessions["s2"] = session2
        state.sessions["s3"] = session3

        # Get sessions for project 1
        p1_sessions = state.get_sessions_for_project("p1")

        assert len(p1_sessions) == 2
        assert session1 in p1_sessions
        assert session2 in p1_sessions
        assert session3 not in p1_sessions


class TestStateEventSubscription:
    """Tests for state event subscription system."""

    def test_subscribe_and_emit(self) -> None:
        """Test subscribing and emitting events."""
        state = AppState()
        received_kwargs = {}

        def callback(**kwargs):
            received_kwargs.update(kwargs)

        state.subscribe(StateEvent.CONFIG_CHANGED, callback)
        state.emit(StateEvent.CONFIG_CHANGED, test_value="hello")

        assert received_kwargs.get("test_value") == "hello"

    def test_multiple_subscribers(self) -> None:
        """Test multiple subscribers receive events."""
        state = AppState()
        calls = []

        def callback1(**kwargs):
            calls.append("callback1")

        def callback2(**kwargs):
            calls.append("callback2")

        state.subscribe(StateEvent.SESSION_SPAWNED, callback1)
        state.subscribe(StateEvent.SESSION_SPAWNED, callback2)
        state.emit(StateEvent.SESSION_SPAWNED)

        assert "callback1" in calls
        assert "callback2" in calls

    def test_unsubscribe(self) -> None:
        """Test unsubscribing from events."""
        state = AppState()
        calls = []

        def callback(**kwargs):
            calls.append("called")

        state.subscribe(StateEvent.SESSION_CLOSED, callback)
        state.unsubscribe(StateEvent.SESSION_CLOSED, callback)
        state.emit(StateEvent.SESSION_CLOSED)

        assert len(calls) == 0

    def test_unsubscribe_nonexistent_no_error(self) -> None:
        """Test unsubscribing non-subscribed callback doesn't raise."""
        state = AppState()

        def callback(**kwargs):
            pass

        # Should not raise
        state.unsubscribe(StateEvent.PROJECT_OPENED, callback)

    def test_emit_with_subscriber_error_continues(self) -> None:
        """Test that emit continues even if subscriber raises."""
        state = AppState()
        calls = []

        def error_callback(**kwargs):
            raise RuntimeError("Test error")

        def good_callback(**kwargs):
            calls.append("good")

        state.subscribe(StateEvent.PLAN_RELOADED, error_callback)
        state.subscribe(StateEvent.PLAN_RELOADED, good_callback)
        state.emit(StateEvent.PLAN_RELOADED)

        # Good callback should still be called despite error in first
        assert "good" in calls


@pytest.mark.asyncio
class TestAppStateAsync:
    """Async tests for AppState."""

    async def test_load_config(self) -> None:
        """Test loading configuration."""
        state = AppState()
        await state.load_config()

        # Config should be loaded (may be default config)
        assert state.config is not None

    async def test_open_project(self) -> None:
        """Test opening a project."""
        state = AppState()
        project = Project(id="project-1", name="Test", path="/test")
        state.projects["project-1"] = project

        await state.open_project("project-1")

        assert state.active_project_id == "project-1"
        assert project.is_open

    async def test_close_project(self) -> None:
        """Test closing a project."""
        state = AppState()
        project = Project(id="project-1", name="Test", path="/test", is_open=True)
        state.projects["project-1"] = project
        state.active_project_id = "project-1"

        await state.close_project("project-1")

        assert state.active_project_id is None
        assert not project.is_open
