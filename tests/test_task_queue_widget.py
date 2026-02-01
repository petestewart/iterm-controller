"""Tests for the TaskQueueWidget."""

from unittest.mock import patch

import pytest

from iterm_controller.models import Phase, Plan, Task, TaskStatus
from iterm_controller.widgets.task_queue import TaskQueueWidget


def make_task(
    task_id: str = "1.1",
    title: str = "Test Task",
    status: TaskStatus = TaskStatus.PENDING,
    depends: list[str] | None = None,
) -> Task:
    """Create a test task."""
    return Task(
        id=task_id,
        title=title,
        status=status,
        depends=depends or [],
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


class TestTaskQueueWidgetInit:
    """Tests for TaskQueueWidget initialization."""

    def test_init_empty(self) -> None:
        """Test widget initializes with empty plan."""
        widget = TaskQueueWidget()

        assert widget.plan.phases == []
        assert widget.selected_task is None
        assert widget.selected_index == 0

    def test_init_with_plan(self) -> None:
        """Test widget initializes with provided plan."""
        task = make_task(status=TaskStatus.PENDING)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = TaskQueueWidget(plan=plan)

        assert len(widget.plan.phases) == 1
        assert widget.selected_task == task

    def test_only_pending_tasks_visible(self) -> None:
        """Test only pending tasks appear in the queue."""
        pending = make_task(task_id="1.1", status=TaskStatus.PENDING)
        complete = make_task(task_id="1.2", status=TaskStatus.COMPLETE)
        in_progress = make_task(task_id="1.3", status=TaskStatus.IN_PROGRESS)
        phase = make_phase(tasks=[pending, complete, in_progress])
        plan = make_plan(phases=[phase])

        widget = TaskQueueWidget(plan=plan)

        assert len(widget._visible_tasks) == 1
        assert widget._visible_tasks[0].id == "1.1"


class TestTaskQueueSelection:
    """Tests for task selection functionality."""

    def test_select_next(self) -> None:
        """Test select_next moves to next task."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.PENDING),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskQueueWidget(plan=plan)

        with patch.object(widget, "update"):
            widget.select_next()

        assert widget.selected_index == 1
        assert widget.selected_task.id == "1.2"

    def test_select_next_wraps(self) -> None:
        """Test select_next wraps to first task."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.PENDING),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskQueueWidget(plan=plan)
        widget._selected_index = 1

        with patch.object(widget, "update"):
            widget.select_next()

        assert widget.selected_index == 0
        assert widget.selected_task.id == "1.1"

    def test_select_previous(self) -> None:
        """Test select_previous moves to previous task."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.PENDING),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskQueueWidget(plan=plan)
        widget._selected_index = 1

        with patch.object(widget, "update"):
            widget.select_previous()

        assert widget.selected_index == 0
        assert widget.selected_task.id == "1.1"

    def test_select_previous_wraps(self) -> None:
        """Test select_previous wraps to last task."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.PENDING),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskQueueWidget(plan=plan)
        widget._selected_index = 0

        with patch.object(widget, "update"):
            widget.select_previous()

        assert widget.selected_index == 1
        assert widget.selected_task.id == "1.2"


class TestTaskQueueBlockedTasks:
    """Tests for blocked task detection."""

    def test_task_not_blocked_without_depends(self) -> None:
        """Test task without dependencies is not blocked."""
        task = make_task(depends=[])
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = TaskQueueWidget(plan=plan)

        assert not widget.is_task_blocked(task)

    def test_task_blocked_with_incomplete_dependency(self) -> None:
        """Test task is blocked when dependency is incomplete."""
        dep_task = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked_task = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep_task, blocked_task])
        plan = make_plan(phases=[phase])
        widget = TaskQueueWidget(plan=plan)

        assert widget.is_task_blocked(blocked_task)

    def test_task_not_blocked_with_complete_dependency(self) -> None:
        """Test task is not blocked when dependency is complete."""
        dep_task = make_task(task_id="1.1", status=TaskStatus.COMPLETE)
        task = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep_task, task])
        plan = make_plan(phases=[phase])
        widget = TaskQueueWidget(plan=plan)

        assert not widget.is_task_blocked(task)

    def test_get_available_tasks(self) -> None:
        """Test get_available_tasks returns non-blocked pending tasks."""
        available = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked = make_task(task_id="1.2", status=TaskStatus.PENDING, depends=["1.1"])
        phase = make_phase(tasks=[available, blocked])
        plan = make_plan(phases=[phase])
        widget = TaskQueueWidget(plan=plan)

        available_tasks = widget.get_available_tasks()

        assert len(available_tasks) == 1
        assert available_tasks[0].id == "1.1"

    def test_get_blocked_tasks(self) -> None:
        """Test get_blocked_tasks returns blocked tasks."""
        available = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked = make_task(task_id="1.2", status=TaskStatus.PENDING, depends=["1.1"])
        phase = make_phase(tasks=[available, blocked])
        plan = make_plan(phases=[phase])
        widget = TaskQueueWidget(plan=plan)

        blocked_tasks = widget.get_blocked_tasks()

        assert len(blocked_tasks) == 1
        assert blocked_tasks[0].id == "1.2"

    def test_get_blocking_tasks(self) -> None:
        """Test get_blocking_tasks returns correct blockers."""
        dep1 = make_task(task_id="1.1", status=TaskStatus.PENDING)
        dep2 = make_task(task_id="1.2", status=TaskStatus.COMPLETE)
        blocked_task = make_task(task_id="1.3", depends=["1.1", "1.2"])
        phase = make_phase(tasks=[dep1, dep2, blocked_task])
        plan = make_plan(phases=[phase])
        widget = TaskQueueWidget(plan=plan)

        blockers = widget.get_blocking_tasks(blocked_task)

        assert "1.1" in blockers
        assert "1.2" not in blockers  # Complete, not blocking


class TestTaskQueueRendering:
    """Tests for task queue rendering."""

    def test_render_empty_queue(self) -> None:
        """Test rendering with no pending tasks."""
        complete = make_task(status=TaskStatus.COMPLETE)
        phase = make_phase(tasks=[complete])
        plan = make_plan(phases=[phase])
        widget = TaskQueueWidget(plan=plan)

        result = widget._render_queue()

        assert "No pending tasks" in str(result)

    def test_render_header_with_count(self) -> None:
        """Test header shows task count."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.PENDING),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskQueueWidget(plan=plan)

        result = widget._render_queue()

        assert "Task Queue" in str(result)
        assert "2 left" in str(result)

    def test_render_available_task(self) -> None:
        """Test available task uses ○ icon."""
        task = make_task(status=TaskStatus.PENDING)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = TaskQueueWidget(plan=plan)

        result = widget._render_task(task, is_selected=False)

        assert "○" in str(result)

    def test_render_blocked_task(self) -> None:
        """Test blocked task uses ⊘ icon and shows blockers."""
        dep = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep, blocked])
        plan = make_plan(phases=[phase])
        widget = TaskQueueWidget(plan=plan)

        result = widget._render_task(blocked, is_selected=False)

        assert "⊘" in str(result)
        assert "blocked by 1.1" in str(result)

    def test_render_selected_task(self) -> None:
        """Test selected task has selection indicator."""
        task = make_task(status=TaskStatus.PENDING)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = TaskQueueWidget(plan=plan)

        result = widget._render_task(task, is_selected=True)

        assert "▸" in str(result)


class TestTaskQueueRefresh:
    """Tests for plan refresh functionality."""

    def test_refresh_plan_updates_tasks(self) -> None:
        """Test refreshing the plan updates visible tasks."""
        widget = TaskQueueWidget()

        task = make_task(status=TaskStatus.PENDING)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        with patch.object(widget, "update"):
            widget.refresh_plan(plan)

        assert len(widget._visible_tasks) == 1
        assert widget._visible_tasks[0] == task

    def test_refresh_plan_clamps_selection(self) -> None:
        """Test refresh clamps selection index to valid range."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.PENDING),
            make_task(task_id="1.2", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskQueueWidget(plan=plan)
        widget._selected_index = 1

        # New plan with only one pending task
        new_task = make_task(task_id="2.1", status=TaskStatus.PENDING)
        new_phase = make_phase(tasks=[new_task])
        new_plan = make_plan(phases=[new_phase])

        with patch.object(widget, "update"):
            widget.refresh_plan(new_plan)

        assert widget._selected_index == 0
