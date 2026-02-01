"""Workflow stage automation.

This module provides automatic workflow stage inference and monitoring.
It integrates with the plan watcher to detect stage transitions and
can automatically execute stage commands when advancing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable

from .models import (
    AutoModeConfig,
    GitHubStatus,
    Plan,
    WorkflowStage,
    WorkflowState,
)

if TYPE_CHECKING:
    from textual.app import App

    from .github import GitHubIntegration
    from .iterm_api import ItermController
    from .state import AppState

logger = logging.getLogger(__name__)


@dataclass
class StageTransition:
    """Represents a workflow stage transition."""

    old_stage: WorkflowStage | None
    new_stage: WorkflowStage
    project_id: str


class WorkflowStageInferrer:
    """Infers workflow stage from project state.

    This class centralizes the logic for determining the current
    workflow stage based on:
    - PLAN.md task completion
    - PRD.md existence
    - GitHub PR status
    """

    def __init__(self, project_path: str | Path) -> None:
        """Initialize the inferrer.

        Args:
            project_path: Path to the project directory.
        """
        self.project_path = Path(project_path)

    def check_prd_exists(self) -> bool:
        """Check if PRD file exists for the project.

        Returns:
            True if PRD.md exists in the project directory.
        """
        prd_path = self.project_path / "PRD.md"
        return prd_path.exists()

    def infer_stage(
        self,
        plan: Plan,
        github_status: GitHubStatus | None,
        prd_unneeded: bool = False,
    ) -> WorkflowState:
        """Infer the current workflow stage.

        Args:
            plan: The parsed PLAN.md document.
            github_status: Current GitHub status, if available.
            prd_unneeded: Whether PRD has been marked as unnecessary.

        Returns:
            WorkflowState with inferred stage.
        """
        prd_exists = self.check_prd_exists()
        return WorkflowState.infer_stage(
            plan=plan,
            github_status=github_status,
            prd_exists=prd_exists,
            prd_unneeded=prd_unneeded,
        )


class AutoModeController:
    """Controls automatic workflow stage monitoring and advancement.

    This controller:
    1. Monitors PLAN.md changes via the state event system
    2. Re-evaluates the workflow stage when changes occur
    3. Tracks stage transitions for UI updates
    4. Optionally triggers stage commands when advancing

    Usage:
        controller = AutoModeController(
            config=config.auto_mode,
            project_id="my-project",
            project_path="/path/to/project",
        )

        # Connect to state for event handling
        state.subscribe(StateEvent.PLAN_RELOADED, controller.on_plan_reloaded)

        # Check current stage
        stage = controller.current_stage
    """

    def __init__(
        self,
        config: AutoModeConfig,
        project_id: str,
        project_path: str | Path,
        github: GitHubIntegration | None = None,
        on_stage_change: Callable[[StageTransition], None] | None = None,
    ) -> None:
        """Initialize the auto mode controller.

        Args:
            config: Auto mode configuration.
            project_id: ID of the project being monitored.
            project_path: Path to the project directory.
            github: GitHub integration for PR status checks.
            on_stage_change: Callback invoked when stage changes.
        """
        self.config = config
        self.project_id = project_id
        self.project_path = Path(project_path)
        self.github = github
        self.on_stage_change = on_stage_change

        self._inferrer = WorkflowStageInferrer(project_path)
        self._current_state: WorkflowState | None = None
        self._prd_unneeded: bool = False

    @property
    def current_stage(self) -> WorkflowStage | None:
        """Get the current workflow stage."""
        return self._current_state.stage if self._current_state else None

    @property
    def current_state(self) -> WorkflowState | None:
        """Get the current workflow state."""
        return self._current_state

    def set_prd_unneeded(self, unneeded: bool) -> None:
        """Mark the PRD as unneeded.

        Args:
            unneeded: Whether the PRD is not needed for this project.
        """
        self._prd_unneeded = unneeded

    async def evaluate_stage(
        self,
        plan: Plan,
        github_status: GitHubStatus | None = None,
    ) -> WorkflowState:
        """Evaluate and update the workflow stage.

        This method:
        1. Infers the new stage from current state
        2. Detects stage transitions
        3. Updates internal state
        4. Calls the stage change callback if transition occurred

        Args:
            plan: The current PLAN.md document.
            github_status: Optional GitHub status. If not provided and
                          github integration is available, will fetch it.

        Returns:
            The updated WorkflowState.
        """
        # Fetch GitHub status if needed and available
        if github_status is None and self.github is not None:
            github_status = await self.github.get_status(str(self.project_path))

        # Infer the new stage
        new_state = self._inferrer.infer_stage(
            plan=plan,
            github_status=github_status,
            prd_unneeded=self._prd_unneeded,
        )

        # Check for transition
        old_stage = self._current_state.stage if self._current_state else None
        if old_stage != new_state.stage:
            transition = StageTransition(
                old_stage=old_stage,
                new_stage=new_state.stage,
                project_id=self.project_id,
            )

            # Update state before callback
            self._current_state = new_state

            # Notify listener
            if self.on_stage_change:
                self.on_stage_change(transition)
        else:
            self._current_state = new_state

        return new_state

    def evaluate_stage_sync(
        self,
        plan: Plan,
        github_status: GitHubStatus | None = None,
    ) -> WorkflowState:
        """Synchronously evaluate the workflow stage.

        This is a non-async version for use when GitHub status is
        already available or not needed.

        Args:
            plan: The current PLAN.md document.
            github_status: Optional GitHub status.

        Returns:
            The updated WorkflowState.
        """
        # Infer the new stage
        new_state = self._inferrer.infer_stage(
            plan=plan,
            github_status=github_status,
            prd_unneeded=self._prd_unneeded,
        )

        # Check for transition
        old_stage = self._current_state.stage if self._current_state else None
        if old_stage != new_state.stage:
            transition = StageTransition(
                old_stage=old_stage,
                new_stage=new_state.stage,
                project_id=self.project_id,
            )

            # Update state before callback
            self._current_state = new_state

            # Notify listener
            if self.on_stage_change:
                self.on_stage_change(transition)
        else:
            self._current_state = new_state

        return new_state

    def get_stage_command(self, stage: WorkflowStage) -> str | None:
        """Get the command configured for a stage.

        Args:
            stage: The workflow stage.

        Returns:
            The command string if configured, None otherwise.
        """
        return self.config.stage_commands.get(stage.value)

    def should_auto_advance(self) -> bool:
        """Check if auto-advance is enabled.

        Returns:
            True if auto_mode is enabled and auto_advance is True.
        """
        return self.config.enabled and self.config.auto_advance

    def requires_confirmation(self) -> bool:
        """Check if stage advance requires confirmation.

        Returns:
            True if confirmation is required before running stage commands.
        """
        return self.config.require_confirmation


def create_controller_for_project(
    project_id: str,
    project_path: str | Path,
    config: AutoModeConfig,
    github: GitHubIntegration | None = None,
    on_stage_change: Callable[[StageTransition], None] | None = None,
) -> AutoModeController:
    """Factory function to create an AutoModeController for a project.

    Args:
        project_id: ID of the project.
        project_path: Path to the project directory.
        config: Auto mode configuration.
        github: Optional GitHub integration.
        on_stage_change: Optional callback for stage transitions.

    Returns:
        Configured AutoModeController instance.
    """
    return AutoModeController(
        config=config,
        project_id=project_id,
        project_path=project_path,
        github=github,
        on_stage_change=on_stage_change,
    )


# =============================================================================
# Auto Advance Handler
# =============================================================================


@dataclass
class CommandExecutionResult:
    """Result of executing a stage command."""

    success: bool
    command: str
    session_id: str | None = None
    error: str | None = None


class AutoAdvanceHandler:
    """Handles automatic stage advancement with command execution.

    This handler:
    1. Receives stage transition notifications
    2. Optionally shows confirmation modal
    3. Executes stage commands in iTerm2 sessions

    Usage:
        handler = AutoAdvanceHandler(
            config=config.auto_mode,
            iterm=iterm_controller,
            app=textual_app,
        )

        # Connect to controller
        controller = AutoModeController(
            config=config.auto_mode,
            project_id="my-project",
            project_path="/path/to/project",
            on_stage_change=handler.on_stage_transition,
        )
    """

    def __init__(
        self,
        config: AutoModeConfig,
        iterm: ItermController | None = None,
        app: App | None = None,
    ) -> None:
        """Initialize the auto advance handler.

        Args:
            config: Auto mode configuration.
            iterm: iTerm controller for session access.
            app: Textual app for modal display.
        """
        self.config = config
        self.iterm = iterm
        self.app = app
        self._pending_advance: StageTransition | None = None

    async def handle_stage_change(
        self,
        transition: StageTransition,
    ) -> CommandExecutionResult | None:
        """Handle a workflow stage transition.

        If auto-advance is enabled and there's a command configured for the
        new stage, this method will:
        1. Show confirmation modal (if required)
        2. Execute the stage command in the designated session

        Args:
            transition: The stage transition that occurred.

        Returns:
            CommandExecutionResult if a command was executed, None otherwise.
        """
        if not self.config.enabled:
            logger.debug("Auto mode disabled, skipping auto advance")
            return None

        if not self.config.auto_advance:
            logger.debug("Auto advance disabled, skipping command execution")
            return None

        command = self.config.stage_commands.get(transition.new_stage.value)
        if not command:
            logger.debug(
                f"No command configured for stage {transition.new_stage.value}"
            )
            return None

        # Check for confirmation
        if self.config.require_confirmation:
            confirmed = await self._show_confirmation_modal(
                transition.new_stage, command
            )
            if not confirmed:
                logger.info(
                    f"User declined stage advancement to {transition.new_stage.value}"
                )
                return CommandExecutionResult(
                    success=False,
                    command=command,
                    error="User declined confirmation",
                )

        # Execute the command
        return await self._execute_command(command)

    async def _show_confirmation_modal(
        self,
        stage: WorkflowStage,
        command: str,
    ) -> bool:
        """Show confirmation modal for stage advancement.

        Args:
            stage: The stage we're advancing to.
            command: The command that will be executed.

        Returns:
            True if user confirmed, False otherwise.
        """
        if self.app is None:
            logger.warning("No app available for confirmation modal, skipping")
            return True  # Proceed without confirmation

        # Import here to avoid circular imports
        from .screens.modals import StageAdvanceModal

        modal = StageAdvanceModal(stage, command)
        result = await self.app.push_screen_wait(modal)
        return bool(result)

    async def _execute_command(
        self,
        command: str,
    ) -> CommandExecutionResult:
        """Execute a stage command in the appropriate session.

        The command is sent to:
        1. The designated session (if configured and exists)
        2. The current session in the current terminal window (fallback)

        Args:
            command: The command to execute.

        Returns:
            CommandExecutionResult with execution status.
        """
        if self.iterm is None or not self.iterm.is_connected:
            logger.warning("iTerm not connected, cannot execute command")
            return CommandExecutionResult(
                success=False,
                command=command,
                error="iTerm not connected",
            )

        if self.iterm.app is None:
            logger.warning("iTerm app not available, cannot execute command")
            return CommandExecutionResult(
                success=False,
                command=command,
                error="iTerm app not available",
            )

        try:
            session = None
            session_id = None

            # Try designated session first
            if self.config.designated_session:
                session = await self.iterm.app.async_get_session_by_id(
                    self.config.designated_session
                )
                if session:
                    session_id = self.config.designated_session
                    logger.debug(
                        f"Using designated session {self.config.designated_session}"
                    )
                else:
                    logger.warning(
                        f"Designated session {self.config.designated_session} not found"
                    )

            # Fall back to current session
            if session is None:
                window = self.iterm.app.current_terminal_window
                if window and window.current_tab:
                    session = window.current_tab.current_session
                    if session:
                        session_id = session.session_id
                        logger.debug(f"Using current session {session_id}")

            if session is None:
                logger.warning("No session available for command execution")
                return CommandExecutionResult(
                    success=False,
                    command=command,
                    error="No session available",
                )

            # Send the command with newline
            await session.async_send_text(command + "\n")
            logger.info(
                f"Executed stage command in session {session_id}: {command}"
            )

            return CommandExecutionResult(
                success=True,
                command=command,
                session_id=session_id,
            )

        except Exception as e:
            logger.error(f"Failed to execute stage command: {e}")
            return CommandExecutionResult(
                success=False,
                command=command,
                error=str(e),
            )

    def create_transition_handler(
        self,
    ) -> Callable[[StageTransition], Awaitable[CommandExecutionResult | None]]:
        """Create an async handler for stage transitions.

        This is a convenience method that returns a callable suitable for
        use as the on_stage_change callback.

        Returns:
            Async callable that handles stage transitions.
        """
        return self.handle_stage_change


# =============================================================================
# Auto Mode Integration
# =============================================================================


class AutoModeIntegration:
    """Integrates auto mode controller with advance handler.

    This class ties together the stage inference (controller) with
    the command execution (handler) for a complete auto mode experience.

    Usage:
        integration = AutoModeIntegration(
            config=config.auto_mode,
            project_id="my-project",
            project_path="/path/to/project",
            iterm=iterm_controller,
            app=textual_app,
            github=github_integration,
        )

        # Evaluate on plan change
        await integration.on_plan_change(plan)
    """

    def __init__(
        self,
        config: AutoModeConfig,
        project_id: str,
        project_path: str | Path,
        iterm: ItermController | None = None,
        app: App | None = None,
        github: GitHubIntegration | None = None,
    ) -> None:
        """Initialize the integration.

        Args:
            config: Auto mode configuration.
            project_id: ID of the project being monitored.
            project_path: Path to the project directory.
            iterm: iTerm controller for session access.
            app: Textual app for modal display.
            github: GitHub integration for PR status checks.
        """
        self.config = config
        self.handler = AutoAdvanceHandler(
            config=config,
            iterm=iterm,
            app=app,
        )

        # Create controller with our handler
        self.controller = AutoModeController(
            config=config,
            project_id=project_id,
            project_path=project_path,
            github=github,
        )

        self._last_execution_result: CommandExecutionResult | None = None

    @property
    def current_stage(self) -> WorkflowStage | None:
        """Get the current workflow stage."""
        return self.controller.current_stage

    @property
    def current_state(self) -> WorkflowState | None:
        """Get the current workflow state."""
        return self.controller.current_state

    @property
    def last_execution_result(self) -> CommandExecutionResult | None:
        """Get the result of the last command execution."""
        return self._last_execution_result

    async def on_plan_change(
        self,
        plan: Plan,
        github_status: GitHubStatus | None = None,
    ) -> WorkflowState:
        """Handle PLAN.md changes.

        Evaluates the new stage and executes commands if appropriate.

        Args:
            plan: The updated plan.
            github_status: Optional GitHub status.

        Returns:
            The updated WorkflowState.
        """
        # Get old stage before evaluation
        old_stage = self.controller.current_stage

        # Evaluate the new stage
        new_state = await self.controller.evaluate_stage(plan, github_status)

        # Check if stage changed
        if old_stage != new_state.stage:
            transition = StageTransition(
                old_stage=old_stage,
                new_stage=new_state.stage,
                project_id=self.controller.project_id,
            )

            # Handle the transition (may execute command)
            result = await self.handler.handle_stage_change(transition)
            self._last_execution_result = result

        return new_state

    def set_prd_unneeded(self, unneeded: bool) -> None:
        """Mark the PRD as unneeded.

        Args:
            unneeded: Whether the PRD is not needed for this project.
        """
        self.controller.set_prd_unneeded(unneeded)

    def update_iterm(self, iterm: ItermController | None) -> None:
        """Update the iTerm controller reference.

        Args:
            iterm: New iTerm controller instance.
        """
        self.handler.iterm = iterm

    def update_app(self, app: App | None) -> None:
        """Update the Textual app reference.

        Args:
            app: New Textual app instance.
        """
        self.handler.app = app
