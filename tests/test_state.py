"""Tests for the AppState module."""

from unittest.mock import MagicMock

import pytest

from iterm_controller.models import AttentionState, ManagedSession, Plan, Project
from iterm_controller.state import (
    AppState,
    ConfigChanged,
    HealthStatusChanged,
    PlanConflict,
    PlanReloaded,
    ProjectClosed,
    ProjectOpened,
    SessionClosed,
    SessionSpawned,
    SessionStatusChanged,
    StateEvent,
    TaskStatusChanged,
    WorkflowStageChanged,
)


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


class TestAppStateTextualMessages:
    """Tests for Textual message posting from AppState."""

    def test_connect_app(self) -> None:
        """Test connecting a Textual app to state."""
        state = AppState()
        mock_app = MagicMock()

        state.connect_app(mock_app)

        assert state._app is mock_app

    def test_add_session_posts_message(self) -> None:
        """Test that adding a session posts SessionSpawned message."""
        state = AppState()
        mock_app = MagicMock()
        state.connect_app(mock_app)

        session = ManagedSession(
            id="s1", template_id="t1", project_id="p1", tab_id="tab1"
        )
        state.add_session(session)

        # Verify message was posted
        mock_app.post_message.assert_called_once()
        posted = mock_app.post_message.call_args[0][0]
        assert isinstance(posted, SessionSpawned)
        assert posted.session is session

    def test_remove_session_posts_message(self) -> None:
        """Test that removing a session posts SessionClosed message."""
        state = AppState()
        mock_app = MagicMock()
        state.connect_app(mock_app)

        session = ManagedSession(
            id="s1", template_id="t1", project_id="p1", tab_id="tab1"
        )
        state.sessions["s1"] = session
        state.remove_session("s1")

        mock_app.post_message.assert_called_once()
        posted = mock_app.post_message.call_args[0][0]
        assert isinstance(posted, SessionClosed)
        assert posted.session is session

    def test_update_session_status_posts_message(self) -> None:
        """Test that updating session status posts SessionStatusChanged."""
        state = AppState()
        mock_app = MagicMock()
        state.connect_app(mock_app)

        session = ManagedSession(
            id="s1",
            template_id="t1",
            project_id="p1",
            tab_id="tab1",
            attention_state=AttentionState.IDLE,
        )
        state.sessions["s1"] = session
        state.update_session_status("s1", attention_state=AttentionState.WAITING)

        mock_app.post_message.assert_called_once()
        posted = mock_app.post_message.call_args[0][0]
        assert isinstance(posted, SessionStatusChanged)
        assert posted.session.attention_state == AttentionState.WAITING

    def test_set_plan_posts_message(self) -> None:
        """Test that setting a plan posts PlanReloaded message."""
        state = AppState()
        mock_app = MagicMock()
        state.connect_app(mock_app)

        plan = Plan()
        state.set_plan("p1", plan)

        mock_app.post_message.assert_called_once()
        posted = mock_app.post_message.call_args[0][0]
        assert isinstance(posted, PlanReloaded)
        assert posted.project_id == "p1"
        assert posted.plan is plan

    def test_get_plan_returns_stored_plan(self) -> None:
        """Test that get_plan returns the stored plan."""
        state = AppState()
        plan = Plan()
        state.plans["p1"] = plan

        result = state.get_plan("p1")

        assert result is plan

    def test_get_plan_returns_none_for_missing(self) -> None:
        """Test that get_plan returns None for missing project."""
        state = AppState()

        result = state.get_plan("nonexistent")

        assert result is None

    def test_notify_plan_conflict_posts_message(self) -> None:
        """Test that plan conflict notification posts PlanConflict."""
        state = AppState()
        mock_app = MagicMock()
        state.connect_app(mock_app)

        new_plan = Plan()
        state.notify_plan_conflict("p1", new_plan)

        mock_app.post_message.assert_called_once()
        posted = mock_app.post_message.call_args[0][0]
        assert isinstance(posted, PlanConflict)
        assert posted.project_id == "p1"
        assert posted.new_plan is new_plan

    def test_update_task_status_posts_message(self) -> None:
        """Test that task status update posts TaskStatusChanged."""
        state = AppState()
        mock_app = MagicMock()
        state.connect_app(mock_app)

        state.update_task_status("p1", "1.1")

        mock_app.post_message.assert_called_once()
        posted = mock_app.post_message.call_args[0][0]
        assert isinstance(posted, TaskStatusChanged)
        assert posted.project_id == "p1"
        assert posted.task_id == "1.1"

    def test_update_health_status_posts_message(self) -> None:
        """Test that health status update posts HealthStatusChanged."""
        state = AppState()
        mock_app = MagicMock()
        state.connect_app(mock_app)

        state.update_health_status("p1", "api-health", "healthy")

        mock_app.post_message.assert_called_once()
        posted = mock_app.post_message.call_args[0][0]
        assert isinstance(posted, HealthStatusChanged)
        assert posted.project_id == "p1"
        assert posted.check_name == "api-health"
        assert posted.status == "healthy"

    def test_update_workflow_stage_posts_message(self) -> None:
        """Test that workflow stage update posts WorkflowStageChanged."""
        state = AppState()
        mock_app = MagicMock()
        state.connect_app(mock_app)

        state.update_workflow_stage("p1", "execute")

        mock_app.post_message.assert_called_once()
        posted = mock_app.post_message.call_args[0][0]
        assert isinstance(posted, WorkflowStageChanged)
        assert posted.project_id == "p1"
        assert posted.stage == "execute"

    def test_no_message_without_app(self) -> None:
        """Test that no error occurs when app not connected."""
        state = AppState()

        # These should not raise
        session = ManagedSession(
            id="s1", template_id="t1", project_id="p1", tab_id="tab1"
        )
        state.add_session(session)
        state.update_session_status("s1", attention_state=AttentionState.WAITING)
        state.remove_session("s1")
        state.set_plan("p1", Plan())
        state.update_task_status("p1", "1.1")
        state.update_health_status("p1", "check", "healthy")
        state.update_workflow_stage("p1", "execute")


@pytest.mark.asyncio
class TestAppStateAsyncMessages:
    """Async tests for Textual message posting."""

    async def test_open_project_posts_message(self) -> None:
        """Test that opening a project posts ProjectOpened message."""
        state = AppState()
        mock_app = MagicMock()
        state.connect_app(mock_app)

        project = Project(id="p1", name="Test", path="/test")
        state.projects["p1"] = project

        await state.open_project("p1")

        mock_app.post_message.assert_called_once()
        posted = mock_app.post_message.call_args[0][0]
        assert isinstance(posted, ProjectOpened)
        assert posted.project is project

    async def test_close_project_posts_message(self) -> None:
        """Test that closing a project posts ProjectClosed message."""
        state = AppState()
        mock_app = MagicMock()
        state.connect_app(mock_app)

        project = Project(id="p1", name="Test", path="/test", is_open=True)
        state.projects["p1"] = project
        state.active_project_id = "p1"

        await state.close_project("p1")

        mock_app.post_message.assert_called_once()
        posted = mock_app.post_message.call_args[0][0]
        assert isinstance(posted, ProjectClosed)
        assert posted.project_id == "p1"

    async def test_load_config_posts_message(self) -> None:
        """Test that loading config posts ConfigChanged message."""
        state = AppState()
        mock_app = MagicMock()
        state.connect_app(mock_app)

        await state.load_config()

        mock_app.post_message.assert_called_once()
        posted = mock_app.post_message.call_args[0][0]
        assert isinstance(posted, ConfigChanged)
        assert state.config is posted.config
