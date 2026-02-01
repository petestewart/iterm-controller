"""Tests for workflow stage automation."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from iterm_controller.auto_mode import (
    AutoModeController,
    StageTransition,
    WorkflowStageInferrer,
    create_controller_for_project,
)
from iterm_controller.models import (
    AutoModeConfig,
    GitHubStatus,
    Phase,
    Plan,
    PullRequest,
    Task,
    TaskStatus,
    WorkflowStage,
)


class TestWorkflowStageInferrer:
    """Tests for WorkflowStageInferrer class."""

    def test_check_prd_exists_when_file_exists(self, tmp_path):
        """Test that check_prd_exists returns True when PRD.md exists."""
        prd_path = tmp_path / "PRD.md"
        prd_path.write_text("# Product Requirements")

        inferrer = WorkflowStageInferrer(tmp_path)
        assert inferrer.check_prd_exists() is True

    def test_check_prd_exists_when_file_missing(self, tmp_path):
        """Test that check_prd_exists returns False when PRD.md missing."""
        inferrer = WorkflowStageInferrer(tmp_path)
        assert inferrer.check_prd_exists() is False

    def test_infer_stage_planning_no_tasks(self, tmp_path):
        """Test inferring PLANNING stage when no tasks exist."""
        inferrer = WorkflowStageInferrer(tmp_path)
        plan = Plan(phases=[])

        state = inferrer.infer_stage(plan, None)
        assert state.stage == WorkflowStage.PLANNING

    def test_infer_stage_execute_with_tasks(self, tmp_path):
        """Test inferring EXECUTE stage when tasks exist."""
        inferrer = WorkflowStageInferrer(tmp_path)
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.PENDING)],
                )
            ]
        )

        state = inferrer.infer_stage(plan, None)
        assert state.stage == WorkflowStage.EXECUTE

    def test_infer_stage_review_when_all_done(self, tmp_path):
        """Test inferring REVIEW stage when all tasks complete."""
        inferrer = WorkflowStageInferrer(tmp_path)
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.COMPLETE)],
                )
            ]
        )

        state = inferrer.infer_stage(plan, None)
        assert state.stage == WorkflowStage.REVIEW

    def test_infer_stage_prd_exists_sets_flag(self, tmp_path):
        """Test that prd_exists flag is set when file exists."""
        prd_path = tmp_path / "PRD.md"
        prd_path.write_text("# Product Requirements")

        inferrer = WorkflowStageInferrer(tmp_path)
        plan = Plan(phases=[])

        state = inferrer.infer_stage(plan, None)
        assert state.prd_exists is True

    def test_infer_stage_prd_unneeded_sets_flag(self, tmp_path):
        """Test that prd_unneeded flag is passed through."""
        inferrer = WorkflowStageInferrer(tmp_path)
        plan = Plan(phases=[])

        state = inferrer.infer_stage(plan, None, prd_unneeded=True)
        assert state.prd_unneeded is True

    def test_infer_stage_pr_with_github_status(self, tmp_path):
        """Test inferring PR stage when PR exists."""
        inferrer = WorkflowStageInferrer(tmp_path)
        plan = Plan(phases=[])
        github_status = GitHubStatus(
            pr=PullRequest(
                number=42,
                title="Feature PR",
                url="https://github.com/test/repo/pull/42",
                state="open",
                merged=False,
            )
        )

        state = inferrer.infer_stage(plan, github_status)
        assert state.stage == WorkflowStage.PR
        assert state.pr_url == "https://github.com/test/repo/pull/42"

    def test_infer_stage_done_when_pr_merged(self, tmp_path):
        """Test inferring DONE stage when PR is merged."""
        inferrer = WorkflowStageInferrer(tmp_path)
        plan = Plan(phases=[])
        github_status = GitHubStatus(
            pr=PullRequest(
                number=42,
                title="Feature PR",
                url="https://github.com/test/repo/pull/42",
                state="closed",
                merged=True,
            )
        )

        state = inferrer.infer_stage(plan, github_status)
        assert state.stage == WorkflowStage.DONE
        assert state.pr_merged is True


class TestAutoModeController:
    """Tests for AutoModeController class."""

    def test_controller_init(self, tmp_path):
        """Test controller initialization."""
        config = AutoModeConfig(enabled=True)
        controller = AutoModeController(
            config=config,
            project_id="test-project",
            project_path=tmp_path,
        )

        assert controller.project_id == "test-project"
        assert controller.config.enabled is True
        assert controller.current_stage is None
        assert controller.current_state is None

    def test_set_prd_unneeded(self, tmp_path):
        """Test setting PRD as unneeded."""
        config = AutoModeConfig()
        controller = AutoModeController(
            config=config,
            project_id="test-project",
            project_path=tmp_path,
        )

        controller.set_prd_unneeded(True)
        assert controller._prd_unneeded is True

    def test_evaluate_stage_sync_updates_state(self, tmp_path):
        """Test synchronous stage evaluation updates internal state."""
        config = AutoModeConfig()
        controller = AutoModeController(
            config=config,
            project_id="test-project",
            project_path=tmp_path,
        )

        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.PENDING)],
                )
            ]
        )

        state = controller.evaluate_stage_sync(plan)
        assert state.stage == WorkflowStage.EXECUTE
        assert controller.current_stage == WorkflowStage.EXECUTE
        assert controller.current_state is not None

    def test_evaluate_stage_sync_triggers_callback_on_change(self, tmp_path):
        """Test that stage change callback is triggered on transition."""
        config = AutoModeConfig()
        transitions = []

        def on_change(transition: StageTransition) -> None:
            transitions.append(transition)

        controller = AutoModeController(
            config=config,
            project_id="test-project",
            project_path=tmp_path,
            on_stage_change=on_change,
        )

        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.PENDING)],
                )
            ]
        )

        controller.evaluate_stage_sync(plan)

        assert len(transitions) == 1
        assert transitions[0].old_stage is None
        assert transitions[0].new_stage == WorkflowStage.EXECUTE
        assert transitions[0].project_id == "test-project"

    def test_evaluate_stage_sync_no_callback_when_same_stage(self, tmp_path):
        """Test that callback is not triggered when stage unchanged."""
        config = AutoModeConfig()
        transitions = []

        def on_change(transition: StageTransition) -> None:
            transitions.append(transition)

        controller = AutoModeController(
            config=config,
            project_id="test-project",
            project_path=tmp_path,
            on_stage_change=on_change,
        )

        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.PENDING)],
                )
            ]
        )

        # First evaluation triggers callback
        controller.evaluate_stage_sync(plan)
        assert len(transitions) == 1

        # Second evaluation with same plan should not trigger
        controller.evaluate_stage_sync(plan)
        assert len(transitions) == 1

    def test_evaluate_stage_sync_detects_progression(self, tmp_path):
        """Test detection of stage progression."""
        config = AutoModeConfig()
        transitions = []

        def on_change(transition: StageTransition) -> None:
            transitions.append(transition)

        controller = AutoModeController(
            config=config,
            project_id="test-project",
            project_path=tmp_path,
            on_stage_change=on_change,
        )

        # First: Execute stage
        plan1 = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.PENDING)],
                )
            ]
        )
        controller.evaluate_stage_sync(plan1)

        # Second: Review stage (all tasks complete)
        plan2 = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.COMPLETE)],
                )
            ]
        )
        controller.evaluate_stage_sync(plan2)

        assert len(transitions) == 2
        assert transitions[0].new_stage == WorkflowStage.EXECUTE
        assert transitions[1].old_stage == WorkflowStage.EXECUTE
        assert transitions[1].new_stage == WorkflowStage.REVIEW

    @pytest.mark.asyncio
    async def test_evaluate_stage_fetches_github_status(self, tmp_path):
        """Test async stage evaluation fetches GitHub status."""
        config = AutoModeConfig()
        mock_github = MagicMock()
        mock_github.get_status = AsyncMock(
            return_value=GitHubStatus(
                pr=PullRequest(
                    number=42,
                    title="Feature PR",
                    url="https://github.com/test/repo/pull/42",
                    state="open",
                    merged=False,
                )
            )
        )

        controller = AutoModeController(
            config=config,
            project_id="test-project",
            project_path=tmp_path,
            github=mock_github,
        )

        plan = Plan(phases=[])
        state = await controller.evaluate_stage(plan)

        mock_github.get_status.assert_called_once_with(str(tmp_path))
        assert state.stage == WorkflowStage.PR

    @pytest.mark.asyncio
    async def test_evaluate_stage_uses_provided_github_status(self, tmp_path):
        """Test that provided GitHub status is used instead of fetching."""
        config = AutoModeConfig()
        mock_github = MagicMock()
        mock_github.get_status = AsyncMock()

        controller = AutoModeController(
            config=config,
            project_id="test-project",
            project_path=tmp_path,
            github=mock_github,
        )

        plan = Plan(phases=[])
        github_status = GitHubStatus(
            pr=PullRequest(
                number=42,
                title="Feature PR",
                url="https://github.com/test/repo/pull/42",
                state="closed",
                merged=True,
            )
        )

        state = await controller.evaluate_stage(plan, github_status)

        mock_github.get_status.assert_not_called()
        assert state.stage == WorkflowStage.DONE

    def test_get_stage_command(self, tmp_path):
        """Test getting stage command from config."""
        config = AutoModeConfig(
            enabled=True,
            stage_commands={
                "planning": "claude /prd",
                "execute": "claude /plan",
                "review": "claude /review",
            },
        )

        controller = AutoModeController(
            config=config,
            project_id="test-project",
            project_path=tmp_path,
        )

        assert controller.get_stage_command(WorkflowStage.PLANNING) == "claude /prd"
        assert controller.get_stage_command(WorkflowStage.EXECUTE) == "claude /plan"
        assert controller.get_stage_command(WorkflowStage.PR) is None

    def test_should_auto_advance(self, tmp_path):
        """Test should_auto_advance check."""
        config = AutoModeConfig(enabled=True, auto_advance=True)
        controller = AutoModeController(
            config=config,
            project_id="test-project",
            project_path=tmp_path,
        )
        assert controller.should_auto_advance() is True

        config2 = AutoModeConfig(enabled=False, auto_advance=True)
        controller2 = AutoModeController(
            config=config2,
            project_id="test-project",
            project_path=tmp_path,
        )
        assert controller2.should_auto_advance() is False

    def test_requires_confirmation(self, tmp_path):
        """Test requires_confirmation check."""
        config = AutoModeConfig(require_confirmation=True)
        controller = AutoModeController(
            config=config,
            project_id="test-project",
            project_path=tmp_path,
        )
        assert controller.requires_confirmation() is True

        config2 = AutoModeConfig(require_confirmation=False)
        controller2 = AutoModeController(
            config=config2,
            project_id="test-project",
            project_path=tmp_path,
        )
        assert controller2.requires_confirmation() is False


class TestStageTransition:
    """Tests for StageTransition dataclass."""

    def test_stage_transition_creation(self):
        """Test creating a StageTransition."""
        transition = StageTransition(
            old_stage=WorkflowStage.EXECUTE,
            new_stage=WorkflowStage.REVIEW,
            project_id="my-project",
        )

        assert transition.old_stage == WorkflowStage.EXECUTE
        assert transition.new_stage == WorkflowStage.REVIEW
        assert transition.project_id == "my-project"

    def test_stage_transition_with_none_old_stage(self):
        """Test StageTransition with None old stage (initial transition)."""
        transition = StageTransition(
            old_stage=None,
            new_stage=WorkflowStage.PLANNING,
            project_id="my-project",
        )

        assert transition.old_stage is None
        assert transition.new_stage == WorkflowStage.PLANNING


class TestCreateControllerForProject:
    """Tests for create_controller_for_project factory function."""

    def test_create_controller(self, tmp_path):
        """Test factory function creates controller correctly."""
        config = AutoModeConfig(enabled=True)

        controller = create_controller_for_project(
            project_id="test-project",
            project_path=tmp_path,
            config=config,
        )

        assert controller.project_id == "test-project"
        assert controller.project_path == tmp_path
        assert controller.config.enabled is True

    def test_create_controller_with_github(self, tmp_path):
        """Test factory function with GitHub integration."""
        config = AutoModeConfig()
        mock_github = MagicMock()

        controller = create_controller_for_project(
            project_id="test-project",
            project_path=tmp_path,
            config=config,
            github=mock_github,
        )

        assert controller.github is mock_github

    def test_create_controller_with_callback(self, tmp_path):
        """Test factory function with stage change callback."""
        config = AutoModeConfig()
        transitions = []

        def on_change(transition: StageTransition) -> None:
            transitions.append(transition)

        controller = create_controller_for_project(
            project_id="test-project",
            project_path=tmp_path,
            config=config,
            on_stage_change=on_change,
        )

        assert controller.on_stage_change is on_change
