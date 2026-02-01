"""Tests for TEST_PLAN.md conflict resolution modal."""

import pytest

from iterm_controller.models import TestPlan, TestSection, TestStep, TestStatus
from iterm_controller.screens.modals import TestPlanConflictModal
from iterm_controller.test_plan_watcher import TestStepChange


def create_test_plan(steps_data: list[tuple[str, str, TestStatus]]) -> TestPlan:
    """Create a test plan with given steps.

    Args:
        steps_data: List of (id, description, status) tuples
    """
    section_id = "test-section"
    steps = [
        TestStep(id=id, section=section_id, description=description, status=status)
        for id, description, status in steps_data
    ]
    return TestPlan(
        sections=[TestSection(id=section_id, title="Test Section", steps=steps)]
    )


class TestTestPlanConflictModalInit:
    """Test TestPlanConflictModal initialization."""

    def test_create_modal_with_plans_and_changes(self):
        current_plan = create_test_plan([
            ("1.1", "Step A", TestStatus.PENDING),
            ("1.2", "Step B", TestStatus.IN_PROGRESS),
        ])
        new_plan = create_test_plan([
            ("1.1", "Step A", TestStatus.PASSED),
            ("1.2", "Step B", TestStatus.PASSED),
        ])
        changes = [
            TestStepChange(
                step_id="1.1",
                old_status=TestStatus.PENDING,
                new_status=TestStatus.PASSED,
                step_description="Step A",
                change_type="status_changed",
            ),
            TestStepChange(
                step_id="1.2",
                old_status=TestStatus.IN_PROGRESS,
                new_status=TestStatus.PASSED,
                step_description="Step B",
                change_type="status_changed",
            ),
        ]

        modal = TestPlanConflictModal(
            current_plan=current_plan,
            new_plan=new_plan,
            changes=changes,
        )

        assert modal.current_plan is current_plan
        assert modal.new_plan is new_plan
        assert modal.changes == changes

    def test_create_modal_with_optional_parameters(self):
        current_plan = create_test_plan([("1.1", "Step", TestStatus.PENDING)])
        new_plan = create_test_plan([("1.1", "Step", TestStatus.PASSED)])
        changes = []

        modal = TestPlanConflictModal(
            current_plan=current_plan,
            new_plan=new_plan,
            changes=changes,
            name="test_modal",
            id="modal-1",
            classes="custom-class",
        )

        assert modal.current_plan is current_plan
        assert modal.new_plan is new_plan
        assert modal.changes == changes


class TestTestPlanConflictModalActions:
    """Test TestPlanConflictModal action methods."""

    def test_action_reload_returns_reload(self):
        current_plan = create_test_plan([("1.1", "Step", TestStatus.PENDING)])
        new_plan = create_test_plan([("1.1", "Step", TestStatus.PASSED)])

        modal = TestPlanConflictModal(
            current_plan=current_plan,
            new_plan=new_plan,
            changes=[],
        )

        # Track what dismiss was called with
        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_reload()

        assert dismissed_with == ["reload"]

    def test_action_keep_returns_keep(self):
        current_plan = create_test_plan([("1.1", "Step", TestStatus.PENDING)])
        new_plan = create_test_plan([("1.1", "Step", TestStatus.PASSED)])

        modal = TestPlanConflictModal(
            current_plan=current_plan,
            new_plan=new_plan,
            changes=[],
        )

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_keep()

        assert dismissed_with == ["keep"]

    def test_action_dismiss_returns_later(self):
        current_plan = create_test_plan([("1.1", "Step", TestStatus.PENDING)])
        new_plan = create_test_plan([("1.1", "Step", TestStatus.PASSED)])

        modal = TestPlanConflictModal(
            current_plan=current_plan,
            new_plan=new_plan,
            changes=[],
        )

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_dismiss()

        assert dismissed_with == ["later"]


class TestTestPlanConflictModalContent:
    """Test TestPlanConflictModal content generation."""

    def test_max_displayed_changes_limit(self):
        """Verify the MAX_DISPLAYED_CHANGES constant is set correctly."""
        assert TestPlanConflictModal.MAX_DISPLAYED_CHANGES == 10


class TestTestStepChangeDisplay:
    """Test TestStepChange string representation for modal display."""

    def test_status_change_display(self):
        change = TestStepChange(
            step_id="1.2",
            old_status=TestStatus.PENDING,
            new_status=TestStatus.PASSED,
            step_description="Step B",
            change_type="status_changed",
        )
        display = str(change)
        assert "1.2" in display
        assert "pending" in display
        assert "passed" in display

    def test_step_added_display(self):
        change = TestStepChange(
            step_id="2.3",
            old_status=None,
            new_status=TestStatus.PENDING,
            step_description="New Step",
            change_type="step_added",
        )
        display = str(change)
        assert "New step added" in display
        assert "2.3" in display
        assert "New Step" in display

    def test_step_removed_display(self):
        change = TestStepChange(
            step_id="1.5",
            old_status=TestStatus.PASSED,
            new_status=None,
            step_description="Removed Step",
            change_type="step_removed",
        )
        display = str(change)
        assert "Step removed" in display
        assert "1.5" in display
