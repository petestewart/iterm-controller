"""Tests for the TaskProgressWidget."""

from unittest.mock import patch

import pytest

from iterm_controller.models import Phase, Plan, Task, TaskStatus
from iterm_controller.state import PlanReloaded
from iterm_controller.widgets.task_progress import TaskProgressWidget


def make_task(
    task_id: str = "1.1",
    title: str = "Test Task",
    status: TaskStatus = TaskStatus.PENDING,
) -> Task:
    """Create a test task."""
    return Task(
        id=task_id,
        title=title,
        status=status,
    )


def make_phase(
    phase_id: str = "1",
    title: str = "Phase 1: Test",
    tasks: list[Task] | None = None,
) -> Phase:
    """Create a test phase."""
    return Phase(
        id=phase_id,
        title=title,
        tasks=tasks or [],
    )


def make_plan(phases: list[Phase] | None = None) -> Plan:
    """Create a test plan."""
    return Plan(phases=phases or [])


class TestTaskProgressWidgetInit:
    """Tests for TaskProgressWidget initialization."""

    def test_init_empty(self) -> None:
        """Test widget initializes with empty plan."""
        widget = TaskProgressWidget()

        assert widget.plan.phases == []
        assert widget.show_breakdown is False

    def test_init_with_plan(self) -> None:
        """Test widget initializes with provided plan."""
        task = make_task()
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = TaskProgressWidget(plan=plan)

        assert len(widget.plan.phases) == 1
        assert len(widget.plan.phases[0].tasks) == 1

    def test_init_with_show_breakdown(self) -> None:
        """Test widget initializes with show_breakdown option."""
        widget = TaskProgressWidget(show_breakdown=True)

        assert widget.show_breakdown is True

    def test_refresh_plan(self) -> None:
        """Test refreshing the plan."""
        widget = TaskProgressWidget()

        task = make_task()
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        with patch.object(widget, "update"):
            widget.refresh_plan(plan)

        assert len(widget.plan.phases) == 1


class TestProgressText:
    """Tests for progress text generation."""

    def test_empty_plan_shows_zero_tasks(self) -> None:
        """Test empty plan shows '0 tasks'."""
        widget = TaskProgressWidget()

        text = widget.get_progress_text()

        assert text == "0 tasks"

    def test_no_complete_tasks(self) -> None:
        """Test with no complete tasks."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.PENDING),
            make_task(task_id="1.2", status=TaskStatus.IN_PROGRESS),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan)

        text = widget.get_progress_text()

        assert text == "0/2 tasks complete"

    def test_some_complete_tasks(self) -> None:
        """Test with some complete tasks."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.COMPLETE),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
            make_task(task_id="1.3", status=TaskStatus.COMPLETE),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan)

        text = widget.get_progress_text()

        assert text == "2/3 tasks complete"

    def test_all_complete_tasks(self) -> None:
        """Test with all tasks complete."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.COMPLETE),
            make_task(task_id="1.2", status=TaskStatus.COMPLETE),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan)

        text = widget.get_progress_text()

        assert text == "2/2 tasks complete"

    def test_skipped_counts_as_complete(self) -> None:
        """Test that skipped tasks count as complete."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.COMPLETE),
            make_task(task_id="1.2", status=TaskStatus.SKIPPED),
            make_task(task_id="1.3", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan)

        text = widget.get_progress_text()

        assert text == "2/3 tasks complete"


class TestProgressPercentage:
    """Tests for progress percentage calculation."""

    def test_empty_plan_zero_percent(self) -> None:
        """Test empty plan returns 0%."""
        widget = TaskProgressWidget()

        percent = widget.get_progress_percentage()

        assert percent == 0.0

    def test_fifty_percent(self) -> None:
        """Test 50% completion."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.COMPLETE),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan)

        percent = widget.get_progress_percentage()

        assert percent == 50.0

    def test_hundred_percent(self) -> None:
        """Test 100% completion."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.COMPLETE),
            make_task(task_id="1.2", status=TaskStatus.COMPLETE),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan)

        percent = widget.get_progress_percentage()

        assert percent == 100.0


class TestStatusCounts:
    """Tests for status count retrieval."""

    def test_empty_plan_all_zeros(self) -> None:
        """Test empty plan returns all zero counts."""
        widget = TaskProgressWidget()

        counts = widget.get_status_counts()

        assert counts[TaskStatus.PENDING] == 0
        assert counts[TaskStatus.IN_PROGRESS] == 0
        assert counts[TaskStatus.COMPLETE] == 0
        assert counts[TaskStatus.SKIPPED] == 0
        assert counts[TaskStatus.BLOCKED] == 0

    def test_counts_all_statuses(self) -> None:
        """Test counts for various statuses."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.PENDING),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
            make_task(task_id="1.3", status=TaskStatus.IN_PROGRESS),
            make_task(task_id="1.4", status=TaskStatus.COMPLETE),
            make_task(task_id="1.5", status=TaskStatus.COMPLETE),
            make_task(task_id="1.6", status=TaskStatus.COMPLETE),
            make_task(task_id="1.7", status=TaskStatus.SKIPPED),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan)

        counts = widget.get_status_counts()

        assert counts[TaskStatus.PENDING] == 2
        assert counts[TaskStatus.IN_PROGRESS] == 1
        assert counts[TaskStatus.COMPLETE] == 3
        assert counts[TaskStatus.SKIPPED] == 1
        assert counts[TaskStatus.BLOCKED] == 0


class TestRendering:
    """Tests for progress rendering."""

    def test_render_empty_shows_no_tasks(self) -> None:
        """Test rendering empty plan shows 'No tasks'."""
        widget = TaskProgressWidget()

        text = widget._render_progress()

        assert "No tasks" in str(text)

    def test_render_shows_count(self) -> None:
        """Test rendered output includes task count."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.COMPLETE),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
            make_task(task_id="1.3", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan)

        text = widget._render_progress()

        assert "1/3 tasks complete" in str(text)

    def test_render_shows_percentage(self) -> None:
        """Test rendered output includes percentage."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.COMPLETE),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan)

        text = widget._render_progress()

        assert "50%" in str(text)

    def test_render_without_breakdown(self) -> None:
        """Test rendering without breakdown doesn't show status details."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.IN_PROGRESS),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan, show_breakdown=False)

        text = widget._render_progress()

        assert "in progress" not in str(text).lower()
        assert "pending" not in str(text).lower()


class TestBreakdownRendering:
    """Tests for status breakdown rendering."""

    def test_render_with_breakdown(self) -> None:
        """Test rendering with breakdown shows status details."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.IN_PROGRESS),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan, show_breakdown=True)

        text = widget._render_progress()

        assert "in progress" in str(text).lower()
        assert "pending" in str(text).lower()

    def test_breakdown_shows_in_progress_count(self) -> None:
        """Test breakdown shows in progress count."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.IN_PROGRESS),
            make_task(task_id="1.2", status=TaskStatus.IN_PROGRESS),
            make_task(task_id="1.3", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan, show_breakdown=True)

        text = widget._render_progress()

        assert "2 in progress" in str(text)

    def test_breakdown_shows_pending_count(self) -> None:
        """Test breakdown shows pending count."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.PENDING),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
            make_task(task_id="1.3", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan, show_breakdown=True)

        text = widget._render_progress()

        assert "3 pending" in str(text)

    def test_breakdown_shows_blocked_count(self) -> None:
        """Test breakdown shows blocked count."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.BLOCKED),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan, show_breakdown=True)

        text = widget._render_progress()

        assert "1 blocked" in str(text)

    def test_breakdown_shows_skipped_count(self) -> None:
        """Test breakdown shows skipped count."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.SKIPPED),
            make_task(task_id="1.2", status=TaskStatus.COMPLETE),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan, show_breakdown=True)

        text = widget._render_progress()

        assert "1 skipped" in str(text)

    def test_breakdown_omits_zero_counts(self) -> None:
        """Test breakdown doesn't show statuses with zero count."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.COMPLETE),
            make_task(task_id="1.2", status=TaskStatus.COMPLETE),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan, show_breakdown=True)

        text = widget._render_progress()

        # All complete, so no in_progress/pending/blocked should appear
        assert "in progress" not in str(text).lower()
        assert "pending" not in str(text).lower()
        assert "blocked" not in str(text).lower()

    def test_breakdown_uses_status_icons(self) -> None:
        """Test breakdown uses correct status icons."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.IN_PROGRESS),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
            make_task(task_id="1.3", status=TaskStatus.BLOCKED),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan, show_breakdown=True)

        text = widget._render_progress()
        text_str = str(text)

        assert "●" in text_str  # in progress
        assert "○" in text_str  # pending
        assert "⊘" in text_str  # blocked


class TestShowBreakdownProperty:
    """Tests for show_breakdown property."""

    def test_set_show_breakdown_true(self) -> None:
        """Test setting show_breakdown to True."""
        widget = TaskProgressWidget(show_breakdown=False)

        with patch.object(widget, "update"):
            widget.show_breakdown = True

        assert widget.show_breakdown is True

    def test_set_show_breakdown_false(self) -> None:
        """Test setting show_breakdown to False."""
        widget = TaskProgressWidget(show_breakdown=True)

        with patch.object(widget, "update"):
            widget.show_breakdown = False

        assert widget.show_breakdown is False

    def test_set_show_breakdown_triggers_update(self) -> None:
        """Test setting show_breakdown triggers re-render."""
        widget = TaskProgressWidget()

        with patch.object(widget, "update") as mock_update:
            widget.show_breakdown = True
            mock_update.assert_called_once()


class TestEventHandler:
    """Tests for event handler methods."""

    def test_on_plan_reloaded_updates_plan(self) -> None:
        """Test on_plan_reloaded updates the widget's plan."""
        widget = TaskProgressWidget()

        task = make_task()
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        message = PlanReloaded(project_id="test", plan=plan)

        with patch.object(widget, "update"):
            widget.on_plan_reloaded(message)

        assert len(widget.plan.phases) == 1


class TestRenderMethod:
    """Tests for the render method."""

    def test_render_returns_progress(self) -> None:
        """Test render() returns the progress display."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.COMPLETE),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskProgressWidget(plan=plan)

        result = widget.render()

        assert "1/2 tasks complete" in str(result)


class TestMultiplePhases:
    """Tests for plans with multiple phases."""

    def test_counts_tasks_across_phases(self) -> None:
        """Test progress aggregates across all phases."""
        phase1 = make_phase(
            phase_id="1",
            tasks=[
                make_task(task_id="1.1", status=TaskStatus.COMPLETE),
                make_task(task_id="1.2", status=TaskStatus.COMPLETE),
            ],
        )
        phase2 = make_phase(
            phase_id="2",
            tasks=[
                make_task(task_id="2.1", status=TaskStatus.COMPLETE),
                make_task(task_id="2.2", status=TaskStatus.PENDING),
                make_task(task_id="2.3", status=TaskStatus.PENDING),
            ],
        )
        plan = make_plan(phases=[phase1, phase2])
        widget = TaskProgressWidget(plan=plan)

        text = widget.get_progress_text()

        assert text == "3/5 tasks complete"

    def test_percentage_across_phases(self) -> None:
        """Test percentage calculation across phases."""
        phase1 = make_phase(
            phase_id="1",
            tasks=[make_task(task_id="1.1", status=TaskStatus.COMPLETE)],
        )
        phase2 = make_phase(
            phase_id="2",
            tasks=[make_task(task_id="2.1", status=TaskStatus.PENDING)],
        )
        plan = make_plan(phases=[phase1, phase2])
        widget = TaskProgressWidget(plan=plan)

        percent = widget.get_progress_percentage()

        assert percent == 50.0
