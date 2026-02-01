"""Tests for public API exports from iterm_controller package.

Verifies that all expected symbols are importable from the top-level package.
"""

import pytest


class TestPublicAPIExports:
    """Test that all public API symbols are exported correctly."""

    def test_version_info(self):
        """Test version and author exports."""
        from iterm_controller import __version__, __author__

        assert __version__ == "0.1.0"
        assert __author__ == "Pete Stewart"

    def test_main_api_classes(self):
        """Test main API class exports."""
        from iterm_controller import (
            ItermControllerAPI,
            AppAPI,
            APIResult,
            SessionResult,
            TaskResult,
            TestStepResult,
            ProjectResult,
        )

        # Verify they are the correct types
        assert hasattr(ItermControllerAPI, "initialize")
        assert hasattr(ItermControllerAPI, "shutdown")
        assert hasattr(AppAPI, "spawn_session")
        assert hasattr(APIResult, "ok")
        assert hasattr(APIResult, "fail")

    def test_convenience_functions(self):
        """Test convenience function exports."""
        from iterm_controller import (
            spawn_session,
            claim_task,
            toggle_test_step,
            list_projects,
            list_sessions,
        )

        # Verify they are callable
        assert callable(spawn_session)
        assert callable(claim_task)
        assert callable(toggle_test_step)
        assert callable(list_projects)
        assert callable(list_sessions)

    def test_state_query_functions(self):
        """Test state query function exports."""
        from iterm_controller import (
            get_state,
            get_plan,
            get_project,
            get_sessions,
            get_task_progress,
            get_test_plan,
        )

        # Verify they are callable
        assert callable(get_state)
        assert callable(get_plan)
        assert callable(get_project)
        assert callable(get_sessions)
        assert callable(get_task_progress)
        assert callable(get_test_plan)

    def test_session_models(self):
        """Test session model exports."""
        from iterm_controller import (
            AttentionState,
            SessionTemplate,
            ManagedSession,
        )

        # Verify AttentionState enum values
        assert AttentionState.WAITING.value == "waiting"
        assert AttentionState.WORKING.value == "working"
        assert AttentionState.IDLE.value == "idle"

        # Verify SessionTemplate is a dataclass
        import dataclasses

        assert dataclasses.is_dataclass(SessionTemplate)
        assert dataclasses.is_dataclass(ManagedSession)

    def test_task_models(self):
        """Test task model exports."""
        from iterm_controller import (
            TaskStatus,
            Task,
            Phase,
            Plan,
        )

        # Verify TaskStatus enum values
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETE.value == "complete"
        assert TaskStatus.SKIPPED.value == "skipped"
        assert TaskStatus.BLOCKED.value == "blocked"

        # Verify dataclasses
        import dataclasses

        assert dataclasses.is_dataclass(Task)
        assert dataclasses.is_dataclass(Phase)
        assert dataclasses.is_dataclass(Plan)

    def test_test_models(self):
        """Test test model exports."""
        from iterm_controller import (
            TestStatus,
            TestStep,
            TestSection,
            TestPlan,
        )

        # Verify TestStatus enum values
        assert TestStatus.PENDING.value == "pending"
        assert TestStatus.IN_PROGRESS.value == "in_progress"
        assert TestStatus.PASSED.value == "passed"
        assert TestStatus.FAILED.value == "failed"

        # Verify dataclasses
        import dataclasses

        assert dataclasses.is_dataclass(TestStep)
        assert dataclasses.is_dataclass(TestSection)
        assert dataclasses.is_dataclass(TestPlan)

    def test_project_models(self):
        """Test project model exports."""
        from iterm_controller import (
            Project,
            ProjectTemplate,
            WorkflowMode,
            WorkflowStage,
            WorkflowState,
        )

        # Verify WorkflowMode enum values
        assert WorkflowMode.PLAN.value == "plan"
        assert WorkflowMode.DOCS.value == "docs"
        assert WorkflowMode.WORK.value == "work"
        assert WorkflowMode.TEST.value == "test"

        # Verify WorkflowStage enum values
        assert WorkflowStage.PLANNING.value == "planning"
        assert WorkflowStage.EXECUTE.value == "execute"

        # Verify dataclasses
        import dataclasses

        assert dataclasses.is_dataclass(Project)
        assert dataclasses.is_dataclass(ProjectTemplate)
        assert dataclasses.is_dataclass(WorkflowState)

    def test_config_models(self):
        """Test configuration model exports."""
        from iterm_controller import (
            AppConfig,
            AppSettings,
            HealthCheck,
            HealthStatus,
            WindowLayout,
            TabLayout,
            SessionLayout,
            AutoModeConfig,
        )

        # Verify HealthStatus enum
        assert HealthStatus.UNKNOWN.value == "unknown"
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

        # Verify dataclasses
        import dataclasses

        assert dataclasses.is_dataclass(AppConfig)
        assert dataclasses.is_dataclass(AppSettings)
        assert dataclasses.is_dataclass(HealthCheck)
        assert dataclasses.is_dataclass(WindowLayout)
        assert dataclasses.is_dataclass(TabLayout)
        assert dataclasses.is_dataclass(SessionLayout)
        assert dataclasses.is_dataclass(AutoModeConfig)

    def test_github_models(self):
        """Test GitHub model exports."""
        from iterm_controller import (
            GitHubStatus,
            PullRequest,
            WorkflowRun,
        )

        # Verify dataclasses
        import dataclasses

        assert dataclasses.is_dataclass(GitHubStatus)
        assert dataclasses.is_dataclass(PullRequest)
        assert dataclasses.is_dataclass(WorkflowRun)

    def test_artifact_tracking(self):
        """Test artifact tracking exports."""
        from iterm_controller import ArtifactStatus

        import dataclasses

        assert dataclasses.is_dataclass(ArtifactStatus)

    def test_state_management(self):
        """Test state management exports."""
        from iterm_controller import (
            AppState,
            StateSnapshot,
            StateEvent,
        )

        # Verify AppState has expected methods
        assert hasattr(AppState, "to_snapshot")
        assert hasattr(AppState, "load_config")

        # Verify StateSnapshot is a dataclass
        import dataclasses

        assert dataclasses.is_dataclass(StateSnapshot)

        # Verify StateEvent is an enum
        from enum import Enum

        assert issubclass(StateEvent, Enum)

    def test_iterm2_integration(self):
        """Test iTerm2 integration exports."""
        from iterm_controller import (
            ItermController,
            SessionSpawner,
            SessionTerminator,
            WindowLayoutSpawner,
            WindowLayoutManager,
            SpawnResult,
            CloseResult,
            LayoutSpawnResult,
        )

        # Verify classes have expected attributes
        assert hasattr(ItermController, "connect")
        assert hasattr(ItermController, "disconnect")
        assert hasattr(SessionSpawner, "spawn_session")
        assert hasattr(SessionTerminator, "close_session")

        # Verify result dataclasses
        import dataclasses

        assert dataclasses.is_dataclass(SpawnResult)
        assert dataclasses.is_dataclass(CloseResult)
        assert dataclasses.is_dataclass(LayoutSpawnResult)

    def test_config_functions(self):
        """Test configuration function exports."""
        from iterm_controller import (
            load_global_config,
            save_global_config,
            load_project_config,
            save_project_config,
            load_merged_config,
            get_global_config_path,
            get_config_dir,
            get_project_config_path,
        )

        # Verify they are callable
        assert callable(load_global_config)
        assert callable(save_global_config)
        assert callable(load_project_config)
        assert callable(save_project_config)
        assert callable(load_merged_config)
        assert callable(get_global_config_path)
        assert callable(get_config_dir)
        assert callable(get_project_config_path)

    def test_plan_parsing(self):
        """Test plan parsing exports."""
        from iterm_controller import (
            PlanParser,
            PlanUpdater,
            PlanWatcher,
            PlanWriteQueue,
        )

        # Verify classes have expected methods
        assert hasattr(PlanParser, "parse_file")
        assert hasattr(PlanUpdater, "update_task_status_in_file")
        assert hasattr(PlanWatcher, "start_watching")
        assert hasattr(PlanWatcher, "stop_watching")
        assert hasattr(PlanWriteQueue, "enqueue")

    def test_test_plan_parsing(self):
        """Test test plan parsing exports."""
        from iterm_controller import (
            TestPlanParser,
            TestPlanUpdater,
        )

        # Verify classes have expected methods
        assert hasattr(TestPlanParser, "parse_file")
        assert hasattr(TestPlanUpdater, "update_step_status_in_file")

    def test_all_list_contains_all_exports(self):
        """Test that __all__ contains all expected exports."""
        import iterm_controller

        # Get the __all__ list
        all_exports = set(iterm_controller.__all__)

        # Expected minimum count based on implementation
        assert len(all_exports) >= 70, f"Expected at least 70 exports, got {len(all_exports)}"

        # Verify key items are present
        required_exports = {
            "__version__",
            "__author__",
            "ItermControllerAPI",
            "AppAPI",
            "Project",
            "ManagedSession",
            "Task",
            "Plan",
            "AppState",
            "ItermController",
            "load_global_config",
            "PlanParser",
        }

        missing = required_exports - all_exports
        assert not missing, f"Missing required exports: {missing}"

    def test_import_from_package_directly(self):
        """Test that imports work directly from package."""
        # This is the recommended usage pattern from the docstring
        from iterm_controller import ItermControllerAPI, Project, ManagedSession

        # Create instances to verify they work
        api = ItermControllerAPI()
        assert api is not None
        assert not api.is_initialized

        # Verify we can inspect Project fields
        import dataclasses

        fields = {f.name for f in dataclasses.fields(Project)}
        assert "id" in fields
        assert "name" in fields
        assert "path" in fields


class TestAPIResultTypes:
    """Test the API result type classes."""

    def test_api_result_ok(self):
        """Test APIResult.ok() factory method."""
        from iterm_controller import APIResult

        result = APIResult.ok()
        assert result.success is True
        assert result.error is None

    def test_api_result_fail(self):
        """Test APIResult.fail() factory method."""
        from iterm_controller import APIResult

        result = APIResult.fail("Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"

    def test_session_result(self):
        """Test SessionResult class."""
        from iterm_controller import SessionResult

        result = SessionResult(success=True)
        assert result.success is True
        assert result.session is None
        assert result.spawn_result is None

    def test_task_result(self):
        """Test TaskResult class."""
        from iterm_controller import TaskResult, Task, TaskStatus

        task = Task(id="1.1", title="Test task", status=TaskStatus.PENDING)
        result = TaskResult(success=True, task=task)

        assert result.success is True
        assert result.task is task

    def test_project_result(self):
        """Test ProjectResult class."""
        from iterm_controller import ProjectResult, Project

        project = Project(id="test", name="Test Project", path="/tmp/test")
        result = ProjectResult(success=True, project=project)

        assert result.success is True
        assert result.project is project
