"""Tests for core data models and serialization."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from iterm_controller.models import (
    AppConfig,
    AppSettings,
    AttentionState,
    AutoModeConfig,
    GitHubStatus,
    HealthCheck,
    HealthStatus,
    ManagedSession,
    Phase,
    Plan,
    Project,
    ProjectTemplate,
    PullRequest,
    ReviewConfig,
    ReviewContextConfig,
    ReviewResult,
    SessionLayout,
    SessionProgress,
    SessionTemplate,
    SessionType,
    TabLayout,
    Task,
    TaskReview,
    TaskStatus,
    TestPlan,
    TestSection,
    TestStatus,
    TestStep,
    WindowLayout,
    WorkflowMode,
    WorkflowStage,
    WorkflowState,
    load_config,
    load_config_from_dict,
    model_from_dict,
    model_to_dict,
    save_config,
)


class TestEnums:
    """Test enum definitions and values."""

    def test_session_type_values(self):
        """Test SessionType enum values match spec."""
        assert SessionType.CLAUDE_TASK.value == "claude_task"
        assert SessionType.ORCHESTRATOR.value == "orchestrator"
        assert SessionType.REVIEW.value == "review"
        assert SessionType.TEST_RUNNER.value == "test_runner"
        assert SessionType.SCRIPT.value == "script"
        assert SessionType.SERVER.value == "server"
        assert SessionType.SHELL.value == "shell"

    def test_attention_state_values(self):
        assert AttentionState.WAITING.value == "waiting"
        assert AttentionState.WORKING.value == "working"
        assert AttentionState.IDLE.value == "idle"

    def test_task_status_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.AWAITING_REVIEW.value == "awaiting_review"
        assert TaskStatus.COMPLETE.value == "complete"
        assert TaskStatus.SKIPPED.value == "skipped"
        assert TaskStatus.BLOCKED.value == "blocked"

    def test_workflow_stage_values(self):
        assert WorkflowStage.PLANNING.value == "planning"
        assert WorkflowStage.EXECUTE.value == "execute"
        assert WorkflowStage.REVIEW.value == "review"
        assert WorkflowStage.PR.value == "pr"
        assert WorkflowStage.DONE.value == "done"

    def test_health_status_values(self):
        assert HealthStatus.UNKNOWN.value == "unknown"
        assert HealthStatus.CHECKING.value == "checking"
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_workflow_mode_values(self):
        assert WorkflowMode.PLAN.value == "plan"
        assert WorkflowMode.DOCS.value == "docs"
        assert WorkflowMode.WORK.value == "work"
        assert WorkflowMode.TEST.value == "test"

    def test_review_result_values(self):
        """Test ReviewResult enum values match spec."""
        assert ReviewResult.PENDING.value == "pending"
        assert ReviewResult.APPROVED.value == "approved"
        assert ReviewResult.NEEDS_REVISION.value == "needs_revision"
        assert ReviewResult.REJECTED.value == "rejected"


class TestReviewModels:
    """Test review-related dataclasses."""

    def test_task_review_creation(self):
        """Test creating a TaskReview with all fields."""
        reviewed_at = datetime.now()
        review = TaskReview(
            id="review-123",
            task_id="1.1",
            attempt=1,
            result=ReviewResult.APPROVED,
            issues=[],
            summary="Task completed correctly",
            blocking=False,
            reviewed_at=reviewed_at,
            reviewer_command="/review-task",
            raw_output="Review output...",
        )
        assert review.id == "review-123"
        assert review.task_id == "1.1"
        assert review.attempt == 1
        assert review.result == ReviewResult.APPROVED
        assert review.issues == []
        assert review.summary == "Task completed correctly"
        assert review.blocking is False
        assert review.reviewed_at == reviewed_at
        assert review.reviewer_command == "/review-task"
        assert review.raw_output == "Review output..."

    def test_task_review_with_issues(self):
        """Test TaskReview with issues list."""
        review = TaskReview(
            id="review-456",
            task_id="2.1",
            attempt=2,
            result=ReviewResult.NEEDS_REVISION,
            issues=["Missing error handling", "Need more tests"],
            summary="Implementation needs work",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="/review-task",
        )
        assert review.result == ReviewResult.NEEDS_REVISION
        assert len(review.issues) == 2
        assert "Missing error handling" in review.issues
        assert review.raw_output is None

    def test_task_review_rejected_blocking(self):
        """Test TaskReview with rejected/blocking status."""
        review = TaskReview(
            id="review-789",
            task_id="3.1",
            attempt=1,
            result=ReviewResult.REJECTED,
            issues=["Security vulnerability found"],
            summary="Critical issue requires human review",
            blocking=True,
            reviewed_at=datetime.now(),
            reviewer_command="/review-task",
        )
        assert review.result == ReviewResult.REJECTED
        assert review.blocking is True

    def test_task_review_serialization(self):
        """Test TaskReview serializes to/from dict correctly."""
        reviewed_at = datetime.now()
        review = TaskReview(
            id="review-123",
            task_id="1.1",
            attempt=1,
            result=ReviewResult.NEEDS_REVISION,
            issues=["Issue 1", "Issue 2"],
            summary="Needs work",
            blocking=False,
            reviewed_at=reviewed_at,
            reviewer_command="/review-task",
            raw_output="Raw output here",
        )
        data = model_to_dict(review)
        assert data["id"] == "review-123"
        assert data["task_id"] == "1.1"
        assert data["attempt"] == 1
        assert data["result"] == "needs_revision"
        assert data["issues"] == ["Issue 1", "Issue 2"]
        assert data["summary"] == "Needs work"
        assert data["blocking"] is False

        restored = model_from_dict(TaskReview, data)
        assert restored.id == "review-123"
        assert restored.result == ReviewResult.NEEDS_REVISION
        assert len(restored.issues) == 2

    def test_review_context_config_defaults(self):
        """Test ReviewContextConfig default values."""
        config = ReviewContextConfig()
        assert config.include_task_definition is True
        assert config.include_git_diff is True
        assert config.include_test_results is True
        assert config.include_lint_results is False
        assert config.include_session_log is False

    def test_review_context_config_custom(self):
        """Test ReviewContextConfig with custom values."""
        config = ReviewContextConfig(
            include_task_definition=True,
            include_git_diff=True,
            include_test_results=False,
            include_lint_results=True,
            include_session_log=True,
        )
        assert config.include_test_results is False
        assert config.include_lint_results is True
        assert config.include_session_log is True

    def test_review_context_config_serialization(self):
        """Test ReviewContextConfig serializes to/from dict correctly."""
        config = ReviewContextConfig(
            include_git_diff=False,
            include_lint_results=True,
        )
        data = model_to_dict(config)
        assert data["include_git_diff"] is False
        assert data["include_lint_results"] is True

        restored = model_from_dict(ReviewContextConfig, data)
        assert restored.include_git_diff is False
        assert restored.include_lint_results is True

    def test_review_config_defaults(self):
        """Test ReviewConfig default values."""
        config = ReviewConfig()
        assert config.enabled is True
        assert config.command == "/review-task"
        assert config.model is None
        assert config.max_revisions == 3
        assert config.trigger == "script_completion"
        assert config.context is None

    def test_review_config_custom(self):
        """Test ReviewConfig with custom values."""
        context = ReviewContextConfig(include_lint_results=True)
        config = ReviewConfig(
            enabled=True,
            command="/custom-review",
            model="opus",
            max_revisions=5,
            trigger="manual",
            context=context,
        )
        assert config.command == "/custom-review"
        assert config.model == "opus"
        assert config.max_revisions == 5
        assert config.trigger == "manual"
        assert config.context is not None
        assert config.context.include_lint_results is True

    def test_review_config_serialization(self):
        """Test ReviewConfig serializes to/from dict correctly."""
        context = ReviewContextConfig(include_session_log=True)
        config = ReviewConfig(
            enabled=False,
            command="/review",
            model="haiku",
            max_revisions=2,
            trigger="script_completion",
            context=context,
        )
        data = model_to_dict(config)
        assert data["enabled"] is False
        assert data["command"] == "/review"
        assert data["model"] == "haiku"
        assert data["max_revisions"] == 2
        assert data["context"]["include_session_log"] is True

        restored = model_from_dict(ReviewConfig, data)
        assert restored.enabled is False
        assert restored.model == "haiku"
        assert restored.context is not None
        assert restored.context.include_session_log is True

    def test_review_config_with_none_context_serialization(self):
        """Test ReviewConfig with None context serializes correctly."""
        config = ReviewConfig(context=None)
        data = model_to_dict(config)
        assert data["context"] is None

        restored = model_from_dict(ReviewConfig, data)
        assert restored.context is None


class TestProjectModel:
    """Test Project dataclass."""

    def test_project_creation(self):
        project = Project(
            id="test-project",
            name="Test Project",
            path="/path/to/project",
        )
        assert project.id == "test-project"
        assert project.name == "Test Project"
        assert project.path == "/path/to/project"
        assert project.plan_path == "PLAN.md"
        assert project.test_plan_path == "TEST_PLAN.md"
        assert project.config_path is None
        assert project.template_id is None
        assert project.jira_ticket is None
        assert project.last_mode is None
        assert project.is_open is False
        assert project.sessions == []

    def test_project_with_jira_ticket(self):
        project = Project(
            id="test-project",
            name="Test Project",
            path="/path/to/project",
            jira_ticket="PROJ-123",
        )
        assert project.jira_ticket == "PROJ-123"

    def test_project_with_last_mode(self):
        project = Project(
            id="test-project",
            name="Test Project",
            path="/path/to/project",
            last_mode=WorkflowMode.WORK,
        )
        assert project.last_mode == WorkflowMode.WORK

    def test_project_last_mode_serialization(self):
        """Test that last_mode persists to/from JSON correctly."""
        project = Project(
            id="test-project",
            name="Test Project",
            path="/path/to/project",
            last_mode=WorkflowMode.PLAN,
        )
        data = model_to_dict(project)
        assert data["last_mode"] == "plan"

        restored = model_from_dict(Project, data)
        assert restored.last_mode == WorkflowMode.PLAN

    def test_project_last_mode_none_serialization(self):
        """Test that last_mode=None persists correctly."""
        project = Project(
            id="test-project",
            name="Test Project",
            path="/path/to/project",
            last_mode=None,
        )
        data = model_to_dict(project)
        assert data["last_mode"] is None

        restored = model_from_dict(Project, data)
        assert restored.last_mode is None

    def test_full_plan_path_property(self):
        project = Project(
            id="test",
            name="Test",
            path="/home/user/myproject",
            plan_path="docs/PLAN.md",
        )
        assert project.full_plan_path == Path("/home/user/myproject/docs/PLAN.md")

    def test_project_serialization(self):
        project = Project(
            id="test",
            name="Test",
            path="/path",
        )
        data = model_to_dict(project)
        assert data["id"] == "test"
        assert data["name"] == "Test"
        assert data["path"] == "/path"

        restored = model_from_dict(Project, data)
        assert restored.id == project.id
        assert restored.name == project.name


class TestSessionModels:
    """Test session-related dataclasses."""

    def test_session_template(self):
        template = SessionTemplate(
            id="server",
            name="Dev Server",
            command="npm run dev",
            working_dir="./frontend",
            env={"NODE_ENV": "development"},
        )
        assert template.id == "server"
        assert template.command == "npm run dev"
        assert template.env == {"NODE_ENV": "development"}

    def test_managed_session(self):
        session = ManagedSession(
            id="session-123",
            template_id="server",
            project_id="my-project",
            tab_id="tab-456",
        )
        assert session.attention_state == AttentionState.IDLE
        assert session.is_active is True
        assert session.is_managed is True
        assert session.last_output == ""

    def test_managed_session_serialization(self):
        session = ManagedSession(
            id="session-123",
            template_id="server",
            project_id="my-project",
            tab_id="tab-456",
            attention_state=AttentionState.WAITING,
        )
        data = model_to_dict(session)
        assert data["attention_state"] == "waiting"

        restored = model_from_dict(ManagedSession, data)
        assert restored.attention_state == AttentionState.WAITING

    def test_session_progress_creation(self):
        """Test creating a SessionProgress with all fields."""
        progress = SessionProgress(
            total_tasks=10,
            completed_tasks=5,
            current_task_id="2.1",
            current_task_title="Implement feature X",
            phase_id="2",
        )
        assert progress.total_tasks == 10
        assert progress.completed_tasks == 5
        assert progress.current_task_id == "2.1"
        assert progress.current_task_title == "Implement feature X"
        assert progress.phase_id == "2"

    def test_session_progress_defaults(self):
        """Test SessionProgress default values for optional fields."""
        progress = SessionProgress(
            total_tasks=5,
            completed_tasks=2,
        )
        assert progress.total_tasks == 5
        assert progress.completed_tasks == 2
        assert progress.current_task_id is None
        assert progress.current_task_title is None
        assert progress.phase_id is None

    def test_session_progress_serialization(self):
        """Test SessionProgress serializes to/from dict correctly."""
        progress = SessionProgress(
            total_tasks=8,
            completed_tasks=3,
            current_task_id="1.5",
            current_task_title="Build tests",
            phase_id="1",
        )
        data = model_to_dict(progress)
        assert data["total_tasks"] == 8
        assert data["completed_tasks"] == 3
        assert data["current_task_id"] == "1.5"
        assert data["current_task_title"] == "Build tests"
        assert data["phase_id"] == "1"

        restored = model_from_dict(SessionProgress, data)
        assert restored.total_tasks == 8
        assert restored.completed_tasks == 3
        assert restored.current_task_id == "1.5"
        assert restored.current_task_title == "Build tests"
        assert restored.phase_id == "1"

    def test_session_progress_none_values_serialization(self):
        """Test SessionProgress with None values serializes correctly."""
        progress = SessionProgress(
            total_tasks=10,
            completed_tasks=0,
            current_task_id=None,
            current_task_title=None,
            phase_id=None,
        )
        data = model_to_dict(progress)
        assert data["current_task_id"] is None
        assert data["current_task_title"] is None
        assert data["phase_id"] is None

        restored = model_from_dict(SessionProgress, data)
        assert restored.current_task_id is None
        assert restored.current_task_title is None
        assert restored.phase_id is None


class TestTaskModels:
    """Test task-related dataclasses."""

    def test_task_creation(self):
        task = Task(
            id="1.1",
            title="Implement feature X",
            status=TaskStatus.IN_PROGRESS,
            spec_ref="specs/feature.md",
            depends=["1.0"],
        )
        assert task.id == "1.1"
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.depends == ["1.0"]
        assert task.is_blocked is False

    def test_task_is_blocked(self):
        blocked_task = Task(
            id="1.2",
            title="Blocked task",
            status=TaskStatus.BLOCKED,
        )
        assert blocked_task.is_blocked is True

    def test_phase_completion_count(self):
        phase = Phase(
            id="1",
            title="Phase 1",
            tasks=[
                Task(id="1.1", title="Task 1", status=TaskStatus.COMPLETE),
                Task(id="1.2", title="Task 2", status=TaskStatus.IN_PROGRESS),
                Task(id="1.3", title="Task 3", status=TaskStatus.SKIPPED),
                Task(id="1.4", title="Task 4", status=TaskStatus.PENDING),
            ],
        )
        completed, total = phase.completion_count
        assert completed == 2  # COMPLETE + SKIPPED
        assert total == 4

    def test_phase_completion_percent(self):
        phase = Phase(
            id="1",
            title="Phase 1",
            tasks=[
                Task(id="1.1", title="Task 1", status=TaskStatus.COMPLETE),
                Task(id="1.2", title="Task 2", status=TaskStatus.PENDING),
            ],
        )
        assert phase.completion_percent == 50.0

    def test_phase_empty_completion(self):
        phase = Phase(id="1", title="Empty Phase", tasks=[])
        assert phase.completion_percent == 0.0

    def test_plan_all_tasks(self):
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[
                        Task(id="1.1", title="Task 1"),
                        Task(id="1.2", title="Task 2"),
                    ],
                ),
                Phase(
                    id="2",
                    title="Phase 2",
                    tasks=[Task(id="2.1", title="Task 3")],
                ),
            ],
        )
        all_tasks = plan.all_tasks
        assert len(all_tasks) == 3
        assert all_tasks[0].id == "1.1"
        assert all_tasks[2].id == "2.1"

    def test_plan_completion_summary(self):
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[
                        Task(id="1.1", title="T1", status=TaskStatus.COMPLETE),
                        Task(id="1.2", title="T2", status=TaskStatus.IN_PROGRESS),
                        Task(id="1.3", title="T3", status=TaskStatus.PENDING),
                    ],
                ),
            ],
        )
        summary = plan.completion_summary
        assert summary["complete"] == 1
        assert summary["in_progress"] == 1
        assert summary["awaiting_review"] == 0
        assert summary["pending"] == 1
        assert summary["skipped"] == 0
        assert summary["blocked"] == 0

    def test_plan_overall_progress(self):
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[
                        Task(id="1.1", title="T1", status=TaskStatus.COMPLETE),
                        Task(id="1.2", title="T2", status=TaskStatus.SKIPPED),
                        Task(id="1.3", title="T3", status=TaskStatus.PENDING),
                        Task(id="1.4", title="T4", status=TaskStatus.PENDING),
                    ],
                ),
            ],
        )
        assert plan.overall_progress == 50.0

    def test_plan_serialization(self):
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.COMPLETE)],
                ),
            ],
            overview="Test plan",
            success_criteria=["Tests pass"],
        )
        data = model_to_dict(plan)
        assert data["overview"] == "Test plan"
        assert data["phases"][0]["tasks"][0]["status"] == "complete"

        restored = model_from_dict(Plan, data)
        assert restored.overview == "Test plan"
        assert restored.phases[0].tasks[0].status == TaskStatus.COMPLETE

    def test_plan_get_task_by_id(self):
        """Test Plan.get_task_by_id() returns correct task."""
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[
                        Task(id="1.1", title="Task 1"),
                        Task(id="1.2", title="Task 2"),
                    ],
                ),
                Phase(
                    id="2",
                    title="Phase 2",
                    tasks=[Task(id="2.1", title="Task 3")],
                ),
            ],
        )
        task = plan.get_task_by_id("1.2")
        assert task is not None
        assert task.id == "1.2"
        assert task.title == "Task 2"

        task = plan.get_task_by_id("2.1")
        assert task is not None
        assert task.id == "2.1"
        assert task.title == "Task 3"

    def test_plan_get_task_by_id_not_found(self):
        """Test Plan.get_task_by_id() returns None for missing task."""
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1")],
                ),
            ],
        )
        assert plan.get_task_by_id("nonexistent") is None

    def test_plan_get_task_by_id_empty_plan(self):
        """Test Plan.get_task_by_id() on empty plan returns None."""
        plan = Plan()
        assert plan.get_task_by_id("1.1") is None

    def test_plan_task_cache_is_populated_on_first_access(self):
        """Test that task cache is built lazily on first access."""
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1")],
                ),
            ],
        )
        # Cache should be None initially (internal attribute)
        assert getattr(plan, "_task_map_cache", None) is None

        # First lookup should populate cache
        plan.get_task_by_id("1.1")
        cache = getattr(plan, "_task_map_cache", None)
        assert cache is not None
        assert "1.1" in cache

    def test_plan_invalidate_task_cache(self):
        """Test Plan.invalidate_task_cache() clears the cache."""
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1")],
                ),
            ],
        )
        # Populate cache
        plan.get_task_by_id("1.1")
        assert getattr(plan, "_task_map_cache", None) is not None

        # Invalidate cache
        plan.invalidate_task_cache()
        assert getattr(plan, "_task_map_cache", None) is None

        # Cache should be rebuilt on next access
        plan.get_task_by_id("1.1")
        assert getattr(plan, "_task_map_cache", None) is not None

    def test_plan_task_lookup_is_o1(self):
        """Test that task lookup uses O(1) dictionary access."""
        # Create a plan with many tasks
        tasks = [Task(id=f"1.{i}", title=f"Task {i}") for i in range(1000)]
        plan = Plan(
            phases=[
                Phase(id="1", title="Phase 1", tasks=tasks),
            ],
        )

        # Populate cache
        plan.get_task_by_id("1.500")

        # Verify the internal cache is a dict (O(1) lookup)
        cache = getattr(plan, "_task_map_cache", None)
        assert isinstance(cache, dict)
        assert len(cache) == 1000

        # Multiple lookups should be fast (using cached dict)
        for i in [0, 500, 999]:
            task = plan.get_task_by_id(f"1.{i}")
            assert task is not None
            assert task.id == f"1.{i}"

    def test_plan_task_cache_not_serialized(self):
        """Test that _task_map_cache is not included in serialization."""
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1")],
                ),
            ],
        )
        # Populate cache
        plan.get_task_by_id("1.1")

        data = model_to_dict(plan)
        # Cache field should not be in serialized data
        assert "_task_map_cache" not in data

        # Restored plan should work correctly
        restored = model_from_dict(Plan, data)
        assert restored.get_task_by_id("1.1") is not None


class TestTestPlanModels:
    """Test TEST_PLAN.md related dataclasses."""

    def test_test_status_enum_values(self):
        """Test TestStatus enum values match spec."""
        assert TestStatus.PENDING.value == "pending"
        assert TestStatus.IN_PROGRESS.value == "in_progress"
        assert TestStatus.PASSED.value == "passed"
        assert TestStatus.FAILED.value == "failed"

    def test_test_step_creation(self):
        """Test creating a TestStep with all fields."""
        step = TestStep(
            id="section-0-1",
            section="Functional Tests",
            description="Verify login works",
            status=TestStatus.PENDING,
            notes=None,
            line_number=5,
        )
        assert step.id == "section-0-1"
        assert step.section == "Functional Tests"
        assert step.description == "Verify login works"
        assert step.status == TestStatus.PENDING
        assert step.notes is None
        assert step.line_number == 5

    def test_test_step_with_failure_notes(self):
        """Test TestStep with failure notes."""
        step = TestStep(
            id="section-0-2",
            section="Integration",
            description="API responds correctly",
            status=TestStatus.FAILED,
            notes="Connection timeout after 5s",
            line_number=10,
        )
        assert step.status == TestStatus.FAILED
        assert step.notes == "Connection timeout after 5s"

    def test_test_step_defaults(self):
        """Test TestStep default values."""
        step = TestStep(
            id="test-1",
            section="Test Section",
            description="Test step",
        )
        assert step.status == TestStatus.PENDING
        assert step.notes is None
        assert step.line_number == 0

    def test_test_section_creation(self):
        """Test creating a TestSection."""
        section = TestSection(
            id="section-0",
            title="Functional Tests",
            steps=[
                TestStep(id="section-0-1", section="Functional Tests", description="Step 1"),
                TestStep(id="section-0-2", section="Functional Tests", description="Step 2"),
            ],
        )
        assert section.id == "section-0"
        assert section.title == "Functional Tests"
        assert len(section.steps) == 2

    def test_test_section_completion_count(self):
        """Test TestSection.completion_count property."""
        section = TestSection(
            id="section-0",
            title="Tests",
            steps=[
                TestStep(id="1", section="Tests", description="S1", status=TestStatus.PASSED),
                TestStep(id="2", section="Tests", description="S2", status=TestStatus.PASSED),
                TestStep(id="3", section="Tests", description="S3", status=TestStatus.PENDING),
                TestStep(id="4", section="Tests", description="S4", status=TestStatus.FAILED),
            ],
        )
        passed, total = section.completion_count
        assert passed == 2
        assert total == 4

    def test_test_section_completion_count_empty(self):
        """Test TestSection.completion_count with no steps."""
        section = TestSection(id="section-0", title="Empty")
        passed, total = section.completion_count
        assert passed == 0
        assert total == 0

    def test_test_section_has_failures(self):
        """Test TestSection.has_failures property."""
        section_with_failures = TestSection(
            id="section-0",
            title="Tests",
            steps=[
                TestStep(id="1", section="Tests", description="S1", status=TestStatus.PASSED),
                TestStep(id="2", section="Tests", description="S2", status=TestStatus.FAILED),
            ],
        )
        assert section_with_failures.has_failures is True

        section_no_failures = TestSection(
            id="section-1",
            title="Tests",
            steps=[
                TestStep(id="1", section="Tests", description="S1", status=TestStatus.PASSED),
                TestStep(id="2", section="Tests", description="S2", status=TestStatus.PENDING),
            ],
        )
        assert section_no_failures.has_failures is False

    def test_test_plan_creation(self):
        """Test creating a TestPlan."""
        plan = TestPlan(
            sections=[
                TestSection(
                    id="section-0",
                    title="Functional",
                    steps=[TestStep(id="1", section="Functional", description="S1")],
                ),
            ],
            title="My Test Plan",
            path="/path/to/TEST_PLAN.md",
        )
        assert plan.title == "My Test Plan"
        assert plan.path == "/path/to/TEST_PLAN.md"
        assert len(plan.sections) == 1

    def test_test_plan_defaults(self):
        """Test TestPlan default values."""
        plan = TestPlan()
        assert plan.sections == []
        assert plan.title == "Test Plan"
        assert plan.path == ""

    def test_test_plan_all_steps(self):
        """Test TestPlan.all_steps property."""
        plan = TestPlan(
            sections=[
                TestSection(
                    id="s0",
                    title="Sec1",
                    steps=[
                        TestStep(id="s0-1", section="Sec1", description="Step 1"),
                        TestStep(id="s0-2", section="Sec1", description="Step 2"),
                    ],
                ),
                TestSection(
                    id="s1",
                    title="Sec2",
                    steps=[
                        TestStep(id="s1-1", section="Sec2", description="Step 3"),
                    ],
                ),
            ],
        )
        all_steps = plan.all_steps
        assert len(all_steps) == 3
        assert all_steps[0].id == "s0-1"
        assert all_steps[1].id == "s0-2"
        assert all_steps[2].id == "s1-1"

    def test_test_plan_all_steps_empty(self):
        """Test TestPlan.all_steps with no sections."""
        plan = TestPlan()
        assert plan.all_steps == []

    def test_test_plan_completion_percentage(self):
        """Test TestPlan.completion_percentage property."""
        plan = TestPlan(
            sections=[
                TestSection(
                    id="s0",
                    title="Tests",
                    steps=[
                        TestStep(id="1", section="Tests", description="S1", status=TestStatus.PASSED),
                        TestStep(id="2", section="Tests", description="S2", status=TestStatus.PASSED),
                        TestStep(id="3", section="Tests", description="S3", status=TestStatus.PENDING),
                        TestStep(id="4", section="Tests", description="S4", status=TestStatus.FAILED),
                    ],
                ),
            ],
        )
        # 2 passed out of 4 = 50%
        assert plan.completion_percentage == 50.0

    def test_test_plan_completion_percentage_empty(self):
        """Test TestPlan.completion_percentage with no steps."""
        plan = TestPlan()
        assert plan.completion_percentage == 0.0

    def test_test_plan_completion_percentage_all_passed(self):
        """Test TestPlan.completion_percentage with all passed."""
        plan = TestPlan(
            sections=[
                TestSection(
                    id="s0",
                    title="Tests",
                    steps=[
                        TestStep(id="1", section="Tests", description="S1", status=TestStatus.PASSED),
                        TestStep(id="2", section="Tests", description="S2", status=TestStatus.PASSED),
                    ],
                ),
            ],
        )
        assert plan.completion_percentage == 100.0

    def test_test_plan_summary(self):
        """Test TestPlan.summary property."""
        plan = TestPlan(
            sections=[
                TestSection(
                    id="s0",
                    title="Tests",
                    steps=[
                        TestStep(id="1", section="Tests", description="S1", status=TestStatus.PASSED),
                        TestStep(id="2", section="Tests", description="S2", status=TestStatus.PENDING),
                        TestStep(id="3", section="Tests", description="S3", status=TestStatus.PENDING),
                        TestStep(id="4", section="Tests", description="S4", status=TestStatus.FAILED),
                        TestStep(id="5", section="Tests", description="S5", status=TestStatus.IN_PROGRESS),
                    ],
                ),
            ],
        )
        summary = plan.summary
        assert summary["passed"] == 1
        assert summary["pending"] == 2
        assert summary["failed"] == 1
        assert summary["in_progress"] == 1

    def test_test_plan_summary_empty(self):
        """Test TestPlan.summary with no steps."""
        plan = TestPlan()
        summary = plan.summary
        assert summary["passed"] == 0
        assert summary["pending"] == 0
        assert summary["failed"] == 0
        assert summary["in_progress"] == 0

    def test_test_step_serialization(self):
        """Test TestStep serializes to/from dict correctly."""
        step = TestStep(
            id="test-1",
            section="Section",
            description="Test step",
            status=TestStatus.FAILED,
            notes="Error message",
            line_number=15,
        )
        data = model_to_dict(step)
        assert data["id"] == "test-1"
        assert data["status"] == "failed"
        assert data["notes"] == "Error message"

        restored = model_from_dict(TestStep, data)
        assert restored.id == "test-1"
        assert restored.status == TestStatus.FAILED
        assert restored.notes == "Error message"

    def test_test_section_serialization(self):
        """Test TestSection serializes to/from dict correctly."""
        section = TestSection(
            id="section-0",
            title="Test Section",
            steps=[
                TestStep(id="s0-1", section="Test Section", description="Step 1", status=TestStatus.PASSED),
            ],
        )
        data = model_to_dict(section)
        assert data["id"] == "section-0"
        assert data["title"] == "Test Section"
        assert len(data["steps"]) == 1
        assert data["steps"][0]["status"] == "passed"

        restored = model_from_dict(TestSection, data)
        assert restored.id == "section-0"
        assert len(restored.steps) == 1
        assert restored.steps[0].status == TestStatus.PASSED

    def test_test_plan_serialization(self):
        """Test TestPlan serializes to/from dict correctly."""
        plan = TestPlan(
            sections=[
                TestSection(
                    id="section-0",
                    title="Functional Tests",
                    steps=[
                        TestStep(id="s0-1", section="Functional Tests", description="Step 1"),
                    ],
                ),
            ],
            title="My Test Plan",
            path="/path/to/TEST_PLAN.md",
        )
        data = model_to_dict(plan)
        assert data["title"] == "My Test Plan"
        assert data["path"] == "/path/to/TEST_PLAN.md"
        assert len(data["sections"]) == 1

        restored = model_from_dict(TestPlan, data)
        assert restored.title == "My Test Plan"
        assert restored.path == "/path/to/TEST_PLAN.md"
        assert len(restored.sections) == 1
        assert restored.sections[0].title == "Functional Tests"


class TestWorkflowModels:
    """Test workflow-related dataclasses."""

    def test_workflow_state_defaults(self):
        state = WorkflowState()
        assert state.stage == WorkflowStage.PLANNING
        assert state.prd_exists is False
        assert state.pr_url is None

    def test_infer_stage_planning(self):
        plan = Plan(phases=[])
        state = WorkflowState.infer_stage(plan, None)
        assert state.stage == WorkflowStage.PLANNING

    def test_infer_stage_execute(self):
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.PENDING)],
                ),
            ],
        )
        state = WorkflowState.infer_stage(plan, None)
        assert state.stage == WorkflowStage.EXECUTE

    def test_infer_stage_review(self):
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.COMPLETE)],
                ),
            ],
        )
        state = WorkflowState.infer_stage(plan, None)
        assert state.stage == WorkflowStage.REVIEW

    def test_infer_stage_pr(self):
        plan = Plan(phases=[])
        github_status = GitHubStatus(
            pr=PullRequest(
                number=123,
                title="Test PR",
                url="https://github.com/test/repo/pull/123",
                state="open",
                merged=False,
            ),
        )
        state = WorkflowState.infer_stage(plan, github_status)
        assert state.stage == WorkflowStage.PR
        assert state.pr_url == "https://github.com/test/repo/pull/123"

    def test_infer_stage_done(self):
        plan = Plan(phases=[])
        github_status = GitHubStatus(
            pr=PullRequest(
                number=123,
                title="Test PR",
                url="https://github.com/test/repo/pull/123",
                state="closed",
                merged=True,
            ),
        )
        state = WorkflowState.infer_stage(plan, github_status)
        assert state.stage == WorkflowStage.DONE
        assert state.pr_merged is True

    def test_infer_stage_with_prd_exists(self):
        """Test that prd_exists is stored in state."""
        plan = Plan(phases=[])
        state = WorkflowState.infer_stage(plan, None, prd_exists=True)
        assert state.prd_exists is True
        assert state.stage == WorkflowStage.PLANNING  # No tasks yet

    def test_infer_stage_with_prd_unneeded(self):
        """Test that prd_unneeded is stored in state."""
        plan = Plan(phases=[])
        state = WorkflowState.infer_stage(plan, None, prd_unneeded=True)
        assert state.prd_unneeded is True
        assert state.stage == WorkflowStage.PLANNING  # No tasks yet

    def test_infer_stage_execute_with_tasks(self):
        """Test EXECUTE stage when tasks exist."""
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[
                        Task(id="1.1", title="Task 1", status=TaskStatus.PENDING),
                        Task(id="1.2", title="Task 2", status=TaskStatus.IN_PROGRESS),
                    ],
                ),
            ],
        )
        state = WorkflowState.infer_stage(plan, None, prd_exists=True)
        assert state.stage == WorkflowStage.EXECUTE
        assert state.prd_exists is True

    def test_infer_stage_review_all_skipped(self):
        """Test REVIEW stage when all tasks are skipped."""
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[
                        Task(id="1.1", title="Task 1", status=TaskStatus.SKIPPED),
                        Task(id="1.2", title="Task 2", status=TaskStatus.SKIPPED),
                    ],
                ),
            ],
        )
        state = WorkflowState.infer_stage(plan, None)
        assert state.stage == WorkflowStage.REVIEW

    def test_infer_stage_review_mixed_complete_skipped(self):
        """Test REVIEW stage with mix of complete and skipped tasks."""
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[
                        Task(id="1.1", title="Task 1", status=TaskStatus.COMPLETE),
                        Task(id="1.2", title="Task 2", status=TaskStatus.SKIPPED),
                    ],
                ),
            ],
        )
        state = WorkflowState.infer_stage(plan, None)
        assert state.stage == WorkflowStage.REVIEW

    def test_infer_stage_pr_takes_priority(self):
        """Test that PR stage takes priority over review."""
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.COMPLETE)],
                ),
            ],
        )
        github_status = GitHubStatus(
            pr=PullRequest(
                number=123,
                title="Test PR",
                url="https://github.com/test/repo/pull/123",
                state="open",
                merged=False,
            ),
        )
        state = WorkflowState.infer_stage(plan, github_status)
        # PR takes priority even if all tasks complete
        assert state.stage == WorkflowStage.PR

    def test_infer_stage_done_takes_highest_priority(self):
        """Test that DONE stage takes highest priority when PR merged."""
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.IN_PROGRESS)],
                ),
            ],
        )
        github_status = GitHubStatus(
            pr=PullRequest(
                number=123,
                title="Test PR",
                url="https://github.com/test/repo/pull/123",
                state="closed",
                merged=True,
            ),
        )
        state = WorkflowState.infer_stage(plan, github_status)
        # DONE takes highest priority even if tasks incomplete
        assert state.stage == WorkflowStage.DONE


class TestConfigModels:
    """Test configuration-related dataclasses."""

    def test_health_check(self):
        check = HealthCheck(
            name="API Health",
            url="http://localhost:3000/health",
            method="GET",
            expected_status=200,
            timeout_seconds=5.0,
            interval_seconds=10.0,
        )
        assert check.name == "API Health"
        assert check.method == "GET"

    def test_auto_mode_config(self):
        config = AutoModeConfig(
            enabled=True,
            stage_commands={"execute": "claude /plan"},
            auto_advance=True,
            require_confirmation=False,
        )
        assert config.enabled is True
        assert config.stage_commands["execute"] == "claude /plan"

    def test_app_settings_defaults(self):
        settings = AppSettings()
        assert settings.default_ide == "vscode"
        assert settings.default_shell == "zsh"
        assert settings.polling_interval_ms == 500
        assert settings.notification_enabled is True
        assert settings.github_refresh_seconds == 60
        assert settings.health_check_interval_seconds == 10.0
        assert settings.dangerously_skip_permissions is False

    def test_app_settings_dangerously_skip_permissions(self):
        """Test dangerously_skip_permissions setting."""
        settings = AppSettings(dangerously_skip_permissions=True)
        assert settings.dangerously_skip_permissions is True

    def test_app_settings_dangerously_skip_permissions_serialization(self):
        """Test that dangerously_skip_permissions persists to/from JSON correctly."""
        settings = AppSettings(dangerously_skip_permissions=True)
        data = model_to_dict(settings)
        assert data["dangerously_skip_permissions"] is True

        restored = model_from_dict(AppSettings, data)
        assert restored.dangerously_skip_permissions is True


class TestWindowLayoutModels:
    """Test window layout dataclasses."""

    def test_session_layout(self):
        layout = SessionLayout(
            template_id="server",
            split="horizontal",
            size_percent=70,
        )
        assert layout.template_id == "server"
        assert layout.split == "horizontal"
        assert layout.size_percent == 70

    def test_tab_layout(self):
        tab = TabLayout(
            name="Dev Tab",
            sessions=[
                SessionLayout(template_id="server"),
                SessionLayout(template_id="logs", split="vertical"),
            ],
        )
        assert tab.name == "Dev Tab"
        assert len(tab.sessions) == 2

    def test_window_layout(self):
        window = WindowLayout(
            id="dev-layout",
            name="Development",
            tabs=[
                TabLayout(
                    name="Main",
                    sessions=[SessionLayout(template_id="editor")],
                ),
            ],
        )
        assert window.id == "dev-layout"
        assert len(window.tabs) == 1


class TestGitHubModels:
    """Test GitHub-related dataclasses."""

    def test_pull_request(self):
        pr = PullRequest(
            number=42,
            title="Add feature",
            url="https://github.com/test/repo/pull/42",
            state="open",
            draft=True,
            comments=3,
            reviews_pending=1,
        )
        assert pr.number == 42
        assert pr.draft is True
        assert pr.merged is False

    def test_github_status(self):
        status = GitHubStatus(
            available=True,
            current_branch="feature/test",
            default_branch="main",
            ahead=2,
            behind=1,
        )
        assert status.available is True
        assert status.current_branch == "feature/test"
        assert status.ahead == 2


class TestAppConfig:
    """Test AppConfig serialization."""

    def test_empty_config(self):
        config = AppConfig()
        assert config.settings.default_ide == "vscode"
        assert config.projects == []
        assert config.templates == []

    def test_config_with_data(self):
        config = AppConfig(
            settings=AppSettings(default_ide="cursor"),
            projects=[
                Project(id="p1", name="Project 1", path="/path/1"),
            ],
            session_templates=[
                SessionTemplate(id="dev", name="Dev Server", command="npm run dev"),
            ],
        )
        assert config.settings.default_ide == "cursor"
        assert len(config.projects) == 1
        assert len(config.session_templates) == 1

    def test_config_serialization_roundtrip(self):
        config = AppConfig(
            settings=AppSettings(
                default_ide="cursor",
                polling_interval_ms=250,
            ),
            projects=[
                Project(id="p1", name="Project 1", path="/path/1"),
            ],
            templates=[
                ProjectTemplate(
                    id="t1",
                    name="Template 1",
                    description="Test template",
                    initial_sessions=["dev"],
                ),
            ],
            session_templates=[
                SessionTemplate(
                    id="dev",
                    name="Dev Server",
                    command="npm run dev",
                    env={"PORT": "3000"},
                ),
            ],
            window_layouts=[
                WindowLayout(
                    id="default",
                    name="Default Layout",
                    tabs=[
                        TabLayout(
                            name="Main",
                            sessions=[SessionLayout(template_id="dev")],
                        ),
                    ],
                ),
            ],
        )

        data = model_to_dict(config)
        restored = load_config_from_dict(data)

        assert restored.settings.default_ide == "cursor"
        assert restored.settings.polling_interval_ms == 250
        assert len(restored.projects) == 1
        assert restored.projects[0].id == "p1"
        assert len(restored.templates) == 1
        assert restored.session_templates[0].env == {"PORT": "3000"}
        assert len(restored.window_layouts) == 1


class TestFileSerialization:
    """Test saving and loading config from files."""

    def test_save_and_load_config(self):
        config = AppConfig(
            settings=AppSettings(default_ide="vim"),
            projects=[
                Project(id="test", name="Test", path="/test"),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            save_config(config, config_path)

            # Verify file exists and is valid JSON
            assert config_path.exists()
            with open(config_path) as f:
                data = json.load(f)
            assert data["settings"]["default_ide"] == "vim"

            # Load and verify
            loaded = load_config(config_path)
            assert loaded.settings.default_ide == "vim"
            assert len(loaded.projects) == 1
            assert loaded.projects[0].id == "test"

    def test_save_creates_parent_directories(self):
        config = AppConfig()

        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = Path(tmpdir) / "nested" / "dir" / "config.json"
            save_config(config, nested_path)
            assert nested_path.exists()

    def test_datetime_serialization(self):
        """Test that datetime fields serialize correctly."""
        now = datetime.now()
        session = ManagedSession(
            id="session-123",
            template_id="server",
            project_id="my-project",
            tab_id="tab-456",
            spawned_at=now,
            last_activity=now,
        )

        data = model_to_dict(session)
        # datetime should be converted to ISO format string by json encoder
        assert "spawned_at" in data

        # Verify JSON encoding works with our datetime encoder
        json_str = json.dumps(data, default=lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x))
        parsed = json.loads(json_str)
        assert "spawned_at" in parsed


class TestProjectTemplate:
    """Test ProjectTemplate dataclass."""

    def test_template_creation(self):
        template = ProjectTemplate(
            id="web-app",
            name="Web Application",
            description="Standard web app setup",
            setup_script="./setup.sh",
            initial_sessions=["dev-server", "tests"],
            default_plan="# PLAN.md\n\n## Tasks\n",
            files={"README.md": "# My Project"},
            required_fields=["name", "description"],
        )
        assert template.id == "web-app"
        assert len(template.initial_sessions) == 2
        assert "README.md" in template.files
        assert len(template.required_fields) == 2

    def test_template_serialization(self):
        template = ProjectTemplate(
            id="test",
            name="Test",
            files={"a.txt": "content"},
        )
        data = model_to_dict(template)
        restored = model_from_dict(ProjectTemplate, data)
        assert restored.id == "test"
        assert restored.files == {"a.txt": "content"}
