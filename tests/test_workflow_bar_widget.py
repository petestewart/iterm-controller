"""Tests for the WorkflowBarWidget."""

from unittest.mock import patch

import pytest

from iterm_controller.models import WorkflowStage, WorkflowState
from iterm_controller.state import WorkflowStageChanged
from iterm_controller.widgets.workflow_bar import WorkflowBarWidget


class TestWorkflowBarWidget:
    """Tests for WorkflowBarWidget initialization and properties."""

    def test_init_default_state(self) -> None:
        """Test widget initializes with default PLANNING stage."""
        widget = WorkflowBarWidget()

        assert widget.current_stage == WorkflowStage.PLANNING

    def test_init_with_state(self) -> None:
        """Test widget initializes with provided state."""
        state = WorkflowState(stage=WorkflowStage.EXECUTE)
        widget = WorkflowBarWidget(workflow_state=state)

        assert widget.current_stage == WorkflowStage.EXECUTE

    def test_workflow_state_property(self) -> None:
        """Test workflow_state property returns the state."""
        state = WorkflowState(stage=WorkflowStage.REVIEW)
        widget = WorkflowBarWidget(workflow_state=state)

        assert widget.workflow_state == state
        assert widget.workflow_state.stage == WorkflowStage.REVIEW

    def test_stages_constant(self) -> None:
        """Test STAGES constant contains all stages in order."""
        assert WorkflowBarWidget.STAGES == [
            WorkflowStage.PLANNING,
            WorkflowStage.EXECUTE,
            WorkflowStage.REVIEW,
            WorkflowStage.PR,
            WorkflowStage.DONE,
        ]


class TestUpdateState:
    """Tests for state update methods."""

    def test_update_state(self) -> None:
        """Test update_state updates the internal state."""
        widget = WorkflowBarWidget()
        new_state = WorkflowState(stage=WorkflowStage.PR)

        with patch.object(widget, "update"):
            widget.update_state(new_state)

        assert widget.current_stage == WorkflowStage.PR

    def test_set_stage(self) -> None:
        """Test set_stage updates the stage directly."""
        widget = WorkflowBarWidget()

        with patch.object(widget, "update"):
            widget.set_stage(WorkflowStage.REVIEW)

        assert widget.current_stage == WorkflowStage.REVIEW


class TestStageCompletion:
    """Tests for stage completion detection."""

    def test_is_complete_for_earlier_stage(self) -> None:
        """Test _is_complete returns True for stages before current."""
        state = WorkflowState(stage=WorkflowStage.EXECUTE)
        widget = WorkflowBarWidget(workflow_state=state)

        assert widget._is_complete(WorkflowStage.PLANNING) is True

    def test_is_complete_for_current_stage(self) -> None:
        """Test _is_complete returns False for current stage."""
        state = WorkflowState(stage=WorkflowStage.EXECUTE)
        widget = WorkflowBarWidget(workflow_state=state)

        assert widget._is_complete(WorkflowStage.EXECUTE) is False

    def test_is_complete_for_later_stage(self) -> None:
        """Test _is_complete returns False for stages after current."""
        state = WorkflowState(stage=WorkflowStage.EXECUTE)
        widget = WorkflowBarWidget(workflow_state=state)

        assert widget._is_complete(WorkflowStage.REVIEW) is False
        assert widget._is_complete(WorkflowStage.PR) is False
        assert widget._is_complete(WorkflowStage.DONE) is False

    def test_is_complete_at_done_stage(self) -> None:
        """Test all previous stages are complete at DONE."""
        state = WorkflowState(stage=WorkflowStage.DONE)
        widget = WorkflowBarWidget(workflow_state=state)

        assert widget._is_complete(WorkflowStage.PLANNING) is True
        assert widget._is_complete(WorkflowStage.EXECUTE) is True
        assert widget._is_complete(WorkflowStage.REVIEW) is True
        assert widget._is_complete(WorkflowStage.PR) is True


class TestRenderStage:
    """Tests for individual stage rendering."""

    def test_render_current_stage_highlighted(self) -> None:
        """Test current stage has highlighted styling."""
        state = WorkflowState(stage=WorkflowStage.EXECUTE)
        widget = WorkflowBarWidget(workflow_state=state)

        text = widget._render_stage(WorkflowStage.EXECUTE)
        rendered = str(text)

        assert "Execute" in rendered

    def test_render_completed_stage_has_checkmark(self) -> None:
        """Test completed stages show checkmark."""
        state = WorkflowState(stage=WorkflowStage.EXECUTE)
        widget = WorkflowBarWidget(workflow_state=state)

        text = widget._render_stage(WorkflowStage.PLANNING)
        rendered = str(text)

        assert "Planning" in rendered
        assert "✓" in rendered

    def test_render_future_stage(self) -> None:
        """Test future stages are rendered without checkmark."""
        state = WorkflowState(stage=WorkflowStage.EXECUTE)
        widget = WorkflowBarWidget(workflow_state=state)

        text = widget._render_stage(WorkflowStage.REVIEW)
        rendered = str(text)

        assert "Review" in rendered
        assert "✓" not in rendered


class TestRenderBar:
    """Tests for full bar rendering."""

    def test_render_bar_contains_all_stages(self) -> None:
        """Test rendered bar contains all stage names."""
        widget = WorkflowBarWidget()
        text = widget._render_bar()
        rendered = str(text)

        assert "Planning" in rendered
        assert "Execute" in rendered
        assert "Review" in rendered
        assert "Pr" in rendered
        assert "Done" in rendered

    def test_render_bar_has_arrows(self) -> None:
        """Test rendered bar has arrow separators."""
        widget = WorkflowBarWidget()
        text = widget._render_bar()
        rendered = str(text)

        assert "→" in rendered

    def test_render_at_planning(self) -> None:
        """Test render at PLANNING stage."""
        state = WorkflowState(stage=WorkflowStage.PLANNING)
        widget = WorkflowBarWidget(workflow_state=state)

        text = widget.render()
        rendered = str(text)

        # No checkmarks should appear at first stage
        # (Planning is current, not complete)
        assert "Planning" in rendered

    def test_render_at_done(self) -> None:
        """Test render at DONE stage shows all previous as complete."""
        state = WorkflowState(stage=WorkflowStage.DONE)
        widget = WorkflowBarWidget(workflow_state=state)

        text = widget.render()
        rendered = str(text)

        # All stages should be shown
        assert "Planning" in rendered
        assert "Done" in rendered


class TestEventHandlers:
    """Tests for event handler methods."""

    def test_on_workflow_stage_changed(self) -> None:
        """Test on_workflow_stage_changed updates stage."""
        widget = WorkflowBarWidget()
        message = WorkflowStageChanged("project-1", "review")

        with patch.object(widget, "update"):
            widget.on_workflow_stage_changed(message)

        assert widget.current_stage == WorkflowStage.REVIEW

    def test_on_workflow_stage_changed_invalid_stage(self) -> None:
        """Test on_workflow_stage_changed ignores invalid stage values."""
        widget = WorkflowBarWidget()
        original_stage = widget.current_stage
        message = WorkflowStageChanged("project-1", "invalid_stage")

        with patch.object(widget, "update"):
            widget.on_workflow_stage_changed(message)

        # Stage should remain unchanged
        assert widget.current_stage == original_stage


class TestAdvanceStage:
    """Tests for stage advancement."""

    def test_advance_from_planning(self) -> None:
        """Test advancing from PLANNING to EXECUTE."""
        widget = WorkflowBarWidget()

        with patch.object(widget, "update"):
            result = widget.advance_stage()

        assert result == WorkflowStage.EXECUTE
        assert widget.current_stage == WorkflowStage.EXECUTE

    def test_advance_from_execute(self) -> None:
        """Test advancing from EXECUTE to REVIEW."""
        state = WorkflowState(stage=WorkflowStage.EXECUTE)
        widget = WorkflowBarWidget(workflow_state=state)

        with patch.object(widget, "update"):
            result = widget.advance_stage()

        assert result == WorkflowStage.REVIEW
        assert widget.current_stage == WorkflowStage.REVIEW

    def test_advance_from_pr_to_done(self) -> None:
        """Test advancing from PR to DONE."""
        state = WorkflowState(stage=WorkflowStage.PR)
        widget = WorkflowBarWidget(workflow_state=state)

        with patch.object(widget, "update"):
            result = widget.advance_stage()

        assert result == WorkflowStage.DONE
        assert widget.current_stage == WorkflowStage.DONE

    def test_advance_at_done_returns_none(self) -> None:
        """Test advancing at DONE returns None."""
        state = WorkflowState(stage=WorkflowStage.DONE)
        widget = WorkflowBarWidget(workflow_state=state)

        result = widget.advance_stage()

        assert result is None
        assert widget.current_stage == WorkflowStage.DONE


class TestHelperMethods:
    """Tests for helper methods."""

    def test_is_at_stage_true(self) -> None:
        """Test is_at_stage returns True for current stage."""
        state = WorkflowState(stage=WorkflowStage.REVIEW)
        widget = WorkflowBarWidget(workflow_state=state)

        assert widget.is_at_stage(WorkflowStage.REVIEW) is True

    def test_is_at_stage_false(self) -> None:
        """Test is_at_stage returns False for different stage."""
        state = WorkflowState(stage=WorkflowStage.REVIEW)
        widget = WorkflowBarWidget(workflow_state=state)

        assert widget.is_at_stage(WorkflowStage.PLANNING) is False
        assert widget.is_at_stage(WorkflowStage.PR) is False

    def test_is_done_true(self) -> None:
        """Test is_done returns True at DONE stage."""
        state = WorkflowState(stage=WorkflowStage.DONE)
        widget = WorkflowBarWidget(workflow_state=state)

        assert widget.is_done() is True

    def test_is_done_false(self) -> None:
        """Test is_done returns False at other stages."""
        state = WorkflowState(stage=WorkflowStage.EXECUTE)
        widget = WorkflowBarWidget(workflow_state=state)

        assert widget.is_done() is False
