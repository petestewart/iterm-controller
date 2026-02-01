"""iTerm2 connection and session management.

This module provides the core integration with iTerm2's Python API for:
- Connection lifecycle management
- Session spawning and termination
- Window and tab tracking
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, TypeVar

import iterm2

from iterm_controller.models import ManagedSession, Project, SessionTemplate, WindowLayout

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Exceptions
# =============================================================================


class ItermConnectionError(Exception):
    """Raised when iTerm2 connection fails."""

    pass


class ItermSessionError(Exception):
    """Raised when session operations fail."""

    pass


class ItermNotConnectedError(Exception):
    """Raised when operation requires connection but not connected."""

    pass


# =============================================================================
# Connection Management
# =============================================================================


class ItermController:
    """Manages iTerm2 connection and session operations."""

    def __init__(self) -> None:
        self.connection: iterm2.Connection | None = None
        self.app: iterm2.App | None = None
        self._connected: bool = False

    async def connect(self) -> bool:
        """Establish connection to iTerm2.

        Returns:
            True if connection established successfully.

        Raises:
            ItermConnectionError: If connection fails.
        """
        try:
            self.connection = await iterm2.Connection.async_create()
            self.app = await iterm2.async_get_app(self.connection)
            self._connected = True
            logger.info("Connected to iTerm2")
            return True
        except ConnectionRefusedError as e:
            self._connected = False
            raise ItermConnectionError(
                "Connection refused. Is iTerm2 running with Python API enabled?"
            ) from e
        except Exception as e:
            self._connected = False
            raise ItermConnectionError(f"Failed to connect to iTerm2: {e}") from e

    async def disconnect(self) -> None:
        """Cleanly disconnect from iTerm2."""
        if self.connection:
            # Connection auto-closes when garbage collected
            self.connection = None
            self.app = None
            self._connected = False
            logger.info("Disconnected from iTerm2")

    async def reconnect(self) -> bool:
        """Attempt to reconnect after disconnection.

        Returns:
            True if reconnection successful.

        Raises:
            ItermConnectionError: If reconnection fails.
        """
        await self.disconnect()
        return await self.connect()

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to iTerm2."""
        return self._connected and self.connection is not None

    async def verify_version(self) -> tuple[bool, str]:
        """Check iTerm2 version meets requirements.

        Returns:
            Tuple of (success, message).
        """
        if not self.app:
            return (False, "Not connected to iTerm2")

        # iTerm2 API doesn't expose version directly, but connection success
        # implies compatible version (3.5+ required for Python API)
        return (True, "Connected to iTerm2 (3.5+ required)")

    def require_connection(self) -> None:
        """Raise if not connected.

        Raises:
            ItermNotConnectedError: If not connected to iTerm2.
        """
        if not self.is_connected:
            raise ItermNotConnectedError("Not connected to iTerm2. Call connect() first.")


# =============================================================================
# Retry Helper
# =============================================================================


async def with_reconnect(
    controller: ItermController,
    operation: Callable[[], T],
    max_retries: int = 3,
) -> T:
    """Execute operation with automatic reconnect on failure.

    Args:
        controller: The iTerm controller to use.
        operation: Async callable to execute.
        max_retries: Maximum number of retry attempts.

    Returns:
        The result of the operation.

    Raises:
        Exception: If all retries fail.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            return await operation()
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            is_connection_error = (
                "connection" in error_str
                or "closed" in error_str
                or isinstance(e, ItermConnectionError)
            )

            if is_connection_error and attempt < max_retries - 1:
                logger.warning(f"Connection error on attempt {attempt + 1}, reconnecting...")
                try:
                    await controller.reconnect()
                except ItermConnectionError:
                    # If reconnect fails, continue to next attempt
                    pass
            else:
                raise

    # Should not reach here, but satisfy type checker
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected state in with_reconnect")


# =============================================================================
# Spawn Result
# =============================================================================


@dataclass
class SpawnResult:
    """Result of spawning a session."""

    session_id: str
    tab_id: str
    success: bool
    error: str | None = None


# =============================================================================
# Window State Tracking
# =============================================================================


@dataclass
class TabState:
    """Tracks iTerm2 tab state."""

    tab_id: str
    title: str
    session_ids: list[str] = field(default_factory=list)
    is_managed: bool = False


@dataclass
class WindowState:
    """Tracks iTerm2 window state."""

    window_id: str
    tabs: list[TabState] = field(default_factory=list)
    managed_tab_ids: set[str] = field(default_factory=set)


class WindowTracker:
    """Tracks window and tab state across the application."""

    def __init__(self, controller: ItermController) -> None:
        self.controller = controller
        self.windows: dict[str, WindowState] = {}

    async def refresh(self) -> None:
        """Refresh window state from iTerm2."""
        self.controller.require_connection()
        self.windows.clear()

        if not self.controller.app:
            return

        for window in self.controller.app.terminal_windows:
            state = WindowState(window_id=window.window_id)

            for tab in window.tabs:
                try:
                    title = await tab.async_get_variable("title") or ""
                except Exception:
                    title = ""

                tab_state = TabState(
                    tab_id=tab.tab_id,
                    title=title,
                    session_ids=[s.session_id for s in tab.sessions],
                    is_managed=tab.tab_id in state.managed_tab_ids,
                )
                state.tabs.append(tab_state)

            self.windows[window.window_id] = state

    def mark_managed(self, tab_id: str, window_id: str) -> None:
        """Mark a tab as managed by this application."""
        if window_id in self.windows:
            self.windows[window_id].managed_tab_ids.add(tab_id)

    def get_managed_tab_ids(self, window_id: str | None = None) -> set[str]:
        """Get all managed tab IDs, optionally filtered by window."""
        if window_id:
            if window_id in self.windows:
                return self.windows[window_id].managed_tab_ids
            return set()

        all_managed: set[str] = set()
        for window_state in self.windows.values():
            all_managed.update(window_state.managed_tab_ids)
        return all_managed


# =============================================================================
# Session Spawner (placeholder for future implementation)
# =============================================================================


class SessionSpawner:
    """Spawns and manages terminal sessions.

    This class will be fully implemented in the session spawning task.
    """

    def __init__(self, controller: ItermController) -> None:
        self.controller = controller
        self.managed_sessions: dict[str, ManagedSession] = {}

    async def spawn_session(
        self,
        template: SessionTemplate,
        project: Project,
        window: iterm2.Window | None = None,
    ) -> SpawnResult:
        """Spawn a new session from template.

        This method will be fully implemented in the session spawning task.
        """
        raise NotImplementedError("Session spawning not yet implemented")

    async def spawn_split(
        self,
        template: SessionTemplate,
        project: Project,
        parent_session: iterm2.Session,
        vertical: bool = True,
        size_percent: int = 50,
    ) -> SpawnResult:
        """Spawn session as split pane.

        This method will be fully implemented in the session spawning task.
        """
        raise NotImplementedError("Session split spawning not yet implemented")


# =============================================================================
# Session Terminator (placeholder for future implementation)
# =============================================================================


class SessionTerminator:
    """Handles graceful session termination.

    This class will be fully implemented in the session termination task.
    """

    SIGTERM_TIMEOUT = 5.0  # Seconds to wait for graceful shutdown

    async def close_session(
        self,
        session: iterm2.Session,
        force: bool = False,
    ) -> bool:
        """Close a session, optionally with force.

        This method will be fully implemented in the session termination task.
        """
        raise NotImplementedError("Session termination not yet implemented")

    async def close_tab(self, tab: iterm2.Tab) -> bool:
        """Close a tab and all its sessions.

        This method will be fully implemented in the session termination task.
        """
        raise NotImplementedError("Tab closing not yet implemented")

    async def close_all_managed(
        self,
        sessions: list[ManagedSession],
        controller: ItermController,
    ) -> int:
        """Close all managed sessions, return count closed.

        This method will be fully implemented in the session termination task.
        """
        raise NotImplementedError("Managed session closing not yet implemented")


# =============================================================================
# Window Layout Spawner (placeholder for future implementation)
# =============================================================================


class WindowLayoutSpawner:
    """Spawns window layouts with predefined tabs and sessions.

    This class will be fully implemented in the window layout spawning task.
    """

    def __init__(self, controller: ItermController, spawner: SessionSpawner) -> None:
        self.controller = controller
        self.spawner = spawner

    async def spawn_layout(
        self,
        layout: WindowLayout,
        project: Project,
        session_templates: dict[str, SessionTemplate],
    ) -> list[SpawnResult]:
        """Spawn a complete window layout.

        This method will be fully implemented in the window layout spawning task.
        """
        raise NotImplementedError("Window layout spawning not yet implemented")
