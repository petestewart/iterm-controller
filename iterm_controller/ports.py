"""Terminal provider abstraction layer.

This module defines protocols (interfaces) for terminal operations, allowing the
application to work with different terminal implementations (iTerm2, mock for testing,
or potentially other terminal emulators in the future).

The abstraction follows the "ports and adapters" (hexagonal) architecture pattern,
where ports define the interfaces and adapters (like the iterm/ package) provide
implementations.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from iterm_controller.models import ManagedSession, Project, SessionTemplate


# =============================================================================
# Data Types
# =============================================================================


@dataclass
class TerminalSession:
    """Abstract representation of a terminal session.

    This is a minimal data structure that represents a session without
    depending on any specific terminal implementation.
    """

    id: str
    """Unique identifier for the session."""

    tab_id: str
    """ID of the tab containing this session."""

    is_active: bool = True
    """Whether the session is still active/valid."""


@dataclass
class TerminalTab:
    """Abstract representation of a terminal tab."""

    id: str
    """Unique identifier for the tab."""

    title: str = ""
    """Title displayed for the tab."""

    session_ids: list[str] = field(default_factory=list)
    """IDs of sessions contained in this tab."""


@dataclass
class TerminalWindow:
    """Abstract representation of a terminal window."""

    id: str
    """Unique identifier for the window."""

    tabs: list[TerminalTab] = field(default_factory=list)
    """Tabs in this window."""


@dataclass
class SpawnConfig:
    """Configuration for spawning a new session.

    This provides a terminal-agnostic way to describe what session
    should be created.
    """

    command: str
    """Command to run in the session."""

    working_directory: str
    """Working directory for the session."""

    environment: dict[str, str] = field(default_factory=dict)
    """Environment variables to set."""

    name: str = ""
    """Display name for the session."""


@dataclass
class SpawnResultData:
    """Result of a session spawn operation."""

    session_id: str
    """ID of the spawned session, or empty string on failure."""

    tab_id: str
    """ID of the tab containing the session, or empty string on failure."""

    success: bool
    """Whether the spawn was successful."""

    error: str | None = None
    """Error message if spawn failed."""


@dataclass
class CloseResultData:
    """Result of a session close operation."""

    session_id: str
    """ID of the session that was closed."""

    success: bool
    """Whether the close was successful."""

    force_required: bool = False
    """Whether force-close was required (graceful shutdown failed)."""

    error: str | None = None
    """Error message if close failed."""


# =============================================================================
# Protocols
# =============================================================================


@runtime_checkable
class TerminalConnection(Protocol):
    """Protocol for terminal connection management.

    Implementations must provide methods for connecting and disconnecting
    from the terminal emulator.
    """

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if currently connected to the terminal."""
        ...

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the terminal.

        Returns:
            True if connection was successful.

        Raises:
            ItermConnectionError: If connection fails (for iTerm implementation).
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Cleanly disconnect from the terminal."""
        ...

    @abstractmethod
    async def reconnect(self) -> bool:
        """Attempt to reconnect after disconnection.

        Returns:
            True if reconnection was successful.
        """
        ...


@runtime_checkable
class SessionSpawnerProtocol(Protocol):
    """Protocol for creating terminal sessions.

    Implementations must provide methods for spawning sessions as new tabs
    or as split panes within existing sessions.
    """

    @abstractmethod
    async def spawn_session(
        self,
        template: SessionTemplate,
        project: Project,
    ) -> SpawnResultData:
        """Spawn a new session in a new tab.

        Args:
            template: Session template with command and environment.
            project: Project for context (working directory, etc.).

        Returns:
            Result indicating success/failure and session IDs.
        """
        ...

    @abstractmethod
    async def spawn_split(
        self,
        template: SessionTemplate,
        project: Project,
        parent_session_id: str,
        vertical: bool = True,
    ) -> SpawnResultData:
        """Spawn a session as a split pane of an existing session.

        Args:
            template: Session template with command and environment.
            project: Project for context.
            parent_session_id: ID of the session to split.
            vertical: If True, split vertically; if False, horizontally.

        Returns:
            Result indicating success/failure and session IDs.
        """
        ...

    @abstractmethod
    def get_session(self, session_id: str) -> ManagedSession | None:
        """Get a managed session by ID.

        Args:
            session_id: The session ID to look up.

        Returns:
            The managed session if found, None otherwise.
        """
        ...

    @abstractmethod
    def get_sessions_for_project(self, project_id: str) -> list[ManagedSession]:
        """Get all managed sessions for a project.

        Args:
            project_id: The project ID to filter by.

        Returns:
            List of managed sessions belonging to the project.
        """
        ...

    @abstractmethod
    def untrack_session(self, session_id: str) -> None:
        """Remove a session from tracking.

        Args:
            session_id: The session ID to untrack.
        """
        ...


@runtime_checkable
class SessionTerminatorProtocol(Protocol):
    """Protocol for terminating terminal sessions.

    Implementations must provide methods for gracefully closing sessions
    with fallback to force-close if needed.
    """

    @abstractmethod
    async def close_session(
        self,
        session_id: str,
        force: bool = False,
    ) -> CloseResultData:
        """Close a session.

        For graceful shutdown, implementations should:
        1. Send interrupt signal (Ctrl+C)
        2. Send exit command
        3. Wait for session to close (with timeout)
        4. Force close if timeout exceeded

        Args:
            session_id: ID of the session to close.
            force: If True, skip graceful shutdown.

        Returns:
            Result indicating success/failure.
        """
        ...

    @abstractmethod
    async def close_tab(self, tab_id: str, force: bool = False) -> bool:
        """Close a tab and all its sessions.

        Args:
            tab_id: ID of the tab to close.
            force: If True, force-close without confirmation.

        Returns:
            True if the tab was closed successfully.
        """
        ...

    @abstractmethod
    async def close_all_managed(
        self,
        sessions: list[ManagedSession],
        spawner: SessionSpawnerProtocol,
        force: bool = False,
    ) -> tuple[int, list[CloseResultData]]:
        """Close all managed sessions.

        Args:
            sessions: List of sessions to close.
            spawner: The spawner to update for tracking cleanup.
            force: If True, force-close all sessions.

        Returns:
            Tuple of (count closed successfully, list of results).
        """
        ...


@runtime_checkable
class OutputReaderProtocol(Protocol):
    """Protocol for reading session output.

    Implementations must provide methods for reading terminal output
    for attention state detection and monitoring.
    """

    @abstractmethod
    async def read_output(self, session_id: str, lines: int = 50) -> str:
        """Read recent output from a session.

        Args:
            session_id: ID of the session to read from.
            lines: Number of lines to read (from the end).

        Returns:
            The session's recent output as a string.

        Raises:
            SessionNotFoundError: If the session doesn't exist.
        """
        ...

    @abstractmethod
    async def read_batch(self, session_ids: list[str]) -> dict[str, str]:
        """Read output from multiple sessions concurrently.

        Args:
            session_ids: List of session IDs to read from.

        Returns:
            Dictionary mapping session_id to output content.
            Sessions that couldn't be read are omitted.
        """
        ...


@runtime_checkable
class WindowTrackerProtocol(Protocol):
    """Protocol for tracking terminal window state.

    Implementations must provide methods for refreshing and querying
    the current state of windows, tabs, and sessions.
    """

    @abstractmethod
    async def refresh(self) -> None:
        """Refresh window state from the terminal."""
        ...

    @abstractmethod
    def get_windows(self) -> list[TerminalWindow]:
        """Get all tracked windows.

        Returns:
            List of window state objects.
        """
        ...

    @abstractmethod
    def get_window(self, window_id: str) -> TerminalWindow | None:
        """Get a specific window by ID.

        Args:
            window_id: The window ID to look up.

        Returns:
            The window state if found, None otherwise.
        """
        ...

    @abstractmethod
    def mark_managed(self, tab_id: str, window_id: str) -> None:
        """Mark a tab as managed by this application.

        Args:
            tab_id: The tab ID to mark.
            window_id: The window containing the tab.
        """
        ...

    @abstractmethod
    def get_managed_tab_ids(self, window_id: str | None = None) -> set[str]:
        """Get all managed tab IDs.

        Args:
            window_id: If provided, filter to this window only.

        Returns:
            Set of managed tab IDs.
        """
        ...


@runtime_checkable
class TerminalProvider(Protocol):
    """Composite protocol for all terminal operations.

    This is the main protocol that terminal implementations should satisfy.
    It combines all the individual protocols for a complete terminal integration.

    Example usage:
        # For production with iTerm2
        controller = ItermController()
        await controller.connect()
        spawner = SessionSpawner(controller)
        terminator = SessionTerminator(controller)
        # ... use them as TerminalProvider components

        # For testing with mocks
        class MockController:
            ...  # implement TerminalConnection
        mock_controller = MockController()
        # ... tests can now run without iTerm2
    """

    @property
    @abstractmethod
    def connection(self) -> TerminalConnection:
        """Get the connection component."""
        ...

    @property
    @abstractmethod
    def spawner(self) -> SessionSpawnerProtocol:
        """Get the session spawner component."""
        ...

    @property
    @abstractmethod
    def terminator(self) -> SessionTerminatorProtocol:
        """Get the session terminator component."""
        ...

    @property
    @abstractmethod
    def output_reader(self) -> OutputReaderProtocol:
        """Get the output reader component."""
        ...

    @property
    @abstractmethod
    def tracker(self) -> WindowTrackerProtocol:
        """Get the window tracker component."""
        ...
