"""Tests for the FocusWatcher module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iterm_controller.iterm import FocusWatcher, ItermController


class TestFocusWatcher:
    """Tests for FocusWatcher class."""

    def test_init(self):
        """FocusWatcher initializes with correct defaults."""
        controller = ItermController()
        watcher = FocusWatcher(controller)

        assert watcher.controller is controller
        assert watcher.on_tab_focused is None
        assert watcher._our_tab_id is None
        assert watcher._our_session_id is None
        assert watcher._task is None
        assert not watcher._running
        assert not watcher.is_running

    def test_init_with_callback(self):
        """FocusWatcher can be initialized with a callback."""
        controller = ItermController()
        callback = MagicMock()
        watcher = FocusWatcher(controller, on_tab_focused=callback)

        assert watcher.on_tab_focused is callback

    @pytest.mark.asyncio
    async def test_find_our_tab_not_connected(self):
        """find_our_tab returns None when not connected."""
        controller = ItermController()
        watcher = FocusWatcher(controller)

        result = await watcher.find_our_tab()
        assert result is None

    @pytest.mark.asyncio
    async def test_find_our_tab_success(self):
        """find_our_tab finds the tab containing the TUI."""
        controller = ItermController()
        controller._connected = True

        # Mock the app structure
        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.async_get_variable = AsyncMock(return_value=12345)  # Some parent PID

        mock_tab = MagicMock()
        mock_tab.tab_id = "tab-456"
        mock_tab.sessions = [mock_session]

        mock_window = MagicMock()
        mock_window.tabs = [mock_tab]

        mock_app = MagicMock()
        mock_app.terminal_windows = [mock_window]
        controller.app = mock_app

        watcher = FocusWatcher(controller)

        # Mock _get_parent_pids to include the session's PID
        with patch.object(watcher, "_get_parent_pids", return_value=[12345, 1]):
            result = await watcher.find_our_tab()

        assert result == "tab-456"
        assert watcher._our_tab_id == "tab-456"
        assert watcher._our_session_id == "session-123"

    @pytest.mark.asyncio
    async def test_find_our_tab_not_found(self):
        """find_our_tab returns None when tab not found."""
        controller = ItermController()
        controller._connected = True

        # Mock the app with a session that doesn't match
        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.async_get_variable = AsyncMock(return_value=99999)

        mock_tab = MagicMock()
        mock_tab.tab_id = "tab-456"
        mock_tab.sessions = [mock_session]

        mock_window = MagicMock()
        mock_window.tabs = [mock_tab]

        mock_app = MagicMock()
        mock_app.terminal_windows = [mock_window]
        controller.app = mock_app

        watcher = FocusWatcher(controller)

        # PIDs don't match
        with patch.object(watcher, "_get_parent_pids", return_value=[1, 2, 3]):
            result = await watcher.find_our_tab()

        assert result is None

    def test_get_parent_pids_includes_self(self):
        """_get_parent_pids includes the starting PID."""
        controller = ItermController()
        watcher = FocusWatcher(controller)

        pids = watcher._get_parent_pids(12345)
        assert 12345 in pids

    @pytest.mark.asyncio
    async def test_start_not_connected(self):
        """start does nothing when not connected."""
        controller = ItermController()
        watcher = FocusWatcher(controller)

        await watcher.start()

        assert not watcher.is_running
        assert watcher._task is None

    @pytest.mark.asyncio
    async def test_start_tab_not_found(self):
        """start does nothing when tab not found."""
        controller = ItermController()
        controller._connected = True
        controller.connection = MagicMock()
        controller.app = MagicMock()
        controller.app.terminal_windows = []

        watcher = FocusWatcher(controller)

        await watcher.start()

        assert not watcher.is_running

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """start does nothing when already running."""
        controller = ItermController()
        watcher = FocusWatcher(controller)
        watcher._running = True

        await watcher.start()

        # Should still be running but no new task created
        assert watcher._running
        assert watcher._task is None

    @pytest.mark.asyncio
    async def test_stop(self):
        """stop cancels the watcher task."""
        controller = ItermController()
        watcher = FocusWatcher(controller)
        watcher._running = True

        # Create a real asyncio task that we can cancel
        async def long_running():
            await asyncio.sleep(100)

        # Create a task and store it
        task = asyncio.create_task(long_running())
        watcher._task = task

        await watcher.stop()

        assert not watcher._running
        assert task.cancelled() or task.done()
        assert watcher._task is None

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """stop does nothing when not running."""
        controller = ItermController()
        watcher = FocusWatcher(controller)

        await watcher.stop()

        assert not watcher._running
        assert watcher._task is None

    @pytest.mark.asyncio
    async def test_watch_loop_calls_callback_on_our_tab(self):
        """_watch_loop calls callback when our tab is selected."""
        controller = ItermController()
        controller._connected = True
        controller.connection = MagicMock()

        callback = MagicMock()
        watcher = FocusWatcher(controller, on_tab_focused=callback)
        watcher._our_tab_id = "tab-123"

        # Create a mock focus update
        mock_update = MagicMock()
        mock_update.selected_tab_changed = MagicMock()
        mock_update.selected_tab_changed.tab_id = "tab-123"

        # Track iterations to stop the loop
        call_count = 0

        async def mock_get_next_update():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_update
            else:
                # Stop the watcher after first iteration
                watcher._running = False
                # Wait longer than the timeout to exit loop
                await asyncio.sleep(10)

        mock_monitor = MagicMock()
        mock_monitor.__aenter__ = AsyncMock(return_value=mock_monitor)
        mock_monitor.__aexit__ = AsyncMock(return_value=None)
        mock_monitor.async_get_next_update = mock_get_next_update

        watcher._running = True

        with patch("iterm2.FocusMonitor", return_value=mock_monitor):
            # Run the watch loop with a timeout
            try:
                await asyncio.wait_for(watcher._watch_loop(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_watch_loop_ignores_other_tabs(self):
        """_watch_loop ignores tab selection for other tabs."""
        controller = ItermController()
        controller._connected = True
        controller.connection = MagicMock()

        callback = MagicMock()
        watcher = FocusWatcher(controller, on_tab_focused=callback)
        watcher._our_tab_id = "tab-123"

        # Create a mock focus update for a different tab
        mock_update = MagicMock()
        mock_update.selected_tab_changed = MagicMock()
        mock_update.selected_tab_changed.tab_id = "tab-other"

        call_count = 0

        async def mock_get_next_update():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_update
            else:
                watcher._running = False
                await asyncio.sleep(10)

        mock_monitor = MagicMock()
        mock_monitor.__aenter__ = AsyncMock(return_value=mock_monitor)
        mock_monitor.__aexit__ = AsyncMock(return_value=None)
        mock_monitor.async_get_next_update = mock_get_next_update

        watcher._running = True

        with patch("iterm2.FocusMonitor", return_value=mock_monitor):
            try:
                await asyncio.wait_for(watcher._watch_loop(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_watch_loop_handles_no_connection(self):
        """_watch_loop exits early when no connection."""
        controller = ItermController()
        controller.connection = None

        watcher = FocusWatcher(controller)
        watcher._running = True

        # Should exit without error
        await watcher._watch_loop()

        # Running flag should remain True (not modified by early exit)
        assert watcher._running

    @pytest.mark.asyncio
    async def test_watch_loop_handles_exception(self):
        """_watch_loop handles exceptions gracefully."""
        controller = ItermController()
        controller._connected = True
        controller.connection = MagicMock()

        watcher = FocusWatcher(controller)
        watcher._our_tab_id = "tab-123"
        watcher._running = True

        mock_monitor = MagicMock()
        mock_monitor.__aenter__ = AsyncMock(side_effect=Exception("Monitor error"))
        mock_monitor.__aexit__ = AsyncMock(return_value=None)

        with patch("iterm2.FocusMonitor", return_value=mock_monitor):
            await watcher._watch_loop()

        # Running should be set to False on error
        assert not watcher._running

    def test_is_running_property(self):
        """is_running property reflects correct state."""
        controller = ItermController()
        watcher = FocusWatcher(controller)

        # Not running initially
        assert not watcher.is_running

        # Running but no task
        watcher._running = True
        assert not watcher.is_running

        # Running with task
        watcher._task = MagicMock()
        assert watcher.is_running

        # Not running with task
        watcher._running = False
        assert not watcher.is_running


class TestFocusWatcherPidRetrieval:
    """Tests for the _get_parent_pids method."""

    def test_get_parent_pids_with_psutil(self):
        """_get_parent_pids uses psutil when available."""
        controller = ItermController()
        watcher = FocusWatcher(controller)

        # Just test that it doesn't crash and includes the start PID
        import os

        pids = watcher._get_parent_pids(os.getpid())
        assert os.getpid() in pids
        # Should have at least our PID and one parent
        assert len(pids) >= 1

    def test_get_parent_pids_handles_exception(self):
        """_get_parent_pids handles exceptions gracefully."""
        controller = ItermController()
        watcher = FocusWatcher(controller)

        # Use an invalid PID that won't exist
        pids = watcher._get_parent_pids(999999999)

        # Should at least include the starting PID
        assert 999999999 in pids
