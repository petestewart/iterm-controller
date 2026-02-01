"""Tests for iTerm2 connection and session management."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iterm_controller.iterm_api import (
    ItermConnectionError,
    ItermController,
    ItermNotConnectedError,
    SpawnResult,
    TabState,
    WindowState,
    WindowTracker,
    with_reconnect,
)


class TestItermController:
    """Test ItermController connection management."""

    def test_init_not_connected(self):
        """Controller starts in disconnected state."""
        controller = ItermController()
        assert controller.connection is None
        assert controller.app is None
        assert controller.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Successful connection sets state correctly."""
        controller = ItermController()

        mock_connection = MagicMock()
        mock_app = MagicMock()

        with patch("iterm2.Connection.async_create", new_callable=AsyncMock) as mock_create:
            with patch("iterm2.async_get_app", new_callable=AsyncMock) as mock_get_app:
                mock_create.return_value = mock_connection
                mock_get_app.return_value = mock_app

                result = await controller.connect()

        assert result is True
        assert controller.connection is mock_connection
        assert controller.app is mock_app
        assert controller.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_connection_refused(self):
        """Connection refused raises ItermConnectionError."""
        controller = ItermController()

        with patch("iterm2.Connection.async_create", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = ConnectionRefusedError("Connection refused")

            with pytest.raises(ItermConnectionError) as exc_info:
                await controller.connect()

            assert "Connection refused" in str(exc_info.value)
            assert "Python API enabled" in str(exc_info.value)
            assert controller.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_generic_error(self):
        """Generic connection error raises ItermConnectionError."""
        controller = ItermController()

        with patch("iterm2.Connection.async_create", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = Exception("Unknown error")

            with pytest.raises(ItermConnectionError) as exc_info:
                await controller.connect()

            assert "Failed to connect" in str(exc_info.value)
            assert controller.is_connected is False

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Disconnect clears connection state."""
        controller = ItermController()
        controller.connection = MagicMock()
        controller.app = MagicMock()
        controller._connected = True

        await controller.disconnect()

        assert controller.connection is None
        assert controller.app is None
        assert controller.is_connected is False

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        """Disconnect is safe when not connected."""
        controller = ItermController()
        assert controller.is_connected is False

        # Should not raise
        await controller.disconnect()

        assert controller.is_connected is False

    @pytest.mark.asyncio
    async def test_reconnect(self):
        """Reconnect disconnects then connects."""
        controller = ItermController()
        controller.connection = MagicMock()
        controller._connected = True

        mock_new_connection = MagicMock()
        mock_new_app = MagicMock()

        with patch("iterm2.Connection.async_create", new_callable=AsyncMock) as mock_create:
            with patch("iterm2.async_get_app", new_callable=AsyncMock) as mock_get_app:
                mock_create.return_value = mock_new_connection
                mock_get_app.return_value = mock_new_app

                result = await controller.reconnect()

        assert result is True
        assert controller.connection is mock_new_connection
        assert controller.app is mock_new_app

    @pytest.mark.asyncio
    async def test_verify_version_not_connected(self):
        """Verify version fails when not connected."""
        controller = ItermController()

        success, message = await controller.verify_version()

        assert success is False
        assert "Not connected" in message

    @pytest.mark.asyncio
    async def test_verify_version_connected(self):
        """Verify version succeeds when connected."""
        controller = ItermController()
        controller.app = MagicMock()

        success, message = await controller.verify_version()

        assert success is True
        assert "3.5+" in message

    def test_require_connection_when_connected(self):
        """require_connection does nothing when connected."""
        controller = ItermController()
        controller.connection = MagicMock()
        controller._connected = True

        # Should not raise
        controller.require_connection()

    def test_require_connection_when_not_connected(self):
        """require_connection raises when not connected."""
        controller = ItermController()

        with pytest.raises(ItermNotConnectedError) as exc_info:
            controller.require_connection()

        assert "Not connected" in str(exc_info.value)

    def test_is_connected_property(self):
        """is_connected property reflects actual state."""
        controller = ItermController()

        # Not connected
        assert controller.is_connected is False

        # Set _connected but no connection object
        controller._connected = True
        assert controller.is_connected is False

        # Set connection but not _connected flag
        controller._connected = False
        controller.connection = MagicMock()
        assert controller.is_connected is False

        # Both set
        controller._connected = True
        assert controller.is_connected is True


class TestWithReconnect:
    """Test the with_reconnect retry helper."""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        """Operation succeeding on first try returns result."""
        controller = ItermController()
        controller._connected = True
        controller.connection = MagicMock()

        async def operation():
            return "success"

        result = await with_reconnect(controller, operation)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        """Connection error triggers reconnect and retry."""
        controller = ItermController()

        attempt = {"count": 0}

        async def operation():
            attempt["count"] += 1
            if attempt["count"] == 1:
                raise Exception("Connection closed")
            return "success"

        mock_connection = MagicMock()
        mock_app = MagicMock()

        with patch("iterm2.Connection.async_create", new_callable=AsyncMock) as mock_create:
            with patch("iterm2.async_get_app", new_callable=AsyncMock) as mock_get_app:
                mock_create.return_value = mock_connection
                mock_get_app.return_value = mock_app

                result = await with_reconnect(controller, operation)

        assert result == "success"
        assert attempt["count"] == 2

    @pytest.mark.asyncio
    async def test_non_connection_error_not_retried(self):
        """Non-connection errors are not retried."""
        controller = ItermController()

        async def operation():
            raise ValueError("Not a connection error")

        with pytest.raises(ValueError):
            await with_reconnect(controller, operation)

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Error raised after max retries exhausted."""
        controller = ItermController()

        async def operation():
            raise Exception("Connection failed")

        with patch("iterm2.Connection.async_create", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = Exception("Reconnect failed")

            with pytest.raises(Exception) as exc_info:
                await with_reconnect(controller, operation, max_retries=2)

            assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_reconnect_failure_continues_to_next_attempt(self):
        """Failed reconnect attempts continue to next retry."""
        controller = ItermController()

        attempt = {"count": 0}

        async def operation():
            attempt["count"] += 1
            if attempt["count"] < 3:
                raise Exception("Connection closed")
            return "success"

        # First reconnect fails, second succeeds
        with patch("iterm2.Connection.async_create", new_callable=AsyncMock) as mock_create:
            with patch("iterm2.async_get_app", new_callable=AsyncMock) as mock_get_app:
                mock_create.side_effect = [
                    ItermConnectionError("First reconnect failed"),
                    MagicMock(),  # Second reconnect succeeds
                ]
                mock_get_app.return_value = MagicMock()

                result = await with_reconnect(controller, operation, max_retries=3)

        assert result == "success"
        assert attempt["count"] == 3


class TestSpawnResult:
    """Test SpawnResult dataclass."""

    def test_spawn_result_success(self):
        """SpawnResult with success state."""
        result = SpawnResult(
            session_id="session-1",
            tab_id="tab-1",
            success=True,
        )
        assert result.session_id == "session-1"
        assert result.tab_id == "tab-1"
        assert result.success is True
        assert result.error is None

    def test_spawn_result_failure(self):
        """SpawnResult with failure state."""
        result = SpawnResult(
            session_id="",
            tab_id="",
            success=False,
            error="Failed to spawn session",
        )
        assert result.success is False
        assert result.error == "Failed to spawn session"


class TestWindowState:
    """Test WindowState and TabState dataclasses."""

    def test_tab_state_defaults(self):
        """TabState has correct defaults."""
        tab = TabState(tab_id="tab-1", title="Test Tab")
        assert tab.tab_id == "tab-1"
        assert tab.title == "Test Tab"
        assert tab.session_ids == []
        assert tab.is_managed is False

    def test_window_state_defaults(self):
        """WindowState has correct defaults."""
        window = WindowState(window_id="window-1")
        assert window.window_id == "window-1"
        assert window.tabs == []
        assert window.managed_tab_ids == set()

    def test_window_state_with_tabs(self):
        """WindowState can contain tabs."""
        tabs = [
            TabState(tab_id="tab-1", title="Tab 1", session_ids=["s1", "s2"]),
            TabState(tab_id="tab-2", title="Tab 2", session_ids=["s3"]),
        ]
        window = WindowState(
            window_id="window-1",
            tabs=tabs,
            managed_tab_ids={"tab-1"},
        )
        assert len(window.tabs) == 2
        assert "tab-1" in window.managed_tab_ids
        assert "tab-2" not in window.managed_tab_ids


class TestWindowTracker:
    """Test WindowTracker class."""

    def test_init(self):
        """WindowTracker initializes with empty state."""
        controller = ItermController()
        tracker = WindowTracker(controller)
        assert tracker.controller is controller
        assert tracker.windows == {}

    def test_mark_managed(self):
        """mark_managed adds tab to managed set."""
        controller = ItermController()
        tracker = WindowTracker(controller)

        # Create a window state
        tracker.windows["window-1"] = WindowState(window_id="window-1")

        # Mark tab as managed
        tracker.mark_managed("tab-1", "window-1")

        assert "tab-1" in tracker.windows["window-1"].managed_tab_ids

    def test_mark_managed_nonexistent_window(self):
        """mark_managed is safe for nonexistent window."""
        controller = ItermController()
        tracker = WindowTracker(controller)

        # Should not raise
        tracker.mark_managed("tab-1", "nonexistent")

    def test_get_managed_tab_ids_all(self):
        """get_managed_tab_ids returns all managed tabs."""
        controller = ItermController()
        tracker = WindowTracker(controller)

        tracker.windows["window-1"] = WindowState(
            window_id="window-1",
            managed_tab_ids={"tab-1", "tab-2"},
        )
        tracker.windows["window-2"] = WindowState(
            window_id="window-2",
            managed_tab_ids={"tab-3"},
        )

        all_managed = tracker.get_managed_tab_ids()

        assert all_managed == {"tab-1", "tab-2", "tab-3"}

    def test_get_managed_tab_ids_by_window(self):
        """get_managed_tab_ids filters by window."""
        controller = ItermController()
        tracker = WindowTracker(controller)

        tracker.windows["window-1"] = WindowState(
            window_id="window-1",
            managed_tab_ids={"tab-1", "tab-2"},
        )
        tracker.windows["window-2"] = WindowState(
            window_id="window-2",
            managed_tab_ids={"tab-3"},
        )

        window1_managed = tracker.get_managed_tab_ids("window-1")
        window2_managed = tracker.get_managed_tab_ids("window-2")
        nonexistent_managed = tracker.get_managed_tab_ids("nonexistent")

        assert window1_managed == {"tab-1", "tab-2"}
        assert window2_managed == {"tab-3"}
        assert nonexistent_managed == set()

    @pytest.mark.asyncio
    async def test_refresh_requires_connection(self):
        """refresh raises when not connected."""
        controller = ItermController()
        tracker = WindowTracker(controller)

        with pytest.raises(ItermNotConnectedError):
            await tracker.refresh()

    @pytest.mark.asyncio
    async def test_refresh_clears_existing_state(self):
        """refresh clears existing window state."""
        controller = ItermController()
        controller._connected = True
        controller.connection = MagicMock()
        controller.app = MagicMock()
        controller.app.terminal_windows = []

        tracker = WindowTracker(controller)
        tracker.windows["old-window"] = WindowState(window_id="old-window")

        await tracker.refresh()

        assert "old-window" not in tracker.windows
        assert tracker.windows == {}

    @pytest.mark.asyncio
    async def test_refresh_populates_window_state(self):
        """refresh populates window state from iTerm2."""
        controller = ItermController()
        controller._connected = True
        controller.connection = MagicMock()

        # Mock iTerm2 app structure
        mock_session = MagicMock()
        mock_session.session_id = "session-1"

        mock_tab = MagicMock()
        mock_tab.tab_id = "tab-1"
        mock_tab.sessions = [mock_session]
        mock_tab.async_get_variable = AsyncMock(return_value="Test Tab")

        mock_window = MagicMock()
        mock_window.window_id = "window-1"
        mock_window.tabs = [mock_tab]

        mock_app = MagicMock()
        mock_app.terminal_windows = [mock_window]
        controller.app = mock_app

        tracker = WindowTracker(controller)
        await tracker.refresh()

        assert "window-1" in tracker.windows
        window_state = tracker.windows["window-1"]
        assert len(window_state.tabs) == 1
        assert window_state.tabs[0].tab_id == "tab-1"
        assert window_state.tabs[0].title == "Test Tab"
        assert window_state.tabs[0].session_ids == ["session-1"]
