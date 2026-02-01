"""AppState and event system.

This module provides the reactive application state with event dispatch
for coordinating UI updates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from iterm_controller.models import AppConfig, ManagedSession, Project


class StateEvent(Enum):
    """Events that can be dispatched from state changes."""

    PROJECT_OPENED = "project_opened"
    PROJECT_CLOSED = "project_closed"
    SESSION_SPAWNED = "session_spawned"
    SESSION_CLOSED = "session_closed"
    SESSION_STATUS_CHANGED = "session_status_changed"
    TASK_STATUS_CHANGED = "task_status_changed"
    PLAN_RELOADED = "plan_reloaded"
    PLAN_CONFLICT = "plan_conflict"
    CONFIG_CHANGED = "config_changed"
    HEALTH_STATUS_CHANGED = "health_status_changed"
    WORKFLOW_STAGE_CHANGED = "workflow_stage_changed"


@dataclass
class AppState:
    """Reactive application state with event dispatch."""

    # Core state
    projects: dict[str, Project] = field(default_factory=dict)
    active_project_id: str | None = None
    sessions: dict[str, ManagedSession] = field(default_factory=dict)
    config: AppConfig | None = None

    # Event subscribers
    _listeners: dict[StateEvent, list[Callable[..., Any]]] = field(
        default_factory=lambda: {e: [] for e in StateEvent}
    )

    def subscribe(self, event: StateEvent, callback: Callable[..., Any]) -> None:
        """Register callback for state event.

        Args:
            event: The event type to subscribe to.
            callback: Function to call when event occurs.
        """
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)

    def unsubscribe(self, event: StateEvent, callback: Callable[..., Any]) -> None:
        """Remove callback from event.

        Args:
            event: The event type to unsubscribe from.
            callback: The callback function to remove.
        """
        if event in self._listeners:
            try:
                self._listeners[event].remove(callback)
            except ValueError:
                pass

    def emit(self, event: StateEvent, **kwargs: Any) -> None:
        """Dispatch event to all subscribers.

        Args:
            event: The event type to dispatch.
            **kwargs: Additional arguments to pass to callbacks.
        """
        for callback in self._listeners.get(event, []):
            try:
                callback(**kwargs)
            except Exception:
                # Log but don't crash on subscriber errors
                pass

    @property
    def has_active_sessions(self) -> bool:
        """Check if any sessions are currently active."""
        return any(s.is_active for s in self.sessions.values())

    @property
    def active_project(self) -> Project | None:
        """Get currently active project."""
        if self.active_project_id:
            return self.projects.get(self.active_project_id)
        return None

    async def load_config(self) -> None:
        """Load configuration from disk."""
        from iterm_controller.config import load_global_config

        self.config = load_global_config()

        # Load projects from config
        if self.config.projects:
            self.projects = {p.id: p for p in self.config.projects}

        self.emit(StateEvent.CONFIG_CHANGED, config=self.config)

    async def open_project(self, project_id: str) -> None:
        """Open a project and spawn its sessions.

        Args:
            project_id: The ID of the project to open.
        """
        if project_id not in self.projects:
            return

        project = self.projects[project_id]
        project.is_open = True
        self.active_project_id = project_id
        self.emit(StateEvent.PROJECT_OPENED, project=project)

    async def close_project(self, project_id: str) -> None:
        """Close a project and its sessions.

        Args:
            project_id: The ID of the project to close.
        """
        if project_id in self.projects:
            self.projects[project_id].is_open = False

        self.emit(StateEvent.PROJECT_CLOSED, project_id=project_id)

        if self.active_project_id == project_id:
            self.active_project_id = None

    def add_session(self, session: ManagedSession) -> None:
        """Add a session to the state.

        Args:
            session: The managed session to add.
        """
        self.sessions[session.id] = session
        self.emit(StateEvent.SESSION_SPAWNED, session=session)

    def remove_session(self, session_id: str) -> None:
        """Remove a session from the state.

        Args:
            session_id: The ID of the session to remove.
        """
        if session_id in self.sessions:
            session = self.sessions.pop(session_id)
            self.emit(StateEvent.SESSION_CLOSED, session=session)

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
            self.emit(StateEvent.SESSION_STATUS_CHANGED, session=session)

    def get_sessions_for_project(self, project_id: str) -> list[ManagedSession]:
        """Get all sessions for a project.

        Args:
            project_id: The project ID to filter by.

        Returns:
            List of managed sessions for the project.
        """
        return [s for s in self.sessions.values() if s.project_id == project_id]
