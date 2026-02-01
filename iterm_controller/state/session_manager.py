"""Session state manager.

Handles session-related state operations including adding, removing,
and updating session status.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from iterm_controller.models import ManagedSession
from iterm_controller.state.events import (
    SessionClosed,
    SessionSpawned,
    SessionStatusChanged,
    StateEvent,
)

if TYPE_CHECKING:
    from textual.app import App


class SessionStateManager:
    """Manages session-related state.

    Handles:
    - Tracking active sessions
    - Adding and removing sessions
    - Updating session status
    - Filtering sessions by project
    """

    def __init__(self) -> None:
        """Initialize the session state manager."""
        self.sessions: dict[str, ManagedSession] = {}
        self._app: App | None = None
        self._emit_callback: Callable[[StateEvent, dict[str, Any]], None] | None = None

    def connect_app(self, app: App) -> None:
        """Connect to a Textual App for message posting.

        Args:
            app: The Textual App instance.
        """
        self._app = app

    def set_emit_callback(
        self, callback: Callable[[StateEvent, dict[str, Any]], None]
    ) -> None:
        """Set callback for emitting events to legacy subscribers.

        Args:
            callback: Function to call with (event, kwargs) when emitting.
        """
        self._emit_callback = callback

    def _post_message(self, message: Any) -> None:
        """Post a message to the connected Textual app."""
        if self._app is not None:
            self._app.post_message(message)

    def _emit(self, event: StateEvent, **kwargs: Any) -> None:
        """Emit event to legacy subscribers."""
        if self._emit_callback:
            self._emit_callback(event, kwargs)

    @property
    def has_active_sessions(self) -> bool:
        """Check if any sessions are currently active."""
        return any(s.is_active for s in self.sessions.values())

    def add_session(self, session: ManagedSession) -> None:
        """Add a session to the state.

        Args:
            session: The managed session to add.
        """
        self.sessions[session.id] = session
        self._emit(StateEvent.SESSION_SPAWNED, session=session)
        self._post_message(SessionSpawned(session))

    def remove_session(self, session_id: str) -> None:
        """Remove a session from the state.

        Args:
            session_id: The ID of the session to remove.
        """
        if session_id in self.sessions:
            session = self.sessions.pop(session_id)
            self._emit(StateEvent.SESSION_CLOSED, session=session)
            self._post_message(SessionClosed(session))

    def update_session_status(self, session_id: str, **kwargs: Any) -> None:
        """Update session status.

        Args:
            session_id: The ID of the session to update.
            **kwargs: Attributes to update on the session.
        """
        if session_id in self.sessions:
            session = self.sessions[session_id]
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)
            self._emit(StateEvent.SESSION_STATUS_CHANGED, session=session)
            self._post_message(SessionStatusChanged(session))

    def get_sessions_for_project(self, project_id: str) -> list[ManagedSession]:
        """Get all sessions for a project.

        Args:
            project_id: The project ID to filter by.

        Returns:
            List of managed sessions for the project.
        """
        return [s for s in self.sessions.values() if s.project_id == project_id]

    def get_session(self, session_id: str) -> ManagedSession | None:
        """Get a session by ID.

        Args:
            session_id: The session ID.

        Returns:
            The session if found, None otherwise.
        """
        return self.sessions.get(session_id)
