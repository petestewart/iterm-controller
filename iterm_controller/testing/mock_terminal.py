"""Mock terminal implementation for testing.

This module provides mock implementations of all terminal protocols,
enabling unit testing without requiring iTerm2 to be running.

Example usage in tests:
    from iterm_controller.testing import MockTerminalProvider

    def test_spawn_session():
        provider = MockTerminalProvider()
        provider.connection.set_connected(True)

        # Spawn a session
        result = await provider.spawner.spawn_session(template, project)
        assert result.success

        # Read output
        provider.output_reader.set_output(result.session_id, "Hello, World!")
        output = await provider.output_reader.read_output(result.session_id)
        assert output == "Hello, World!"
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from iterm_controller.models import ManagedSession
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

if TYPE_CHECKING:
    from iterm_controller.models import Project, SessionTemplate


@dataclass
class MockSession:
    """A mock session for testing."""

    id: str
    tab_id: str
    template_id: str
    project_id: str
    output: str = ""
    is_closed: bool = False


class MockConnection:
    """Mock implementation of TerminalConnection for testing."""

    def __init__(self) -> None:
        self._connected = False
        self._connect_should_fail = False
        self._fail_message = "Mock connection failure"

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        if self._connect_should_fail:
            raise RuntimeError(self._fail_message)
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def reconnect(self) -> bool:
        await self.disconnect()
        return await self.connect()

    # Test helpers
    def set_connected(self, connected: bool) -> None:
        """Set the connection state directly for testing."""
        self._connected = connected

    def set_connect_failure(
        self, should_fail: bool, message: str = "Mock connection failure"
    ) -> None:
        """Configure connect() to fail for testing error handling."""
        self._connect_should_fail = should_fail
        self._fail_message = message


class MockSessionSpawner:
    """Mock implementation of SessionSpawnerProtocol for testing."""

    def __init__(self) -> None:
        self._sessions: dict[str, MockSession] = {}
        self._managed_sessions: dict[str, ManagedSession] = {}
        self._spawn_should_fail = False
        self._fail_message = "Mock spawn failure"
        self._tab_counter = 0

    async def spawn_session(
        self,
        template: SessionTemplate,
        project: Project,
    ) -> SpawnResultData:
        if self._spawn_should_fail:
            return SpawnResultData(
                session_id="",
                tab_id="",
                success=False,
                error=self._fail_message,
            )

        session_id = f"mock-session-{uuid.uuid4().hex[:8]}"
        self._tab_counter += 1
        tab_id = f"mock-tab-{self._tab_counter}"

        mock_session = MockSession(
            id=session_id,
            tab_id=tab_id,
            template_id=template.id,
            project_id=project.id,
        )
        self._sessions[session_id] = mock_session

        managed = ManagedSession(
            id=session_id,
            template_id=template.id,
            project_id=project.id,
            tab_id=tab_id,
        )
        self._managed_sessions[session_id] = managed

        return SpawnResultData(
            session_id=session_id,
            tab_id=tab_id,
            success=True,
        )

    async def spawn_split(
        self,
        template: SessionTemplate,
        project: Project,
        parent_session_id: str,
        vertical: bool = True,
    ) -> SpawnResultData:
        if self._spawn_should_fail:
            return SpawnResultData(
                session_id="",
                tab_id="",
                success=False,
                error=self._fail_message,
            )

        parent = self._sessions.get(parent_session_id)
        if not parent:
            return SpawnResultData(
                session_id="",
                tab_id="",
                success=False,
                error=f"Parent session {parent_session_id} not found",
            )

        session_id = f"mock-session-{uuid.uuid4().hex[:8]}"
        tab_id = parent.tab_id  # Split stays in same tab

        mock_session = MockSession(
            id=session_id,
            tab_id=tab_id,
            template_id=template.id,
            project_id=project.id,
        )
        self._sessions[session_id] = mock_session

        managed = ManagedSession(
            id=session_id,
            template_id=template.id,
            project_id=project.id,
            tab_id=tab_id,
        )
        self._managed_sessions[session_id] = managed

        return SpawnResultData(
            session_id=session_id,
            tab_id=tab_id,
            success=True,
        )

    def get_session(self, session_id: str) -> ManagedSession | None:
        return self._managed_sessions.get(session_id)

    def get_sessions_for_project(self, project_id: str) -> list[ManagedSession]:
        return [s for s in self._managed_sessions.values() if s.project_id == project_id]

    def untrack_session(self, session_id: str) -> None:
        self._managed_sessions.pop(session_id, None)

    # Test helpers
    def set_spawn_failure(
        self, should_fail: bool, message: str = "Mock spawn failure"
    ) -> None:
        """Configure spawn operations to fail for testing error handling."""
        self._spawn_should_fail = should_fail
        self._fail_message = message

    def get_mock_session(self, session_id: str) -> MockSession | None:
        """Get the mock session object for inspection."""
        return self._sessions.get(session_id)

    def get_all_sessions(self) -> list[MockSession]:
        """Get all mock sessions."""
        return list(self._sessions.values())


class MockSessionTerminator:
    """Mock implementation of SessionTerminatorProtocol for testing."""

    def __init__(self, spawner: MockSessionSpawner) -> None:
        self._spawner = spawner
        self._close_should_fail = False
        self._fail_message = "Mock close failure"
        self._require_force = False

    async def close_session(
        self,
        session_id: str,
        force: bool = False,
    ) -> CloseResultData:
        if self._close_should_fail:
            return CloseResultData(
                session_id=session_id,
                success=False,
                error=self._fail_message,
            )

        mock_session = self._spawner.get_mock_session(session_id)
        if not mock_session:
            return CloseResultData(
                session_id=session_id,
                success=True,
                error="Session not found (already closed)",
            )

        force_required = self._require_force and not force
        if force_required:
            # Simulate needing force but not having it - still close but note it
            pass

        mock_session.is_closed = True
        return CloseResultData(
            session_id=session_id,
            success=True,
            force_required=self._require_force,
        )

    async def close_tab(self, tab_id: str, force: bool = False) -> bool:
        if self._close_should_fail:
            return False

        # Close all sessions in this tab
        for session in self._spawner.get_all_sessions():
            if session.tab_id == tab_id:
                session.is_closed = True

        return True

    async def close_all_managed(
        self,
        sessions: list[ManagedSession],
        spawner: SessionSpawnerProtocol,
        force: bool = False,
    ) -> tuple[int, list[CloseResultData]]:
        results = []
        closed = 0

        for session in sessions:
            result = await self.close_session(session.id, force)
            results.append(result)
            if result.success:
                closed += 1
                spawner.untrack_session(session.id)

        return (closed, results)

    # Test helpers
    def set_close_failure(
        self, should_fail: bool, message: str = "Mock close failure"
    ) -> None:
        """Configure close operations to fail for testing error handling."""
        self._close_should_fail = should_fail
        self._fail_message = message

    def set_require_force(self, require: bool) -> None:
        """Configure whether sessions require force-close."""
        self._require_force = require


class MockOutputReader:
    """Mock implementation of OutputReaderProtocol for testing."""

    def __init__(self) -> None:
        self._outputs: dict[str, str] = {}
        self._read_should_fail = False
        self._fail_message = "Mock read failure"

    async def read_output(self, session_id: str, lines: int = 50) -> str:
        if self._read_should_fail:
            raise RuntimeError(self._fail_message)

        output = self._outputs.get(session_id, "")
        # Simulate reading last N lines
        output_lines = output.split("\n")
        return "\n".join(output_lines[-lines:])

    async def read_batch(self, session_ids: list[str]) -> dict[str, str]:
        result = {}
        for session_id in session_ids:
            if self._read_should_fail:
                continue
            if session_id in self._outputs:
                result[session_id] = self._outputs[session_id]
        return result

    # Test helpers
    def set_output(self, session_id: str, output: str) -> None:
        """Set the output for a session."""
        self._outputs[session_id] = output

    def append_output(self, session_id: str, output: str) -> None:
        """Append output to a session."""
        current = self._outputs.get(session_id, "")
        self._outputs[session_id] = current + output

    def clear_output(self, session_id: str | None = None) -> None:
        """Clear output for a session or all sessions."""
        if session_id:
            self._outputs.pop(session_id, None)
        else:
            self._outputs.clear()

    def set_read_failure(
        self, should_fail: bool, message: str = "Mock read failure"
    ) -> None:
        """Configure read operations to fail for testing error handling."""
        self._read_should_fail = should_fail
        self._fail_message = message


@dataclass
class MockWindowState:
    """Mock window state for testing."""

    window_id: str
    tabs: list[TerminalTab] = field(default_factory=list)
    managed_tab_ids: set[str] = field(default_factory=set)


class MockWindowTracker:
    """Mock implementation of WindowTrackerProtocol for testing."""

    def __init__(self) -> None:
        self._windows: dict[str, MockWindowState] = {}
        self._window_counter = 0

    async def refresh(self) -> None:
        # In mock, this is a no-op - state is managed directly
        pass

    def get_windows(self) -> list[TerminalWindow]:
        return [
            TerminalWindow(id=w.window_id, tabs=list(w.tabs))
            for w in self._windows.values()
        ]

    def get_window(self, window_id: str) -> TerminalWindow | None:
        state = self._windows.get(window_id)
        if state:
            return TerminalWindow(id=state.window_id, tabs=list(state.tabs))
        return None

    def mark_managed(self, tab_id: str, window_id: str) -> None:
        if window_id in self._windows:
            self._windows[window_id].managed_tab_ids.add(tab_id)

    def get_managed_tab_ids(self, window_id: str | None = None) -> set[str]:
        if window_id:
            state = self._windows.get(window_id)
            return set(state.managed_tab_ids) if state else set()

        all_managed: set[str] = set()
        for state in self._windows.values():
            all_managed.update(state.managed_tab_ids)
        return all_managed

    # Test helpers
    def add_window(self, window_id: str | None = None) -> str:
        """Add a mock window and return its ID."""
        if window_id is None:
            self._window_counter += 1
            window_id = f"mock-window-{self._window_counter}"
        self._windows[window_id] = MockWindowState(window_id=window_id)
        return window_id

    def add_tab(
        self, window_id: str, tab_id: str | None = None, title: str = ""
    ) -> str:
        """Add a mock tab to a window and return its ID."""
        if window_id not in self._windows:
            self.add_window(window_id)

        if tab_id is None:
            tab_id = f"mock-tab-{uuid.uuid4().hex[:8]}"

        tab = TerminalTab(id=tab_id, title=title, session_ids=[])
        self._windows[window_id].tabs.append(tab)
        return tab_id

    def add_session_to_tab(
        self, window_id: str, tab_id: str, session_id: str
    ) -> None:
        """Add a session ID to a tab."""
        if window_id in self._windows:
            for tab in self._windows[window_id].tabs:
                if tab.id == tab_id:
                    tab.session_ids.append(session_id)
                    break

    def clear(self) -> None:
        """Clear all mock window state."""
        self._windows.clear()
        self._window_counter = 0


class MockTerminalProvider:
    """Complete mock implementation of TerminalProvider for testing.

    Example:
        def test_workflow():
            provider = MockTerminalProvider()
            provider.connection.set_connected(True)

            # Spawn sessions
            result = await provider.spawner.spawn_session(template, project)
            assert result.success

            # Set up output for attention detection
            provider.output_reader.set_output(
                result.session_id,
                "Should I proceed? [y/N]"
            )

            # Read and check
            output = await provider.output_reader.read_output(result.session_id)
            assert "Should I proceed" in output
    """

    def __init__(self) -> None:
        self._connection = MockConnection()
        self._spawner = MockSessionSpawner()
        self._terminator = MockSessionTerminator(self._spawner)
        self._output_reader = MockOutputReader()
        self._tracker = MockWindowTracker()

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

    # Direct access to mock implementations for test setup
    @property
    def mock_connection(self) -> MockConnection:
        return self._connection

    @property
    def mock_spawner(self) -> MockSessionSpawner:
        return self._spawner

    @property
    def mock_terminator(self) -> MockSessionTerminator:
        return self._terminator

    @property
    def mock_output_reader(self) -> MockOutputReader:
        return self._output_reader

    @property
    def mock_tracker(self) -> MockWindowTracker:
        return self._tracker
