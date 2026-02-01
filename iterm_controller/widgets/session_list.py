"""Session list widget with status indicators.

Displays list of sessions with status icons (Working/Waiting/Idle).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

from rich.text import Text
from textual.widgets import Static

from iterm_controller.models import AttentionState, ManagedSession
from iterm_controller.state import SessionClosed, SessionSpawned, SessionStatusChanged
from iterm_controller.status_display import get_attention_color, get_attention_icon

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

    def __init__(
        self,
        sessions: Iterable[ManagedSession] | None = None,
        show_project: bool = True,
        **kwargs: Any,
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
        self._sorted_cache: list[ManagedSession] | None = None

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
        self._invalidate_cache()
        self.update(self._render_sessions())

    def _invalidate_cache(self) -> None:
        """Invalidate the sorted session cache."""
        self._sorted_cache = None

    def _get_sorted_sessions(self) -> list[ManagedSession]:
        """Get sessions sorted by attention state priority.

        Caches the sorted list and returns cached value on subsequent calls
        until cache is invalidated.

        Returns:
            Sessions sorted with WAITING first, then WORKING, then IDLE.
        """
        if self._sorted_cache is not None:
            return self._sorted_cache

        # Sort sessions: WAITING first, then WORKING, then IDLE
        priority = {
            AttentionState.WAITING: 0,
            AttentionState.WORKING: 1,
            AttentionState.IDLE: 2,
        }
        self._sorted_cache = sorted(
            self._sessions, key=lambda s: priority.get(s.attention_state, 3)
        )
        return self._sorted_cache

    def _get_status_icon(self, state: AttentionState) -> str:
        """Get the icon for a given attention state.

        Args:
            state: The attention state.

        Returns:
            Unicode icon representing the state.
        """
        return get_attention_icon(state)

    def _get_status_color(self, state: AttentionState) -> str:
        """Get the color for a given attention state.

        Args:
            state: The attention state.

        Returns:
            Color name for Rich markup.
        """
        return get_attention_color(state)

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

        # Pad name to align columns
        name_padded = f"{name:<25}"
        text.append(name_padded)

        # Task info if session is linked to a task
        task_id = session.metadata.get("task_id", "")
        if task_id:
            task_display = f"Task {task_id:<8}"
            text.append(task_display, style="cyan")
        else:
            # No task linked - show placeholder
            text.append(f"{'—':<13}", style="dim")

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

        sorted_sessions = self._get_sorted_sessions()

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
            self._invalidate_cache()
            self.update(self._render_sessions())

    def on_session_closed(self, message: SessionClosed) -> None:
        """Handle session closed event.

        Args:
            message: The session closed message.
        """
        self._sessions = [s for s in self._sessions if s.id != message.session.id]
        self._invalidate_cache()
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
        self._invalidate_cache()
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
