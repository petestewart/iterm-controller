"""Tests for the SessionListWidget."""

from unittest.mock import patch

import pytest

from iterm_controller.models import AttentionState, ManagedSession
from iterm_controller.state import SessionClosed, SessionSpawned, SessionStatusChanged
from iterm_controller.widgets.session_list import SessionListWidget


def make_session(
    session_id: str = "session-1",
    template_id: str = "test-template",
    project_id: str = "project-1",
    attention_state: AttentionState = AttentionState.IDLE,
) -> ManagedSession:
    """Create a test session."""
    return ManagedSession(
        id=session_id,
        template_id=template_id,
        project_id=project_id,
        tab_id="tab-1",
        attention_state=attention_state,
    )


class TestSessionListWidget:
    """Tests for SessionListWidget."""

    def test_init_empty(self) -> None:
        """Test widget initializes with no sessions."""
        widget = SessionListWidget()

        assert widget.sessions == []

    def test_init_with_sessions(self) -> None:
        """Test widget initializes with provided sessions."""
        session = make_session()
        widget = SessionListWidget(sessions=[session])

        assert len(widget.sessions) == 1
        assert widget.sessions[0] == session

    def test_refresh_sessions(self) -> None:
        """Test refreshing the session list."""
        widget = SessionListWidget()

        session1 = make_session(session_id="s1")
        session2 = make_session(session_id="s2")

        # Mock update() to avoid needing an active app
        with patch.object(widget, "update"):
            widget.refresh_sessions([session1, session2])

        assert len(widget.sessions) == 2
        assert widget.sessions[0].id == "s1"
        assert widget.sessions[1].id == "s2"

    def test_refresh_sessions_replaces_list(self) -> None:
        """Test that refresh replaces the entire session list."""
        old_session = make_session(session_id="old")
        widget = SessionListWidget(sessions=[old_session])

        new_session = make_session(session_id="new")

        # Mock update() to avoid needing an active app
        with patch.object(widget, "update"):
            widget.refresh_sessions([new_session])

        assert len(widget.sessions) == 1
        assert widget.sessions[0].id == "new"


class TestStatusIcons:
    """Tests for status icon rendering."""

    def test_waiting_icon(self) -> None:
        """Test WAITING state uses correct icon."""
        widget = SessionListWidget()
        icon = widget._get_status_icon(AttentionState.WAITING)

        assert icon == "⧖"

    def test_working_icon(self) -> None:
        """Test WORKING state uses correct icon."""
        widget = SessionListWidget()
        icon = widget._get_status_icon(AttentionState.WORKING)

        assert icon == "●"

    def test_idle_icon(self) -> None:
        """Test IDLE state uses correct icon."""
        widget = SessionListWidget()
        icon = widget._get_status_icon(AttentionState.IDLE)

        assert icon == "○"


class TestStatusColors:
    """Tests for status color assignment."""

    def test_waiting_color(self) -> None:
        """Test WAITING state uses yellow color."""
        widget = SessionListWidget()
        color = widget._get_status_color(AttentionState.WAITING)

        assert color == "yellow"

    def test_working_color(self) -> None:
        """Test WORKING state uses green color."""
        widget = SessionListWidget()
        color = widget._get_status_color(AttentionState.WORKING)

        assert color == "green"

    def test_idle_color(self) -> None:
        """Test IDLE state uses dim color."""
        widget = SessionListWidget()
        color = widget._get_status_color(AttentionState.IDLE)

        assert color == "dim"


class TestSessionRendering:
    """Tests for session row rendering."""

    def test_render_empty_shows_message(self) -> None:
        """Test rendering with no sessions shows placeholder."""
        widget = SessionListWidget()
        result = widget._render_sessions()

        assert "No active sessions" in str(result)

    def test_render_session_includes_icon(self) -> None:
        """Test rendered session includes status icon."""
        session = make_session(attention_state=AttentionState.WORKING)
        widget = SessionListWidget(sessions=[session])

        text = widget._render_session(session)

        assert "●" in str(text)

    def test_render_session_includes_template_id(self) -> None:
        """Test rendered session includes template ID."""
        session = make_session(template_id="my-template")
        widget = SessionListWidget(sessions=[session])

        text = widget._render_session(session)

        assert "my-template" in str(text)

    def test_render_session_includes_project_when_enabled(self) -> None:
        """Test rendered session includes project ID when show_project=True."""
        session = make_session(project_id="my-project", template_id="my-template")
        widget = SessionListWidget(sessions=[session], show_project=True)

        text = widget._render_session(session)

        assert "my-project/my-template" in str(text)

    def test_render_session_excludes_project_when_disabled(self) -> None:
        """Test rendered session excludes project ID when show_project=False."""
        session = make_session(project_id="my-project", template_id="my-template")
        widget = SessionListWidget(sessions=[session], show_project=False)

        text = widget._render_session(session)

        assert "my-project/" not in str(text)
        assert "my-template" in str(text)

    def test_render_session_includes_status_text(self) -> None:
        """Test rendered session includes status text."""
        session = make_session(attention_state=AttentionState.WAITING)
        widget = SessionListWidget(sessions=[session])

        text = widget._render_session(session)

        assert "Waiting" in str(text)


class TestSessionSorting:
    """Tests for session sorting by priority."""

    def test_waiting_sessions_first(self) -> None:
        """Test WAITING sessions appear before others."""
        idle = make_session(session_id="idle", attention_state=AttentionState.IDLE)
        waiting = make_session(
            session_id="waiting", attention_state=AttentionState.WAITING
        )
        working = make_session(
            session_id="working", attention_state=AttentionState.WORKING
        )

        # Add in wrong order
        widget = SessionListWidget(sessions=[idle, working, waiting])
        text = str(widget._render_sessions())

        # WAITING should come first
        assert text.index("⧖") < text.index("●")
        assert text.index("●") < text.index("○")

    def test_working_sessions_before_idle(self) -> None:
        """Test WORKING sessions appear before IDLE."""
        idle = make_session(session_id="idle", attention_state=AttentionState.IDLE)
        working = make_session(
            session_id="working", attention_state=AttentionState.WORKING
        )

        widget = SessionListWidget(sessions=[idle, working])
        text = str(widget._render_sessions())

        # WORKING should come before IDLE
        assert text.index("●") < text.index("○")


class TestEventHandlers:
    """Tests for event handler methods."""

    def test_on_session_spawned_adds_session(self) -> None:
        """Test on_session_spawned adds session to list."""
        widget = SessionListWidget()
        session = make_session()
        message = SessionSpawned(session)

        # Mock update() to avoid needing an active app
        with patch.object(widget, "update"):
            widget.on_session_spawned(message)

        assert len(widget.sessions) == 1
        assert widget.sessions[0].id == session.id

    def test_on_session_spawned_prevents_duplicates(self) -> None:
        """Test on_session_spawned doesn't add duplicate sessions."""
        session = make_session(session_id="s1")
        widget = SessionListWidget(sessions=[session])

        # Try to add the same session again
        message = SessionSpawned(session)

        # Mock update() to avoid needing an active app
        with patch.object(widget, "update"):
            widget.on_session_spawned(message)

        assert len(widget.sessions) == 1

    def test_on_session_closed_removes_session(self) -> None:
        """Test on_session_closed removes session from list."""
        session = make_session(session_id="s1")
        widget = SessionListWidget(sessions=[session])

        message = SessionClosed(session)

        # Mock update() to avoid needing an active app
        with patch.object(widget, "update"):
            widget.on_session_closed(message)

        assert len(widget.sessions) == 0

    def test_on_session_closed_only_removes_matching(self) -> None:
        """Test on_session_closed only removes the matching session."""
        session1 = make_session(session_id="s1")
        session2 = make_session(session_id="s2")
        widget = SessionListWidget(sessions=[session1, session2])

        message = SessionClosed(session1)

        # Mock update() to avoid needing an active app
        with patch.object(widget, "update"):
            widget.on_session_closed(message)

        assert len(widget.sessions) == 1
        assert widget.sessions[0].id == "s2"

    def test_on_session_status_changed_updates_session(self) -> None:
        """Test on_session_status_changed updates session in list."""
        session = make_session(session_id="s1", attention_state=AttentionState.IDLE)
        widget = SessionListWidget(sessions=[session])

        # Create updated session
        updated = make_session(session_id="s1", attention_state=AttentionState.WAITING)
        message = SessionStatusChanged(updated)

        # Mock update() to avoid needing an active app
        with patch.object(widget, "update"):
            widget.on_session_status_changed(message)

        assert widget.sessions[0].attention_state == AttentionState.WAITING

    def test_on_session_status_changed_ignores_unknown_session(self) -> None:
        """Test on_session_status_changed ignores unknown session IDs."""
        session = make_session(session_id="s1")
        widget = SessionListWidget(sessions=[session])

        # Create message for different session
        other = make_session(session_id="other")
        message = SessionStatusChanged(other)

        # Mock update() to avoid needing an active app
        with patch.object(widget, "update"):
            widget.on_session_status_changed(message)

        # Original session should be unchanged
        assert len(widget.sessions) == 1
        assert widget.sessions[0].id == "s1"


class TestHelperMethods:
    """Tests for helper methods."""

    def test_get_waiting_sessions(self) -> None:
        """Test get_waiting_sessions returns only WAITING sessions."""
        idle = make_session(session_id="idle", attention_state=AttentionState.IDLE)
        waiting1 = make_session(
            session_id="waiting1", attention_state=AttentionState.WAITING
        )
        waiting2 = make_session(
            session_id="waiting2", attention_state=AttentionState.WAITING
        )
        working = make_session(
            session_id="working", attention_state=AttentionState.WORKING
        )

        widget = SessionListWidget(sessions=[idle, waiting1, working, waiting2])
        waiting = widget.get_waiting_sessions()

        assert len(waiting) == 2
        assert all(s.attention_state == AttentionState.WAITING for s in waiting)

    def test_get_waiting_sessions_empty_when_none(self) -> None:
        """Test get_waiting_sessions returns empty list when no WAITING sessions."""
        idle = make_session(attention_state=AttentionState.IDLE)
        widget = SessionListWidget(sessions=[idle])

        waiting = widget.get_waiting_sessions()

        assert waiting == []

    def test_get_session_by_id_found(self) -> None:
        """Test get_session_by_id returns session when found."""
        session = make_session(session_id="s1")
        widget = SessionListWidget(sessions=[session])

        found = widget.get_session_by_id("s1")

        assert found is not None
        assert found.id == "s1"

    def test_get_session_by_id_not_found(self) -> None:
        """Test get_session_by_id returns None when not found."""
        session = make_session(session_id="s1")
        widget = SessionListWidget(sessions=[session])

        found = widget.get_session_by_id("nonexistent")

        assert found is None

    def test_get_session_by_id_empty_list(self) -> None:
        """Test get_session_by_id returns None with empty list."""
        widget = SessionListWidget()

        found = widget.get_session_by_id("s1")

        assert found is None
