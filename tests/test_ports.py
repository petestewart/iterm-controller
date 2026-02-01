"""Tests for terminal abstraction layer (ports.py) and mock implementation."""

import pytest

from iterm_controller.models import ManagedSession, Project, SessionTemplate
from iterm_controller.ports import (
    CloseResultData,
    OutputReaderProtocol,
    SessionSpawnerProtocol,
    SessionTerminatorProtocol,
    SpawnResultData,
    TerminalConnection,
    TerminalProvider,
    TerminalSession,
    TerminalTab,
    TerminalWindow,
    WindowTrackerProtocol,
)
from iterm_controller.testing import (
    MockConnection,
    MockOutputReader,
    MockSessionSpawner,
    MockSessionTerminator,
    MockTerminalProvider,
    MockWindowTracker,
)


# =============================================================================
# Test Data Types
# =============================================================================


class TestTerminalSession:
    """Test TerminalSession data class."""

    def test_create_with_defaults(self):
        """TerminalSession creates with correct defaults."""
        session = TerminalSession(id="session-1", tab_id="tab-1")
        assert session.id == "session-1"
        assert session.tab_id == "tab-1"
        assert session.is_active is True

    def test_create_inactive(self):
        """TerminalSession can be created as inactive."""
        session = TerminalSession(id="s", tab_id="t", is_active=False)
        assert session.is_active is False


class TestTerminalTab:
    """Test TerminalTab data class."""

    def test_create_with_defaults(self):
        """TerminalTab creates with correct defaults."""
        tab = TerminalTab(id="tab-1")
        assert tab.id == "tab-1"
        assert tab.title == ""
        assert tab.session_ids == []

    def test_create_with_sessions(self):
        """TerminalTab can have session IDs."""
        tab = TerminalTab(id="tab-1", title="Dev", session_ids=["s1", "s2"])
        assert tab.title == "Dev"
        assert tab.session_ids == ["s1", "s2"]


class TestTerminalWindow:
    """Test TerminalWindow data class."""

    def test_create_with_defaults(self):
        """TerminalWindow creates with correct defaults."""
        window = TerminalWindow(id="window-1")
        assert window.id == "window-1"
        assert window.tabs == []

    def test_create_with_tabs(self):
        """TerminalWindow can have tabs."""
        tab1 = TerminalTab(id="t1")
        tab2 = TerminalTab(id="t2")
        window = TerminalWindow(id="w1", tabs=[tab1, tab2])
        assert len(window.tabs) == 2


class TestSpawnResultData:
    """Test SpawnResultData data class."""

    def test_create_success(self):
        """SpawnResultData can indicate success."""
        result = SpawnResultData(
            session_id="s1",
            tab_id="t1",
            success=True,
        )
        assert result.success is True
        assert result.error is None

    def test_create_failure(self):
        """SpawnResultData can indicate failure with error."""
        result = SpawnResultData(
            session_id="",
            tab_id="",
            success=False,
            error="Connection refused",
        )
        assert result.success is False
        assert result.error == "Connection refused"


class TestCloseResultData:
    """Test CloseResultData data class."""

    def test_create_success(self):
        """CloseResultData can indicate success."""
        result = CloseResultData(
            session_id="s1",
            success=True,
        )
        assert result.success is True
        assert result.force_required is False
        assert result.error is None

    def test_create_forced(self):
        """CloseResultData can indicate force was required."""
        result = CloseResultData(
            session_id="s1",
            success=True,
            force_required=True,
        )
        assert result.force_required is True


# =============================================================================
# Test Mock Connection
# =============================================================================


class TestMockConnection:
    """Test MockConnection implementation."""

    def test_starts_disconnected(self):
        """MockConnection starts disconnected."""
        conn = MockConnection()
        assert conn.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_succeeds(self):
        """MockConnection connect succeeds by default."""
        conn = MockConnection()
        result = await conn.connect()
        assert result is True
        assert conn.is_connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """MockConnection disconnect works."""
        conn = MockConnection()
        await conn.connect()
        await conn.disconnect()
        assert conn.is_connected is False

    @pytest.mark.asyncio
    async def test_reconnect(self):
        """MockConnection reconnect works."""
        conn = MockConnection()
        await conn.connect()
        result = await conn.reconnect()
        assert result is True
        assert conn.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_failure_configured(self):
        """MockConnection can be configured to fail."""
        conn = MockConnection()
        conn.set_connect_failure(True, "Test failure")

        with pytest.raises(RuntimeError) as exc_info:
            await conn.connect()
        assert "Test failure" in str(exc_info.value)

    def test_set_connected_directly(self):
        """MockConnection can set state directly for testing."""
        conn = MockConnection()
        conn.set_connected(True)
        assert conn.is_connected is True


# =============================================================================
# Test Mock Spawner
# =============================================================================


class TestMockSessionSpawner:
    """Test MockSessionSpawner implementation."""

    def _make_template(self, template_id: str = "t1") -> SessionTemplate:
        """Create a test template."""
        return SessionTemplate(id=template_id, name="Test", command="echo test")

    def _make_project(self, project_id: str = "p1") -> Project:
        """Create a test project."""
        return Project(id=project_id, name="Test Project", path="/tmp/test")

    @pytest.mark.asyncio
    async def test_spawn_session_success(self):
        """MockSessionSpawner spawns session successfully."""
        spawner = MockSessionSpawner()
        template = self._make_template()
        project = self._make_project()

        result = await spawner.spawn_session(template, project)

        assert result.success is True
        assert result.session_id != ""
        assert result.tab_id != ""

    @pytest.mark.asyncio
    async def test_spawn_creates_managed_session(self):
        """Spawned session is tracked as ManagedSession."""
        spawner = MockSessionSpawner()
        template = self._make_template()
        project = self._make_project()

        result = await spawner.spawn_session(template, project)
        managed = spawner.get_session(result.session_id)

        assert managed is not None
        assert managed.template_id == template.id
        assert managed.project_id == project.id

    @pytest.mark.asyncio
    async def test_spawn_failure_configured(self):
        """MockSessionSpawner can be configured to fail."""
        spawner = MockSessionSpawner()
        spawner.set_spawn_failure(True, "Out of memory")

        result = await spawner.spawn_session(
            self._make_template(),
            self._make_project(),
        )

        assert result.success is False
        assert result.error == "Out of memory"

    @pytest.mark.asyncio
    async def test_spawn_split_success(self):
        """MockSessionSpawner can spawn split panes."""
        spawner = MockSessionSpawner()
        template = self._make_template()
        project = self._make_project()

        # First spawn a parent session
        parent = await spawner.spawn_session(template, project)
        assert parent.success

        # Then split it
        split = await spawner.spawn_split(
            template, project, parent.session_id, vertical=True
        )

        assert split.success
        assert split.tab_id == parent.tab_id  # Same tab

    @pytest.mark.asyncio
    async def test_spawn_split_parent_not_found(self):
        """Splitting non-existent parent fails."""
        spawner = MockSessionSpawner()

        result = await spawner.spawn_split(
            self._make_template(),
            self._make_project(),
            "nonexistent",
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_get_sessions_for_project(self):
        """Can get all sessions for a project."""
        spawner = MockSessionSpawner()
        template = self._make_template()
        project1 = self._make_project("p1")
        project2 = self._make_project("p2")

        # Spawn sessions for both projects
        import asyncio

        asyncio.get_event_loop().run_until_complete(
            spawner.spawn_session(template, project1)
        )
        asyncio.get_event_loop().run_until_complete(
            spawner.spawn_session(template, project1)
        )
        asyncio.get_event_loop().run_until_complete(
            spawner.spawn_session(template, project2)
        )

        sessions = spawner.get_sessions_for_project("p1")
        assert len(sessions) == 2

    def test_untrack_session(self):
        """Can untrack a session."""
        spawner = MockSessionSpawner()
        template = self._make_template()
        project = self._make_project()

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(
            spawner.spawn_session(template, project)
        )

        spawner.untrack_session(result.session_id)

        assert spawner.get_session(result.session_id) is None


# =============================================================================
# Test Mock Terminator
# =============================================================================


class TestMockSessionTerminator:
    """Test MockSessionTerminator implementation."""

    @pytest.mark.asyncio
    async def test_close_session_success(self):
        """MockSessionTerminator closes session successfully."""
        spawner = MockSessionSpawner()
        terminator = MockSessionTerminator(spawner)

        # Create a session first
        template = SessionTemplate(id="t", name="Test", command="test")
        project = Project(id="p", name="P", path="/tmp")
        spawn_result = await spawner.spawn_session(template, project)

        result = await terminator.close_session(spawn_result.session_id)

        assert result.success is True
        mock_session = spawner.get_mock_session(spawn_result.session_id)
        assert mock_session.is_closed is True

    @pytest.mark.asyncio
    async def test_close_nonexistent_session(self):
        """Closing nonexistent session succeeds (already closed)."""
        spawner = MockSessionSpawner()
        terminator = MockSessionTerminator(spawner)

        result = await terminator.close_session("nonexistent")

        assert result.success is True
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_close_failure_configured(self):
        """MockSessionTerminator can be configured to fail."""
        spawner = MockSessionSpawner()
        terminator = MockSessionTerminator(spawner)
        terminator.set_close_failure(True, "Permission denied")

        result = await terminator.close_session("any-session")

        assert result.success is False
        assert result.error == "Permission denied"

    @pytest.mark.asyncio
    async def test_close_all_managed(self):
        """Can close all managed sessions."""
        spawner = MockSessionSpawner()
        terminator = MockSessionTerminator(spawner)

        template = SessionTemplate(id="t", name="Test", command="test")
        project = Project(id="p", name="P", path="/tmp")

        # Spawn multiple sessions
        r1 = await spawner.spawn_session(template, project)
        r2 = await spawner.spawn_session(template, project)

        sessions = [
            ManagedSession(id=r1.session_id, template_id="t", project_id="p", tab_id=r1.tab_id),
            ManagedSession(id=r2.session_id, template_id="t", project_id="p", tab_id=r2.tab_id),
        ]

        count, results = await terminator.close_all_managed(sessions, spawner)

        assert count == 2
        assert len(results) == 2
        assert all(r.success for r in results)


# =============================================================================
# Test Mock Output Reader
# =============================================================================


class TestMockOutputReader:
    """Test MockOutputReader implementation."""

    @pytest.mark.asyncio
    async def test_read_empty_output(self):
        """Reading from session with no output returns empty string."""
        reader = MockOutputReader()
        output = await reader.read_output("session-1")
        assert output == ""

    @pytest.mark.asyncio
    async def test_read_set_output(self):
        """Can set and read output."""
        reader = MockOutputReader()
        reader.set_output("session-1", "Hello World")

        output = await reader.read_output("session-1")

        assert output == "Hello World"

    @pytest.mark.asyncio
    async def test_append_output(self):
        """Can append to session output."""
        reader = MockOutputReader()
        reader.set_output("session-1", "Line 1\n")
        reader.append_output("session-1", "Line 2\n")

        output = await reader.read_output("session-1")

        assert "Line 1" in output
        assert "Line 2" in output

    @pytest.mark.asyncio
    async def test_read_batch(self):
        """Can read multiple sessions at once."""
        reader = MockOutputReader()
        reader.set_output("s1", "Output 1")
        reader.set_output("s2", "Output 2")

        result = await reader.read_batch(["s1", "s2", "s3"])

        assert result["s1"] == "Output 1"
        assert result["s2"] == "Output 2"
        assert "s3" not in result  # Not set

    def test_clear_output(self):
        """Can clear session output."""
        reader = MockOutputReader()
        reader.set_output("s1", "data")
        reader.clear_output("s1")

        import asyncio

        output = asyncio.get_event_loop().run_until_complete(
            reader.read_output("s1")
        )
        assert output == ""


# =============================================================================
# Test Mock Window Tracker
# =============================================================================


class TestMockWindowTracker:
    """Test MockWindowTracker implementation."""

    @pytest.mark.asyncio
    async def test_get_windows_empty(self):
        """Returns empty list when no windows."""
        tracker = MockWindowTracker()
        windows = tracker.get_windows()
        assert windows == []

    def test_add_window(self):
        """Can add mock windows."""
        tracker = MockWindowTracker()
        window_id = tracker.add_window()

        windows = tracker.get_windows()
        assert len(windows) == 1
        assert windows[0].id == window_id

    def test_add_tab(self):
        """Can add tabs to windows."""
        tracker = MockWindowTracker()
        window_id = tracker.add_window()
        tab_id = tracker.add_tab(window_id, title="Dev Tab")

        window = tracker.get_window(window_id)
        assert len(window.tabs) == 1
        assert window.tabs[0].id == tab_id
        assert window.tabs[0].title == "Dev Tab"

    def test_mark_managed(self):
        """Can mark tabs as managed."""
        tracker = MockWindowTracker()
        window_id = tracker.add_window()
        tab_id = tracker.add_tab(window_id)

        tracker.mark_managed(tab_id, window_id)

        managed = tracker.get_managed_tab_ids()
        assert tab_id in managed

    def test_get_managed_for_window(self):
        """Can filter managed tabs by window."""
        tracker = MockWindowTracker()
        w1 = tracker.add_window()
        w2 = tracker.add_window()
        t1 = tracker.add_tab(w1)
        t2 = tracker.add_tab(w2)

        tracker.mark_managed(t1, w1)
        tracker.mark_managed(t2, w2)

        managed_w1 = tracker.get_managed_tab_ids(w1)
        assert t1 in managed_w1
        assert t2 not in managed_w1


# =============================================================================
# Test Mock Terminal Provider
# =============================================================================


class TestMockTerminalProvider:
    """Test MockTerminalProvider composite implementation."""

    def test_has_all_components(self):
        """Provider has all protocol components."""
        provider = MockTerminalProvider()

        assert isinstance(provider.connection, TerminalConnection)
        assert isinstance(provider.spawner, SessionSpawnerProtocol)
        assert isinstance(provider.terminator, SessionTerminatorProtocol)
        assert isinstance(provider.output_reader, OutputReaderProtocol)
        assert isinstance(provider.tracker, WindowTrackerProtocol)

    def test_mock_accessors(self):
        """Can access mock implementations for test setup."""
        provider = MockTerminalProvider()

        assert isinstance(provider.mock_connection, MockConnection)
        assert isinstance(provider.mock_spawner, MockSessionSpawner)
        assert isinstance(provider.mock_terminator, MockSessionTerminator)
        assert isinstance(provider.mock_output_reader, MockOutputReader)
        assert isinstance(provider.mock_tracker, MockWindowTracker)

    @pytest.mark.asyncio
    async def test_integration_workflow(self):
        """Test a complete workflow using the mock provider."""
        provider = MockTerminalProvider()
        provider.mock_connection.set_connected(True)

        # Create template and project
        template = SessionTemplate(id="dev", name="Dev Server", command="npm run dev")
        project = Project(id="myapp", name="My App", path="/tmp/myapp")

        # Spawn a session
        spawn_result = await provider.spawner.spawn_session(template, project)
        assert spawn_result.success

        # Set up some output
        provider.mock_output_reader.set_output(
            spawn_result.session_id,
            "Server running on port 3000\nShould I proceed? [y/N]",
        )

        # Read the output
        output = await provider.output_reader.read_output(spawn_result.session_id)
        assert "Should I proceed" in output

        # Close the session
        close_result = await provider.terminator.close_session(spawn_result.session_id)
        assert close_result.success


# =============================================================================
# Protocol Compliance Tests
# =============================================================================


class TestProtocolCompliance:
    """Test that mock implementations satisfy protocol contracts."""

    def test_mock_connection_satisfies_protocol(self):
        """MockConnection satisfies TerminalConnection protocol."""
        conn = MockConnection()
        # runtime_checkable allows isinstance checks
        assert isinstance(conn, TerminalConnection)

    def test_mock_spawner_satisfies_protocol(self):
        """MockSessionSpawner satisfies SessionSpawnerProtocol."""
        spawner = MockSessionSpawner()
        assert isinstance(spawner, SessionSpawnerProtocol)

    def test_mock_terminator_satisfies_protocol(self):
        """MockSessionTerminator satisfies SessionTerminatorProtocol."""
        spawner = MockSessionSpawner()
        terminator = MockSessionTerminator(spawner)
        assert isinstance(terminator, SessionTerminatorProtocol)

    def test_mock_output_reader_satisfies_protocol(self):
        """MockOutputReader satisfies OutputReaderProtocol."""
        reader = MockOutputReader()
        assert isinstance(reader, OutputReaderProtocol)

    def test_mock_tracker_satisfies_protocol(self):
        """MockWindowTracker satisfies WindowTrackerProtocol."""
        tracker = MockWindowTracker()
        assert isinstance(tracker, WindowTrackerProtocol)

    def test_mock_provider_satisfies_protocol(self):
        """MockTerminalProvider satisfies TerminalProvider protocol."""
        provider = MockTerminalProvider()
        assert isinstance(provider, TerminalProvider)
