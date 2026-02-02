"""iTerm2 adapter implementing the terminal provider protocols.

This module provides adapter classes that wrap the existing iTerm2 implementation
to conform to the abstract terminal protocols defined in ports.py. This enables
the application to work with either the real iTerm2 or mock implementations
for testing.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from iterm_controller.iterm.connection import ItermController
from iterm_controller.iterm.spawner import SessionSpawner, SpawnResult
from iterm_controller.iterm.terminator import CloseResult, SessionTerminator
from iterm_controller.iterm.tracker import TabState, WindowState, WindowTracker
from iterm_controller.ports import (
    CloseResultData,
    OutputReaderProtocol,
    SessionSpawnerProtocol,
    SessionTerminatorProtocol,
    SpawnResultData,
    TerminalConnection,
    TerminalProvider,
    TerminalTab,
    TerminalWindow,
    WindowTrackerProtocol,
)
from iterm_controller.session_monitor import BatchOutputReader

if TYPE_CHECKING:
    from iterm_controller.models import ManagedSession, Project, SessionTemplate

logger = logging.getLogger(__name__)


class ItermConnectionAdapter:
    """Adapter for ItermController implementing TerminalConnection protocol."""

    def __init__(self, controller: ItermController) -> None:
        self._controller = controller

    @property
    def is_connected(self) -> bool:
        return self._controller.is_connected

    async def connect(self) -> bool:
        return await self._controller.connect()

    async def disconnect(self) -> None:
        await self._controller.disconnect()

    async def reconnect(self) -> bool:
        return await self._controller.reconnect()

    @property
    def wrapped(self) -> ItermController:
        """Get the underlying iTerm controller for cases needing direct access."""
        return self._controller


class ItermSpawnerAdapter:
    """Adapter for SessionSpawner implementing SessionSpawnerProtocol."""

    def __init__(self, spawner: SessionSpawner) -> None:
        self._spawner = spawner

    def _to_result_data(self, result: SpawnResult) -> SpawnResultData:
        """Convert iTerm SpawnResult to protocol SpawnResultData."""
        return SpawnResultData(
            session_id=result.session_id,
            tab_id=result.tab_id,
            success=result.success,
            error=result.error,
            window_id=result.window_id,
        )

    async def spawn_session(
        self,
        template: SessionTemplate,
        project: Project,
    ) -> SpawnResultData:
        result = await self._spawner.spawn_session(template, project)
        return self._to_result_data(result)

    async def spawn_split(
        self,
        template: SessionTemplate,
        project: Project,
        parent_session_id: str,
        vertical: bool = True,
    ) -> SpawnResultData:
        # Get the actual iTerm2 session object
        controller = self._spawner.controller
        if not controller.app:
            return SpawnResultData(
                session_id="",
                tab_id="",
                success=False,
                error="Not connected to iTerm2",
            )

        parent_session = await controller.app.async_get_session_by_id(parent_session_id)
        if not parent_session:
            return SpawnResultData(
                session_id="",
                tab_id="",
                success=False,
                error=f"Parent session {parent_session_id} not found",
            )

        result = await self._spawner.spawn_split(
            template, project, parent_session, vertical
        )
        return self._to_result_data(result)

    def get_session(self, session_id: str) -> ManagedSession | None:
        return self._spawner.get_session(session_id)

    def get_sessions_for_project(self, project_id: str) -> list[ManagedSession]:
        return self._spawner.get_sessions_for_project(project_id)

    def untrack_session(self, session_id: str) -> None:
        self._spawner.untrack_session(session_id)

    @property
    def wrapped(self) -> SessionSpawner:
        """Get the underlying spawner for cases needing direct access."""
        return self._spawner


class ItermTerminatorAdapter:
    """Adapter for SessionTerminator implementing SessionTerminatorProtocol."""

    def __init__(
        self,
        terminator: SessionTerminator,
        controller: ItermController,
    ) -> None:
        self._terminator = terminator
        self._controller = controller

    def _to_result_data(self, result: CloseResult) -> CloseResultData:
        """Convert iTerm CloseResult to protocol CloseResultData."""
        return CloseResultData(
            session_id=result.session_id,
            success=result.success,
            force_required=result.force_required,
            error=result.error,
        )

    async def close_session(
        self,
        session_id: str,
        force: bool = False,
    ) -> CloseResultData:
        if not self._controller.app:
            return CloseResultData(
                session_id=session_id,
                success=False,
                error="Not connected to iTerm2",
            )

        session = await self._controller.app.async_get_session_by_id(session_id)
        if not session:
            # Session not found - already closed
            return CloseResultData(
                session_id=session_id,
                success=True,
                error="Session not found (already closed)",
            )

        result = await self._terminator.close_session(session, force)
        return self._to_result_data(result)

    async def close_tab(self, tab_id: str, force: bool = False) -> bool:
        if not self._controller.app:
            return False

        # Find the tab by ID
        for window in self._controller.app.terminal_windows:
            for tab in window.tabs:
                if tab.tab_id == tab_id:
                    return await self._terminator.close_tab(tab, force)
        return False

    async def close_all_managed(
        self,
        sessions: list[ManagedSession],
        spawner: SessionSpawnerProtocol,
        force: bool = False,
    ) -> tuple[int, list[CloseResultData]]:
        # Need to unwrap if it's an adapter
        actual_spawner: SessionSpawner
        if isinstance(spawner, ItermSpawnerAdapter):
            actual_spawner = spawner.wrapped
        elif isinstance(spawner, SessionSpawner):
            actual_spawner = spawner
        else:
            # Can't use with non-iTerm spawner
            return (0, [])

        count, results = await self._terminator.close_all_managed(
            sessions, actual_spawner, force
        )
        return (count, [self._to_result_data(r) for r in results])

    @property
    def wrapped(self) -> SessionTerminator:
        """Get the underlying terminator for cases needing direct access."""
        return self._terminator


class ItermOutputReaderAdapter:
    """Adapter for BatchOutputReader implementing OutputReaderProtocol."""

    def __init__(self, reader: BatchOutputReader) -> None:
        self._reader = reader

    async def read_output(self, session_id: str, lines: int = 50) -> str:
        # Create a temporary reader with the specified line count
        original_lines = self._reader.lines_to_read
        self._reader.lines_to_read = lines
        try:
            result = await self._reader.read_batch([session_id])
            return result.get(session_id, "")
        finally:
            self._reader.lines_to_read = original_lines

    async def read_batch(self, session_ids: list[str]) -> dict[str, str]:
        return await self._reader.read_batch(session_ids)

    @property
    def wrapped(self) -> BatchOutputReader:
        """Get the underlying reader for cases needing direct access."""
        return self._reader


class ItermTrackerAdapter:
    """Adapter for WindowTracker implementing WindowTrackerProtocol."""

    def __init__(self, tracker: WindowTracker) -> None:
        self._tracker = tracker

    def _to_terminal_tab(self, tab: TabState) -> TerminalTab:
        """Convert iTerm TabState to protocol TerminalTab."""
        return TerminalTab(
            id=tab.tab_id,
            title=tab.title,
            session_ids=list(tab.session_ids),
        )

    def _to_terminal_window(self, window: WindowState) -> TerminalWindow:
        """Convert iTerm WindowState to protocol TerminalWindow."""
        return TerminalWindow(
            id=window.window_id,
            tabs=[self._to_terminal_tab(t) for t in window.tabs],
        )

    async def refresh(self) -> None:
        await self._tracker.refresh()

    def get_windows(self) -> list[TerminalWindow]:
        return [self._to_terminal_window(w) for w in self._tracker.windows.values()]

    def get_window(self, window_id: str) -> TerminalWindow | None:
        window = self._tracker.windows.get(window_id)
        if window:
            return self._to_terminal_window(window)
        return None

    def mark_managed(self, tab_id: str, window_id: str) -> None:
        self._tracker.mark_managed(tab_id, window_id)

    def get_managed_tab_ids(self, window_id: str | None = None) -> set[str]:
        return self._tracker.get_managed_tab_ids(window_id)

    @property
    def wrapped(self) -> WindowTracker:
        """Get the underlying tracker for cases needing direct access."""
        return self._tracker


class ItermTerminalProvider:
    """Complete iTerm2 implementation of the TerminalProvider protocol.

    This class provides a convenient way to create all the iTerm2 adapters
    with a single factory, ensuring they share the same underlying controller.

    Example:
        provider = await ItermTerminalProvider.create()
        await provider.connection.connect()

        result = await provider.spawner.spawn_session(template, project)
        if result.success:
            output = await provider.output_reader.read_output(result.session_id)
    """

    def __init__(
        self,
        connection: ItermConnectionAdapter,
        spawner: ItermSpawnerAdapter,
        terminator: ItermTerminatorAdapter,
        output_reader: ItermOutputReaderAdapter,
        tracker: ItermTrackerAdapter,
    ) -> None:
        self._connection = connection
        self._spawner = spawner
        self._terminator = terminator
        self._output_reader = output_reader
        self._tracker = tracker

    @classmethod
    def create(cls, controller: ItermController | None = None) -> ItermTerminalProvider:
        """Create a complete iTerm2 terminal provider.

        Args:
            controller: Existing controller to use, or None to create a new one.

        Returns:
            A fully configured ItermTerminalProvider.
        """
        if controller is None:
            controller = ItermController()

        spawner = SessionSpawner(controller)
        terminator = SessionTerminator(controller)
        tracker = WindowTracker(controller)
        reader = BatchOutputReader(controller)

        return cls(
            connection=ItermConnectionAdapter(controller),
            spawner=ItermSpawnerAdapter(spawner),
            terminator=ItermTerminatorAdapter(terminator, controller),
            output_reader=ItermOutputReaderAdapter(reader),
            tracker=ItermTrackerAdapter(tracker),
        )

    @property
    def connection(self) -> TerminalConnection:
        return self._connection

    @property
    def spawner(self) -> SessionSpawnerProtocol:
        return self._spawner

    @property
    def terminator(self) -> SessionTerminatorProtocol:
        return self._terminator

    @property
    def output_reader(self) -> OutputReaderProtocol:
        return self._output_reader

    @property
    def tracker(self) -> WindowTrackerProtocol:
        return self._tracker

    def get_controller(self) -> ItermController:
        """Get the underlying iTerm controller for direct access when needed."""
        return self._connection.wrapped
