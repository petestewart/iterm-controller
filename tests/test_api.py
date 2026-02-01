"""Tests for the public API module."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iterm_controller.api import (
    APIResult,
    ItermControllerAPI,
    ProjectResult,
    SessionResult,
    TaskResult,
    TestStepResult,
    claim_task,
    get_plan,
    get_project,
    get_sessions,
    get_state,
    get_task_progress,
    get_test_plan,
    list_projects,
    toggle_test_step,
)
from iterm_controller.state import StateSnapshot
from iterm_controller.models import (
    AppConfig,
    AppSettings,
    AttentionState,
    ManagedSession,
    Phase,
    Plan,
    Project,
    SessionTemplate,
    Task,
    TaskStatus,
    TestPlan,
    TestSection,
    TestStatus,
    TestStep,
    WorkflowMode,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_project() -> Project:
    """Create a sample project for testing."""
    return Project(
        id="test-project",
        name="Test Project",
        path="/tmp/test-project",
    )


@pytest.fixture
def sample_template() -> SessionTemplate:
    """Create a sample session template for testing."""
    return SessionTemplate(
        id="dev-server",
        name="Dev Server",
        command="npm run dev",
    )


@pytest.fixture
def sample_plan() -> Plan:
    """Create a sample plan for testing."""
    return Plan(
        phases=[
            Phase(
                id="1",
                title="Phase 1",
                tasks=[
                    Task(id="1.1", title="Task 1", status=TaskStatus.PENDING),
                    Task(id="1.2", title="Task 2", status=TaskStatus.IN_PROGRESS),
                    Task(id="1.3", title="Task 3", status=TaskStatus.COMPLETE),
                ],
            ),
        ],
    )


@pytest.fixture
def sample_test_plan() -> TestPlan:
    """Create a sample test plan for testing."""
    return TestPlan(
        sections=[
            TestSection(
                id="section-0",
                title="Core Features",
                steps=[
                    TestStep(
                        id="section-0-1",
                        section="Core Features",
                        description="Test login",
                        status=TestStatus.PENDING,
                        line_number=5,
                    ),
                    TestStep(
                        id="section-0-2",
                        section="Core Features",
                        description="Test logout",
                        status=TestStatus.PASSED,
                        line_number=6,
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def sample_session() -> ManagedSession:
    """Create a sample managed session for testing."""
    return ManagedSession(
        id="session-1",
        template_id="dev-server",
        project_id="test-project",
        tab_id="tab-1",
        attention_state=AttentionState.IDLE,
        is_active=True,
    )


@pytest.fixture
def sample_config(sample_project: Project, sample_template: SessionTemplate) -> AppConfig:
    """Create a sample config for testing."""
    return AppConfig(
        settings=AppSettings(),
        projects=[sample_project],
        session_templates=[sample_template],
    )


# =============================================================================
# APIResult Tests
# =============================================================================


class TestAPIResult:
    """Tests for APIResult class."""

    def test_ok_creates_success_result(self) -> None:
        """Test that ok() creates a successful result."""
        result = APIResult.ok()
        assert result.success is True
        assert result.error is None

    def test_fail_creates_failure_result(self) -> None:
        """Test that fail() creates a failure result."""
        result = APIResult.fail("Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"


# =============================================================================
# ItermControllerAPI Initialization Tests
# =============================================================================


class TestAPIInitialization:
    """Tests for API initialization."""

    def test_initial_state(self) -> None:
        """Test that API starts uninitialized."""
        api = ItermControllerAPI()
        assert not api.is_initialized
        assert not api.is_connected

    @pytest.mark.asyncio
    async def test_initialize_loads_config(self, sample_config: AppConfig) -> None:
        """Test that initialize loads configuration."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            with patch.object(api._iterm, "connect", new_callable=AsyncMock) as mock_connect:
                # Simulate iTerm2 connection failure (should warn but not fail init)
                from iterm_controller.exceptions import ItermConnectionError
                mock_connect.side_effect = ItermConnectionError("No iTerm2")

                result = await api.initialize(connect_iterm=True)

                # Should succeed even without iTerm2 connection
                assert result.success is True
                assert api.is_initialized
                assert api.get_config() is not None

    @pytest.mark.asyncio
    async def test_initialize_without_iterm(self, sample_config: AppConfig) -> None:
        """Test initialization without iTerm2 connection."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            result = await api.initialize(connect_iterm=False)

            assert result.success is True
            assert api.is_initialized
            assert not api.is_connected

    @pytest.mark.asyncio
    async def test_shutdown(self, sample_config: AppConfig) -> None:
        """Test shutdown clears state."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            result = await api.shutdown()

            assert result.success is True
            assert not api.is_initialized


# =============================================================================
# Project Operations Tests
# =============================================================================


class TestProjectOperations:
    """Tests for project operations."""

    @pytest.mark.asyncio
    async def test_list_projects(
        self, sample_config: AppConfig, sample_project: Project
    ) -> None:
        """Test listing projects."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)

            projects = await api.list_projects()

            assert len(projects) == 1
            assert projects[0].id == "test-project"

    @pytest.mark.asyncio
    async def test_get_project(
        self, sample_config: AppConfig, sample_project: Project
    ) -> None:
        """Test getting a specific project."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)

            project = await api.get_project("test-project")

            assert project is not None
            assert project.id == "test-project"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, sample_config: AppConfig) -> None:
        """Test getting a project that doesn't exist."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)

            project = await api.get_project("nonexistent")

            assert project is None

    @pytest.mark.asyncio
    async def test_create_project(self, sample_config: AppConfig) -> None:
        """Test creating a new project."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            with patch("iterm_controller.api.save_global_config"):
                await api.initialize(connect_iterm=False)

                result = await api.create_project(
                    project_id="new-project",
                    name="New Project",
                    path="/tmp/new-project",
                )

                assert result.success is True
                assert result.project is not None
                assert result.project.id == "new-project"

    @pytest.mark.asyncio
    async def test_create_project_already_exists(
        self, sample_config: AppConfig
    ) -> None:
        """Test creating a project that already exists."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)

            result = await api.create_project(
                project_id="test-project",
                name="Test Project",
                path="/tmp/test-project",
            )

            assert result.success is False
            assert "already exists" in result.error.lower()

    @pytest.mark.asyncio
    async def test_delete_project(self, sample_config: AppConfig) -> None:
        """Test deleting a project."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            with patch("iterm_controller.api.save_global_config"):
                await api.initialize(connect_iterm=False)

                result = await api.delete_project("test-project")

                assert result.success is True
                assert await api.get_project("test-project") is None

    @pytest.mark.asyncio
    async def test_delete_project_not_found(self, sample_config: AppConfig) -> None:
        """Test deleting a project that doesn't exist."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)

            result = await api.delete_project("nonexistent")

            assert result.success is False
            assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_update_project_mode(self, sample_config: AppConfig) -> None:
        """Test updating a project's workflow mode."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            with patch("iterm_controller.api.save_global_config"):
                await api.initialize(connect_iterm=False)

                result = await api.update_project_mode("test-project", WorkflowMode.WORK)

                assert result.success is True
                project = await api.get_project("test-project")
                assert project.last_mode == WorkflowMode.WORK


# =============================================================================
# Session Operations Tests
# =============================================================================


class TestSessionOperations:
    """Tests for session operations."""

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, sample_config: AppConfig) -> None:
        """Test listing sessions when none exist."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)

            sessions = await api.list_sessions()

            assert len(sessions) == 0

    @pytest.mark.asyncio
    async def test_list_sessions_with_sessions(
        self, sample_config: AppConfig, sample_session: ManagedSession
    ) -> None:
        """Test listing sessions when some exist."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.add_session(sample_session)

            sessions = await api.list_sessions()

            assert len(sessions) == 1
            assert sessions[0].id == "session-1"

    @pytest.mark.asyncio
    async def test_list_sessions_filtered_by_project(
        self, sample_config: AppConfig, sample_session: ManagedSession
    ) -> None:
        """Test listing sessions filtered by project."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.add_session(sample_session)

            # Add another session for different project
            other_session = ManagedSession(
                id="session-2",
                template_id="dev-server",
                project_id="other-project",
                tab_id="tab-2",
            )
            api._state.add_session(other_session)

            sessions = await api.list_sessions("test-project")

            assert len(sessions) == 1
            assert sessions[0].id == "session-1"

    @pytest.mark.asyncio
    async def test_get_session(
        self, sample_config: AppConfig, sample_session: ManagedSession
    ) -> None:
        """Test getting a specific session."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.add_session(sample_session)

            session = await api.get_session("session-1")

            assert session is not None
            assert session.id == "session-1"

    @pytest.mark.asyncio
    async def test_get_session_status(
        self, sample_config: AppConfig, sample_session: ManagedSession
    ) -> None:
        """Test getting a session's attention state."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.add_session(sample_session)

            status = await api.get_session_status("session-1")

            assert status == AttentionState.IDLE

    @pytest.mark.asyncio
    async def test_spawn_session_without_iterm(self, sample_config: AppConfig) -> None:
        """Test spawning a session when not connected to iTerm2."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)

            result = await api.spawn_session("test-project", "dev-server")

            assert result.success is False
            assert "not connected" in result.error.lower()

    @pytest.mark.asyncio
    async def test_get_sessions_waiting(
        self, sample_config: AppConfig, sample_session: ManagedSession
    ) -> None:
        """Test getting sessions in WAITING state."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)

            # Add idle session
            api._state.add_session(sample_session)

            # Add waiting session
            waiting_session = ManagedSession(
                id="session-2",
                template_id="dev-server",
                project_id="test-project",
                tab_id="tab-2",
                attention_state=AttentionState.WAITING,
            )
            api._state.add_session(waiting_session)

            waiting = await api.get_sessions_waiting()

            assert len(waiting) == 1
            assert waiting[0].id == "session-2"


# =============================================================================
# Task Operations Tests
# =============================================================================


class TestTaskOperations:
    """Tests for task operations."""

    @pytest.mark.asyncio
    async def test_get_plan(
        self, sample_config: AppConfig, sample_plan: Plan
    ) -> None:
        """Test getting a project's plan."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.set_plan("test-project", sample_plan)

            plan = await api.get_plan("test-project")

            assert plan is not None
            assert len(plan.all_tasks) == 3

    @pytest.mark.asyncio
    async def test_list_tasks(
        self, sample_config: AppConfig, sample_plan: Plan
    ) -> None:
        """Test listing tasks."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.set_plan("test-project", sample_plan)

            tasks = await api.list_tasks("test-project")

            assert len(tasks) == 3

    @pytest.mark.asyncio
    async def test_list_tasks_filtered_by_status(
        self, sample_config: AppConfig, sample_plan: Plan
    ) -> None:
        """Test listing tasks filtered by status."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.set_plan("test-project", sample_plan)

            tasks = await api.list_tasks("test-project", status=TaskStatus.PENDING)

            assert len(tasks) == 1
            assert tasks[0].id == "1.1"

    @pytest.mark.asyncio
    async def test_get_task(
        self, sample_config: AppConfig, sample_plan: Plan
    ) -> None:
        """Test getting a specific task."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.set_plan("test-project", sample_plan)

            task = await api.get_task("test-project", "1.2")

            assert task is not None
            assert task.title == "Task 2"
            assert task.status == TaskStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_get_task_progress(
        self, sample_config: AppConfig, sample_plan: Plan
    ) -> None:
        """Test getting task progress summary."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.set_plan("test-project", sample_plan)

            progress = await api.get_task_progress("test-project")

            assert progress["pending"] == 1
            assert progress["in_progress"] == 1
            assert progress["complete"] == 1


# =============================================================================
# Test Plan Operations Tests
# =============================================================================


class TestTestPlanOperations:
    """Tests for test plan operations."""

    @pytest.mark.asyncio
    async def test_get_test_plan(
        self, sample_config: AppConfig, sample_test_plan: TestPlan
    ) -> None:
        """Test getting a project's test plan."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.set_test_plan("test-project", sample_test_plan)

            test_plan = await api.get_test_plan("test-project")

            assert test_plan is not None
            assert len(test_plan.all_steps) == 2

    @pytest.mark.asyncio
    async def test_list_test_steps(
        self, sample_config: AppConfig, sample_test_plan: TestPlan
    ) -> None:
        """Test listing test steps."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.set_test_plan("test-project", sample_test_plan)

            steps = await api.list_test_steps("test-project")

            assert len(steps) == 2

    @pytest.mark.asyncio
    async def test_list_test_steps_filtered(
        self, sample_config: AppConfig, sample_test_plan: TestPlan
    ) -> None:
        """Test listing test steps filtered by status."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.set_test_plan("test-project", sample_test_plan)

            steps = await api.list_test_steps("test-project", status=TestStatus.PENDING)

            assert len(steps) == 1
            assert steps[0].description == "Test login"

    @pytest.mark.asyncio
    async def test_get_test_step(
        self, sample_config: AppConfig, sample_test_plan: TestPlan
    ) -> None:
        """Test getting a specific test step."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.set_test_plan("test-project", sample_test_plan)

            step = await api.get_test_step("test-project", "section-0-1")

            assert step is not None
            assert step.description == "Test login"

    @pytest.mark.asyncio
    async def test_get_test_progress(
        self, sample_config: AppConfig, sample_test_plan: TestPlan
    ) -> None:
        """Test getting test progress summary."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.set_test_plan("test-project", sample_test_plan)

            progress = await api.get_test_progress("test-project")

            assert progress["pending"] == 1
            assert progress["passed"] == 1


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio
    async def test_list_projects_convenience(self, sample_config: AppConfig) -> None:
        """Test list_projects convenience function."""
        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            projects = await list_projects()

            assert len(projects) == 1
            assert projects[0].id == "test-project"


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_operations_before_initialize(self) -> None:
        """Test operations before initialization."""
        api = ItermControllerAPI()

        projects = await api.list_projects()
        assert len(projects) == 0

    @pytest.mark.asyncio
    async def test_get_plan_no_plan_loaded(self, sample_config: AppConfig) -> None:
        """Test getting plan when none loaded."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)

            plan = await api.get_plan("test-project")

            assert plan is None

    @pytest.mark.asyncio
    async def test_get_active_project_none(self, sample_config: AppConfig) -> None:
        """Test getting active project when none active."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)

            project = await api.get_active_project()

            assert project is None

    @pytest.mark.asyncio
    async def test_list_layouts_empty(self, sample_config: AppConfig) -> None:
        """Test listing layouts when none exist."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)

            layouts = await api.list_layouts()

            assert len(layouts) == 0


# =============================================================================
# StateSnapshot Tests
# =============================================================================


class TestStateSnapshot:
    """Tests for StateSnapshot class."""

    @pytest.mark.asyncio
    async def test_to_snapshot_basic(
        self,
        sample_config: AppConfig,
        sample_project: Project,
        sample_session: ManagedSession,
    ) -> None:
        """Test creating a state snapshot."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.add_session(sample_session)

            snapshot = api._state.to_snapshot()

            assert isinstance(snapshot, StateSnapshot)
            assert len(snapshot.projects) == 1
            assert len(snapshot.sessions) == 1
            assert "test-project" in snapshot.projects
            assert "session-1" in snapshot.sessions

    @pytest.mark.asyncio
    async def test_snapshot_is_copy(
        self,
        sample_config: AppConfig,
        sample_session: ManagedSession,
    ) -> None:
        """Test that snapshot contains copies, not references."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.add_session(sample_session)

            snapshot = api._state.to_snapshot()

            # Modify snapshot
            snapshot.sessions.clear()

            # Original state should be unchanged
            assert len(api._state.sessions) == 1

    @pytest.mark.asyncio
    async def test_snapshot_active_project(
        self,
        sample_config: AppConfig,
        sample_project: Project,
    ) -> None:
        """Test snapshot active_project property."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)

            # No active project initially
            snapshot = api._state.to_snapshot()
            assert snapshot.active_project is None

            # Set active project
            api._state.active_project_id = "test-project"
            snapshot = api._state.to_snapshot()
            assert snapshot.active_project is not None
            assert snapshot.active_project.id == "test-project"

    @pytest.mark.asyncio
    async def test_snapshot_has_active_sessions(
        self,
        sample_config: AppConfig,
        sample_session: ManagedSession,
    ) -> None:
        """Test snapshot has_active_sessions property."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)

            # No sessions
            snapshot = api._state.to_snapshot()
            assert not snapshot.has_active_sessions

            # Add active session
            api._state.add_session(sample_session)
            snapshot = api._state.to_snapshot()
            assert snapshot.has_active_sessions

    @pytest.mark.asyncio
    async def test_snapshot_get_sessions_for_project(
        self,
        sample_config: AppConfig,
        sample_session: ManagedSession,
    ) -> None:
        """Test snapshot get_sessions_for_project method."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.add_session(sample_session)

            # Add session for different project
            other_session = ManagedSession(
                id="session-2",
                template_id="dev-server",
                project_id="other-project",
                tab_id="tab-2",
            )
            api._state.add_session(other_session)

            snapshot = api._state.to_snapshot()
            sessions = snapshot.get_sessions_for_project("test-project")

            assert len(sessions) == 1
            assert sessions[0].id == "session-1"

    @pytest.mark.asyncio
    async def test_snapshot_with_plans(
        self,
        sample_config: AppConfig,
        sample_plan: Plan,
        sample_test_plan: TestPlan,
    ) -> None:
        """Test snapshot includes plans."""
        api = ItermControllerAPI()

        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            await api.initialize(connect_iterm=False)
            api._state.set_plan("test-project", sample_plan)
            api._state.set_test_plan("test-project", sample_test_plan)

            snapshot = api._state.to_snapshot()

            assert "test-project" in snapshot.plans
            assert "test-project" in snapshot.test_plans
            assert snapshot.get_plan("test-project") is not None
            assert snapshot.get_test_plan("test-project") is not None


# =============================================================================
# State Query Convenience Function Tests
# =============================================================================


class TestStateQueryFunctions:
    """Tests for state query convenience functions."""

    @pytest.mark.asyncio
    async def test_get_state(self, sample_config: AppConfig) -> None:
        """Test get_state convenience function."""
        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            state = await get_state()

            assert state is not None
            assert isinstance(state, StateSnapshot)
            assert len(state.projects) == 1
            assert "test-project" in state.projects

    @pytest.mark.asyncio
    async def test_get_project_convenience(self, sample_config: AppConfig) -> None:
        """Test get_project convenience function."""
        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            project = await get_project("test-project")

            assert project is not None
            assert project.id == "test-project"
            assert project.name == "Test Project"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, sample_config: AppConfig) -> None:
        """Test get_project returns None for missing project."""
        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            project = await get_project("nonexistent")

            assert project is None

    @pytest.mark.asyncio
    async def test_get_sessions_alias(self, sample_config: AppConfig) -> None:
        """Test get_sessions is alias for list_sessions."""
        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            with patch("iterm_controller.api.list_sessions", new_callable=AsyncMock) as mock:
                mock.return_value = []

                await get_sessions("test-project")

                mock.assert_called_once_with("test-project")

    @pytest.mark.asyncio
    async def test_get_task_progress_convenience(
        self, sample_config: AppConfig, sample_plan: Plan
    ) -> None:
        """Test get_task_progress convenience function."""
        with patch("iterm_controller.config.load_global_config", return_value=sample_config):
            # Create a project directory with PLAN.md
            with tempfile.TemporaryDirectory() as tmpdir:
                # Update project path
                sample_config.projects[0].path = tmpdir
                plan_path = Path(tmpdir) / "PLAN.md"
                plan_path.write_text("""
# Plan

## Phase 1

- [ ] Task 1
- [x] Task 2
- [~] Task 3
""")

                progress = await get_task_progress("test-project")

                # Should have loaded the plan and returned progress
                assert isinstance(progress, dict)
