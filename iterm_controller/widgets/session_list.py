"""Session list widget with status indicators.

Displays list of sessions with status icons (Working/Waiting/Idle).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from rich.text import Text
from textual.widgets import Static

from iterm_controller.models import AttentionState, ManagedSession
from iterm_controller.state import SessionClosed, SessionSpawned, SessionStatusChanged

if TYPE_CHECKING:
    from textual.app import ComposeResult


class SessionListWidget(Static):
    """Displays list of sessions with status indicators.

    This widget shows all sessions with their attention state:
    - ⧖ Waiting: Session needs user input (highest priority)
    - ● Working: Session is actively producing output
    - ○ Idle: Session is at prompt, not doing anything

    Sessions are listed with their template ID and current status.

    Example display:
        ● my-project/API Server         Working
        ⧖ my-project/Claude             Waiting
        ○ my-project/Tests              Idle
    """

    DEFAULT_CSS = """
    SessionListWidget {
        height: auto;
        min-height: 3;
        padding: 0 1;
    }
    """

    STATUS_ICONS = {
        AttentionState.WAITING: "⧖",
        AttentionState.WORKING: "●",
        AttentionState.IDLE: "○",
    }

    STATUS_COLORS = {
        AttentionState.WAITING: "yellow",
        AttentionState.WORKING: "green",
        AttentionState.IDLE: "dim",
    }

    def __init__(
        self,
        sessions: Iterable[ManagedSession] | None = None,
        show_project: bool = True,
        **kwargs,
    ) -> None:
        """Initialize the session list widget.

        Args:
            sessions: Initial sessions to display.
            show_project: Whether to show project name prefix for each session.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self._sessions: list[ManagedSession] = list(sessions) if sessions else []
        self._show_project = show_project

    @property
    def sessions(self) -> list[ManagedSession]:
        """Get the current list of sessions."""
        return self._sessions

    def refresh_sessions(self, sessions: Iterable[ManagedSession]) -> None:
        """Update displayed sessions.

        Args:
            sessions: New list of sessions to display.
        """
        self._sessions = list(sessions)
        self.update(self._render_sessions())

    def _get_status_icon(self, state: AttentionState) -> str:
        """Get the icon for a given attention state.

        Args:
            state: The attention state.

        Returns:
            Unicode icon representing the state.
        """
        return self.STATUS_ICONS.get(state, "○")

    def _get_status_color(self, state: AttentionState) -> str:
        """Get the color for a given attention state.

        Args:
            state: The attention state.

        Returns:
            Color name for Rich markup.
        """
        return self.STATUS_COLORS.get(state, "dim")

    def _render_session(self, session: ManagedSession) -> Text:
        """Render a single session row.

        Args:
            session: The session to render.

        Returns:
            Rich Text object for the session row.
        """
        icon = self._get_status_icon(session.attention_state)
        color = self._get_status_color(session.attention_state)
        status = session.attention_state.value.title()

        text = Text()

        # Icon with color
        text.append(f"{icon} ", style=color)

        # Session name (with optional project prefix)
        if self._show_project:
            name = f"{session.project_id}/{session.template_id}"
        else:
            name = session.template_id

        # Pad name to align status column
        name_padded = f"{name:<30}"
        text.append(name_padded)

        # Status with color
        text.append(status, style=color)

        return text

    def _render_sessions(self) -> Text:
        """Render all sessions.

        Returns:
            Rich Text object containing all session rows.
        """
        if not self._sessions:
            return Text("No active sessions", style="dim italic")

        # Sort sessions: WAITING first, then WORKING, then IDLE
        priority = {
            AttentionState.WAITING: 0,
            AttentionState.WORKING: 1,
            AttentionState.IDLE: 2,
        }
        sorted_sessions = sorted(
            self._sessions, key=lambda s: priority.get(s.attention_state, 3)
        )

        lines = []
        for session in sorted_sessions:
            lines.append(self._render_session(session))

        result = Text()
        for i, line in enumerate(lines):
            if i > 0:
                result.append("\n")
            result.append_text(line)

        return result

    def render(self) -> Text:
        """Render the widget content.

        Returns:
            Rich Text object to display.
        """
        return self._render_sessions()

    def on_session_spawned(self, message: SessionSpawned) -> None:
        """Handle session spawned event.

        Args:
            message: The session spawned message.
        """
        # Check if session already exists to avoid duplicates
        existing_ids = {s.id for s in self._sessions}
        if message.session.id not in existing_ids:
            self._sessions.append(message.session)
            self.update(self._render_sessions())

    def on_session_closed(self, message: SessionClosed) -> None:
        """Handle session closed event.

        Args:
            message: The session closed message.
        """
        self._sessions = [s for s in self._sessions if s.id != message.session.id]
        self.update(self._render_sessions())

    def on_session_status_changed(self, message: SessionStatusChanged) -> None:
        """Handle session status changed event.

        Args:
            message: The session status changed message.
        """
        for i, session in enumerate(self._sessions):
            if session.id == message.session.id:
                self._sessions[i] = message.session
                break
        self.update(self._render_sessions())

    def get_waiting_sessions(self) -> list[ManagedSession]:
        """Get sessions that are waiting for user input.

        Returns:
            List of sessions in WAITING state.
        """
        return [s for s in self._sessions if s.attention_state == AttentionState.WAITING]

    def get_session_by_id(self, session_id: str) -> ManagedSession | None:
        """Get a session by its ID.

        Args:
            session_id: The session ID to look up.

        Returns:
            The session if found, None otherwise.
        """
        for session in self._sessions:
            if session.id == session_id:
                return session
        return None
