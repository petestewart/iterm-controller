"""Workflow stage automation.

This module provides automatic workflow stage inference and monitoring.
It integrates with the plan watcher to detect stage transitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from .models import (
    AutoModeConfig,
    GitHubStatus,
    Plan,
    WorkflowStage,
    WorkflowState,
)

if TYPE_CHECKING:
    from .github import GitHubIntegration
    from .state import AppState


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
