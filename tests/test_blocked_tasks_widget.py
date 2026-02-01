"""Tests for the BlockedTasksWidget."""

from unittest.mock import patch

import pytest

from iterm_controller.models import Phase, Plan, Task, TaskStatus
from iterm_controller.widgets.blocked_tasks import BlockedTasksWidget


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


class TestBlockedTasksWidgetInit:
    """Tests for BlockedTasksWidget initialization."""

    def test_init_empty(self) -> None:
        """Test widget initializes with empty plan."""
        widget = BlockedTasksWidget()

        assert widget.plan.phases == []
        assert widget.get_blocked_tasks() == []

    def test_init_with_plan(self) -> None:
        """Test widget initializes with provided plan."""
        task = make_task(status=TaskStatus.PENDING)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = BlockedTasksWidget(plan=plan)

        assert len(widget.plan.phases) == 1


class TestBlockedTasksDetection:
    """Tests for blocked task detection."""

    def test_task_not_blocked_without_depends(self) -> None:
        """Test task without dependencies is not blocked."""
        task = make_task(depends=[])
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        assert not widget.is_task_blocked(task)

    def test_task_blocked_with_incomplete_dependency(self) -> None:
        """Test task is blocked when dependency is incomplete."""
        dep_task = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked_task = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep_task, blocked_task])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        assert widget.is_task_blocked(blocked_task)

    def test_task_not_blocked_with_complete_dependency(self) -> None:
        """Test task is not blocked when dependency is complete."""
        dep_task = make_task(task_id="1.1", status=TaskStatus.COMPLETE)
        task = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep_task, task])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        assert not widget.is_task_blocked(task)

    def test_task_blocked_with_skipped_dependency_is_not_blocked(self) -> None:
        """Test task with skipped dependency is not blocked."""
        dep_task = make_task(task_id="1.1", status=TaskStatus.SKIPPED)
        task = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep_task, task])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        assert not widget.is_task_blocked(task)

    def test_task_with_blocked_status_is_blocked(self) -> None:
        """Test task with BLOCKED status is considered blocked."""
        task = make_task(status=TaskStatus.BLOCKED)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        assert widget.is_task_blocked(task)


class TestGetBlockedTasks:
    """Tests for get_blocked_tasks method."""

    def test_get_blocked_tasks_empty(self) -> None:
        """Test get_blocked_tasks with no blocked tasks."""
        task = make_task(status=TaskStatus.PENDING)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        blocked = widget.get_blocked_tasks()

        assert blocked == []

    def test_get_blocked_tasks_with_blocked(self) -> None:
        """Test get_blocked_tasks returns blocked tasks."""
        available = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked = make_task(task_id="1.2", status=TaskStatus.PENDING, depends=["1.1"])
        phase = make_phase(tasks=[available, blocked])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        blocked_tasks = widget.get_blocked_tasks()

        assert len(blocked_tasks) == 1
        assert blocked_tasks[0].id == "1.2"

    def test_get_blocked_tasks_ignores_complete_tasks(self) -> None:
        """Test get_blocked_tasks ignores complete tasks."""
        complete = make_task(task_id="1.1", status=TaskStatus.COMPLETE)
        phase = make_phase(tasks=[complete])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        blocked = widget.get_blocked_tasks()

        assert blocked == []


class TestGetBlockingTaskIds:
    """Tests for get_blocking_task_ids method."""

    def test_get_blocking_task_ids_none(self) -> None:
        """Test task with no dependencies returns empty list."""
        task = make_task(depends=[])
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        blockers = widget.get_blocking_task_ids(task)

        assert blockers == []

    def test_get_blocking_task_ids_with_blockers(self) -> None:
        """Test returns IDs of incomplete dependencies."""
        dep1 = make_task(task_id="1.1", status=TaskStatus.PENDING)
        dep2 = make_task(task_id="1.2", status=TaskStatus.COMPLETE)
        blocked = make_task(task_id="1.3", depends=["1.1", "1.2"])
        phase = make_phase(tasks=[dep1, dep2, blocked])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        blockers = widget.get_blocking_task_ids(blocked)

        assert "1.1" in blockers
        assert "1.2" not in blockers


class TestDependencyChain:
    """Tests for get_dependency_chain method."""

    def test_dependency_chain_simple(self) -> None:
        """Test simple dependency chain."""
        dep = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep, blocked])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        chain = widget.get_dependency_chain(blocked)

        assert len(chain) == 2
        # First is the dependency, then the blocked task
        assert chain[0][0].id == "1.1"
        assert chain[1][0].id == "1.2"

    def test_dependency_chain_nested(self) -> None:
        """Test nested dependency chain."""
        dep1 = make_task(task_id="1.1", status=TaskStatus.PENDING)
        dep2 = make_task(task_id="1.2", status=TaskStatus.PENDING, depends=["1.1"])
        blocked = make_task(task_id="1.3", depends=["1.2"])
        phase = make_phase(tasks=[dep1, dep2, blocked])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        chain = widget.get_dependency_chain(blocked)

        assert len(chain) == 3
        # Order: 1.1 (no deps), 1.2 (depends on 1.1), 1.3 (depends on 1.2)
        assert chain[0][0].id == "1.1"
        assert chain[1][0].id == "1.2"
        assert chain[2][0].id == "1.3"

    def test_dependency_chain_no_blockers(self) -> None:
        """Test task with no blockers."""
        task = make_task(task_id="1.1", status=TaskStatus.PENDING)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        chain = widget.get_dependency_chain(task)

        assert len(chain) == 1
        assert chain[0][0].id == "1.1"
        assert chain[0][1] == []  # No blockers


class TestRendering:
    """Tests for BlockedTasksWidget rendering."""

    def test_render_empty(self) -> None:
        """Test rendering with no blocked tasks."""
        task = make_task(status=TaskStatus.PENDING)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        result = widget._render_blocked()

        assert "Blocked: 0" in str(result)
        assert "No blocked tasks" in str(result)

    def test_render_with_blocked(self) -> None:
        """Test rendering with blocked tasks."""
        dep = make_task(task_id="1.1", title="Auth middleware", status=TaskStatus.PENDING)
        blocked = make_task(
            task_id="1.2",
            title="Login form",
            status=TaskStatus.PENDING,
            depends=["1.1"],
        )
        phase = make_phase(tasks=[dep, blocked])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        result = widget._render_blocked()
        result_str = str(result)

        assert "Blocked: 1" in result_str
        assert "1.2" in result_str
        assert "1.1" in result_str
        assert "←" in result_str

    def test_render_truncates_long_titles(self) -> None:
        """Test rendering truncates very long task titles."""
        dep = make_task(task_id="1.1", status=TaskStatus.PENDING)
        long_title = "This is a very long task title that should be truncated"
        blocked = make_task(
            task_id="1.2",
            title=long_title,
            depends=["1.1"],
        )
        phase = make_phase(tasks=[dep, blocked])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        result = widget._render_blocked()
        result_str = str(result)

        # Title should be truncated
        assert "..." in result_str


class TestRefreshPlan:
    """Tests for plan refresh functionality."""

    def test_refresh_plan_updates_blocked(self) -> None:
        """Test refreshing the plan updates blocked tasks."""
        widget = BlockedTasksWidget()

        dep = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep, blocked])
        plan = make_plan(phases=[phase])

        # Mock update to avoid needing an app context
        with patch.object(widget, "update"):
            widget.refresh_plan(plan)

        assert len(widget.get_blocked_tasks()) == 1

    def test_refresh_plan_clears_on_completion(self) -> None:
        """Test blocked tasks cleared when dependencies complete."""
        dep = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep, blocked])
        plan = make_plan(phases=[phase])
        widget = BlockedTasksWidget(plan=plan)

        # Verify blocked initially
        assert len(widget.get_blocked_tasks()) == 1

        # Complete the dependency
        dep_complete = make_task(task_id="1.1", status=TaskStatus.COMPLETE)
        unblocked = make_task(task_id="1.2", depends=["1.1"])
        new_phase = make_phase(tasks=[dep_complete, unblocked])
        new_plan = make_plan(phases=[new_phase])

        # Mock update to avoid needing an app context
        with patch.object(widget, "update"):
            widget.refresh_plan(new_plan)

        assert len(widget.get_blocked_tasks()) == 0
