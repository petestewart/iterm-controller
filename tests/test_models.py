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
    SessionLayout,
    SessionTemplate,
    TabLayout,
    Task,
    TaskStatus,
    WindowLayout,
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

    def test_attention_state_values(self):
        assert AttentionState.WAITING.value == "waiting"
        assert AttentionState.WORKING.value == "working"
        assert AttentionState.IDLE.value == "idle"

    def test_task_status_values(self):
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
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
        assert project.config_path is None
        assert project.template_id is None
        assert project.is_open is False
        assert project.sessions == []

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
            health_check="frontend-health",
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
            service="api-server",
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
