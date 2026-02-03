"""Tests for the SessionCard widget and its subcomponents.

Tests cover:
- SessionCardHeader: header rendering with project, session info, status, duration
- OrchestratorProgress: progress bar rendering
- OutputLog: output buffer management and rendering
- SessionCard: full card composition and updates
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from iterm_controller.models import (
    AttentionState,
    ManagedSession,
    SessionProgress,
    SessionType,
)
from iterm_controller.widgets.session_card import (
    COLLAPSED_OUTPUT_LINES,
    EXPANDED_OUTPUT_LINES,
    MAX_OUTPUT_BUFFER_LINES,
    OrchestratorProgress,
    OutputLog,
    SessionCard,
    SessionCardHeader,
)


def make_session(
    session_id: str = "session-1",
    template_id: str = "test-template",
    project_id: str = "project-1",
    attention_state: AttentionState = AttentionState.IDLE,
    session_type: SessionType = SessionType.SHELL,
    task_id: str | None = None,
    display_name: str | None = None,
    progress: SessionProgress | None = None,
    spawned_at: datetime | None = None,
    metadata: dict[str, str] | None = None,
) -> ManagedSession:
    """Create a test session."""
    return ManagedSession(
        id=session_id,
        template_id=template_id,
        project_id=project_id,
        tab_id="tab-1",
        attention_state=attention_state,
        session_type=session_type,
        task_id=task_id,
        display_name=display_name,
        progress=progress,
        spawned_at=spawned_at or datetime.now(),
        metadata=metadata or {},
    )


def make_progress(
    total: int = 6,
    completed: int = 3,
    current_task_id: str | None = "2.3",
    current_task_title: str | None = "Adding authentication",
) -> SessionProgress:
    """Create test progress data."""
    return SessionProgress(
        total_tasks=total,
        completed_tasks=completed,
        current_task_id=current_task_id,
        current_task_title=current_task_title,
    )


class TestSessionCardHeader:
    """Tests for SessionCardHeader widget."""

    def test_init_with_session(self) -> None:
        """Test header initializes with session data."""
        session = make_session()
        header = SessionCardHeader(session)

        assert header.session == session

    def test_get_session_info_with_display_name(self) -> None:
        """Test session info uses display_name when set."""
        session = make_session(display_name="Creating PLAN.md")
        header = SessionCardHeader(session)

        info = header._get_session_info()

        assert info == "Creating PLAN.md"

    def test_get_session_info_with_task_id(self) -> None:
        """Test session info includes task info when linked."""
        session = make_session(
            session_type=SessionType.CLAUDE_TASK,
            task_id="2.3",
            metadata={"task_title": "Add authentication"},
        )
        header = SessionCardHeader(session)

        info = header._get_session_info()

        assert "Claude" in info
        assert "Add authentication" in info

    def test_get_session_info_without_task(self) -> None:
        """Test session info uses template_id when no task linked."""
        session = make_session(template_id="dev-server", session_type=SessionType.SERVER)
        header = SessionCardHeader(session)

        info = header._get_session_info()

        assert "Server" in info
        assert "dev-server" in info

    def test_get_session_info_for_each_type(self) -> None:
        """Test session type names for all types."""
        type_names = {
            SessionType.CLAUDE_TASK: "Claude",
            SessionType.ORCHESTRATOR: "Orchestrator",
            SessionType.REVIEW: "Review",
            SessionType.TEST_RUNNER: "Tests",
            SessionType.SCRIPT: "Script",
            SessionType.SERVER: "Server",
            SessionType.SHELL: "Shell",
        }

        for session_type, expected_name in type_names.items():
            session = make_session(session_type=session_type, template_id="test")
            header = SessionCardHeader(session)

            info = header._get_session_info()

            assert expected_name in info

    def test_format_duration_under_minute(self) -> None:
        """Test duration formatting for under a minute."""
        session = make_session(spawned_at=datetime.now() - timedelta(seconds=30))
        header = SessionCardHeader(session)

        duration = header._format_duration()

        # Should be 00:00:30 (approximately)
        assert duration.startswith("00:00:")

    def test_format_duration_under_hour(self) -> None:
        """Test duration formatting for under an hour."""
        session = make_session(spawned_at=datetime.now() - timedelta(minutes=5, seconds=42))
        header = SessionCardHeader(session)

        duration = header._format_duration()

        # Should be 00:05:42 (approximately)
        assert duration.startswith("00:05:")

    def test_format_duration_over_hour(self) -> None:
        """Test duration formatting for over an hour."""
        session = make_session(
            spawned_at=datetime.now() - timedelta(hours=2, minutes=30, seconds=15)
        )
        header = SessionCardHeader(session)

        duration = header._format_duration()

        # Should be 02:30:15 (approximately)
        assert duration.startswith("02:30:")

    def test_render_header_includes_project_name(self) -> None:
        """Test rendered header includes project name."""
        session = make_session(project_id="my-project")
        header = SessionCardHeader(session)

        text = header._render_header()

        assert "my-project" in str(text)

    def test_render_header_includes_status(self) -> None:
        """Test rendered header includes attention status."""
        session = make_session(attention_state=AttentionState.WAITING)
        header = SessionCardHeader(session)

        text = header._render_header()

        assert "WAITING" in str(text)

    def test_update_session(self) -> None:
        """Test updating session data."""
        session = make_session(attention_state=AttentionState.IDLE)
        header = SessionCardHeader(session)

        updated = make_session(attention_state=AttentionState.WORKING)
        header.session = updated

        assert header.session.attention_state == AttentionState.WORKING


class TestOrchestratorProgress:
    """Tests for OrchestratorProgress widget."""

    def test_init_with_progress(self) -> None:
        """Test widget initializes with progress data."""
        progress = make_progress()
        widget = OrchestratorProgress(progress)

        assert widget.progress == progress

    def test_init_without_progress(self) -> None:
        """Test widget initializes without progress data."""
        widget = OrchestratorProgress()

        assert widget.progress is None

    def test_render_without_progress(self) -> None:
        """Test rendering without progress shows placeholder."""
        widget = OrchestratorProgress()

        text = widget.render()

        assert "No progress data" in str(text)

    def test_render_with_zero_tasks(self) -> None:
        """Test rendering with zero total tasks."""
        progress = SessionProgress(total_tasks=0, completed_tasks=0)
        widget = OrchestratorProgress(progress)

        text = widget.render()

        assert "0/0" in str(text)
        # Should show empty progress bar (all dots)
        assert "." * 16 in str(text)

    def test_render_with_partial_progress(self) -> None:
        """Test rendering with partial completion."""
        progress = make_progress(total=6, completed=3)
        widget = OrchestratorProgress(progress)

        text = widget.render()

        assert "3/6" in str(text)
        # Should show half-filled progress bar
        assert "########" in str(text)

    def test_render_with_complete_progress(self) -> None:
        """Test rendering with all tasks complete."""
        progress = make_progress(total=6, completed=6)
        widget = OrchestratorProgress(progress)

        text = widget.render()

        assert "6/6" in str(text)
        # Should show fully filled progress bar
        assert "#" * 16 in str(text)

    def test_render_includes_current_task(self) -> None:
        """Test rendering includes current task info."""
        progress = make_progress(
            current_task_id="2.3",
            current_task_title="Adding authentication",
        )
        widget = OrchestratorProgress(progress)

        text = widget.render()

        assert "[2.3]" in str(text)
        assert "Adding authentication" in str(text)

    def test_render_without_current_task(self) -> None:
        """Test rendering without current task doesn't include task line."""
        progress = SessionProgress(
            total_tasks=6,
            completed_tasks=3,
            current_task_id=None,
            current_task_title=None,
        )
        widget = OrchestratorProgress(progress)

        text = widget.render()

        # Should only have progress bar line
        rendered = str(text)
        assert "Progress:" in rendered
        # Should NOT have task info
        assert "[" not in rendered.split("Progress:")[-1]  # No task ID brackets

    def test_update_progress(self) -> None:
        """Test updating progress data."""
        progress1 = make_progress(completed=1)
        widget = OrchestratorProgress(progress1)

        progress2 = make_progress(completed=4)
        widget.progress = progress2

        assert widget.progress.completed_tasks == 4


class TestOutputLog:
    """Tests for OutputLog widget."""

    def test_init_default_collapsed(self) -> None:
        """Test widget initializes in collapsed state."""
        widget = OutputLog()

        assert not widget.expanded
        assert widget.max_display_lines == COLLAPSED_OUTPUT_LINES

    def test_init_expanded(self) -> None:
        """Test widget initializes in expanded state when specified."""
        widget = OutputLog(expanded=True)

        assert widget.expanded
        assert widget.max_display_lines == EXPANDED_OUTPUT_LINES

    def test_render_empty(self) -> None:
        """Test rendering with no output shows placeholder."""
        widget = OutputLog()

        text = widget.render()

        assert "Waiting for output" in str(text)

    def test_append_single_line(self) -> None:
        """Test appending a single line of output."""
        widget = OutputLog()

        widget.append_output("Hello, world!")

        assert len(widget._lines) == 1
        assert "Hello, world!" in widget._lines

    def test_append_multiline(self) -> None:
        """Test appending multi-line output."""
        widget = OutputLog()

        widget.append_output("Line 1\nLine 2\nLine 3")

        assert len(widget._lines) == 3
        assert "Line 1" in widget._lines
        assert "Line 2" in widget._lines
        assert "Line 3" in widget._lines

    def test_append_strips_empty_lines(self) -> None:
        """Test that empty lines are not added."""
        widget = OutputLog()

        widget.append_output("Line 1\n\n\nLine 2")

        assert len(widget._lines) == 2

    def test_buffer_limit(self) -> None:
        """Test that buffer is limited to max lines."""
        widget = OutputLog()

        # Add more lines than the buffer can hold
        for i in range(MAX_OUTPUT_BUFFER_LINES + 10):
            widget.append_output(f"Line {i}")

        assert len(widget._lines) == MAX_OUTPUT_BUFFER_LINES

    def test_render_collapsed_shows_limited_lines(self) -> None:
        """Test collapsed render shows only limited lines."""
        widget = OutputLog(expanded=False)

        # Add more lines than collapsed view shows
        for i in range(10):
            widget.append_output(f"Line {i}")

        text = widget.render()
        rendered = str(text)

        # Should only show last COLLAPSED_OUTPUT_LINES lines
        # Count '>' prefixes (one per line)
        line_count = rendered.count("> ")
        assert line_count == COLLAPSED_OUTPUT_LINES

    def test_render_expanded_shows_more_lines(self) -> None:
        """Test expanded render shows more lines."""
        widget = OutputLog(expanded=True)

        # Add more lines than collapsed view shows but less than expanded
        for i in range(15):
            widget.append_output(f"Line {i}")

        text = widget.render()
        rendered = str(text)

        # Should show all 15 lines (less than EXPANDED_OUTPUT_LINES)
        line_count = rendered.count("> ")
        assert line_count == 15

    def test_render_includes_prefix(self) -> None:
        """Test render includes '>' prefix for each line."""
        widget = OutputLog()
        widget.append_output("Test line")

        text = widget.render()

        assert "> " in str(text)

    def test_set_expanded(self) -> None:
        """Test setting expanded state."""
        widget = OutputLog(expanded=False)

        widget.set_expanded(True)

        assert widget.expanded
        assert widget.max_display_lines == EXPANDED_OUTPUT_LINES

    def test_clear(self) -> None:
        """Test clearing output buffer."""
        widget = OutputLog()
        widget.append_output("Some output")

        widget.clear()

        assert len(widget._lines) == 0

    def test_get_all_output(self) -> None:
        """Test getting all buffered output."""
        widget = OutputLog()
        widget.append_output("Line 1")
        widget.append_output("Line 2")

        lines = widget.get_all_output()

        assert lines == ["Line 1", "Line 2"]


class TestSessionCard:
    """Tests for SessionCard widget."""

    def test_init_with_session(self) -> None:
        """Test card initializes with session data."""
        session = make_session()
        card = SessionCard(session)

        assert card.session == session

    def test_init_sets_id(self) -> None:
        """Test card ID is set from session ID."""
        session = make_session(session_id="my-session")
        card = SessionCard(session)

        assert card.id == "session-my-session"

    def test_init_collapsed_by_default(self) -> None:
        """Test card initializes in collapsed state."""
        session = make_session()
        card = SessionCard(session)

        assert not card.expanded

    def test_init_expanded(self) -> None:
        """Test card initializes in expanded state when specified."""
        session = make_session()
        card = SessionCard(session, expanded=True)

        assert card.expanded

    def test_attention_class_idle(self) -> None:
        """Test idle attention state adds 'idle' class."""
        session = make_session(attention_state=AttentionState.IDLE)
        card = SessionCard(session)

        assert card.has_class("idle")
        assert not card.has_class("working")
        assert not card.has_class("waiting")

    def test_attention_class_working(self) -> None:
        """Test working attention state adds 'working' class."""
        session = make_session(attention_state=AttentionState.WORKING)
        card = SessionCard(session)

        assert card.has_class("working")
        assert not card.has_class("idle")
        assert not card.has_class("waiting")

    def test_attention_class_waiting(self) -> None:
        """Test waiting attention state adds 'waiting' class."""
        session = make_session(attention_state=AttentionState.WAITING)
        card = SessionCard(session)

        assert card.has_class("waiting")
        assert not card.has_class("idle")
        assert not card.has_class("working")

    def test_update_session_changes_attention_class(self) -> None:
        """Test updating session changes attention state class."""
        session = make_session(attention_state=AttentionState.IDLE)
        card = SessionCard(session)

        assert card.has_class("idle")

        updated = make_session(attention_state=AttentionState.WORKING)
        card.update_session(updated)

        assert card.has_class("working")
        assert not card.has_class("idle")

    def test_toggle_expanded(self) -> None:
        """Test toggling expanded state."""
        session = make_session()
        card = SessionCard(session, expanded=False)

        card.toggle_expanded()

        assert card.expanded

        card.toggle_expanded()

        assert not card.expanded

    def test_get_status_icon(self) -> None:
        """Test getting status icon for session."""
        session = make_session(attention_state=AttentionState.WAITING)
        card = SessionCard(session)

        icon = card.get_status_icon()

        assert icon == "⧖"

    def test_get_status_color(self) -> None:
        """Test getting status color for session."""
        session = make_session(attention_state=AttentionState.WORKING)
        card = SessionCard(session)

        color = card.get_status_color()

        assert color == "green"


class TestSessionCardMessages:
    """Tests for SessionCard message handling."""

    def test_selected_message_contains_session(self) -> None:
        """Test Selected message contains session data."""
        session = make_session()
        message = SessionCard.Selected(session)

        assert message.session == session

    def test_expand_toggled_message_contains_state(self) -> None:
        """Test ExpandToggled message contains session ID and state."""
        message = SessionCard.ExpandToggled("session-1", True)

        assert message.session_id == "session-1"
        assert message.expanded is True


class TestOutputLogConstants:
    """Tests for OutputLog constants."""

    def test_collapsed_lines_constant(self) -> None:
        """Test collapsed lines constant is reasonable."""
        assert COLLAPSED_OUTPUT_LINES == 4

    def test_expanded_lines_constant(self) -> None:
        """Test expanded lines constant is reasonable."""
        assert EXPANDED_OUTPUT_LINES == 20

    def test_max_buffer_constant(self) -> None:
        """Test max buffer constant is reasonable."""
        assert MAX_OUTPUT_BUFFER_LINES == 100
