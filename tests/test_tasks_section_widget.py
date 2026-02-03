"""Tests for the TasksSection widget."""

from unittest.mock import patch

import pytest

from iterm_controller.models import Phase, Plan, Project, Task, TaskStatus
from iterm_controller.widgets.tasks_section import TaskRow, TasksSection


def make_project(path: str = "/tmp/test-project") -> Project:
    """Create a test project."""
    return Project(
        id="project-1",
        name="Test Project",
        path=path,
    )


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
    title: str = "Phase 1: Setup",
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
    return Plan(
        phases=phases or [],
        overview="Test plan overview",
    )


class TestTaskRowInit:
    """Tests for TaskRow initialization."""

    def test_init_basic(self) -> None:
        """Test basic initialization."""
        task = make_task()
        row = TaskRow(task=task)

        assert row.task == task

    def test_init_with_blocked(self) -> None:
        """Test initialization with blocked flag."""
        task = make_task()
        row = TaskRow(task=task, is_blocked=True, blocking_tasks=["1.0"])

        assert row._is_blocked is True
        assert row._blocking_tasks == ["1.0"]

    def test_init_with_selected(self) -> None:
        """Test initialization with selected flag."""
        task = make_task()
        row = TaskRow(task=task, is_selected=True)

        assert row._is_selected is True


class TestTaskRowRender:
    """Tests for TaskRow rendering."""

    def test_render_pending_task(self) -> None:
        """Test rendering pending task."""
        task = make_task(status=TaskStatus.PENDING)
        row = TaskRow(task=task)

        text = row.render()
        rendered = str(text)

        assert "1.1" in rendered
        assert "Test Task" in rendered
        assert "○" in rendered  # Pending icon

    def test_render_in_progress_task(self) -> None:
        """Test rendering in progress task."""
        task = make_task(status=TaskStatus.IN_PROGRESS)
        row = TaskRow(task=task)

        text = row.render()
        rendered = str(text)

        assert "In Progress" in rendered
        assert "●" in rendered  # In progress icon

    def test_render_complete_task(self) -> None:
        """Test rendering complete task."""
        task = make_task(status=TaskStatus.COMPLETE)
        row = TaskRow(task=task)

        text = row.render()
        rendered = str(text)

        assert "Done" in rendered
        assert "✓" in rendered  # Complete icon

    def test_render_awaiting_review_task(self) -> None:
        """Test rendering awaiting review task."""
        task = make_task(status=TaskStatus.AWAITING_REVIEW)
        row = TaskRow(task=task)

        text = row.render()
        rendered = str(text)

        assert "⏳" in rendered  # Awaiting review icon
        assert "←REVIEW" in rendered

    def test_render_blocked_task(self) -> None:
        """Test rendering blocked task."""
        task = make_task(status=TaskStatus.PENDING)
        row = TaskRow(task=task, is_blocked=True, blocking_tasks=["1.0", "1.2"])

        text = row.render()
        rendered = str(text)

        assert "⊘" in rendered  # Blocked icon
        assert "blocked by" in rendered
        assert "1.0" in rendered
        assert "1.2" in rendered

    def test_render_selected_task(self) -> None:
        """Test rendering selected task."""
        task = make_task()
        row = TaskRow(task=task, is_selected=True)

        text = row.render()
        rendered = str(text)

        assert ">" in rendered  # Selection indicator


class TestTaskRowStatusIcon:
    """Tests for TaskRow status icon helper."""

    def test_get_status_icon_pending(self) -> None:
        """Test pending icon."""
        task = make_task(status=TaskStatus.PENDING)
        row = TaskRow(task=task)

        assert row._get_status_icon() == "○"

    def test_get_status_icon_in_progress(self) -> None:
        """Test in progress icon."""
        task = make_task(status=TaskStatus.IN_PROGRESS)
        row = TaskRow(task=task)

        assert row._get_status_icon() == "●"

    def test_get_status_icon_complete(self) -> None:
        """Test complete icon."""
        task = make_task(status=TaskStatus.COMPLETE)
        row = TaskRow(task=task)

        assert row._get_status_icon() == "✓"

    def test_get_status_icon_awaiting_review(self) -> None:
        """Test awaiting review icon."""
        task = make_task(status=TaskStatus.AWAITING_REVIEW)
        row = TaskRow(task=task)

        assert row._get_status_icon() == "⏳"


class TestTasksSectionInit:
    """Tests for TasksSection initialization."""

    def test_init_without_project(self) -> None:
        """Test widget initializes without a project."""
        widget = TasksSection()

        assert widget.project is None
        assert widget.collapsed is False
        assert widget.plan is None

    def test_init_with_project(self) -> None:
        """Test widget initializes with a project."""
        project = make_project()
        widget = TasksSection(project=project)

        assert widget.project == project

    def test_init_collapsed(self) -> None:
        """Test widget initializes collapsed."""
        widget = TasksSection(collapsed=True)

        assert widget.collapsed is True


class TestTasksSectionToggle:
    """Tests for section collapse toggle."""

    def test_toggle_collapsed(self) -> None:
        """Test toggling collapsed state."""
        widget = TasksSection()

        assert widget.collapsed is False

        with patch.object(widget, "refresh"):
            widget.toggle_collapsed()

        assert widget.collapsed is True

        with patch.object(widget, "refresh"):
            widget.toggle_collapsed()

        assert widget.collapsed is False


class TestTasksSectionPhaseToggle:
    """Tests for phase collapse toggle."""

    def test_toggle_phase(self) -> None:
        """Test toggling phase collapse state."""
        task = make_task()
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = TasksSection()
        widget.set_plan(plan)

        assert "1" not in widget._collapsed_phases

        with patch.object(widget, "refresh"):
            with patch.object(widget, "post_message"):
                widget.toggle_phase("1")

        assert "1" in widget._collapsed_phases

        with patch.object(widget, "refresh"):
            with patch.object(widget, "post_message"):
                widget.toggle_phase("1")

        assert "1" not in widget._collapsed_phases


class TestTasksSectionNavigation:
    """Tests for task navigation."""

    def test_select_next(self) -> None:
        """Test selecting next item."""
        task1 = make_task(task_id="1.1", title="Task 1")
        task2 = make_task(task_id="1.2", title="Task 2")
        phase = make_phase(tasks=[task1, task2])
        plan = make_plan(phases=[phase])

        widget = TasksSection()
        widget.set_plan(plan)

        # Initial selection is phase
        items = widget._get_selectable_items()
        assert items[widget._selected_index] == phase

        with patch.object(widget, "refresh"):
            widget.select_next()

        items = widget._get_selectable_items()
        assert items[widget._selected_index] == task1

    def test_select_previous(self) -> None:
        """Test selecting previous item."""
        task1 = make_task(task_id="1.1", title="Task 1")
        task2 = make_task(task_id="1.2", title="Task 2")
        phase = make_phase(tasks=[task1, task2])
        plan = make_plan(phases=[phase])

        widget = TasksSection()
        widget.set_plan(plan)
        widget._selected_index = 2  # Task 2

        with patch.object(widget, "refresh"):
            widget.select_previous()

        items = widget._get_selectable_items()
        assert items[widget._selected_index] == task1

    def test_select_previous_at_start(self) -> None:
        """Test select_previous doesn't go below zero."""
        task = make_task()
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = TasksSection()
        widget.set_plan(plan)

        with patch.object(widget, "refresh"):
            widget.select_previous()

        assert widget._selected_index == 0

    def test_select_next_at_end(self) -> None:
        """Test select_next doesn't exceed list bounds."""
        task1 = make_task(task_id="1.1")
        task2 = make_task(task_id="1.2")
        phase = make_phase(tasks=[task1, task2])
        plan = make_plan(phases=[phase])

        widget = TasksSection()
        widget.set_plan(plan)

        with patch.object(widget, "refresh"):
            for _ in range(10):
                widget.select_next()

        items = widget._get_selectable_items()
        assert widget._selected_index == len(items) - 1

    def test_select_when_collapsed_does_nothing(self) -> None:
        """Test navigation disabled when collapsed."""
        task = make_task()
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = TasksSection(collapsed=True)
        widget.set_plan(plan)

        # When collapsed, selected_task should be None
        assert widget.selected_task is None

    def test_selected_task_returns_task(self) -> None:
        """Test selected_task returns task when task is selected."""
        task1 = make_task(task_id="1.1", title="Task 1")
        phase = make_phase(tasks=[task1])
        plan = make_plan(phases=[phase])

        widget = TasksSection()
        widget.set_plan(plan)
        widget._selected_index = 1  # First task

        assert widget.selected_task == task1


class TestTasksSectionSelectableItems:
    """Tests for _get_selectable_items method."""

    def test_empty_plan(self) -> None:
        """Test empty plan returns empty list."""
        widget = TasksSection()

        items = widget._get_selectable_items()

        assert items == []

    def test_single_phase_single_task(self) -> None:
        """Test single phase with single task."""
        task = make_task()
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = TasksSection()
        widget.set_plan(plan)

        items = widget._get_selectable_items()

        assert len(items) == 2  # Phase + task
        assert items[0] == phase
        assert items[1] == task

    def test_collapsed_phase_hides_tasks(self) -> None:
        """Test collapsed phase hides its tasks."""
        task = make_task()
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = TasksSection()
        widget.set_plan(plan)
        widget._collapsed_phases.add("1")

        items = widget._get_selectable_items()

        assert len(items) == 1  # Only phase
        assert items[0] == phase


class TestTasksSectionRendering:
    """Tests for rendering methods."""

    def test_render_phase_header(self) -> None:
        """Test _render_phase_header output."""
        task1 = make_task(task_id="1.1", status=TaskStatus.COMPLETE)
        task2 = make_task(task_id="1.2", status=TaskStatus.PENDING)
        phase = make_phase(tasks=[task1, task2])
        plan = make_plan(phases=[phase])

        widget = TasksSection()
        widget.set_plan(plan)

        text = widget._render_phase_header(phase, is_selected=False)
        rendered = str(text)

        assert "Phase 1: Setup" in rendered
        assert "▼" in rendered  # Expanded icon
        assert "1/2" in rendered  # Progress count

    def test_render_phase_header_collapsed(self) -> None:
        """Test _render_phase_header when collapsed."""
        task = make_task()
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = TasksSection()
        widget.set_plan(plan)
        widget._collapsed_phases.add("1")

        text = widget._render_phase_header(phase, is_selected=False)
        rendered = str(text)

        assert "▶" in rendered  # Collapsed icon

    def test_render_phase_header_selected(self) -> None:
        """Test _render_phase_header with selection."""
        task = make_task()
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = TasksSection()
        widget.set_plan(plan)

        text = widget._render_phase_header(phase, is_selected=True)
        rendered = str(text)

        assert ">" in rendered  # Selection indicator

    def test_render_task_pending(self) -> None:
        """Test _render_task for pending task."""
        task = make_task(status=TaskStatus.PENDING)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = TasksSection()
        widget.set_plan(plan)

        text = widget._render_task(task, is_selected=False)
        rendered = str(text)

        assert "1.1" in rendered
        assert "Test Task" in rendered

    def test_render_task_awaiting_review(self) -> None:
        """Test _render_task for awaiting review task."""
        task = make_task(status=TaskStatus.AWAITING_REVIEW)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = TasksSection()
        widget.set_plan(plan)

        text = widget._render_task(task, is_selected=False)
        rendered = str(text)

        assert "⏳" in rendered
        assert "←REVIEW" in rendered

    def test_render_task_blocked(self) -> None:
        """Test _render_task for blocked task."""
        task1 = make_task(task_id="1.1", status=TaskStatus.IN_PROGRESS)
        task2 = make_task(task_id="1.2", status=TaskStatus.PENDING, depends=["1.1"])
        phase = make_phase(tasks=[task1, task2])
        plan = make_plan(phases=[phase])

        widget = TasksSection()
        widget.set_plan(plan)

        text = widget._render_task(task2, is_selected=False)
        rendered = str(text)

        assert "⊘" in rendered  # Blocked icon
        assert "blocked by" in rendered
        assert "1.1" in rendered


class TestTasksSectionMessages:
    """Tests for message posting."""

    def test_phase_toggled_message(self) -> None:
        """Test PhaseToggled message has correct attributes."""
        msg = TasksSection.PhaseToggled(phase_id="1", collapsed=True)

        assert msg.phase_id == "1"
        assert msg.collapsed is True

    def test_task_selected_message(self) -> None:
        """Test TaskSelected message has correct attributes."""
        task = make_task()
        msg = TasksSection.TaskSelected(task=task)

        assert msg.task == task


class TestTasksSectionHelpers:
    """Tests for helper methods."""

    def test_get_completed_count_empty(self) -> None:
        """Test get_completed_count with empty plan."""
        widget = TasksSection()

        completed, total = widget.get_completed_count()

        assert completed == 0
        assert total == 0

    def test_get_completed_count(self) -> None:
        """Test get_completed_count with tasks."""
        task1 = make_task(task_id="1.1", status=TaskStatus.COMPLETE)
        task2 = make_task(task_id="1.2", status=TaskStatus.PENDING)
        task3 = make_task(task_id="1.3", status=TaskStatus.SKIPPED)
        phase = make_phase(tasks=[task1, task2, task3])
        plan = make_plan(phases=[phase])

        widget = TasksSection()
        widget.set_plan(plan)

        completed, total = widget.get_completed_count()

        assert completed == 2  # Complete + Skipped
        assert total == 3

    def test_get_awaiting_review_tasks_empty(self) -> None:
        """Test get_awaiting_review_tasks with empty plan."""
        widget = TasksSection()

        tasks = widget.get_awaiting_review_tasks()

        assert tasks == []

    def test_get_awaiting_review_tasks(self) -> None:
        """Test get_awaiting_review_tasks with tasks."""
        task1 = make_task(task_id="1.1", status=TaskStatus.AWAITING_REVIEW)
        task2 = make_task(task_id="1.2", status=TaskStatus.PENDING)
        task3 = make_task(task_id="1.3", status=TaskStatus.AWAITING_REVIEW)
        phase = make_phase(tasks=[task1, task2, task3])
        plan = make_plan(phases=[phase])

        widget = TasksSection()
        widget.set_plan(plan)

        tasks = widget.get_awaiting_review_tasks()

        assert len(tasks) == 2
        assert task1 in tasks
        assert task3 in tasks


class TestTaskRowMessage:
    """Tests for TaskRow message."""

    def test_task_selected_message(self) -> None:
        """Test TaskSelected message has correct attributes."""
        task = make_task()
        msg = TaskRow.TaskSelected(task=task)

        assert msg.task == task
