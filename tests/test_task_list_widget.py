"""Tests for the TaskListWidget."""

from unittest.mock import patch

import pytest

from iterm_controller.models import Phase, Plan, Task, TaskStatus
from iterm_controller.state import PlanReloaded, TaskStatusChanged
from iterm_controller.widgets.task_list import TaskListWidget


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


class TestTaskListWidget:
    """Tests for TaskListWidget initialization."""

    def test_init_empty(self) -> None:
        """Test widget initializes with empty plan."""
        widget = TaskListWidget()

        assert widget.plan.phases == []

    def test_init_with_plan(self) -> None:
        """Test widget initializes with provided plan."""
        task = make_task()
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = TaskListWidget(plan=plan)

        assert len(widget.plan.phases) == 1
        assert len(widget.plan.phases[0].tasks) == 1

    def test_init_with_collapsed_phases(self) -> None:
        """Test widget initializes with collapsed phases."""
        widget = TaskListWidget(collapsed_phases={"1", "2"})

        assert "1" in widget._collapsed_phases
        assert "2" in widget._collapsed_phases

    def test_refresh_plan(self) -> None:
        """Test refreshing the plan."""
        widget = TaskListWidget()

        task = make_task()
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        # Mock update() to avoid needing an active app
        with patch.object(widget, "update"):
            widget.refresh_plan(plan)

        assert len(widget.plan.phases) == 1


class TestPhaseCollapse:
    """Tests for phase collapse functionality."""

    def test_toggle_phase_collapses(self) -> None:
        """Test toggle_phase collapses an expanded phase."""
        widget = TaskListWidget()

        with patch.object(widget, "update"):
            widget.toggle_phase("1")

        assert "1" in widget._collapsed_phases

    def test_toggle_phase_expands(self) -> None:
        """Test toggle_phase expands a collapsed phase."""
        widget = TaskListWidget(collapsed_phases={"1"})

        with patch.object(widget, "update"):
            widget.toggle_phase("1")

        assert "1" not in widget._collapsed_phases

    def test_toggle_phase_independent(self) -> None:
        """Test toggling one phase doesn't affect others."""
        widget = TaskListWidget(collapsed_phases={"2"})

        with patch.object(widget, "update"):
            widget.toggle_phase("1")

        assert "1" in widget._collapsed_phases
        assert "2" in widget._collapsed_phases


class TestBlockedTasks:
    """Tests for blocked task detection."""

    def test_task_not_blocked_without_depends(self) -> None:
        """Test task without dependencies is not blocked."""
        task = make_task(depends=[])
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        assert not widget.is_task_blocked(task)

    def test_task_blocked_with_incomplete_dependency(self) -> None:
        """Test task is blocked when dependency is incomplete."""
        dep_task = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked_task = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep_task, blocked_task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        assert widget.is_task_blocked(blocked_task)

    def test_task_not_blocked_with_complete_dependency(self) -> None:
        """Test task is not blocked when dependency is complete."""
        dep_task = make_task(task_id="1.1", status=TaskStatus.COMPLETE)
        task = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep_task, task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        assert not widget.is_task_blocked(task)

    def test_task_not_blocked_with_skipped_dependency(self) -> None:
        """Test task is not blocked when dependency is skipped."""
        dep_task = make_task(task_id="1.1", status=TaskStatus.SKIPPED)
        task = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep_task, task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        assert not widget.is_task_blocked(task)

    def test_task_blocked_with_status_blocked(self) -> None:
        """Test task with BLOCKED status is blocked."""
        task = make_task(status=TaskStatus.BLOCKED)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        assert widget.is_task_blocked(task)

    def test_get_blocking_tasks(self) -> None:
        """Test get_blocking_tasks returns correct blockers."""
        dep1 = make_task(task_id="1.1", status=TaskStatus.PENDING)
        dep2 = make_task(task_id="1.2", status=TaskStatus.COMPLETE)
        dep3 = make_task(task_id="1.3", status=TaskStatus.IN_PROGRESS)
        blocked_task = make_task(task_id="1.4", depends=["1.1", "1.2", "1.3"])
        phase = make_phase(tasks=[dep1, dep2, dep3, blocked_task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        blockers = widget.get_blocking_tasks(blocked_task)

        assert "1.1" in blockers
        assert "1.2" not in blockers  # Complete, not blocking
        assert "1.3" in blockers

    def test_get_blocking_tasks_handles_missing_dependency(self) -> None:
        """Test get_blocking_tasks handles references to non-existent tasks."""
        task = make_task(task_id="1.1", depends=["nonexistent"])
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        blockers = widget.get_blocking_tasks(task)

        # Non-existent dependencies don't appear in blockers
        assert blockers == []


class TestStatusIcons:
    """Tests for status icon rendering."""

    def test_pending_icon(self) -> None:
        """Test PENDING status uses correct icon."""
        widget = TaskListWidget()
        icon = widget._get_status_icon(TaskStatus.PENDING)

        assert icon == "○"

    def test_in_progress_icon(self) -> None:
        """Test IN_PROGRESS status uses correct icon."""
        widget = TaskListWidget()
        icon = widget._get_status_icon(TaskStatus.IN_PROGRESS)

        assert icon == "●"

    def test_complete_icon(self) -> None:
        """Test COMPLETE status uses correct icon."""
        widget = TaskListWidget()
        icon = widget._get_status_icon(TaskStatus.COMPLETE)

        assert icon == "✓"

    def test_skipped_icon(self) -> None:
        """Test SKIPPED status uses correct icon."""
        widget = TaskListWidget()
        icon = widget._get_status_icon(TaskStatus.SKIPPED)

        assert icon == "⊖"

    def test_blocked_icon(self) -> None:
        """Test BLOCKED status uses correct icon."""
        widget = TaskListWidget()
        icon = widget._get_status_icon(TaskStatus.BLOCKED)

        assert icon == "⊘"


class TestStatusColors:
    """Tests for status color assignment."""

    def test_pending_color(self) -> None:
        """Test PENDING status uses white color."""
        widget = TaskListWidget()
        color = widget._get_status_color(TaskStatus.PENDING)

        assert color == "white"

    def test_in_progress_color(self) -> None:
        """Test IN_PROGRESS status uses yellow color."""
        widget = TaskListWidget()
        color = widget._get_status_color(TaskStatus.IN_PROGRESS)

        assert color == "yellow"

    def test_complete_color(self) -> None:
        """Test COMPLETE status uses green color."""
        widget = TaskListWidget()
        color = widget._get_status_color(TaskStatus.COMPLETE)

        assert color == "green"

    def test_blocked_color(self) -> None:
        """Test BLOCKED status uses dim color."""
        widget = TaskListWidget()
        color = widget._get_status_color(TaskStatus.BLOCKED)

        assert color == "dim"


class TestTaskRendering:
    """Tests for task row rendering."""

    def test_render_empty_shows_message(self) -> None:
        """Test rendering with no tasks shows placeholder."""
        widget = TaskListWidget()
        result = widget._render_plan()

        assert "No tasks" in str(result)

    def test_render_task_includes_icon(self) -> None:
        """Test rendered task includes status icon."""
        task = make_task(status=TaskStatus.IN_PROGRESS)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        text = widget._render_task(task)

        assert "●" in str(text)

    def test_render_task_includes_id_and_title(self) -> None:
        """Test rendered task includes task ID and title."""
        task = make_task(task_id="2.1", title="Add auth")
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        text = widget._render_task(task)

        assert "2.1" in str(text)
        assert "Add auth" in str(text)

    def test_render_blocked_task_shows_blockers(self) -> None:
        """Test blocked task shows 'blocked by X' suffix."""
        dep = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked = make_task(task_id="1.2", title="Blocked Task", depends=["1.1"])
        phase = make_phase(tasks=[dep, blocked])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        text = widget._render_task(blocked)

        assert "blocked by 1.1" in str(text)

    def test_render_blocked_task_shows_multiple_blockers(self) -> None:
        """Test blocked task shows all blockers."""
        dep1 = make_task(task_id="1.1", status=TaskStatus.PENDING)
        dep2 = make_task(task_id="1.2", status=TaskStatus.IN_PROGRESS)
        blocked = make_task(task_id="1.3", depends=["1.1", "1.2"])
        phase = make_phase(tasks=[dep1, dep2, blocked])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        text = widget._render_task(blocked)

        assert "1.1" in str(text)
        assert "1.2" in str(text)

    def test_render_in_progress_task_shows_status(self) -> None:
        """Test in-progress task shows status text."""
        task = make_task(status=TaskStatus.IN_PROGRESS)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        text = widget._render_task(task)

        assert "In Progress" in str(text)

    def test_render_complete_task_shows_done(self) -> None:
        """Test complete task shows Done status."""
        task = make_task(status=TaskStatus.COMPLETE)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        text = widget._render_task(task)

        assert "Done" in str(text)


class TestPhaseRendering:
    """Tests for phase header rendering."""

    def test_render_phase_header_includes_title(self) -> None:
        """Test phase header includes title."""
        phase = make_phase(phase_id="1", title="Phase 1: Setup")
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        text = widget._render_phase_header(phase)

        assert "Phase 1: Setup" in str(text)

    def test_render_phase_header_shows_progress(self) -> None:
        """Test phase header shows completion progress."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.COMPLETE),
            make_task(task_id="1.2", status=TaskStatus.COMPLETE),
            make_task(task_id="1.3", status=TaskStatus.PENDING),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        text = widget._render_phase_header(phase)

        assert "2/3" in str(text)

    def test_render_expanded_phase_uses_down_arrow(self) -> None:
        """Test expanded phase uses down arrow icon."""
        phase = make_phase(phase_id="1")
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)  # Not collapsed

        text = widget._render_phase_header(phase)

        assert "▼" in str(text)

    def test_render_collapsed_phase_uses_right_arrow(self) -> None:
        """Test collapsed phase uses right arrow icon."""
        phase = make_phase(phase_id="1")
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan, collapsed_phases={"1"})

        text = widget._render_phase_header(phase)

        assert "▶" in str(text)


class TestPlanRendering:
    """Tests for full plan rendering."""

    def test_render_plan_includes_all_phases(self) -> None:
        """Test rendered plan includes all phases."""
        phase1 = make_phase(phase_id="1", title="Phase 1")
        phase2 = make_phase(phase_id="2", title="Phase 2")
        plan = make_plan(phases=[phase1, phase2])
        widget = TaskListWidget(plan=plan)

        text = widget._render_plan()

        assert "Phase 1" in str(text)
        assert "Phase 2" in str(text)

    def test_render_collapsed_phase_hides_tasks(self) -> None:
        """Test collapsed phase doesn't show tasks."""
        task = make_task(task_id="1.1", title="Hidden Task")
        phase = make_phase(phase_id="1", title="Phase 1", tasks=[task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan, collapsed_phases={"1"})

        text = widget._render_plan()

        assert "Phase 1" in str(text)
        assert "Hidden Task" not in str(text)

    def test_render_expanded_phase_shows_tasks(self) -> None:
        """Test expanded phase shows tasks."""
        task = make_task(task_id="1.1", title="Visible Task")
        phase = make_phase(phase_id="1", title="Phase 1", tasks=[task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)  # Not collapsed

        text = widget._render_plan()

        assert "Phase 1" in str(text)
        assert "Visible Task" in str(text)


class TestEventHandlers:
    """Tests for event handler methods."""

    def test_on_plan_reloaded_updates_plan(self) -> None:
        """Test on_plan_reloaded updates the widget's plan."""
        widget = TaskListWidget()

        task = make_task()
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        message = PlanReloaded(project_id="test", plan=plan)

        # Mock update() to avoid needing an active app
        with patch.object(widget, "update"):
            widget.on_plan_reloaded(message)

        assert len(widget.plan.phases) == 1

    def test_on_task_status_changed_triggers_update(self) -> None:
        """Test on_task_status_changed triggers re-render."""
        task = make_task()
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        message = TaskStatusChanged(task_id="1.1", project_id="test")

        with patch.object(widget, "update") as mock_update:
            widget.on_task_status_changed(message)
            mock_update.assert_called_once()


class TestHelperMethods:
    """Tests for helper methods."""

    def test_get_task_by_id_found(self) -> None:
        """Test get_task_by_id returns task when found."""
        task = make_task(task_id="1.1")
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        found = widget.get_task_by_id("1.1")

        assert found is not None
        assert found.id == "1.1"

    def test_get_task_by_id_not_found(self) -> None:
        """Test get_task_by_id returns None when not found."""
        task = make_task(task_id="1.1")
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        found = widget.get_task_by_id("nonexistent")

        assert found is None

    def test_get_pending_tasks(self) -> None:
        """Test get_pending_tasks returns pending non-blocked tasks."""
        pending = make_task(task_id="1.1", status=TaskStatus.PENDING)
        complete = make_task(task_id="1.2", status=TaskStatus.COMPLETE)
        blocked_pending = make_task(
            task_id="1.3", status=TaskStatus.PENDING, depends=["1.1"]
        )
        phase = make_phase(tasks=[pending, complete, blocked_pending])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        pending_tasks = widget.get_pending_tasks()

        assert len(pending_tasks) == 1
        assert pending_tasks[0].id == "1.1"

    def test_get_in_progress_tasks(self) -> None:
        """Test get_in_progress_tasks returns in-progress tasks."""
        pending = make_task(task_id="1.1", status=TaskStatus.PENDING)
        in_progress = make_task(task_id="1.2", status=TaskStatus.IN_PROGRESS)
        complete = make_task(task_id="1.3", status=TaskStatus.COMPLETE)
        phase = make_phase(tasks=[pending, in_progress, complete])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        in_progress_tasks = widget.get_in_progress_tasks()

        assert len(in_progress_tasks) == 1
        assert in_progress_tasks[0].id == "1.2"

    def test_get_blocked_tasks(self) -> None:
        """Test get_blocked_tasks returns all blocked tasks."""
        dep = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked1 = make_task(task_id="1.2", depends=["1.1"])
        blocked2 = make_task(task_id="1.3", depends=["1.1"])
        phase = make_phase(tasks=[dep, blocked1, blocked2])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        blocked_tasks = widget.get_blocked_tasks()

        assert len(blocked_tasks) == 2
        assert blocked_tasks[0].id == "1.2"
        assert blocked_tasks[1].id == "1.3"

    def test_get_blocked_tasks_empty_when_none(self) -> None:
        """Test get_blocked_tasks returns empty list when no blocked tasks."""
        task = make_task(status=TaskStatus.PENDING)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = TaskListWidget(plan=plan)

        blocked_tasks = widget.get_blocked_tasks()

        assert blocked_tasks == []
