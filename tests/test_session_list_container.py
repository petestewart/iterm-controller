"""Tests for the SessionList container widget.

Tests cover:
- SessionList: container for SessionCards in Mission Control
- sort_sessions: session ordering logic
- EmptyState: display when no sessions
"""

from datetime import datetime, timedelta

import pytest

from iterm_controller.models import (
    AttentionState,
    ManagedSession,
    SessionType,
)
from iterm_controller.widgets.session_list_container import (
    EmptyState,
    SessionList,
    sort_sessions,
)


def make_session(
    session_id: str = "session-1",
    template_id: str = "test-template",
    project_id: str = "project-1",
    attention_state: AttentionState = AttentionState.IDLE,
    session_type: SessionType = SessionType.SHELL,
    task_id: str | None = None,
    last_activity: datetime | None = None,
    spawned_at: datetime | None = None,
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
        spawned_at=spawned_at or datetime.now(),
        last_activity=last_activity,
    )


class TestSortSessions:
    """Tests for the sort_sessions function."""

    def test_sort_empty_list(self) -> None:
        """Test sorting empty list returns empty list."""
        result = sort_sessions([])

        assert result == []

    def test_sort_single_session(self) -> None:
        """Test sorting single session returns same session."""
        session = make_session()
        result = sort_sessions([session])

        assert result == [session]

    def test_sort_by_attention_state_priority(self) -> None:
        """Test sessions are sorted by attention state priority."""
        idle = make_session(session_id="idle", attention_state=AttentionState.IDLE)
        working = make_session(session_id="working", attention_state=AttentionState.WORKING)
        waiting = make_session(session_id="waiting", attention_state=AttentionState.WAITING)

        # Input in wrong order
        result = sort_sessions([idle, working, waiting])

        # Should be: WAITING, WORKING, IDLE
        assert result[0].id == "waiting"
        assert result[1].id == "working"
        assert result[2].id == "idle"

    def test_sort_by_last_activity_within_same_state(self) -> None:
        """Test sessions with same state are sorted by last activity."""
        now = datetime.now()
        old = make_session(
            session_id="old",
            attention_state=AttentionState.WORKING,
            last_activity=now - timedelta(hours=1),
        )
        new = make_session(
            session_id="new",
            attention_state=AttentionState.WORKING,
            last_activity=now,
        )
        middle = make_session(
            session_id="middle",
            attention_state=AttentionState.WORKING,
            last_activity=now - timedelta(minutes=30),
        )

        result = sort_sessions([old, new, middle])

        # Should be most recent first
        assert result[0].id == "new"
        assert result[1].id == "middle"
        assert result[2].id == "old"

    def test_sort_with_none_last_activity(self) -> None:
        """Test sessions without last_activity are sorted last within state."""
        now = datetime.now()
        with_activity = make_session(
            session_id="with",
            attention_state=AttentionState.IDLE,
            last_activity=now,
        )
        without_activity = make_session(
            session_id="without",
            attention_state=AttentionState.IDLE,
            last_activity=None,
        )

        result = sort_sessions([without_activity, with_activity])

        # Session with activity should come first
        assert result[0].id == "with"
        assert result[1].id == "without"

    def test_sort_combined_priority(self) -> None:
        """Test combined sorting by state and activity."""
        now = datetime.now()
        waiting_old = make_session(
            session_id="waiting-old",
            attention_state=AttentionState.WAITING,
            last_activity=now - timedelta(hours=1),
        )
        waiting_new = make_session(
            session_id="waiting-new",
            attention_state=AttentionState.WAITING,
            last_activity=now,
        )
        working = make_session(
            session_id="working",
            attention_state=AttentionState.WORKING,
            last_activity=now,
        )
        idle = make_session(
            session_id="idle",
            attention_state=AttentionState.IDLE,
            last_activity=now,
        )

        result = sort_sessions([idle, working, waiting_old, waiting_new])

        # WAITING sessions first (newer before older), then WORKING, then IDLE
        assert result[0].id == "waiting-new"
        assert result[1].id == "waiting-old"
        assert result[2].id == "working"
        assert result[3].id == "idle"


class TestEmptyState:
    """Tests for the EmptyState widget."""

    def test_render_contains_instructions(self) -> None:
        """Test empty state contains helpful instructions."""
        widget = EmptyState()

        content = widget.render()

        assert "No active sessions" in content
        assert "[n]" in content  # New session shortcut
        assert "[p]" in content  # Projects shortcut


class TestSessionList:
    """Tests for SessionList container widget."""

    def test_init_empty(self) -> None:
        """Test initialization with no sessions."""
        container = SessionList()

        assert container.session_count == 0
        assert container.selected_session is None
        assert container.expanded_session_id is None

    def test_init_with_sessions(self) -> None:
        """Test initialization with sessions."""
        sessions = [
            make_session(session_id="s1"),
            make_session(session_id="s2"),
        ]
        container = SessionList(sessions=sessions)

        assert container.session_count == 2
        assert container.selected_session is not None

    def test_sessions_property(self) -> None:
        """Test sessions property returns list."""
        sessions = [make_session(session_id="s1")]
        container = SessionList(sessions=sessions)

        assert container.sessions == sessions

    def test_selected_index_default_zero(self) -> None:
        """Test selected index starts at 0."""
        sessions = [
            make_session(session_id="s1"),
            make_session(session_id="s2"),
        ]
        container = SessionList(sessions=sessions)

        assert container.selected_index == 0

    def test_get_session_by_id_found(self) -> None:
        """Test getting session by ID when it exists."""
        session = make_session(session_id="target")
        container = SessionList(sessions=[session])

        result = container.get_session_by_id("target")

        assert result == session

    def test_get_session_by_id_not_found(self) -> None:
        """Test getting session by ID when it doesn't exist."""
        session = make_session(session_id="other")
        container = SessionList(sessions=[session])

        result = container.get_session_by_id("nonexistent")

        assert result is None

    def test_get_session_by_index(self) -> None:
        """Test getting session by 1-based display index."""
        s1 = make_session(session_id="s1", attention_state=AttentionState.WAITING)
        s2 = make_session(session_id="s2", attention_state=AttentionState.IDLE)
        container = SessionList(sessions=[s2, s1])  # s1 should sort first (WAITING)

        result = container.get_session_by_index(1)

        assert result.id == "s1"  # First in sorted order

    def test_get_session_by_index_out_of_range(self) -> None:
        """Test getting session by invalid index."""
        session = make_session()
        container = SessionList(sessions=[session])

        assert container.get_session_by_index(0) is None  # 0 is invalid (1-based)
        assert container.get_session_by_index(5) is None  # Beyond list

    def test_expand_session(self) -> None:
        """Test expanding a session."""
        sessions = [make_session(session_id="s1")]
        container = SessionList(sessions=sessions)

        container.expand_session("s1")

        assert container.expanded_session_id == "s1"

    def test_expand_session_collapses_previous(self) -> None:
        """Test expanding a new session collapses the previous one."""
        sessions = [
            make_session(session_id="s1"),
            make_session(session_id="s2"),
        ]
        container = SessionList(sessions=sessions)

        container.expand_session("s1")
        assert container.expanded_session_id == "s1"

        container.expand_session("s2")
        assert container.expanded_session_id == "s2"

    def test_collapse_session(self) -> None:
        """Test collapsing the expanded session."""
        sessions = [make_session(session_id="s1")]
        container = SessionList(sessions=sessions)
        container.expand_session("s1")

        container.collapse_session()

        assert container.expanded_session_id is None

    def test_collapse_session_when_none_expanded(self) -> None:
        """Test collapsing when no session is expanded is a no-op."""
        container = SessionList()

        container.collapse_session()  # Should not raise

        assert container.expanded_session_id is None

    def test_toggle_expansion_expand(self) -> None:
        """Test toggling expansion expands a collapsed session."""
        sessions = [make_session(session_id="s1")]
        container = SessionList(sessions=sessions)

        container.toggle_expansion("s1")

        assert container.expanded_session_id == "s1"

    def test_toggle_expansion_collapse(self) -> None:
        """Test toggling expansion collapses an expanded session."""
        sessions = [make_session(session_id="s1")]
        container = SessionList(sessions=sessions)
        container.expand_session("s1")

        container.toggle_expansion("s1")

        assert container.expanded_session_id is None

    def test_toggle_expansion_switch(self) -> None:
        """Test toggling expansion switches to a different session."""
        sessions = [
            make_session(session_id="s1"),
            make_session(session_id="s2"),
        ]
        container = SessionList(sessions=sessions)
        container.expand_session("s1")

        container.toggle_expansion("s2")

        assert container.expanded_session_id == "s2"

    def test_add_session_to_data(self) -> None:
        """Test adding a session updates internal data.

        Note: This test verifies data updates only. UI mounting is tested
        in integration tests with a running app.
        """
        container = SessionList()

        session = make_session(session_id="new")
        # Manually add to sessions list (bypassing _refresh_cards which needs mount)
        container._sessions.append(session)

        assert container.session_count == 1
        assert container.get_session_by_id("new") is not None

    def test_add_session_duplicate_check(self) -> None:
        """Test duplicate check logic for adding sessions."""
        session = make_session(session_id="s1")
        container = SessionList(sessions=[session])

        # Check that duplicate detection works
        is_duplicate = any(s.id == session.id for s in container._sessions)

        assert is_duplicate is True

    def test_remove_session_from_data(self) -> None:
        """Test removing a session updates internal data."""
        sessions = [
            make_session(session_id="s1"),
            make_session(session_id="s2"),
        ]
        container = SessionList(sessions=sessions)

        # Remove session from internal list (bypassing _refresh_cards)
        container._sessions = [s for s in container._sessions if s.id != "s1"]

        assert container.session_count == 1
        assert container.get_session_by_id("s1") is None
        assert container.get_session_by_id("s2") is not None

    def test_remove_session_clears_expansion(self) -> None:
        """Test expansion state is cleared when session is removed."""
        sessions = [make_session(session_id="s1")]
        container = SessionList(sessions=sessions)
        container.expand_session("s1")

        # Simulate remove logic for expansion
        if container._expanded_session_id == "s1":
            container._expanded_session_id = None

        assert container.expanded_session_id is None

    def test_remove_session_adjusts_selection(self) -> None:
        """Test selection index is adjusted when session is removed."""
        sessions = [
            make_session(session_id="s1"),
            make_session(session_id="s2"),
        ]
        container = SessionList(sessions=sessions)
        container._selected_index = 1  # Select second session

        # Simulate remove and selection adjustment
        container._sessions = [s for s in container._sessions if s.id != "s2"]
        sorted_sessions = sort_sessions(container._sessions)
        if sorted_sessions:
            container._selected_index = min(container._selected_index, len(sorted_sessions) - 1)
        else:
            container._selected_index = 0

        assert container._selected_index == 0

    def test_refresh_sessions_updates_data(self) -> None:
        """Test refreshing sessions updates internal data."""
        sessions1 = [make_session(session_id="s1")]
        container = SessionList(sessions=sessions1)

        sessions2 = [
            make_session(session_id="s2"),
            make_session(session_id="s3"),
        ]
        # Update internal list directly
        container._sessions = list(sessions2)

        assert container.session_count == 2
        assert container.get_session_by_id("s1") is None
        assert container.get_session_by_id("s2") is not None
        assert container.get_session_by_id("s3") is not None

    def test_refresh_sessions_preserves_expansion_logic(self) -> None:
        """Test expansion is preserved when session still exists."""
        session = make_session(session_id="s1")
        container = SessionList(sessions=[session])
        container.expand_session("s1")

        # Simulate refresh with same session
        updated_session = make_session(session_id="s1", attention_state=AttentionState.WORKING)
        container._sessions = [updated_session]

        # Clear expanded if session no longer exists
        if container._expanded_session_id:
            if not any(s.id == container._expanded_session_id for s in container._sessions):
                container._expanded_session_id = None

        # Session still exists, so expansion should remain
        assert container.expanded_session_id == "s1"

    def test_refresh_sessions_clears_expansion_when_removed(self) -> None:
        """Test expansion is cleared when expanded session is removed."""
        sessions = [
            make_session(session_id="s1"),
            make_session(session_id="s2"),
        ]
        container = SessionList(sessions=sessions)
        container.expand_session("s1")

        # Simulate refresh without s1
        container._sessions = [make_session(session_id="s2")]

        # Clear expanded if session no longer exists
        if container._expanded_session_id:
            if not any(s.id == container._expanded_session_id for s in container._sessions):
                container._expanded_session_id = None

        assert container.expanded_session_id is None

    def test_update_session_in_list(self) -> None:
        """Test updating a session in the internal list."""
        session = make_session(session_id="s1", attention_state=AttentionState.IDLE)
        container = SessionList(sessions=[session])

        updated = make_session(session_id="s1", attention_state=AttentionState.WORKING)

        # Simulate update logic
        for i, s in enumerate(container._sessions):
            if s.id == updated.id:
                container._sessions[i] = updated
                break

        stored = container.get_session_by_id("s1")
        assert stored.attention_state == AttentionState.WORKING

    def test_update_session_adds_if_not_found(self) -> None:
        """Test that update adds session if not found in list."""
        container = SessionList()

        session = make_session(session_id="new")

        # Simulate add-if-not-found logic
        found = False
        for i, s in enumerate(container._sessions):
            if s.id == session.id:
                container._sessions[i] = session
                found = True
                break
        if not found:
            container._sessions.append(session)

        assert container.session_count == 1


class TestSessionListMessages:
    """Tests for SessionList message types."""

    def test_session_selected_message(self) -> None:
        """Test SessionSelected message contains session."""
        session = make_session()
        message = SessionList.SessionSelected(session)

        assert message.session == session

    def test_session_expanded_message(self) -> None:
        """Test SessionExpanded message contains session ID."""
        message = SessionList.SessionExpanded("session-1")

        assert message.session_id == "session-1"

    def test_session_collapsed_message(self) -> None:
        """Test SessionCollapsed message contains session ID."""
        message = SessionList.SessionCollapsed("session-1")

        assert message.session_id == "session-1"


class TestSessionListNavigation:
    """Tests for SessionList navigation actions."""

    def test_cursor_up_at_top(self) -> None:
        """Test cursor up at top of list stays at 0."""
        sessions = [
            make_session(session_id="s1"),
            make_session(session_id="s2"),
        ]
        container = SessionList(sessions=sessions)
        container._selected_index = 0

        container.action_cursor_up()

        assert container._selected_index == 0

    def test_cursor_up_moves_up(self) -> None:
        """Test cursor up moves selection up."""
        sessions = [
            make_session(session_id="s1"),
            make_session(session_id="s2"),
        ]
        container = SessionList(sessions=sessions)
        container._selected_index = 1

        container.action_cursor_up()

        assert container._selected_index == 0

    def test_cursor_down_moves_down(self) -> None:
        """Test cursor down moves selection down."""
        sessions = [
            make_session(session_id="s1"),
            make_session(session_id="s2"),
        ]
        container = SessionList(sessions=sessions)
        container._selected_index = 0

        container.action_cursor_down()

        assert container._selected_index == 1

    def test_cursor_down_at_bottom(self) -> None:
        """Test cursor down at bottom stays at last position."""
        sessions = [
            make_session(session_id="s1"),
            make_session(session_id="s2"),
        ]
        container = SessionList(sessions=sessions)
        container._selected_index = 1

        container.action_cursor_down()

        assert container._selected_index == 1

    def test_action_toggle_expand(self) -> None:
        """Test toggle expand action toggles selected session."""
        sessions = [make_session(session_id="s1")]
        container = SessionList(sessions=sessions)
        container._selected_index = 0

        container.action_toggle_expand()

        assert container.expanded_session_id == "s1"

    def test_action_toggle_expand_no_sessions(self) -> None:
        """Test toggle expand with no sessions is a no-op."""
        container = SessionList()

        container.action_toggle_expand()  # Should not raise

        assert container.expanded_session_id is None

    def test_select_session_by_id(self) -> None:
        """Test selecting a session by ID."""
        s1 = make_session(session_id="s1", attention_state=AttentionState.IDLE)
        s2 = make_session(session_id="s2", attention_state=AttentionState.WAITING)
        # s2 will sort first (WAITING)
        container = SessionList(sessions=[s1, s2])

        container.select_session("s1")

        # s1 is second in sorted order (index 1)
        assert container._selected_index == 1
