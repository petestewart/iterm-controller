"""Session list container for Mission Control.

A scrollable container that holds SessionCard widgets and manages
expand/collapse state for sessions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.message import Message
from textual.widgets import Static

from iterm_controller.models import AttentionState, ManagedSession
from iterm_controller.widgets.session_card import SessionCard

if TYPE_CHECKING:
    from textual.app import ComposeResult


def sort_sessions(sessions: list[ManagedSession]) -> list[ManagedSession]:
    """Sort sessions by attention state and last activity.

    Sessions are ordered by:
    1. Attention state (WAITING first, then WORKING, then IDLE)
    2. Last activity (most recent first within same state)

    Args:
        sessions: List of sessions to sort.

    Returns:
        Sorted list of sessions.
    """
    state_priority = {
        AttentionState.WAITING: 0,
        AttentionState.WORKING: 1,
        AttentionState.IDLE: 2,
    }

    return sorted(
        sessions,
        key=lambda s: (
            state_priority.get(s.attention_state, 3),
            -(s.last_activity.timestamp() if s.last_activity else 0),
        ),
    )


class EmptyState(Static):
    """Empty state display when no sessions are active.

    Shows a helpful message with instructions for starting sessions.
    """

    DEFAULT_CSS = """
    EmptyState {
        width: 100%;
        height: 100%;
        content-align: center middle;
        color: $text-muted;
        padding: 4 2;
    }
    """

    def render(self) -> str:
        """Render the empty state message.

        Returns:
            Multi-line string with instructions.
        """
        return """
                    No active sessions

               Press [n] to start a new session
               Press [p] to open a project
        """


class SessionList(ScrollableContainer, can_focus=True):
    """Scrollable container for session cards in Mission Control.

    Displays all active sessions across projects as SessionCard widgets.
    Supports expanding/collapsing individual sessions and keyboard navigation.

    Features:
    - Scrollable list of session cards
    - Single session expansion at a time
    - Keyboard navigation (j/k, arrows)
    - Session selection tracking
    - Empty state display

    Attributes:
        expanded_session_id: ID of the currently expanded session, or None.
        selected_index: Index of the currently focused session.
    """

    DEFAULT_CSS = """
    SessionList {
        height: 100%;
        width: 100%;
        overflow-y: auto;
    }

    SessionList:focus {
        border: solid $accent;
    }
    """

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("x", "toggle_expand", "Expand/Collapse", show=False),
        Binding("enter", "toggle_expand", "Expand/Collapse", show=False),
    ]

    class SessionSelected(Message):
        """Posted when a session is selected/focused."""

        def __init__(self, session: ManagedSession) -> None:
            super().__init__()
            self.session = session

    class SessionExpanded(Message):
        """Posted when a session is expanded."""

        def __init__(self, session_id: str) -> None:
            super().__init__()
            self.session_id = session_id

    class SessionCollapsed(Message):
        """Posted when a session is collapsed."""

        def __init__(self, session_id: str) -> None:
            super().__init__()
            self.session_id = session_id

    def __init__(
        self,
        sessions: list[ManagedSession] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the session list container.

        Args:
            sessions: Initial list of sessions to display.
            **kwargs: Additional arguments passed to ScrollableContainer.
        """
        super().__init__(**kwargs)
        self._sessions: list[ManagedSession] = list(sessions) if sessions else []
        self._expanded_session_id: str | None = None
        self._selected_index: int = 0

    @property
    def expanded_session_id(self) -> str | None:
        """Get the ID of the expanded session.

        Returns:
            Session ID if a session is expanded, None otherwise.
        """
        return self._expanded_session_id

    @property
    def selected_index(self) -> int:
        """Get the current selection index.

        Returns:
            Index of the selected session.
        """
        return self._selected_index

    @property
    def selected_session(self) -> ManagedSession | None:
        """Get the currently selected session.

        Returns:
            The selected session, or None if no sessions.
        """
        sorted_sessions = sort_sessions(self._sessions)
        if not sorted_sessions:
            return None
        if self._selected_index < 0 or self._selected_index >= len(sorted_sessions):
            return None
        return sorted_sessions[self._selected_index]

    @property
    def sessions(self) -> list[ManagedSession]:
        """Get the current list of sessions.

        Returns:
            List of managed sessions.
        """
        return self._sessions

    @property
    def session_count(self) -> int:
        """Get the number of sessions.

        Returns:
            Number of sessions in the list.
        """
        return len(self._sessions)

    def compose(self) -> ComposeResult:
        """Compose the container with session cards.

        Yields:
            SessionCard widgets for each active session, or EmptyState if none.
        """
        if not self._sessions:
            yield EmptyState()
            return

        sorted_sessions = sort_sessions(self._sessions)
        for session in sorted_sessions:
            expanded = session.id == self._expanded_session_id
            yield SessionCard(session, expanded=expanded)

    def refresh_sessions(self, sessions: list[ManagedSession]) -> None:
        """Update the list of sessions and refresh the display.

        Maintains the expanded state if the expanded session still exists.
        Keeps selection in valid bounds.

        Args:
            sessions: New list of sessions to display.
        """
        self._sessions = list(sessions)

        # Clear expanded if session no longer exists
        if self._expanded_session_id:
            if not any(s.id == self._expanded_session_id for s in sessions):
                self._expanded_session_id = None

        # Keep selection in bounds
        sorted_sessions = sort_sessions(self._sessions)
        if sorted_sessions:
            self._selected_index = min(self._selected_index, len(sorted_sessions) - 1)
        else:
            self._selected_index = 0

        # Remove existing children and recompose
        self._refresh_cards()

    def _refresh_cards(self) -> None:
        """Remove existing cards and recreate them."""
        # Remove all children
        for child in list(self.children):
            child.remove()

        # Add new cards or empty state
        if not self._sessions:
            self.mount(EmptyState())
        else:
            sorted_sessions = sort_sessions(self._sessions)
            for i, session in enumerate(sorted_sessions):
                expanded = session.id == self._expanded_session_id
                card = SessionCard(session, expanded=expanded)
                self.mount(card)
                # Set focus style on selected card
                if i == self._selected_index:
                    card.focus()

    def expand_session(self, session_id: str) -> None:
        """Expand a session and collapse any previously expanded session.

        Args:
            session_id: ID of the session to expand.
        """
        old_expanded = self._expanded_session_id
        self._expanded_session_id = session_id

        # Update card expansion states
        for card in self.query(SessionCard):
            if card.session.id == session_id:
                if not card.expanded:
                    card.toggle_expanded()
            elif card.expanded:
                card.toggle_expanded()

        if old_expanded and old_expanded != session_id:
            self.post_message(self.SessionCollapsed(old_expanded))
        self.post_message(self.SessionExpanded(session_id))

    def collapse_session(self) -> None:
        """Collapse the currently expanded session."""
        if not self._expanded_session_id:
            return

        session_id = self._expanded_session_id
        self._expanded_session_id = None

        # Update card expansion states
        for card in self.query(SessionCard):
            if card.expanded:
                card.toggle_expanded()

        self.post_message(self.SessionCollapsed(session_id))

    def toggle_expansion(self, session_id: str) -> None:
        """Toggle expansion state for a session.

        If the session is currently expanded, collapse it.
        If another session is expanded, collapse it and expand this one.
        If no session is expanded, expand this one.

        Args:
            session_id: ID of the session to toggle.
        """
        if self._expanded_session_id == session_id:
            self.collapse_session()
        else:
            self.expand_session(session_id)

    def update_session(self, session: ManagedSession) -> None:
        """Update a single session's display.

        Finds the card for the session and updates it without
        rebuilding the entire list.

        Args:
            session: The updated session data.
        """
        # Update internal list
        for i, s in enumerate(self._sessions):
            if s.id == session.id:
                self._sessions[i] = session
                break
        else:
            # Session not in list - add it
            self._sessions.append(session)
            self._refresh_cards()
            return

        # Find and update the card
        try:
            card = self.query_one(f"#session-{session.id}", SessionCard)
            card.update_session(session)
        except Exception:
            # Card not found - refresh all
            self._refresh_cards()

    def update_session_output(self, session_id: str, output: str) -> None:
        """Update the output log for a session.

        Args:
            session_id: ID of the session to update.
            output: New output text to append.
        """
        try:
            card = self.query_one(f"#session-{session_id}", SessionCard)
            card.update_output(output)
        except Exception:
            pass  # Card may not exist

    def remove_session(self, session_id: str) -> None:
        """Remove a session from the list.

        Args:
            session_id: ID of the session to remove.
        """
        self._sessions = [s for s in self._sessions if s.id != session_id]

        if self._expanded_session_id == session_id:
            self._expanded_session_id = None

        # Keep selection in bounds
        sorted_sessions = sort_sessions(self._sessions)
        if sorted_sessions:
            self._selected_index = min(self._selected_index, len(sorted_sessions) - 1)
        else:
            self._selected_index = 0

        self._refresh_cards()

    def add_session(self, session: ManagedSession) -> None:
        """Add a new session to the list.

        Args:
            session: The session to add.
        """
        # Check if session already exists
        if any(s.id == session.id for s in self._sessions):
            return

        self._sessions.append(session)
        self._refresh_cards()

    def get_session_by_id(self, session_id: str) -> ManagedSession | None:
        """Get a session by its ID.

        Args:
            session_id: The session ID to find.

        Returns:
            The session if found, None otherwise.
        """
        for session in self._sessions:
            if session.id == session_id:
                return session
        return None

    def get_session_by_index(self, index: int) -> ManagedSession | None:
        """Get a session by its display index (1-9).

        Args:
            index: 1-based index of the session in display order.

        Returns:
            The session if found, None otherwise.
        """
        sorted_sessions = sort_sessions(self._sessions)
        if 1 <= index <= len(sorted_sessions):
            return sorted_sessions[index - 1]
        return None

    def select_session(self, session_id: str) -> None:
        """Select a session by ID.

        Args:
            session_id: ID of the session to select.
        """
        sorted_sessions = sort_sessions(self._sessions)
        for i, session in enumerate(sorted_sessions):
            if session.id == session_id:
                self._select_index(i)
                return

    def _select_index(self, index: int) -> None:
        """Select a session by index and focus the card.

        Args:
            index: Index of the session to select.
        """
        sorted_sessions = sort_sessions(self._sessions)
        if not sorted_sessions:
            return

        # Clamp to valid range
        self._selected_index = max(0, min(index, len(sorted_sessions) - 1))

        # Focus the card
        cards = list(self.query(SessionCard))
        if cards and 0 <= self._selected_index < len(cards):
            cards[self._selected_index].focus()

        # Post message
        if self.selected_session:
            self.post_message(self.SessionSelected(self.selected_session))

    def action_cursor_up(self) -> None:
        """Move selection up."""
        if self._selected_index > 0:
            self._select_index(self._selected_index - 1)

    def action_cursor_down(self) -> None:
        """Move selection down."""
        sorted_sessions = sort_sessions(self._sessions)
        if self._selected_index < len(sorted_sessions) - 1:
            self._select_index(self._selected_index + 1)

    def action_toggle_expand(self) -> None:
        """Toggle expansion for the selected session."""
        session = self.selected_session
        if session:
            self.toggle_expansion(session.id)

    def on_session_card_selected(self, message: SessionCard.Selected) -> None:
        """Handle when a session card is selected/focused.

        Args:
            message: The card selection message.
        """
        # Update selection index
        sorted_sessions = sort_sessions(self._sessions)
        for i, session in enumerate(sorted_sessions):
            if session.id == message.session.id:
                self._selected_index = i
                break

        # Re-post as our own message
        self.post_message(self.SessionSelected(message.session))

    def on_session_card_expand_toggled(
        self, message: SessionCard.ExpandToggled
    ) -> None:
        """Handle when a session card's expansion is toggled.

        Args:
            message: The expansion toggle message.
        """
        if message.expanded:
            # Collapse other sessions
            if self._expanded_session_id and self._expanded_session_id != message.session_id:
                try:
                    old_card = self.query_one(
                        f"#session-{self._expanded_session_id}", SessionCard
                    )
                    if old_card.expanded:
                        old_card.toggle_expanded()
                except Exception:
                    pass
            self._expanded_session_id = message.session_id
            self.post_message(self.SessionExpanded(message.session_id))
        else:
            if self._expanded_session_id == message.session_id:
                self._expanded_session_id = None
            self.post_message(self.SessionCollapsed(message.session_id))
