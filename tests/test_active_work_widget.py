"""Tests for the ActiveWorkWidget."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from iterm_controller.models import (
    AttentionState,
    ManagedSession,
    Phase,
    Plan,
    Task,
    TaskStatus,
)
from iterm_controller.widgets.active_work import ActiveWorkWidget


def make_task(
    task_id: str = "1.1",
    title: str = "Test Task",
    status: TaskStatus = TaskStatus.PENDING,
    session_id: str | None = None,
) -> Task:
    """Create a test task."""
    return Task(
        id=task_id,
        title=title,
        status=status,
        session_id=session_id,
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


def make_session(
    session_id: str = "session-1",
    template_id: str = "claude",
    attention_state: AttentionState = AttentionState.IDLE,
    spawned_at: datetime | None = None,
) -> ManagedSession:
    """Create a test session."""
    return ManagedSession(
        id=session_id,
        template_id=template_id,
        project_id="test-project",
        tab_id="tab-1",
        attention_state=attention_state,
        spawned_at=spawned_at or datetime.now(),
    )


class TestActiveWorkWidgetInit:
    """Tests for ActiveWorkWidget initialization."""

    def test_init_empty(self) -> None:
        """Test widget initializes with empty plan."""
        widget = ActiveWorkWidget()

        assert widget.plan.phases == []
        assert widget.selected_task is None
        assert widget.selected_index == 0

    def test_init_with_plan(self) -> None:
        """Test widget initializes with provided plan."""
        task = make_task(status=TaskStatus.IN_PROGRESS)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = ActiveWorkWidget(plan=plan)

        assert len(widget._active_tasks) == 1
        assert widget.selected_task == task

    def test_only_in_progress_tasks_active(self) -> None:
        """Test only in-progress tasks appear in active work."""
        pending = make_task(task_id="1.1", status=TaskStatus.PENDING)
        in_progress = make_task(task_id="1.2", status=TaskStatus.IN_PROGRESS)
        complete = make_task(task_id="1.3", status=TaskStatus.COMPLETE)
        phase = make_phase(tasks=[pending, in_progress, complete])
        plan = make_plan(phases=[phase])

        widget = ActiveWorkWidget(plan=plan)

        assert len(widget._active_tasks) == 1
        assert widget._active_tasks[0].id == "1.2"


class TestActiveWorkSelection:
    """Tests for task selection functionality."""

    def test_select_next(self) -> None:
        """Test select_next moves to next task."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.IN_PROGRESS),
            make_task(task_id="1.2", status=TaskStatus.IN_PROGRESS),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = ActiveWorkWidget(plan=plan)

        with patch.object(widget, "update"):
            widget.select_next()

        assert widget.selected_index == 1
        assert widget.selected_task.id == "1.2"

    def test_select_previous(self) -> None:
        """Test select_previous moves to previous task."""
        tasks = [
            make_task(task_id="1.1", status=TaskStatus.IN_PROGRESS),
            make_task(task_id="1.2", status=TaskStatus.IN_PROGRESS),
        ]
        phase = make_phase(tasks=tasks)
        plan = make_plan(phases=[phase])
        widget = ActiveWorkWidget(plan=plan)
        widget._selected_index = 1

        with patch.object(widget, "update"):
            widget.select_previous()

        assert widget.selected_index == 0
        assert widget.selected_task.id == "1.1"


class TestActiveWorkSessionLinking:
    """Tests for task-session linking."""

    def test_get_session_for_task_with_link(self) -> None:
        """Test getting session linked to task."""
        session = make_session(session_id="sess-1")
        task = make_task(session_id="sess-1", status=TaskStatus.IN_PROGRESS)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = ActiveWorkWidget(plan=plan, sessions={"sess-1": session})

        result = widget.get_session_for_task(task)

        assert result == session

    def test_get_session_for_task_without_link(self) -> None:
        """Test getting session when task has no session_id."""
        task = make_task(session_id=None, status=TaskStatus.IN_PROGRESS)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = ActiveWorkWidget(plan=plan)

        result = widget.get_session_for_task(task)

        assert result is None

    def test_get_session_for_task_session_not_found(self) -> None:
        """Test getting session when session_id doesn't match."""
        task = make_task(session_id="missing", status=TaskStatus.IN_PROGRESS)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = ActiveWorkWidget(plan=plan, sessions={})

        result = widget.get_session_for_task(task)

        assert result is None


class TestActiveWorkRendering:
    """Tests for active work rendering."""

    def test_render_empty_active(self) -> None:
        """Test rendering with no in-progress tasks."""
        pending = make_task(status=TaskStatus.PENDING)
        phase = make_phase(tasks=[pending])
        plan = make_plan(phases=[phase])
        widget = ActiveWorkWidget(plan=plan)

        result = widget._render_active()

        assert "No tasks in progress" in str(result)

    def test_render_header(self) -> None:
        """Test header shows Active Work title."""
        task = make_task(status=TaskStatus.IN_PROGRESS)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = ActiveWorkWidget(plan=plan)

        result = widget._render_active()

        assert "Active Work" in str(result)

    def test_render_task_with_session(self) -> None:
        """Test task rendering with linked session."""
        session = make_session(
            session_id="sess-1",
            template_id="claude-main",
            attention_state=AttentionState.WORKING,
        )
        task = make_task(
            task_id="1.1",
            title="Build API",
            session_id="sess-1",
            status=TaskStatus.IN_PROGRESS,
        )
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = ActiveWorkWidget(plan=plan, sessions={"sess-1": session})

        result = widget._render_task(task, is_selected=False)
        result_str = str(result)

        assert "1.1" in result_str
        assert "Build API" in result_str
        assert "claude-main" in result_str
        assert "Working" in result_str

    def test_render_task_without_session(self) -> None:
        """Test task rendering without linked session."""
        task = make_task(
            task_id="1.1",
            title="Build API",
            session_id=None,
            status=TaskStatus.IN_PROGRESS,
        )
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        widget = ActiveWorkWidget(plan=plan)

        result = widget._render_task(task, is_selected=False)
        result_str = str(result)

        assert "1.1" in result_str
        assert "Build API" in result_str
        assert "Session:" in result_str
        assert "none" in result_str

    def test_render_selected_task(self) -> None:
        """Test selected task has selection indicator."""
        task = make_task(status=TaskStatus.IN_PROGRESS)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])
        widget = ActiveWorkWidget(plan=plan)

        result = widget._render_task(task, is_selected=True)

        assert "▸" in str(result)

    def test_render_attention_state_icons(self) -> None:
        """Test attention state icons are rendered correctly."""
        widget = ActiveWorkWidget()

        assert widget.STATUS_ICONS[AttentionState.WAITING] == "⧖"
        assert widget.STATUS_ICONS[AttentionState.WORKING] == "●"
        assert widget.STATUS_ICONS[AttentionState.IDLE] == "○"


class TestActiveWorkTimeFormatting:
    """Tests for time formatting."""

    def test_format_time_ago_just_now(self) -> None:
        """Test formatting recent time."""
        widget = ActiveWorkWidget()

        result = widget._format_time_ago(datetime.now() - timedelta(seconds=30))

        assert result == "just now"

    def test_format_time_ago_minutes(self) -> None:
        """Test formatting minutes ago."""
        widget = ActiveWorkWidget()

        result = widget._format_time_ago(datetime.now() - timedelta(minutes=5))

        assert result == "5 min ago"

    def test_format_time_ago_hours(self) -> None:
        """Test formatting hours ago."""
        widget = ActiveWorkWidget()

        result = widget._format_time_ago(datetime.now() - timedelta(hours=2))

        assert result == "2 hours ago"

    def test_format_time_ago_one_hour(self) -> None:
        """Test formatting one hour ago (no plural)."""
        widget = ActiveWorkWidget()

        result = widget._format_time_ago(datetime.now() - timedelta(hours=1))

        assert result == "1 hour ago"

    def test_format_time_ago_days(self) -> None:
        """Test formatting days ago."""
        widget = ActiveWorkWidget()

        result = widget._format_time_ago(datetime.now() - timedelta(days=3))

        assert result == "3 days ago"

    def test_format_time_ago_none(self) -> None:
        """Test formatting None datetime."""
        widget = ActiveWorkWidget()

        result = widget._format_time_ago(None)

        assert result == "unknown"


class TestActiveWorkRefresh:
    """Tests for refresh functionality."""

    def test_refresh_plan_updates_tasks(self) -> None:
        """Test refreshing the plan updates active tasks."""
        widget = ActiveWorkWidget()

        task = make_task(status=TaskStatus.IN_PROGRESS)
        phase = make_phase(tasks=[task])
        plan = make_plan(phases=[phase])

        with patch.object(widget, "update"):
            widget.refresh_plan(plan)

        assert len(widget._active_tasks) == 1
        assert widget._active_tasks[0] == task

    def test_refresh_sessions(self) -> None:
        """Test refreshing sessions."""
        widget = ActiveWorkWidget()
        session = make_session(session_id="sess-1")

        with patch.object(widget, "update"):
            widget.refresh_sessions({"sess-1": session})

        assert widget._sessions == {"sess-1": session}
