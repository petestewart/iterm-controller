"""Tests for the TaskDependencyResolver utility."""

import pytest

from iterm_controller.models import Phase, Plan, Task, TaskStatus
from iterm_controller.task_dependency import TaskDependencyResolver


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


class TestTaskDependencyResolverInit:
    """Tests for TaskDependencyResolver initialization."""

    def test_init_with_none_plan(self) -> None:
        """Test resolver initializes with None plan."""
        resolver = TaskDependencyResolver(None)
        assert resolver.plan.phases == []

    def test_init_with_empty_plan(self) -> None:
        """Test resolver initializes with empty plan."""
        resolver = TaskDependencyResolver(Plan())
        assert resolver.plan.phases == []

    def test_init_with_plan(self) -> None:
        """Test resolver initializes with provided plan."""
        task = make_task()
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        resolver = TaskDependencyResolver(plan)

        assert len(resolver.plan.phases) == 1
        assert len(resolver.plan.phases[0].tasks) == 1

    def test_update_plan(self) -> None:
        """Test updating the plan."""
        resolver = TaskDependencyResolver(Plan())
        assert resolver.plan.phases == []

        task = make_task()
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        resolver.update_plan(plan)

        assert len(resolver.plan.phases) == 1


class TestGetTaskById:
    """Tests for get_task_by_id method."""

    def test_get_task_found(self) -> None:
        """Test get_task_by_id returns task when found."""
        task = make_task(task_id="1.1")
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        found = resolver.get_task_by_id("1.1")

        assert found is not None
        assert found.id == "1.1"

    def test_get_task_not_found(self) -> None:
        """Test get_task_by_id returns None when not found."""
        task = make_task(task_id="1.1")
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        found = resolver.get_task_by_id("nonexistent")

        assert found is None

    def test_get_task_across_phases(self) -> None:
        """Test get_task_by_id finds tasks in different phases."""
        task1 = make_task(task_id="1.1")
        task2 = make_task(task_id="2.1")
        phase1 = make_phase(phase_id="1", tasks=[task1])
        phase2 = make_phase(phase_id="2", tasks=[task2])
        plan = make_plan(phases=[phase1, phase2])
        resolver = TaskDependencyResolver(plan)

        found1 = resolver.get_task_by_id("1.1")
        found2 = resolver.get_task_by_id("2.1")

        assert found1 is not None
        assert found1.id == "1.1"
        assert found2 is not None
        assert found2.id == "2.1"


class TestIsTaskBlocked:
    """Tests for is_task_blocked method."""

    def test_task_not_blocked_without_depends(self) -> None:
        """Test task without dependencies is not blocked."""
        task = make_task(depends=[])
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        assert not resolver.is_task_blocked(task)

    def test_task_blocked_with_pending_dependency(self) -> None:
        """Test task is blocked when dependency is pending."""
        dep_task = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked_task = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep_task, blocked_task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        assert resolver.is_task_blocked(blocked_task)

    def test_task_blocked_with_in_progress_dependency(self) -> None:
        """Test task is blocked when dependency is in progress."""
        dep_task = make_task(task_id="1.1", status=TaskStatus.IN_PROGRESS)
        blocked_task = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep_task, blocked_task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        assert resolver.is_task_blocked(blocked_task)

    def test_task_not_blocked_with_complete_dependency(self) -> None:
        """Test task is not blocked when dependency is complete."""
        dep_task = make_task(task_id="1.1", status=TaskStatus.COMPLETE)
        task = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep_task, task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        assert not resolver.is_task_blocked(task)

    def test_task_not_blocked_with_skipped_dependency(self) -> None:
        """Test task is not blocked when dependency is skipped."""
        dep_task = make_task(task_id="1.1", status=TaskStatus.SKIPPED)
        task = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep_task, task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        assert not resolver.is_task_blocked(task)

    def test_task_blocked_with_status_blocked(self) -> None:
        """Test task with BLOCKED status is blocked."""
        task = make_task(status=TaskStatus.BLOCKED)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        assert resolver.is_task_blocked(task)

    def test_task_blocked_if_any_dependency_incomplete(self) -> None:
        """Test task is blocked if any dependency is incomplete."""
        dep1 = make_task(task_id="1.1", status=TaskStatus.COMPLETE)
        dep2 = make_task(task_id="1.2", status=TaskStatus.PENDING)
        task = make_task(task_id="1.3", depends=["1.1", "1.2"])
        phase = make_phase(tasks=[dep1, dep2, task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        assert resolver.is_task_blocked(task)

    def test_task_not_blocked_with_missing_dependency(self) -> None:
        """Test task is not blocked if dependency doesn't exist."""
        task = make_task(task_id="1.1", depends=["nonexistent"])
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        # Non-existent dependencies don't block
        assert not resolver.is_task_blocked(task)


class TestGetBlockingTasks:
    """Tests for get_blocking_tasks method."""

    def test_get_blocking_tasks_returns_incomplete(self) -> None:
        """Test get_blocking_tasks returns incomplete dependencies."""
        dep1 = make_task(task_id="1.1", status=TaskStatus.PENDING)
        dep2 = make_task(task_id="1.2", status=TaskStatus.COMPLETE)
        dep3 = make_task(task_id="1.3", status=TaskStatus.IN_PROGRESS)
        blocked_task = make_task(task_id="1.4", depends=["1.1", "1.2", "1.3"])
        phase = make_phase(tasks=[dep1, dep2, dep3, blocked_task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        blockers = resolver.get_blocking_tasks(blocked_task)

        assert "1.1" in blockers
        assert "1.2" not in blockers  # Complete, not blocking
        assert "1.3" in blockers

    def test_get_blocking_tasks_empty_when_all_complete(self) -> None:
        """Test get_blocking_tasks returns empty when all deps complete."""
        dep1 = make_task(task_id="1.1", status=TaskStatus.COMPLETE)
        dep2 = make_task(task_id="1.2", status=TaskStatus.SKIPPED)
        task = make_task(task_id="1.3", depends=["1.1", "1.2"])
        phase = make_phase(tasks=[dep1, dep2, task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        blockers = resolver.get_blocking_tasks(task)

        assert blockers == []

    def test_get_blocking_tasks_handles_missing_dependency(self) -> None:
        """Test get_blocking_tasks ignores non-existent dependencies."""
        task = make_task(task_id="1.1", depends=["nonexistent"])
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        blockers = resolver.get_blocking_tasks(task)

        assert blockers == []

    def test_get_blocking_tasks_preserves_order(self) -> None:
        """Test get_blocking_tasks preserves dependency order."""
        dep1 = make_task(task_id="1.1", status=TaskStatus.PENDING)
        dep2 = make_task(task_id="1.2", status=TaskStatus.PENDING)
        dep3 = make_task(task_id="1.3", status=TaskStatus.PENDING)
        task = make_task(task_id="1.4", depends=["1.1", "1.2", "1.3"])
        phase = make_phase(tasks=[dep1, dep2, dep3, task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        blockers = resolver.get_blocking_tasks(task)

        assert blockers == ["1.1", "1.2", "1.3"]


class TestGetDependencyChain:
    """Tests for get_dependency_chain method."""

    def test_single_blocker(self) -> None:
        """Test chain with single blocker."""
        dep = make_task(task_id="1.1", status=TaskStatus.PENDING)
        task = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep, task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        chain = resolver.get_dependency_chain(task)

        # Chain should include dep (no blockers) and task (blocked by 1.1)
        assert len(chain) == 2
        assert chain[0][0].id == "1.1"
        assert chain[0][1] == []
        assert chain[1][0].id == "1.2"
        assert chain[1][1] == ["1.1"]

    def test_chain_with_transitive_dependencies(self) -> None:
        """Test chain with transitive dependencies."""
        task1 = make_task(task_id="1.1", status=TaskStatus.PENDING)
        task2 = make_task(task_id="1.2", status=TaskStatus.PENDING, depends=["1.1"])
        task3 = make_task(task_id="1.3", status=TaskStatus.PENDING, depends=["1.2"])
        phase = make_phase(tasks=[task1, task2, task3])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        chain = resolver.get_dependency_chain(task3)

        # Should show: 1.1 (root), then 1.2, then 1.3
        assert len(chain) == 3
        assert chain[0][0].id == "1.1"
        assert chain[1][0].id == "1.2"
        assert chain[2][0].id == "1.3"

    def test_chain_handles_diamond_dependency(self) -> None:
        """Test chain with diamond dependency pattern doesn't duplicate."""
        #     1.1
        #    /   \
        #   1.2  1.3
        #    \   /
        #     1.4
        task1 = make_task(task_id="1.1", status=TaskStatus.PENDING)
        task2 = make_task(task_id="1.2", status=TaskStatus.PENDING, depends=["1.1"])
        task3 = make_task(task_id="1.3", status=TaskStatus.PENDING, depends=["1.1"])
        task4 = make_task(task_id="1.4", status=TaskStatus.PENDING, depends=["1.2", "1.3"])
        phase = make_phase(tasks=[task1, task2, task3, task4])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        chain = resolver.get_dependency_chain(task4)

        # Should include each task once
        task_ids = [t[0].id for t in chain]
        assert len(task_ids) == 4
        assert len(set(task_ids)) == 4  # No duplicates

    def test_chain_no_blockers(self) -> None:
        """Test chain for task with no dependencies."""
        task = make_task(task_id="1.1", status=TaskStatus.PENDING)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        chain = resolver.get_dependency_chain(task)

        # Just the task itself, no blockers
        assert len(chain) == 1
        assert chain[0][0].id == "1.1"
        assert chain[0][1] == []


class TestGetAllBlockedTasks:
    """Tests for get_all_blocked_tasks method."""

    def test_no_blocked_tasks(self) -> None:
        """Test when no tasks are blocked."""
        task1 = make_task(task_id="1.1", status=TaskStatus.PENDING)
        task2 = make_task(task_id="1.2", status=TaskStatus.COMPLETE)
        phase = make_phase(tasks=[task1, task2])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        blocked = resolver.get_all_blocked_tasks()

        assert blocked == []

    def test_returns_blocked_by_status(self) -> None:
        """Test returns tasks with BLOCKED status."""
        task = make_task(task_id="1.1", status=TaskStatus.BLOCKED)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        blocked = resolver.get_all_blocked_tasks()

        assert len(blocked) == 1
        assert blocked[0].id == "1.1"

    def test_returns_blocked_by_dependency(self) -> None:
        """Test returns tasks blocked by incomplete dependencies."""
        dep = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked_task = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep, blocked_task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        blocked = resolver.get_all_blocked_tasks()

        assert len(blocked) == 1
        assert blocked[0].id == "1.2"

    def test_multiple_blocked_tasks(self) -> None:
        """Test returns all blocked tasks."""
        dep = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked1 = make_task(task_id="1.2", depends=["1.1"])
        blocked2 = make_task(task_id="1.3", depends=["1.1"])
        phase = make_phase(tasks=[dep, blocked1, blocked2])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        blocked = resolver.get_all_blocked_tasks()

        assert len(blocked) == 2
        ids = {t.id for t in blocked}
        assert ids == {"1.2", "1.3"}


class TestGetAvailableTasks:
    """Tests for get_available_tasks method."""

    def test_pending_task_is_available(self) -> None:
        """Test pending task without dependencies is available."""
        task = make_task(task_id="1.1", status=TaskStatus.PENDING)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        available = resolver.get_available_tasks()

        assert len(available) == 1
        assert available[0].id == "1.1"

    def test_blocked_task_not_available(self) -> None:
        """Test blocked task is not available."""
        dep = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep, blocked])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        available = resolver.get_available_tasks()

        assert len(available) == 1
        assert available[0].id == "1.1"

    def test_complete_task_not_available(self) -> None:
        """Test complete task is not available."""
        task = make_task(task_id="1.1", status=TaskStatus.COMPLETE)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        available = resolver.get_available_tasks()

        assert available == []

    def test_in_progress_task_not_available(self) -> None:
        """Test in-progress task is not available."""
        task = make_task(task_id="1.1", status=TaskStatus.IN_PROGRESS)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        available = resolver.get_available_tasks()

        assert available == []


class TestGetInProgressTasks:
    """Tests for get_in_progress_tasks method."""

    def test_returns_in_progress(self) -> None:
        """Test returns in-progress tasks."""
        pending = make_task(task_id="1.1", status=TaskStatus.PENDING)
        in_progress = make_task(task_id="1.2", status=TaskStatus.IN_PROGRESS)
        complete = make_task(task_id="1.3", status=TaskStatus.COMPLETE)
        phase = make_phase(tasks=[pending, in_progress, complete])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        in_progress_tasks = resolver.get_in_progress_tasks()

        assert len(in_progress_tasks) == 1
        assert in_progress_tasks[0].id == "1.2"

    def test_empty_when_none_in_progress(self) -> None:
        """Test returns empty when no tasks in progress."""
        task = make_task(task_id="1.1", status=TaskStatus.PENDING)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        in_progress_tasks = resolver.get_in_progress_tasks()

        assert in_progress_tasks == []

    def test_multiple_in_progress(self) -> None:
        """Test returns all in-progress tasks."""
        task1 = make_task(task_id="1.1", status=TaskStatus.IN_PROGRESS)
        task2 = make_task(task_id="1.2", status=TaskStatus.IN_PROGRESS)
        phase = make_phase(tasks=[task1, task2])
        plan = make_plan(phases=[phase])
        resolver = TaskDependencyResolver(plan)

        in_progress_tasks = resolver.get_in_progress_tasks()

        assert len(in_progress_tasks) == 2
        ids = {t.id for t in in_progress_tasks}
        assert ids == {"1.1", "1.2"}
