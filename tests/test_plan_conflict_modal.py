"""Tests for PLAN.md conflict resolution modal."""

import pytest

from iterm_controller.models import Plan, Phase, Task, TaskStatus
from iterm_controller.plan_parser import PlanParser
from iterm_controller.plan_watcher import PlanChange, PlanWatcher
from iterm_controller.screens.modals import PlanConflictModal


# Sample PLAN.md content for testing
SAMPLE_PLAN_MD = """# Plan: Test Project

## Overview

Test project for conflict resolution testing.

### Phase 1: Foundation

- [x] **Task A** `[complete]`
  - Scope: Do A

- [ ] **Task B** `[pending]`
  - Scope: Do B

### Phase 2: Features

- [ ] **Task C** `[in_progress]`
  - Scope: Do C
"""


def create_test_plan(tasks_data: list[tuple[str, str, TaskStatus]]) -> Plan:
    """Create a test plan with given tasks.

    Args:
        tasks_data: List of (id, title, status) tuples
    """
    tasks = [
        Task(id=id, title=title, status=status)
        for id, title, status in tasks_data
    ]
    return Plan(phases=[Phase(id="1", title="Test Phase", tasks=tasks)])


class TestPlanConflictModalInit:
    """Test PlanConflictModal initialization."""

    def test_create_modal_with_plans_and_changes(self):
        current_plan = create_test_plan([
            ("1.1", "Task A", TaskStatus.PENDING),
            ("1.2", "Task B", TaskStatus.IN_PROGRESS),
        ])
        new_plan = create_test_plan([
            ("1.1", "Task A", TaskStatus.COMPLETE),
            ("1.2", "Task B", TaskStatus.COMPLETE),
        ])
        changes = [
            PlanChange(
                task_id="1.1",
                old_status=TaskStatus.PENDING,
                new_status=TaskStatus.COMPLETE,
                task_title="Task A",
                change_type="status_changed",
            ),
            PlanChange(
                task_id="1.2",
                old_status=TaskStatus.IN_PROGRESS,
                new_status=TaskStatus.COMPLETE,
                task_title="Task B",
                change_type="status_changed",
            ),
        ]

        modal = PlanConflictModal(
            current_plan=current_plan,
            new_plan=new_plan,
            changes=changes,
        )

        assert modal.current_plan is current_plan
        assert modal.new_plan is new_plan
        assert modal.changes == changes

    def test_create_modal_with_optional_parameters(self):
        current_plan = create_test_plan([("1.1", "Task", TaskStatus.PENDING)])
        new_plan = create_test_plan([("1.1", "Task", TaskStatus.COMPLETE)])
        changes = []

        modal = PlanConflictModal(
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


class TestPlanConflictModalActions:
    """Test PlanConflictModal action methods."""

    def test_action_reload_returns_reload(self):
        current_plan = create_test_plan([("1.1", "Task", TaskStatus.PENDING)])
        new_plan = create_test_plan([("1.1", "Task", TaskStatus.COMPLETE)])

        modal = PlanConflictModal(
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
        current_plan = create_test_plan([("1.1", "Task", TaskStatus.PENDING)])
        new_plan = create_test_plan([("1.1", "Task", TaskStatus.COMPLETE)])

        modal = PlanConflictModal(
            current_plan=current_plan,
            new_plan=new_plan,
            changes=[],
        )

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_keep()

        assert dismissed_with == ["keep"]

    def test_action_dismiss_returns_later(self):
        current_plan = create_test_plan([("1.1", "Task", TaskStatus.PENDING)])
        new_plan = create_test_plan([("1.1", "Task", TaskStatus.COMPLETE)])

        modal = PlanConflictModal(
            current_plan=current_plan,
            new_plan=new_plan,
            changes=[],
        )

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_dismiss()

        assert dismissed_with == ["later"]


class TestPlanConflictModalContent:
    """Test PlanConflictModal content generation."""

    def test_max_displayed_changes_limit(self):
        """Verify the MAX_DISPLAYED_CHANGES constant is set correctly."""
        assert PlanConflictModal.MAX_DISPLAYED_CHANGES == 10


class TestPlanWatcherModalIntegration:
    """Test integration between PlanWatcher and PlanConflictModal."""

    def test_create_conflict_modal(self):
        parser = PlanParser()
        current_plan = parser.parse(SAMPLE_PLAN_MD)

        modified_md = SAMPLE_PLAN_MD.replace(
            "- [ ] **Task B** `[pending]`",
            "- [x] **Task B** `[complete]`",
        )
        new_plan = parser.parse(modified_md)

        watcher = PlanWatcher(plan=current_plan)
        changes = watcher._compute_changes(new_plan)

        modal = watcher.create_conflict_modal(new_plan, changes)

        assert isinstance(modal, PlanConflictModal)
        assert modal.current_plan is current_plan
        assert modal.new_plan is new_plan
        assert len(modal.changes) == 1

    def test_create_conflict_modal_without_current_plan_raises(self):
        parser = PlanParser()
        new_plan = parser.parse(SAMPLE_PLAN_MD)

        watcher = PlanWatcher(plan=None)

        with pytest.raises(ValueError, match="Cannot create conflict modal"):
            watcher.create_conflict_modal(new_plan, [])

    def test_handle_conflict_resolution_reload(self):
        parser = PlanParser()
        current_plan = parser.parse(SAMPLE_PLAN_MD)

        modified_md = SAMPLE_PLAN_MD.replace(
            "- [ ] **Task B** `[pending]`",
            "- [x] **Task B** `[complete]`",
        )
        new_plan = parser.parse(modified_md)

        reloaded_plans = []

        def on_reloaded(plan: Plan):
            reloaded_plans.append(plan)

        watcher = PlanWatcher(plan=current_plan, on_plan_reloaded=on_reloaded)
        watcher.handle_conflict_resolution("reload", new_plan)

        assert watcher.plan is new_plan
        assert len(reloaded_plans) == 1
        assert reloaded_plans[0] is new_plan

    def test_handle_conflict_resolution_keep(self):
        parser = PlanParser()
        current_plan = parser.parse(SAMPLE_PLAN_MD)
        new_plan = parser.parse(SAMPLE_PLAN_MD)

        watcher = PlanWatcher(plan=current_plan, queued_reload=new_plan)
        watcher.handle_conflict_resolution("keep", new_plan)

        # Plan should remain unchanged
        assert watcher.plan is current_plan
        assert watcher.queued_reload is None

    def test_handle_conflict_resolution_later(self):
        parser = PlanParser()
        current_plan = parser.parse(SAMPLE_PLAN_MD)
        new_plan = parser.parse(SAMPLE_PLAN_MD)

        watcher = PlanWatcher(plan=current_plan)
        original_plan = watcher.plan

        # "later" should do nothing
        watcher.handle_conflict_resolution("later", new_plan)

        assert watcher.plan is original_plan


class TestPlanChangeDisplay:
    """Test PlanChange string representation for modal display."""

    def test_status_change_display(self):
        change = PlanChange(
            task_id="1.2",
            old_status=TaskStatus.PENDING,
            new_status=TaskStatus.COMPLETE,
            task_title="Task B",
            change_type="status_changed",
        )
        display = str(change)
        assert "1.2" in display
        assert "pending" in display
        assert "complete" in display

    def test_task_added_display(self):
        change = PlanChange(
            task_id="2.3",
            old_status=None,
            new_status=TaskStatus.PENDING,
            task_title="New Feature",
            change_type="task_added",
        )
        display = str(change)
        assert "New task added" in display
        assert "2.3" in display
        assert "New Feature" in display

    def test_task_removed_display(self):
        change = PlanChange(
            task_id="1.5",
            old_status=TaskStatus.SKIPPED,
            new_status=None,
            task_title="Removed Task",
            change_type="task_removed",
        )
        display = str(change)
        assert "Task removed" in display
        assert "1.5" in display
