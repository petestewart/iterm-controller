"""Tests for the DependencyChainModal."""

import pytest

from iterm_controller.models import Phase, Plan, Task, TaskStatus
from iterm_controller.screens.modals.dependency_chain import DependencyChainModal


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


class TestDependencyChainModalInit:
    """Tests for DependencyChainModal initialization."""

    def test_init_with_task_and_plan(self) -> None:
        """Test modal initializes with task and plan."""
        blocked = make_task(task_id="1.2", title="Login form", depends=["1.1"])
        dep = make_task(task_id="1.1", title="Auth middleware")
        phase = make_phase(tasks=[dep, blocked])
        plan = make_plan(phases=[phase])

        modal = DependencyChainModal(blocked, plan)

        assert modal._task == blocked
        assert modal._plan == plan
        assert "1.1" in modal._task_lookup
        assert "1.2" in modal._task_lookup


class TestGetDependencyChain:
    """Tests for dependency chain building."""

    def test_simple_chain(self) -> None:
        """Test simple dependency chain."""
        dep = make_task(task_id="1.1", status=TaskStatus.PENDING)
        blocked = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep, blocked])
        plan = make_plan(phases=[phase])
        modal = DependencyChainModal(blocked, plan)

        chain = modal._get_dependency_chain(blocked)

        assert len(chain) == 2
        assert chain[0][0].id == "1.1"
        assert chain[1][0].id == "1.2"

    def test_nested_chain(self) -> None:
        """Test nested dependency chain."""
        dep1 = make_task(task_id="1.1", status=TaskStatus.PENDING)
        dep2 = make_task(task_id="1.2", status=TaskStatus.PENDING, depends=["1.1"])
        blocked = make_task(task_id="1.3", depends=["1.2"])
        phase = make_phase(tasks=[dep1, dep2, blocked])
        plan = make_plan(phases=[phase])
        modal = DependencyChainModal(blocked, plan)

        chain = modal._get_dependency_chain(blocked)

        assert len(chain) == 3
        assert chain[0][0].id == "1.1"
        assert chain[1][0].id == "1.2"
        assert chain[2][0].id == "1.3"

    def test_multiple_blockers(self) -> None:
        """Test chain with multiple blockers at same level."""
        dep1 = make_task(task_id="1.1", status=TaskStatus.PENDING)
        dep2 = make_task(task_id="1.2", status=TaskStatus.PENDING)
        blocked = make_task(task_id="1.3", depends=["1.1", "1.2"])
        phase = make_phase(tasks=[dep1, dep2, blocked])
        plan = make_plan(phases=[phase])
        modal = DependencyChainModal(blocked, plan)

        chain = modal._get_dependency_chain(blocked)

        assert len(chain) == 3
        # Both deps should be in chain before the blocked task
        task_ids = [t.id for t, _ in chain]
        assert "1.1" in task_ids
        assert "1.2" in task_ids
        assert task_ids[-1] == "1.3"


class TestGetBlockingTaskIds:
    """Tests for getting blocking task IDs."""

    def test_no_blockers(self) -> None:
        """Test task with no dependencies."""
        task = make_task(depends=[])
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        modal = DependencyChainModal(task, plan)

        blockers = modal._get_blocking_task_ids(task)

        assert blockers == []

    def test_with_incomplete_blockers(self) -> None:
        """Test task with incomplete dependencies."""
        dep1 = make_task(task_id="1.1", status=TaskStatus.PENDING)
        dep2 = make_task(task_id="1.2", status=TaskStatus.COMPLETE)
        blocked = make_task(task_id="1.3", depends=["1.1", "1.2"])
        phase = make_phase(tasks=[dep1, dep2, blocked])
        plan = make_plan(phases=[phase])
        modal = DependencyChainModal(blocked, plan)

        blockers = modal._get_blocking_task_ids(blocked)

        assert "1.1" in blockers
        assert "1.2" not in blockers

    def test_skipped_dependency_not_blocking(self) -> None:
        """Test skipped dependency doesn't block."""
        dep = make_task(task_id="1.1", status=TaskStatus.SKIPPED)
        blocked = make_task(task_id="1.2", depends=["1.1"])
        phase = make_phase(tasks=[dep, blocked])
        plan = make_plan(phases=[phase])
        modal = DependencyChainModal(blocked, plan)

        blockers = modal._get_blocking_task_ids(blocked)

        assert blockers == []


class TestGetStatusText:
    """Tests for status text generation."""

    def test_pending_status(self) -> None:
        """Test pending status text."""
        task = make_task(status=TaskStatus.PENDING)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        modal = DependencyChainModal(task, plan)

        assert modal._get_status_text(task) == "pending"

    def test_in_progress_status(self) -> None:
        """Test in progress status text."""
        task = make_task(status=TaskStatus.IN_PROGRESS)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        modal = DependencyChainModal(task, plan)

        assert modal._get_status_text(task) == "in progress"

    def test_complete_status(self) -> None:
        """Test complete status text."""
        task = make_task(status=TaskStatus.COMPLETE)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        modal = DependencyChainModal(task, plan)

        assert modal._get_status_text(task) == "complete"

    def test_skipped_status(self) -> None:
        """Test skipped status text."""
        task = make_task(status=TaskStatus.SKIPPED)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        modal = DependencyChainModal(task, plan)

        assert modal._get_status_text(task) == "skipped"

    def test_blocked_status(self) -> None:
        """Test blocked status text."""
        task = make_task(status=TaskStatus.BLOCKED)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        modal = DependencyChainModal(task, plan)

        assert modal._get_status_text(task) == "blocked"


class TestBuildChainDisplay:
    """Tests for chain display building."""

    def test_no_blockers_message(self) -> None:
        """Test message when task has no blockers."""
        task = make_task(depends=[])
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        modal = DependencyChainModal(task, plan)

        widgets = modal._build_chain_display()

        # Should have a message indicating no blockers
        assert len(widgets) == 1
        assert "No blockers" in str(widgets[0].renderable) or "available" in str(widgets[0].renderable).lower()

    def test_chain_display_shows_dependencies(self) -> None:
        """Test chain display includes all dependencies."""
        dep = make_task(task_id="1.1", title="Auth middleware", status=TaskStatus.PENDING)
        blocked = make_task(task_id="1.2", title="Login form", depends=["1.1"])
        phase = make_phase(tasks=[dep, blocked])
        plan = make_plan(phases=[phase])
        modal = DependencyChainModal(blocked, plan)

        widgets = modal._build_chain_display()

        # Should have widgets for the dependency chain
        assert len(widgets) >= 1
        widget_text = " ".join(str(w.renderable) for w in widgets)
        assert "1.1" in widget_text
        assert "Auth middleware" in widget_text
