"""Tests for the AppState module."""

from unittest.mock import MagicMock, patch

import pytest

from iterm_controller.models import (
    AttentionState,
    HealthStatus,
    ManagedSession,
    Plan,
    Project,
)
from iterm_controller.state import (
    AppState,
    ConfigChanged,
    HealthStatusChanged,
    PlanConflict,
    PlanReloaded,
    ProjectClosed,
    ProjectOpened,
    ReviewCompleted,
    ReviewFailed,
    ReviewStarted,
    ReviewStateManager,
    SessionClosed,
    SessionSpawned,
    SessionStatusChanged,
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

        state.update_health_status("p1", "api-health", HealthStatus.HEALTHY)

        mock_app.post_message.assert_called_once()
        posted = mock_app.post_message.call_args[0][0]
        assert isinstance(posted, HealthStatusChanged)
        assert posted.project_id == "p1"
        assert posted.check_name == "api-health"
        assert posted.status == "healthy"

    def test_update_health_status_stores_status(self) -> None:
        """Test that health status update stores the status."""
        state = AppState()

        state.update_health_status("p1", "api", HealthStatus.HEALTHY)
        state.update_health_status("p1", "db", HealthStatus.UNHEALTHY)

        statuses = state.get_health_statuses("p1")
        assert statuses["api"] == HealthStatus.HEALTHY
        assert statuses["db"] == HealthStatus.UNHEALTHY

    def test_get_health_statuses_returns_empty_for_unknown_project(self) -> None:
        """Test that get_health_statuses returns empty dict for unknown project."""
        state = AppState()

        statuses = state.get_health_statuses("unknown-project")
        assert statuses == {}

    def test_get_health_statuses_returns_copy(self) -> None:
        """Test that get_health_statuses returns a copy, not the original."""
        state = AppState()
        state.update_health_status("p1", "api", HealthStatus.HEALTHY)

        statuses = state.get_health_statuses("p1")
        statuses["api"] = HealthStatus.UNHEALTHY

        # Original should be unchanged
        assert state.get_health_statuses("p1")["api"] == HealthStatus.HEALTHY

    def test_clear_health_statuses(self) -> None:
        """Test that clear_health_statuses removes all statuses for project."""
        state = AppState()
        state.update_health_status("p1", "api", HealthStatus.HEALTHY)
        state.update_health_status("p1", "db", HealthStatus.HEALTHY)

        state.clear_health_statuses("p1")

        assert state.get_health_statuses("p1") == {}

    def test_clear_health_statuses_unknown_project_no_error(self) -> None:
        """Test that clear_health_statuses doesn't error for unknown project."""
        state = AppState()

        # Should not raise
        state.clear_health_statuses("unknown-project")

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
        state.update_health_status("p1", "check", HealthStatus.HEALTHY)
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


class TestUpdateProjectPersistence:
    """Tests for update_project with persistence."""

    def test_update_project_updates_in_memory(self) -> None:
        """Test that update_project updates in-memory state."""
        state = AppState()
        project = Project(id="p1", name="Test", path="/test")
        state.projects["p1"] = project

        # Update with persist=False to avoid file operations
        project.name = "Updated Name"
        state.update_project(project, persist=False)

        assert state.projects["p1"].name == "Updated Name"

    def test_update_project_with_persist_updates_config(self) -> None:
        """Test that update_project with persist=True updates config.projects."""
        from iterm_controller.models import AppConfig, WorkflowMode

        state = AppState()
        # Create config with the project
        project = Project(id="p1", name="Test", path="/test")
        state.config = AppConfig(projects=[project])
        state.projects["p1"] = project

        # Update last_mode
        project.last_mode = WorkflowMode.WORK

        # Mock save_global_config to avoid file operations
        with patch("iterm_controller.config.save_global_config") as mock_save:
            state.update_project(project, persist=True)

            # Config.projects should be updated
            assert state.config.projects[0].last_mode == WorkflowMode.WORK

            # save_global_config should have been called
            mock_save.assert_called_once_with(state.config)

    def test_update_project_adds_to_config_if_missing(self) -> None:
        """Test that update_project adds project to config if not present."""
        from iterm_controller.models import AppConfig

        state = AppState()
        # Create config without the project
        state.config = AppConfig(projects=[])
        project = Project(id="p1", name="Test", path="/test")
        state.projects["p1"] = project

        with patch("iterm_controller.config.save_global_config") as mock_save:
            state.update_project(project, persist=True)

            # Project should be added to config.projects
            assert len(state.config.projects) == 1
            assert state.config.projects[0].id == "p1"
            mock_save.assert_called_once()

    def test_update_project_no_persist_when_no_config(self) -> None:
        """Test that update_project doesn't error when config is None."""
        state = AppState()
        project = Project(id="p1", name="Test", path="/test")
        state.projects["p1"] = project
        state.config = None

        # Should not raise even with persist=True
        state.update_project(project, persist=True)

        assert state.projects["p1"] == project

    def test_update_project_handles_save_error(self) -> None:
        """Test that update_project handles save errors gracefully."""
        from iterm_controller.models import AppConfig

        state = AppState()
        project = Project(id="p1", name="Test", path="/test")
        state.config = AppConfig(projects=[project])
        state.projects["p1"] = project

        # Make save_global_config raise an error
        with patch(
            "iterm_controller.config.save_global_config",
            side_effect=Exception("Save failed"),
        ):
            # Should not raise - error is caught
            state.update_project(project, persist=True)

            # In-memory state should still be updated
            assert state.projects["p1"] == project


class TestStateManagers:
    """Tests for the focused state managers."""

    def test_project_manager_load_projects(self) -> None:
        """Test ProjectStateManager.load_projects()."""
        from iterm_controller.state.project_manager import ProjectStateManager

        manager = ProjectStateManager()
        projects = [
            Project(id="p1", name="Project 1", path="/test1"),
            Project(id="p2", name="Project 2", path="/test2"),
        ]

        manager.load_projects(projects)

        assert len(manager.projects) == 2
        assert "p1" in manager.projects
        assert "p2" in manager.projects
        assert manager.projects["p1"].name == "Project 1"

    def test_project_manager_active_project(self) -> None:
        """Test ProjectStateManager.active_project property."""
        from iterm_controller.state.project_manager import ProjectStateManager

        manager = ProjectStateManager()
        project = Project(id="p1", name="Test", path="/test")
        manager.projects["p1"] = project

        # Initially no active project
        assert manager.active_project is None

        # Set active project
        manager.active_project_id = "p1"
        assert manager.active_project == project

    def test_session_manager_operations(self) -> None:
        """Test SessionStateManager add/remove/update operations."""
        from iterm_controller.state.session_manager import SessionStateManager

        manager = SessionStateManager()
        session = ManagedSession(
            id="s1",
            template_id="t1",
            project_id="p1",
            tab_id="tab1",
            attention_state=AttentionState.IDLE,
        )

        # Add session
        manager.add_session(session)
        assert "s1" in manager.sessions
        assert manager.has_active_sessions  # Default is_active=True

        # Update session status
        manager.update_session_status("s1", attention_state=AttentionState.WAITING)
        assert manager.sessions["s1"].attention_state == AttentionState.WAITING

        # Remove session
        manager.remove_session("s1")
        assert "s1" not in manager.sessions

    def test_session_manager_get_sessions_for_project(self) -> None:
        """Test SessionStateManager.get_sessions_for_project()."""
        from iterm_controller.state.session_manager import SessionStateManager

        manager = SessionStateManager()

        session1 = ManagedSession(id="s1", template_id="t1", project_id="p1", tab_id="t1")
        session2 = ManagedSession(id="s2", template_id="t2", project_id="p1", tab_id="t2")
        session3 = ManagedSession(id="s3", template_id="t3", project_id="p2", tab_id="t3")

        manager.sessions["s1"] = session1
        manager.sessions["s2"] = session2
        manager.sessions["s3"] = session3

        p1_sessions = manager.get_sessions_for_project("p1")
        assert len(p1_sessions) == 2
        assert session1 in p1_sessions
        assert session2 in p1_sessions

    def test_plan_manager_operations(self) -> None:
        """Test PlanStateManager plan operations."""
        from iterm_controller.state.plan_manager import PlanStateManager

        manager = PlanStateManager()
        plan = Plan()

        # Set and get plan
        manager.set_plan("p1", plan)
        assert manager.get_plan("p1") is plan
        assert manager.get_plan("nonexistent") is None

    def test_plan_manager_test_plan_operations(self) -> None:
        """Test PlanStateManager test plan operations."""
        from iterm_controller.models import TestPlan
        from iterm_controller.state.plan_manager import PlanStateManager

        manager = PlanStateManager()
        test_plan = TestPlan()

        # Set and get test plan
        manager.set_test_plan("p1", test_plan)
        assert manager.get_test_plan("p1") is test_plan

        # Clear test plan
        manager.clear_test_plan("p1")
        assert manager.get_test_plan("p1") is None

    def test_health_manager_operations(self) -> None:
        """Test HealthStateManager operations."""
        from iterm_controller.state.health_manager import HealthStateManager

        manager = HealthStateManager()

        # Update health status
        manager.update_health_status("p1", "api", HealthStatus.HEALTHY)
        manager.update_health_status("p1", "db", HealthStatus.UNHEALTHY)

        # Get health statuses
        statuses = manager.get_health_statuses("p1")
        assert statuses["api"] == HealthStatus.HEALTHY
        assert statuses["db"] == HealthStatus.UNHEALTHY

        # Clear health statuses
        manager.clear_health_statuses("p1")
        assert manager.get_health_statuses("p1") == {}

    def test_app_state_composes_managers(self) -> None:
        """Test that AppState properly composes the state managers."""
        state = AppState()

        # Access through AppState should work
        project = Project(id="p1", name="Test", path="/test")
        state.projects["p1"] = project

        session = ManagedSession(
            id="s1", template_id="t1", project_id="p1", tab_id="tab1"
        )
        state.add_session(session)

        plan = Plan()
        state.set_plan("p1", plan)

        state.update_health_status("p1", "api", HealthStatus.HEALTHY)

        # Verify all data is accessible
        assert state.projects["p1"] == project
        assert state.sessions["s1"] == session
        assert state.get_plan("p1") is plan
        assert state.get_health_statuses("p1")["api"] == HealthStatus.HEALTHY

    def test_state_snapshot_with_managers(self) -> None:
        """Test that to_snapshot() works correctly with composed managers."""
        state = AppState()

        project = Project(id="p1", name="Test", path="/test")
        state.projects["p1"] = project
        state.active_project_id = "p1"

        session = ManagedSession(
            id="s1", template_id="t1", project_id="p1", tab_id="tab1"
        )
        state.add_session(session)

        plan = Plan()
        state.set_plan("p1", plan)

        state.update_health_status("p1", "api", HealthStatus.HEALTHY)

        # Create snapshot
        snapshot = state.to_snapshot()

        assert snapshot.projects["p1"] == project
        assert snapshot.active_project_id == "p1"
        assert snapshot.sessions["s1"] == session
        assert snapshot.plans["p1"] is plan
        assert snapshot.health_statuses["p1"]["api"] == HealthStatus.HEALTHY


class TestReviewStateManager:
    """Tests for the ReviewStateManager."""

    def test_review_manager_initialization(self) -> None:
        """Test that ReviewStateManager initializes correctly."""
        manager = ReviewStateManager()

        assert manager.active_reviews == {}
        assert manager.review_service is None
        assert manager._app is None

    def test_review_manager_connect_app(self) -> None:
        """Test connecting a Textual app to the manager."""
        manager = ReviewStateManager()
        mock_app = MagicMock()

        manager.connect_app(mock_app)

        assert manager._app is mock_app

    def test_is_reviewing_false_when_empty(self) -> None:
        """Test is_reviewing returns False when no reviews."""
        manager = ReviewStateManager()

        assert not manager.is_reviewing("task-1")

    def test_is_reviewing_true_when_active(self) -> None:
        """Test is_reviewing returns True when review in progress."""
        from datetime import datetime

        from iterm_controller.models import ReviewResult, TaskReview

        manager = ReviewStateManager()
        review = TaskReview(
            id="review-1",
            task_id="task-1",
            attempt=1,
            result=ReviewResult.PENDING,
            issues=[],
            summary="",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="",
        )
        manager.active_reviews["task-1"] = review

        assert manager.is_reviewing("task-1")

    def test_get_active_review_returns_none_when_not_reviewing(self) -> None:
        """Test get_active_review returns None when no active review."""
        manager = ReviewStateManager()

        assert manager.get_active_review("task-1") is None

    def test_get_active_review_returns_review_when_active(self) -> None:
        """Test get_active_review returns the review when active."""
        from datetime import datetime

        from iterm_controller.models import ReviewResult, TaskReview

        manager = ReviewStateManager()
        review = TaskReview(
            id="review-1",
            task_id="task-1",
            attempt=1,
            result=ReviewResult.PENDING,
            issues=[],
            summary="",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="",
        )
        manager.active_reviews["task-1"] = review

        result = manager.get_active_review("task-1")

        assert result is review

    def test_get_all_active_reviews(self) -> None:
        """Test get_all_active_reviews returns all active reviews."""
        from datetime import datetime

        from iterm_controller.models import ReviewResult, TaskReview

        manager = ReviewStateManager()

        review1 = TaskReview(
            id="review-1",
            task_id="task-1",
            attempt=1,
            result=ReviewResult.PENDING,
            issues=[],
            summary="",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="",
        )
        review2 = TaskReview(
            id="review-2",
            task_id="task-2",
            attempt=1,
            result=ReviewResult.PENDING,
            issues=[],
            summary="",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="",
        )

        manager.active_reviews["task-1"] = review1
        manager.active_reviews["task-2"] = review2

        reviews = manager.get_all_active_reviews()

        assert len(reviews) == 2
        assert review1 in reviews
        assert review2 in reviews

    def test_get_review_count(self) -> None:
        """Test get_review_count returns correct count."""
        from datetime import datetime

        from iterm_controller.models import ReviewResult, TaskReview

        manager = ReviewStateManager()

        assert manager.get_review_count() == 0

        review = TaskReview(
            id="review-1",
            task_id="task-1",
            attempt=1,
            result=ReviewResult.PENDING,
            issues=[],
            summary="",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="",
        )
        manager.active_reviews["task-1"] = review

        assert manager.get_review_count() == 1

    def test_clear_removes_all_reviews(self) -> None:
        """Test clear removes all active reviews."""
        from datetime import datetime

        from iterm_controller.models import ReviewResult, TaskReview

        manager = ReviewStateManager()
        review = TaskReview(
            id="review-1",
            task_id="task-1",
            attempt=1,
            result=ReviewResult.PENDING,
            issues=[],
            summary="",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="",
        )
        manager.active_reviews["task-1"] = review

        manager.clear()

        assert manager.active_reviews == {}
        assert not manager.is_reviewing("task-1")


@pytest.mark.asyncio
class TestReviewStateManagerAsync:
    """Async tests for ReviewStateManager."""

    async def test_start_review_without_service_returns_none(self) -> None:
        """Test start_review returns None when no ReviewService configured."""
        manager = ReviewStateManager()
        mock_app = MagicMock()
        manager.connect_app(mock_app)

        result = await manager.start_review("project-1", "task-1")

        assert result is None

    async def test_start_review_without_app_returns_none(self) -> None:
        """Test start_review returns None when project not found."""
        from unittest.mock import AsyncMock

        mock_service = MagicMock()
        manager = ReviewStateManager(review_service=mock_service)
        # No app connected, so project lookup will fail

        result = await manager.start_review("project-1", "task-1")

        assert result is None


class TestReviewStateManagerEvents:
    """Tests for ReviewStateManager event posting."""

    def test_post_message_calls_app(self) -> None:
        """Test that _post_message calls app.post_message."""
        manager = ReviewStateManager()
        mock_app = MagicMock()
        manager.connect_app(mock_app)

        message = MagicMock()
        manager._post_message(message)

        mock_app.post_message.assert_called_once_with(message)

    def test_post_message_no_error_without_app(self) -> None:
        """Test that _post_message doesn't error without app."""
        manager = ReviewStateManager()

        # Should not raise
        manager._post_message(MagicMock())


class TestAppStateReviewOperations:
    """Tests for review operations on AppState."""

    def test_reviews_property_returns_manager(self) -> None:
        """Test that reviews property returns the ReviewStateManager."""
        state = AppState()

        assert isinstance(state.reviews, ReviewStateManager)

    def test_is_reviewing_delegates_to_manager(self) -> None:
        """Test that is_reviewing delegates to ReviewStateManager."""
        from datetime import datetime

        from iterm_controller.models import ReviewResult, TaskReview

        state = AppState()

        # Add a review directly to the manager
        review = TaskReview(
            id="review-1",
            task_id="task-1",
            attempt=1,
            result=ReviewResult.PENDING,
            issues=[],
            summary="",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="",
        )
        state._review_manager.active_reviews["task-1"] = review

        assert state.is_reviewing("task-1")
        assert not state.is_reviewing("task-2")

    def test_get_active_review_delegates_to_manager(self) -> None:
        """Test that get_active_review delegates to ReviewStateManager."""
        from datetime import datetime

        from iterm_controller.models import ReviewResult, TaskReview

        state = AppState()

        review = TaskReview(
            id="review-1",
            task_id="task-1",
            attempt=1,
            result=ReviewResult.PENDING,
            issues=[],
            summary="",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="",
        )
        state._review_manager.active_reviews["task-1"] = review

        result = state.get_active_review("task-1")

        assert result is review

    def test_clear_reviews_delegates_to_manager(self) -> None:
        """Test that clear_reviews delegates to ReviewStateManager."""
        from datetime import datetime

        from iterm_controller.models import ReviewResult, TaskReview

        state = AppState()

        review = TaskReview(
            id="review-1",
            task_id="task-1",
            attempt=1,
            result=ReviewResult.PENDING,
            issues=[],
            summary="",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="",
        )
        state._review_manager.active_reviews["task-1"] = review

        state.clear_reviews()

        assert not state.is_reviewing("task-1")

    def test_connect_app_connects_review_manager(self) -> None:
        """Test that connect_app connects the review manager."""
        state = AppState()
        mock_app = MagicMock()

        state.connect_app(mock_app)

        assert state._review_manager._app is mock_app
