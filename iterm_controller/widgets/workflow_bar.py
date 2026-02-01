"""Planning -> Execute -> Review -> PR -> Done workflow bar.

Displays workflow stage progression with visual indicators for current,
completed, and future stages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.widgets import Static

from iterm_controller.models import WorkflowStage, WorkflowState
from iterm_controller.state import WorkflowStageChanged

if TYPE_CHECKING:
    pass


class WorkflowBarWidget(Static):
    """Displays workflow stage progression.

    This widget shows the current workflow stage in a horizontal bar:
    - Completed stages: Green with checkmark
    - Current stage: Highlighted with blue background
    - Future stages: Dimmed

    Example display:
        Planning ✓ → [Execute] → Review → PR → Done

    Attributes:
        STAGES: List of workflow stages in order.
    """

    DEFAULT_CSS = """
    WorkflowBarWidget {
        height: 1;
        padding: 0 1;
    }
    """

    STAGES = [
        WorkflowStage.PLANNING,
        WorkflowStage.EXECUTE,
        WorkflowStage.REVIEW,
        WorkflowStage.PR,
        WorkflowStage.DONE,
    ]

    def __init__(
        self,
        workflow_state: WorkflowState | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the workflow bar widget.

        Args:
            workflow_state: Initial workflow state to display.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self._workflow_state = workflow_state or WorkflowState()

    @property
    def workflow_state(self) -> WorkflowState:
        """Get the current workflow state."""
        return self._workflow_state

    @property
    def current_stage(self) -> WorkflowStage:
        """Get the current workflow stage."""
        return self._workflow_state.stage

    def update_state(self, state: WorkflowState) -> None:
        """Update the workflow state and refresh display.

        Args:
            state: New workflow state to display.
        """
        self._workflow_state = state
        self.update(self._render_bar())

    def set_stage(self, stage: WorkflowStage) -> None:
        """Set the current stage directly.

        Args:
            stage: The stage to set as current.
        """
        self._workflow_state.stage = stage
        self.update(self._render_bar())

    def _is_complete(self, stage: WorkflowStage) -> bool:
        """Check if a stage is complete (before current stage).

        Args:
            stage: The stage to check.

        Returns:
            True if the stage is before the current stage.
        """
        order = {s: i for i, s in enumerate(self.STAGES)}
        return order[stage] < order[self._workflow_state.stage]

    def _render_stage(self, stage: WorkflowStage) -> Text:
        """Render a single stage.

        Args:
            stage: The stage to render.

        Returns:
            Rich Text object for the stage.
        """
        name = stage.value.title()
        text = Text()

        if stage == self._workflow_state.stage:
            # Current stage - highlighted with blue background
            text.append(f" {name} ", style="bold white on blue")
        elif self._is_complete(stage):
            # Completed stage - green with checkmark
            text.append(f"{name} ✓", style="green")
        else:
            # Future stage - dimmed
            text.append(name, style="dim")

        return text

    def _render_bar(self) -> Text:
        """Render the complete workflow bar.

        Returns:
            Rich Text object containing the full bar.
        """
        result = Text()

        for i, stage in enumerate(self.STAGES):
            if i > 0:
                result.append(" → ", style="dim")
            result.append_text(self._render_stage(stage))

        return result

    def render(self) -> Text:
        """Render the widget content.

        Returns:
            Rich Text object to display.
        """
        return self._render_bar()

    def on_workflow_stage_changed(self, message: WorkflowStageChanged) -> None:
        """Handle workflow stage changed event.

        Args:
            message: The workflow stage changed message.
        """
        # Update stage from message (stage is passed as string value)
        try:
            new_stage = WorkflowStage(message.stage)
            self._workflow_state.stage = new_stage
            self.update(self._render_bar())
        except ValueError:
            # Invalid stage value, ignore
            pass

    def advance_stage(self) -> WorkflowStage | None:
        """Advance to the next stage if possible.

        Returns:
            The new stage if advanced, None if already at DONE.
        """
        current_index = self.STAGES.index(self._workflow_state.stage)
        if current_index < len(self.STAGES) - 1:
            new_stage = self.STAGES[current_index + 1]
            self._workflow_state.stage = new_stage
            self.update(self._render_bar())
            return new_stage
        return None

    def is_at_stage(self, stage: WorkflowStage) -> bool:
        """Check if currently at a specific stage.

        Args:
            stage: The stage to check.

        Returns:
            True if the current stage matches.
        """
        return self._workflow_state.stage == stage

    def is_done(self) -> bool:
        """Check if workflow is complete.

        Returns:
            True if at the DONE stage.
        """
        return self._workflow_state.stage == WorkflowStage.DONE
