"""iTerm2 connection and session management.

This module provides the core integration with iTerm2's Python API for:
- Connection lifecycle management
- Session spawning and termination
- Window and tab tracking
"""

from __future__ import annotations

import asyncio
import logging
import re
import shlex
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, TypeVar

import iterm2

# Valid environment variable key pattern: starts with letter or underscore,
# followed by letters, digits, or underscores
_ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

from iterm_controller.exceptions import (
    ItermConnectionError,
    ItermNotConnectedError,
    ItermSessionError,
)
from iterm_controller.models import (
    ManagedSession,
    Project,
    SessionLayout,
    SessionTemplate,
    TabLayout,
    WindowLayout,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

T = TypeVar("T")


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
# Session Spawner
# =============================================================================


class SessionSpawner:
    """Spawns and manages terminal sessions."""

    def __init__(self, controller: ItermController) -> None:
        self.controller = controller
        self.managed_sessions: dict[str, ManagedSession] = {}

    def _validate_env_key(self, key: str) -> bool:
        """Validate that an environment variable key is safe.

        Valid keys must start with a letter or underscore, followed by
        letters, digits, or underscores. This prevents injection attacks
        via malicious key names.

        Args:
            key: The environment variable key to validate.

        Returns:
            True if the key is valid, False otherwise.
        """
        return bool(_ENV_KEY_PATTERN.match(key))

    def _build_command(
        self,
        template: SessionTemplate,
        project: Project,
    ) -> str:
        """Build the full command string for a session.

        Includes cd to working directory, environment exports, and the template command.

        Raises:
            ValueError: If any environment variable key is invalid.
        """
        working_dir = template.working_dir or project.path
        parts = [f"cd {self._quote_path(working_dir)}"]

        # Add environment exports if any
        if template.env:
            env_pairs = []
            for key, value in template.env.items():
                # Validate the key to prevent injection via key names
                if not self._validate_env_key(key):
                    raise ValueError(
                        f"Invalid environment variable key: {key!r}. "
                        "Keys must match ^[A-Za-z_][A-Za-z0-9_]*$"
                    )
                # Use shlex.quote for the value (returns single-quoted string)
                env_pairs.append(f"{key}={self._escape_value(value)}")
            parts.append(f"export {' '.join(env_pairs)}")

        # Add the main command if specified
        if template.command:
            parts.append(template.command)

        return " && ".join(parts)

    def _quote_path(self, path: str) -> str:
        """Quote a path for safe shell usage.

        Uses shlex.quote() to properly escape all shell metacharacters,
        preventing command injection attacks via malicious path names.
        """
        return shlex.quote(path)

    def _escape_value(self, value: str) -> str:
        """Escape special characters in environment variable values.

        Uses shlex.quote() to properly escape all shell metacharacters,
        preventing command injection attacks.
        """
        return shlex.quote(value)

    async def spawn_session(
        self,
        template: SessionTemplate,
        project: Project,
        window: iterm2.Window | None = None,
    ) -> SpawnResult:
        """Spawn a new session from template.

        Creates a new tab in the specified window (or current window) and
        sends the initial command from the template.

        Args:
            template: Session template defining the command and environment.
            project: Project context for working directory.
            window: Target window, or None to use current window (creating one if needed).

        Returns:
            SpawnResult with session_id, tab_id, and success status.
        """
        self.controller.require_connection()

        try:
            app = self.controller.app
            assert app is not None  # require_connection ensures this

            # Use provided window, current window, or create new
            if window is None:
                window = app.current_terminal_window
                if window is None:
                    window = await iterm2.Window.async_create(self.controller.connection)
                    logger.info("Created new iTerm2 window")

            # Create new tab
            tab = await window.async_create_tab()
            session = tab.current_session
            assert session is not None

            # Build and send command
            full_command = self._build_command(template, project)
            await session.async_send_text(full_command + "\n")

            # Track session
            managed = ManagedSession(
                id=session.session_id,
                template_id=template.id,
                project_id=project.id,
                tab_id=tab.tab_id,
            )
            self.managed_sessions[session.session_id] = managed

            logger.info(
                f"Spawned session {session.session_id} from template '{template.name}' "
                f"in tab {tab.tab_id}"
            )

            return SpawnResult(
                session_id=session.session_id,
                tab_id=tab.tab_id,
                success=True,
            )

        except Exception as e:
            logger.error(f"Failed to spawn session from template '{template.id}': {e}")
            return SpawnResult(
                session_id="",
                tab_id="",
                success=False,
                error=str(e),
            )

    async def spawn_split(
        self,
        template: SessionTemplate,
        project: Project,
        parent_session: iterm2.Session,
        vertical: bool = True,
    ) -> SpawnResult:
        """Spawn session as split pane.

        Creates a new pane by splitting an existing session and sends the
        initial command from the template.

        Args:
            template: Session template defining the command and environment.
            project: Project context for working directory.
            parent_session: Existing session to split.
            vertical: If True, split vertically (side by side); if False, horizontally.

        Returns:
            SpawnResult with session_id, tab_id, and success status.
        """
        self.controller.require_connection()

        try:
            # Split the parent session
            session = await parent_session.async_split_pane(vertical=vertical)

            # Build and send command
            full_command = self._build_command(template, project)
            await session.async_send_text(full_command + "\n")

            # Get tab_id from parent session's tab
            # Note: session.tab is available after split
            tab_id = parent_session.tab.tab_id if parent_session.tab else ""

            # Track session
            managed = ManagedSession(
                id=session.session_id,
                template_id=template.id,
                project_id=project.id,
                tab_id=tab_id,
            )
            self.managed_sessions[session.session_id] = managed

            logger.info(
                f"Spawned split session {session.session_id} from template '{template.name}' "
                f"(vertical={vertical})"
            )

            return SpawnResult(
                session_id=session.session_id,
                tab_id=tab_id,
                success=True,
            )

        except Exception as e:
            logger.error(f"Failed to spawn split session from template '{template.id}': {e}")
            return SpawnResult(
                session_id="",
                tab_id="",
                success=False,
                error=str(e),
            )

    def get_session(self, session_id: str) -> ManagedSession | None:
        """Get a managed session by ID."""
        return self.managed_sessions.get(session_id)

    def get_sessions_for_project(self, project_id: str) -> list[ManagedSession]:
        """Get all managed sessions for a project."""
        return [s for s in self.managed_sessions.values() if s.project_id == project_id]

    def untrack_session(self, session_id: str) -> None:
        """Remove a session from tracking."""
        if session_id in self.managed_sessions:
            del self.managed_sessions[session_id]
            logger.debug(f"Untracked session {session_id}")


# =============================================================================
# Session Terminator
# =============================================================================


@dataclass
class CloseResult:
    """Result of a session close operation."""

    session_id: str
    success: bool
    force_required: bool = False
    error: str | None = None


class SessionTerminator:
    """Handles graceful session termination.

    Provides methods for closing individual sessions, tabs, and bulk managed
    sessions with proper timeout handling and force-close fallback.
    """

    SIGTERM_TIMEOUT = 5.0  # Seconds to wait for graceful shutdown
    POLL_INTERVAL = 0.1  # Seconds between session state polls

    def __init__(self, controller: ItermController) -> None:
        """Initialize the terminator with an iTerm controller.

        Args:
            controller: The iTerm controller for session operations.
        """
        self.controller = controller

    async def close_session(
        self,
        session: iterm2.Session,
        force: bool = False,
    ) -> CloseResult:
        """Close a session, optionally with force.

        For graceful shutdown:
        1. Send Ctrl+C to interrupt any running process
        2. Wait briefly, then send "exit" command
        3. Wait up to SIGTERM_TIMEOUT for session to close
        4. Force close if timeout exceeded

        Args:
            session: The iTerm2 session to close.
            force: If True, skip graceful shutdown and force-close immediately.

        Returns:
            CloseResult with success status and details.
        """
        session_id = session.session_id

        try:
            if force:
                await session.async_close(force=True)
                logger.info(f"Force-closed session {session_id}")
                return CloseResult(
                    session_id=session_id,
                    success=True,
                    force_required=True,
                )

            # Try graceful shutdown
            # Send Ctrl+C to interrupt any running process
            await session.async_send_text("\x03")
            await asyncio.sleep(0.5)

            # Send exit command
            await session.async_send_text("exit\n")
            logger.debug(f"Sent exit command to session {session_id}")

            # Wait for session to close
            try:
                await asyncio.wait_for(
                    self._wait_for_close(session),
                    timeout=self.SIGTERM_TIMEOUT,
                )
                logger.info(f"Gracefully closed session {session_id}")
                return CloseResult(
                    session_id=session_id,
                    success=True,
                    force_required=False,
                )
            except asyncio.TimeoutError:
                # Graceful shutdown failed, force close
                logger.warning(
                    f"Graceful shutdown timed out for session {session_id}, forcing close"
                )
                await session.async_close(force=True)
                logger.info(f"Force-closed session {session_id} after timeout")
                return CloseResult(
                    session_id=session_id,
                    success=True,
                    force_required=True,
                )

        except Exception as e:
            logger.error(f"Failed to close session {session_id}: {e}")
            return CloseResult(
                session_id=session_id,
                success=False,
                error=str(e),
            )

    async def _wait_for_close(self, session: iterm2.Session) -> None:
        """Wait for a session to terminate.

        Polls the session state until it's no longer valid, indicating
        the session has closed.

        Args:
            session: The session to wait for.
        """
        while True:
            try:
                # Try to access session properties - raises if session is gone
                # We use async_get_screen_contents as a reliable way to check
                # if the session is still alive
                await session.async_get_screen_contents()
                await asyncio.sleep(self.POLL_INTERVAL)
            except Exception:
                # Session is gone (or inaccessible), which means it's closed
                break

    async def close_tab(self, tab: iterm2.Tab, force: bool = False) -> bool:
        """Close a tab and all its sessions.

        Args:
            tab: The iTerm2 tab to close.
            force: If True, force-close without asking for confirmation.

        Returns:
            True if the tab was closed successfully.
        """
        try:
            await tab.async_close(force=force)
            logger.info(f"Closed tab {tab.tab_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to close tab {tab.tab_id}: {e}")
            return False

    async def close_all_managed(
        self,
        sessions: list[ManagedSession],
        spawner: "SessionSpawner",
        force: bool = False,
    ) -> tuple[int, list[CloseResult]]:
        """Close all managed sessions, return count closed.

        Closes sessions in parallel for efficiency, then updates the spawner
        to untrack closed sessions.

        Args:
            sessions: List of managed sessions to close.
            spawner: The SessionSpawner to update for tracking cleanup.
            force: If True, force-close all sessions without graceful shutdown.

        Returns:
            Tuple of (count of successfully closed sessions, list of CloseResults).
        """
        if not sessions:
            return (0, [])

        self.controller.require_connection()

        if not self.controller.app:
            return (0, [])

        results: list[CloseResult] = []
        closed = 0

        # Gather all close operations to run in parallel
        async def close_one(managed: ManagedSession) -> CloseResult:
            try:
                session = await self.controller.app.async_get_session_by_id(managed.id)
                if session:
                    result = await self.close_session(session, force=force)
                    if result.success:
                        spawner.untrack_session(managed.id)
                    return result
                else:
                    # Session not found - already closed
                    spawner.untrack_session(managed.id)
                    return CloseResult(
                        session_id=managed.id,
                        success=True,
                        error="Session not found (already closed)",
                    )
            except Exception as e:
                logger.error(f"Error closing managed session {managed.id}: {e}")
                return CloseResult(
                    session_id=managed.id,
                    success=False,
                    error=str(e),
                )

        # Run all close operations concurrently
        results = await asyncio.gather(*[close_one(s) for s in sessions])

        closed = sum(1 for r in results if r.success)
        logger.info(f"Closed {closed}/{len(sessions)} managed sessions")

        return (closed, list(results))


# =============================================================================
# Window Layout Spawner
# =============================================================================


@dataclass
class LayoutSpawnResult:
    """Result of spawning an entire window layout."""

    window_id: str
    results: list[SpawnResult]
    success: bool
    error: str | None = None

    @property
    def all_successful(self) -> bool:
        """Check if all sessions spawned successfully."""
        return all(r.success for r in self.results)

    @property
    def spawned_session_ids(self) -> list[str]:
        """Get list of successfully spawned session IDs."""
        return [r.session_id for r in self.results if r.success]


class WindowLayoutSpawner:
    """Spawns window layouts with predefined tabs and sessions."""

    def __init__(self, controller: ItermController, spawner: SessionSpawner) -> None:
        self.controller = controller
        self.spawner = spawner

    async def spawn_layout(
        self,
        layout: WindowLayout,
        project: Project,
        session_templates: dict[str, SessionTemplate],
    ) -> LayoutSpawnResult:
        """Spawn a complete window layout.

        Creates a new iTerm2 window and populates it with tabs and sessions
        according to the WindowLayout configuration.

        Args:
            layout: The window layout configuration specifying tabs and sessions.
            project: Project context for working directories and environment.
            session_templates: Mapping of template IDs to SessionTemplate objects.

        Returns:
            LayoutSpawnResult containing the window ID, individual spawn results,
            and overall success status.
        """
        self.controller.require_connection()
        results: list[SpawnResult] = []

        try:
            # Create new window
            window = await iterm2.Window.async_create(self.controller.connection)
            window_id = window.window_id
            logger.info(f"Created new window {window_id} for layout '{layout.name}'")

            if not layout.tabs:
                logger.warning(f"Layout '{layout.name}' has no tabs defined")
                return LayoutSpawnResult(
                    window_id=window_id,
                    results=results,
                    success=True,
                )

            for tab_index, tab_layout in enumerate(layout.tabs):
                tab_results = await self._spawn_tab(
                    window=window,
                    tab_index=tab_index,
                    tab_layout=tab_layout,
                    project=project,
                    session_templates=session_templates,
                )
                results.extend(tab_results)

            success = all(r.success for r in results) if results else True
            logger.info(
                f"Layout '{layout.name}' spawned with {len(results)} sessions "
                f"({sum(1 for r in results if r.success)} successful)"
            )

            return LayoutSpawnResult(
                window_id=window_id,
                results=results,
                success=success,
            )

        except Exception as e:
            logger.error(f"Failed to spawn layout '{layout.name}': {e}")
            return LayoutSpawnResult(
                window_id="",
                results=results,
                success=False,
                error=str(e),
            )

    async def _spawn_tab(
        self,
        window: iterm2.Window,
        tab_index: int,
        tab_layout: "TabLayout",
        project: Project,
        session_templates: dict[str, SessionTemplate],
    ) -> list[SpawnResult]:
        """Spawn a single tab with its sessions.

        Args:
            window: The iTerm2 window to create the tab in.
            tab_index: Index of this tab (0 = use window's default tab).
            tab_layout: Configuration for this tab's layout.
            project: Project context.
            session_templates: Available session templates.

        Returns:
            List of SpawnResult for each session in the tab.
        """
        results: list[SpawnResult] = []

        try:
            # First tab uses window's default tab, others create new tabs
            if tab_index == 0:
                tab = window.current_tab
                if tab is None:
                    logger.error("Window has no current tab")
                    return results
            else:
                tab = await window.async_create_tab()

            # Set tab title
            if tab_layout.name:
                await tab.async_set_title(tab_layout.name)
                logger.debug(f"Set tab title to '{tab_layout.name}'")

            if not tab_layout.sessions:
                logger.debug(f"Tab '{tab_layout.name}' has no sessions defined")
                return results

            # Get the tab's initial session as the parent for splits
            current_session = tab.current_session
            if current_session is None:
                logger.error(f"Tab '{tab_layout.name}' has no current session")
                return results

            for session_index, session_layout in enumerate(tab_layout.sessions):
                result = await self._spawn_session_in_tab(
                    tab=tab,
                    current_session=current_session,
                    session_index=session_index,
                    session_layout=session_layout,
                    project=project,
                    session_templates=session_templates,
                )
                if result:
                    results.append(result)
                    # Update current_session for the next split if successful
                    if result.success and session_index > 0:
                        # After a split, continue splitting from the new session
                        try:
                            new_session = (
                                await self.controller.app.async_get_session_by_id(
                                    result.session_id
                                )
                            )
                            if new_session:
                                current_session = new_session
                        except Exception:
                            pass  # Keep using the previous session

        except Exception as e:
            logger.error(f"Failed to spawn tab '{tab_layout.name}': {e}")

        return results

    async def _spawn_session_in_tab(
        self,
        tab: iterm2.Tab,
        current_session: iterm2.Session,
        session_index: int,
        session_layout: "SessionLayout",
        project: Project,
        session_templates: dict[str, SessionTemplate],
    ) -> SpawnResult | None:
        """Spawn a single session within a tab.

        Args:
            tab: The tab to spawn the session in.
            current_session: The session to use or split from.
            session_index: Index of this session (0 = use tab's default session).
            session_layout: Configuration for this session.
            project: Project context.
            session_templates: Available session templates.

        Returns:
            SpawnResult for this session, or None if template not found.
        """
        template = session_templates.get(session_layout.template_id)
        if not template:
            logger.warning(
                f"Session template '{session_layout.template_id}' not found, skipping"
            )
            return SpawnResult(
                session_id="",
                tab_id=tab.tab_id,
                success=False,
                error=f"Template '{session_layout.template_id}' not found",
            )

        try:
            if session_index == 0:
                # First session uses the tab's default session
                # Send command directly to it
                full_command = self.spawner._build_command(template, project)
                await current_session.async_send_text(full_command + "\n")

                # Track session
                managed = ManagedSession(
                    id=current_session.session_id,
                    template_id=template.id,
                    project_id=project.id,
                    tab_id=tab.tab_id,
                )
                self.spawner.managed_sessions[current_session.session_id] = managed

                logger.info(
                    f"Initialized tab's default session with template '{template.name}'"
                )

                return SpawnResult(
                    session_id=current_session.session_id,
                    tab_id=tab.tab_id,
                    success=True,
                )
            else:
                # Subsequent sessions are splits
                vertical = session_layout.split == "vertical"
                return await self.spawner.spawn_split(
                    template=template,
                    project=project,
                    parent_session=current_session,
                    vertical=vertical,
                )

        except Exception as e:
            logger.error(
                f"Failed to spawn session from template '{template.id}': {e}"
            )
            return SpawnResult(
                session_id="",
                tab_id=tab.tab_id,
                success=False,
                error=str(e),
            )


# =============================================================================
# Window Layout Manager
# =============================================================================


class WindowLayoutManager:
    """Manages window layout persistence.

    Provides functionality to save, load, delete, and list window layouts.
    Also supports capturing the current window state as a new layout.
    """

    def __init__(self, controller: ItermController) -> None:
        """Initialize the layout manager.

        Args:
            controller: The iTerm controller for session operations.
        """
        self.controller = controller
        self._layouts: dict[str, WindowLayout] = {}

    def load_from_config(self, layouts: list[WindowLayout]) -> None:
        """Load layouts from configuration.

        Args:
            layouts: List of WindowLayout objects from AppConfig.
        """
        self._layouts = {layout.id: layout for layout in layouts}
        logger.debug(f"Loaded {len(self._layouts)} window layouts")

    def list_layouts(self) -> list[WindowLayout]:
        """List all available layouts.

        Returns:
            List of all stored WindowLayout objects.
        """
        return list(self._layouts.values())

    def get_layout(self, layout_id: str) -> WindowLayout | None:
        """Get a layout by ID.

        Args:
            layout_id: The unique identifier of the layout.

        Returns:
            The WindowLayout if found, None otherwise.
        """
        return self._layouts.get(layout_id)

    def save_layout(self, layout: WindowLayout) -> None:
        """Save or update a layout.

        If a layout with the same ID exists, it will be replaced.

        Args:
            layout: The WindowLayout to save.
        """
        self._layouts[layout.id] = layout
        logger.info(f"Saved layout '{layout.name}' with ID '{layout.id}'")

    def delete_layout(self, layout_id: str) -> bool:
        """Delete a layout by ID.

        Args:
            layout_id: The unique identifier of the layout to delete.

        Returns:
            True if the layout was deleted, False if not found.
        """
        if layout_id in self._layouts:
            del self._layouts[layout_id]
            logger.info(f"Deleted layout '{layout_id}'")
            return True
        return False

    def get_layouts_for_config(self) -> list[WindowLayout]:
        """Get all layouts for saving to configuration.

        Returns:
            List of WindowLayout objects to be saved to AppConfig.
        """
        return list(self._layouts.values())

    async def capture_current_layout(
        self,
        layout_id: str,
        layout_name: str,
        window: iterm2.Window | None = None,
    ) -> WindowLayout | None:
        """Capture the current window state as a new layout.

        Captures the tab and session structure of a window, inferring
        split directions from session positions.

        Args:
            layout_id: Unique identifier for the new layout.
            layout_name: Display name for the layout.
            window: The window to capture, or None for current window.

        Returns:
            The captured WindowLayout, or None if capture failed.
        """
        self.controller.require_connection()

        if not self.controller.app:
            return None

        try:
            if window is None:
                window = self.controller.app.current_terminal_window

            if window is None:
                logger.warning("No window available to capture")
                return None

            tabs: list[TabLayout] = []

            for tab in window.tabs:
                tab_layout = await self._capture_tab(tab)
                if tab_layout:
                    tabs.append(tab_layout)

            layout = WindowLayout(
                id=layout_id,
                name=layout_name,
                tabs=tabs,
            )

            logger.info(
                f"Captured layout '{layout_name}' with {len(tabs)} tabs "
                f"from window {window.window_id}"
            )

            return layout

        except Exception as e:
            logger.error(f"Failed to capture layout: {e}")
            return None

    async def _capture_tab(self, tab: iterm2.Tab) -> TabLayout | None:
        """Capture a single tab's layout.

        Args:
            tab: The iTerm2 tab to capture.

        Returns:
            TabLayout for the tab, or None if capture failed.
        """
        try:
            title = await tab.async_get_variable("title") or ""
            sessions: list[SessionLayout] = []

            for i, session in enumerate(tab.sessions):
                session_layout = await self._capture_session(session, i)
                sessions.append(session_layout)

            return TabLayout(
                name=title,
                sessions=sessions,
            )

        except Exception as e:
            logger.error(f"Failed to capture tab: {e}")
            return None

    async def _capture_session(
        self,
        session: iterm2.Session,
        index: int,
    ) -> SessionLayout:
        """Capture a single session's layout.

        Since we can't determine the exact template that created a session,
        we use a placeholder template ID that should be mapped when the
        layout is reused.

        Args:
            session: The iTerm2 session to capture.
            index: The position of this session in the tab.

        Returns:
            SessionLayout for the session.
        """
        # Determine split direction based on session position
        # First session has no split, subsequent sessions are splits
        if index == 0:
            split = "none"
        else:
            # Try to infer split direction from session layout
            # This is a best-effort approach; iTerm2 doesn't expose this directly
            split = await self._infer_split_direction(session)

        # Use a placeholder template ID - the user should map this
        # to an actual template when reusing the layout
        template_id = f"session_{index}"

        return SessionLayout(
            template_id=template_id,
            split=split,
            size_percent=50,  # Default size
        )

    async def _infer_split_direction(self, session: iterm2.Session) -> str:
        """Infer the split direction for a session.

        Attempts to determine if a session was created via horizontal or
        vertical split by examining its position relative to siblings.

        Args:
            session: The session to analyze.

        Returns:
            "horizontal" or "vertical" (defaults to vertical).
        """
        try:
            # Get frame to determine split direction
            # If the session is wider than it is tall relative to neighbors,
            # it was likely a horizontal split
            frame = await session.async_get_property("frame")
            if frame:
                # Frame is a dict with 'origin' and 'size'
                size = frame.get("size", {})
                width = size.get("width", 0)
                height = size.get("height", 0)

                # Heuristic: if aspect ratio suggests horizontal split
                if width > height * 1.5:
                    return "horizontal"

            return "vertical"
        except Exception:
            return "vertical"

    async def capture_and_save(
        self,
        layout_id: str,
        layout_name: str,
        window: iterm2.Window | None = None,
    ) -> WindowLayout | None:
        """Capture the current window layout and save it.

        Convenience method that captures and saves in one step.

        Args:
            layout_id: Unique identifier for the new layout.
            layout_name: Display name for the layout.
            window: The window to capture, or None for current window.

        Returns:
            The captured and saved WindowLayout, or None if capture failed.
        """
        layout = await self.capture_current_layout(layout_id, layout_name, window)
        if layout:
            self.save_layout(layout)
        return layout
