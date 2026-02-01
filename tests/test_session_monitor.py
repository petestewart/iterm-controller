"""Tests for session monitor output polling system."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iterm_controller.models import ManagedSession
from iterm_controller.session_monitor import (
    BatchOutputReader,
    MetricsCollector,
    MonitorConfig,
    MonitorMetrics,
    OutputCache,
    OutputChange,
    OutputProcessor,
    OutputThrottle,
    SessionMonitor,
    SessionNotFoundError,
)


class TestOutputCache:
    """Test OutputCache functionality."""

    def test_init_defaults(self):
        """Cache initializes with correct defaults."""
        cache = OutputCache()
        assert cache.max_entries == 100

    def test_init_custom_max(self):
        """Cache accepts custom max entries."""
        cache = OutputCache(max_entries=50)
        assert cache.max_entries == 50

    def test_get_missing_returns_none(self):
        """Get returns None for missing session."""
        cache = OutputCache()
        assert cache.get("nonexistent") is None

    def test_set_and_get(self):
        """Set and get work correctly."""
        cache = OutputCache()
        cache.set("session-1", "Hello World")

        result = cache.get("session-1")
        assert result == "Hello World"

    def test_set_overwrites(self):
        """Set overwrites existing value."""
        cache = OutputCache()
        cache.set("session-1", "First")
        cache.set("session-1", "Second")

        result = cache.get("session-1")
        assert result == "Second"

    def test_invalidate_removes_entry(self):
        """Invalidate removes cached entry."""
        cache = OutputCache()
        cache.set("session-1", "data")
        cache.invalidate("session-1")

        assert cache.get("session-1") is None

    def test_invalidate_nonexistent_safe(self):
        """Invalidate is safe for nonexistent entry."""
        cache = OutputCache()
        cache.invalidate("nonexistent")  # Should not raise

    def test_clear_removes_all(self):
        """Clear removes all entries."""
        cache = OutputCache()
        cache.set("session-1", "data1")
        cache.set("session-2", "data2")
        cache.clear()

        assert cache.get("session-1") is None
        assert cache.get("session-2") is None

    def test_evicts_oldest_at_capacity(self):
        """Evicts oldest entry when at capacity."""
        cache = OutputCache(max_entries=2)

        # Set with slight delays to ensure ordering
        cache.set("session-1", "first")
        cache.set("session-2", "second")
        cache.set("session-3", "third")  # Should evict session-1

        assert cache.get("session-1") is None
        assert cache.get("session-2") == "second"
        assert cache.get("session-3") == "third"

    def test_updating_existing_doesnt_evict(self):
        """Updating existing entry doesn't trigger eviction."""
        cache = OutputCache(max_entries=2)

        cache.set("session-1", "first")
        cache.set("session-2", "second")
        cache.set("session-1", "updated")  # Update existing

        assert cache.get("session-1") == "updated"
        assert cache.get("session-2") == "second"


class TestOutputThrottle:
    """Test OutputThrottle functionality."""

    def test_init_defaults(self):
        """Throttle initializes with correct defaults."""
        throttle = OutputThrottle()
        assert throttle.min_interval == 0.1  # 100ms

    def test_init_custom_interval(self):
        """Throttle accepts custom interval."""
        throttle = OutputThrottle(min_process_interval_ms=200)
        assert throttle.min_interval == 0.2

    def test_should_process_first_time(self):
        """First call for a session always returns True."""
        throttle = OutputThrottle()
        assert throttle.should_process("session-1") is True

    def test_should_process_respects_interval(self):
        """Should process respects minimum interval."""
        throttle = OutputThrottle(min_process_interval_ms=1000)  # 1 second

        throttle.mark_processed("session-1")
        assert throttle.should_process("session-1") is False

    def test_should_process_after_interval(self):
        """Should process returns True after interval elapsed."""
        throttle = OutputThrottle(min_process_interval_ms=10)  # 10ms

        throttle.mark_processed("session-1")

        # Wait a bit longer than the interval
        import time

        time.sleep(0.02)

        assert throttle.should_process("session-1") is True

    def test_mark_processed_updates_timestamp(self):
        """Mark processed updates the timestamp."""
        throttle = OutputThrottle()
        throttle.mark_processed("session-1")

        # Should not be ready to process immediately
        assert throttle.should_process("session-1") is False

    def test_clear_single_session(self):
        """Clear resets throttle for single session."""
        throttle = OutputThrottle()
        throttle.mark_processed("session-1")
        throttle.mark_processed("session-2")

        throttle.clear("session-1")

        assert throttle.should_process("session-1") is True
        assert throttle.should_process("session-2") is False

    def test_clear_all_sessions(self):
        """Clear with None resets all sessions."""
        throttle = OutputThrottle()
        throttle.mark_processed("session-1")
        throttle.mark_processed("session-2")

        throttle.clear()

        assert throttle.should_process("session-1") is True
        assert throttle.should_process("session-2") is True


class TestOutputProcessor:
    """Test OutputProcessor functionality."""

    def test_first_output_is_new(self):
        """First output for a session is always 'new'."""
        processor = OutputProcessor()
        change = processor.extract_new_output("session-1", "Hello World")

        assert change.session_id == "session-1"
        assert change.old_output is None
        assert change.new_output == "Hello World"
        assert change.changed is True

    def test_same_output_no_change(self):
        """Same output returns changed=False."""
        processor = OutputProcessor()
        processor.extract_new_output("session-1", "Hello World")

        change = processor.extract_new_output("session-1", "Hello World")

        assert change.changed is False
        assert change.new_output == "Hello World"

    def test_appended_output_extracts_new(self):
        """Appended output extracts just the new portion."""
        processor = OutputProcessor()
        processor.extract_new_output("session-1", "Line 1")

        change = processor.extract_new_output("session-1", "Line 1\nLine 2")

        assert change.changed is True
        assert change.new_output == "\nLine 2"

    def test_scrolled_output_returns_full_new(self):
        """Scrolled output (old not in new) returns full new output."""
        processor = OutputProcessor()
        processor.extract_new_output("session-1", "Old content")

        change = processor.extract_new_output("session-1", "Completely new content")

        assert change.changed is True
        assert change.new_output == "Completely new content"

    def test_clear_single_session(self):
        """Clear resets state for single session."""
        processor = OutputProcessor()
        processor.extract_new_output("session-1", "data")
        processor.extract_new_output("session-2", "data")

        processor.clear("session-1")

        # session-1 should be treated as new
        change1 = processor.extract_new_output("session-1", "new")
        assert change1.old_output is None

        # session-2 should still have history
        change2 = processor.extract_new_output("session-2", "data")
        assert change2.changed is False

    def test_clear_all_sessions(self):
        """Clear with None resets all sessions."""
        processor = OutputProcessor()
        processor.extract_new_output("session-1", "data")
        processor.extract_new_output("session-2", "data")

        processor.clear()

        # Both should be treated as new
        change1 = processor.extract_new_output("session-1", "data")
        change2 = processor.extract_new_output("session-2", "data")

        assert change1.old_output is None
        assert change2.old_output is None


class TestBatchOutputReader:
    """Test BatchOutputReader functionality."""

    def make_mock_controller(self):
        """Create a mock controller."""
        controller = MagicMock()
        controller.app = MagicMock()
        return controller

    @pytest.mark.asyncio
    async def test_read_batch_empty_list(self):
        """Read batch with empty list returns empty dict."""
        controller = self.make_mock_controller()
        reader = BatchOutputReader(controller)

        result = await reader.read_batch([])

        assert result == {}

    @pytest.mark.asyncio
    async def test_read_batch_success(self):
        """Read batch returns output for found sessions."""
        controller = self.make_mock_controller()

        mock_session = MagicMock()
        mock_session.async_get_contents = AsyncMock(return_value="Session output")

        controller.app.async_get_session_by_id = AsyncMock(return_value=mock_session)

        reader = BatchOutputReader(controller)
        result = await reader.read_batch(["session-1"])

        assert result == {"session-1": "Session output"}
        mock_session.async_get_contents.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_batch_multiple_sessions(self):
        """Read batch handles multiple sessions concurrently."""
        controller = self.make_mock_controller()

        sessions = {
            "session-1": MagicMock(
                async_get_contents=AsyncMock(return_value="Output 1")
            ),
            "session-2": MagicMock(
                async_get_contents=AsyncMock(return_value="Output 2")
            ),
        }

        async def get_session(session_id):
            return sessions.get(session_id)

        controller.app.async_get_session_by_id = AsyncMock(side_effect=get_session)

        reader = BatchOutputReader(controller)
        result = await reader.read_batch(["session-1", "session-2"])

        assert result == {"session-1": "Output 1", "session-2": "Output 2"}

    @pytest.mark.asyncio
    async def test_read_batch_session_not_found(self):
        """Read batch omits sessions that aren't found."""
        controller = self.make_mock_controller()
        controller.app.async_get_session_by_id = AsyncMock(return_value=None)

        reader = BatchOutputReader(controller)
        result = await reader.read_batch(["nonexistent"])

        assert result == {}

    @pytest.mark.asyncio
    async def test_read_batch_mixed_success_failure(self):
        """Read batch returns successful reads, omits failures."""
        controller = self.make_mock_controller()

        mock_session = MagicMock()
        mock_session.async_get_contents = AsyncMock(return_value="Good output")

        async def get_session(session_id):
            if session_id == "good":
                return mock_session
            return None

        controller.app.async_get_session_by_id = AsyncMock(side_effect=get_session)

        reader = BatchOutputReader(controller)
        result = await reader.read_batch(["good", "bad"])

        assert result == {"good": "Good output"}

    @pytest.mark.asyncio
    async def test_read_one_not_connected(self):
        """Read one raises when not connected."""
        controller = MagicMock()
        controller.app = None

        reader = BatchOutputReader(controller)

        with pytest.raises(SessionNotFoundError) as exc_info:
            await reader._read_one("session-1")

        assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_read_one_session_not_found(self):
        """Read one raises when session not found."""
        controller = self.make_mock_controller()
        controller.app.async_get_session_by_id = AsyncMock(return_value=None)

        reader = BatchOutputReader(controller)

        with pytest.raises(SessionNotFoundError) as exc_info:
            await reader._read_one("missing")

        assert "missing" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_read_uses_configured_lines(self):
        """Read uses configured number of lines."""
        controller = self.make_mock_controller()

        mock_session = MagicMock()
        mock_session.async_get_contents = AsyncMock(return_value="output")
        controller.app.async_get_session_by_id = AsyncMock(return_value=mock_session)

        reader = BatchOutputReader(controller, lines_to_read=100)
        await reader._read_one("session-1")

        mock_session.async_get_contents.assert_called_once_with(
            first_line=-100, number_of_lines=100
        )


class TestMonitorConfig:
    """Test MonitorConfig defaults."""

    def test_defaults(self):
        """Config has correct defaults."""
        config = MonitorConfig()
        assert config.polling_interval_ms == 500
        assert config.batch_size == 10
        assert config.lines_to_read == 50
        assert config.throttle_interval_ms == 100
        assert config.cache_max_entries == 100

    def test_custom_values(self):
        """Config accepts custom values."""
        config = MonitorConfig(
            polling_interval_ms=1000,
            batch_size=5,
            lines_to_read=100,
        )
        assert config.polling_interval_ms == 1000
        assert config.batch_size == 5
        assert config.lines_to_read == 100


class TestSessionMonitor:
    """Test SessionMonitor functionality."""

    def make_mock_controller(self):
        """Create a mock controller."""
        controller = MagicMock()
        controller.app = MagicMock()
        return controller

    def make_mock_spawner(self, sessions=None):
        """Create a mock spawner with optional sessions."""
        spawner = MagicMock()
        spawner.managed_sessions = sessions or {}
        return spawner

    def make_session(self, session_id="session-1"):
        """Create a ManagedSession for testing."""
        return ManagedSession(
            id=session_id,
            template_id="test-template",
            project_id="test-project",
            tab_id="tab-1",
        )

    def test_init_defaults(self):
        """Monitor initializes with correct defaults."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()

        monitor = SessionMonitor(controller, spawner)

        assert monitor.controller is controller
        assert monitor.spawner is spawner
        assert monitor.config.polling_interval_ms == 500
        assert monitor.is_running is False
        assert monitor.poll_count == 0

    def test_init_custom_config(self):
        """Monitor accepts custom config."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        config = MonitorConfig(polling_interval_ms=1000)

        monitor = SessionMonitor(controller, spawner, config=config)

        assert monitor.config.polling_interval_ms == 1000

    def test_init_with_callback(self):
        """Monitor accepts output callback."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()

        callback_called = []

        def on_output(session, output, changed):
            callback_called.append((session.id, output, changed))

        monitor = SessionMonitor(controller, spawner, on_output=on_output)

        assert monitor.on_output is not None

    @pytest.mark.asyncio
    async def test_start_sets_running(self):
        """Start sets running flag and creates task."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        await monitor.start()

        assert monitor.is_running is True
        assert monitor._task is not None

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_clears_running(self):
        """Stop clears running flag and cancels task."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        await monitor.start()
        await monitor.stop()

        assert monitor.is_running is False
        assert monitor._task is None

    @pytest.mark.asyncio
    async def test_start_when_already_running(self):
        """Start is safe when already running."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        await monitor.start()
        task1 = monitor._task

        await monitor.start()  # Should not raise
        task2 = monitor._task

        assert task1 is task2  # Same task

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_poll_once_no_sessions(self):
        """Poll once with no sessions returns empty dict."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        result = await monitor.poll_once()

        assert result == {}

    @pytest.mark.asyncio
    async def test_poll_once_with_sessions(self):
        """Poll once with sessions returns changes."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(return_value="New output")
        controller.app.async_get_session_by_id = AsyncMock(
            return_value=mock_iterm_session
        )

        monitor = SessionMonitor(controller, spawner)
        result = await monitor.poll_once()

        assert "session-1" in result
        assert result["session-1"].changed is True
        assert result["session-1"].new_output == "New output"

    @pytest.mark.asyncio
    async def test_poll_updates_session_state(self):
        """Poll updates session last_output and last_activity."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(return_value="New output")
        controller.app.async_get_session_by_id = AsyncMock(
            return_value=mock_iterm_session
        )

        monitor = SessionMonitor(controller, spawner)
        await monitor.poll_once()

        assert session.last_output == "New output"
        assert session.last_activity is not None

    @pytest.mark.asyncio
    async def test_poll_invokes_callback(self):
        """Poll invokes callback on output change."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(return_value="New output")
        controller.app.async_get_session_by_id = AsyncMock(
            return_value=mock_iterm_session
        )

        callback_calls = []

        def on_output(sess, output, changed):
            callback_calls.append((sess.id, output, changed))

        monitor = SessionMonitor(controller, spawner, on_output=on_output)
        await monitor.poll_once()

        assert len(callback_calls) == 1
        assert callback_calls[0] == ("session-1", "New output", True)

    @pytest.mark.asyncio
    async def test_poll_handles_callback_error(self):
        """Poll continues even if callback raises."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(return_value="Output")
        controller.app.async_get_session_by_id = AsyncMock(
            return_value=mock_iterm_session
        )

        def bad_callback(sess, output, changed):
            raise ValueError("Callback error")

        monitor = SessionMonitor(controller, spawner, on_output=bad_callback)

        # Should not raise
        result = await monitor.poll_once()

        assert "session-1" in result

    @pytest.mark.asyncio
    async def test_poll_batches_sessions(self):
        """Poll processes sessions in batches."""
        controller = self.make_mock_controller()

        # Create 15 sessions to test batching (batch size is 10)
        sessions = {}
        for i in range(15):
            sess = self.make_session(f"session-{i}")
            sessions[f"session-{i}"] = sess

        spawner = self.make_mock_spawner(sessions)

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(return_value="Output")
        controller.app.async_get_session_by_id = AsyncMock(
            return_value=mock_iterm_session
        )

        monitor = SessionMonitor(controller, spawner)
        result = await monitor.poll_once()

        # All sessions should be polled
        assert len(result) == 15

    @pytest.mark.asyncio
    async def test_poll_uses_cache(self):
        """Poll uses cache to avoid redundant processing."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(return_value="Same output")
        controller.app.async_get_session_by_id = AsyncMock(
            return_value=mock_iterm_session
        )

        # Use short throttle to allow rapid polling
        config = MonitorConfig(throttle_interval_ms=1)
        monitor = SessionMonitor(controller, spawner, config=config)

        # First poll should return change
        result1 = await monitor.poll_once()
        assert "session-1" in result1

        # Wait for throttle
        await asyncio.sleep(0.01)

        # Second poll with same output should not return change
        result2 = await monitor.poll_once()
        assert "session-1" not in result2

    def test_clear_session(self):
        """Clear session removes all cached state for that session."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        # Pre-populate caches
        monitor._cache.set("session-1", "cached")
        monitor._processor._last_output["session-1"] = "output"
        monitor._throttle._last_process["session-1"] = datetime.now()

        monitor.clear_session("session-1")

        assert monitor._cache.get("session-1") is None
        assert "session-1" not in monitor._processor._last_output
        assert "session-1" not in monitor._throttle._last_process

    def test_clear_all(self):
        """Clear all removes all cached state."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        # Pre-populate caches
        monitor._cache.set("session-1", "cached")
        monitor._cache.set("session-2", "cached")
        monitor._processor._last_output["session-1"] = "output"
        monitor._throttle._last_process["session-1"] = datetime.now()

        monitor.clear_all()

        assert monitor._cache.get("session-1") is None
        assert monitor._cache.get("session-2") is None
        assert len(monitor._processor._last_output) == 0
        assert len(monitor._throttle._last_process) == 0


class TestMetricsCollector:
    """Test MetricsCollector functionality."""

    def test_init(self):
        """Collector initializes with zero metrics."""
        collector = MetricsCollector()

        assert collector.metrics.poll_count == 0
        assert collector.metrics.sessions_polled == 0
        assert collector.metrics.output_changes == 0
        assert collector.metrics.errors == 0
        assert collector.metrics.avg_poll_duration_ms == 0.0

    def test_record_poll(self):
        """Record poll updates metrics."""
        collector = MetricsCollector()

        collector.record_poll(duration_ms=50.0, sessions_polled=5, changes=2)

        assert collector.metrics.poll_count == 1
        assert collector.metrics.sessions_polled == 5
        assert collector.metrics.output_changes == 2
        assert collector.metrics.avg_poll_duration_ms == 50.0

    def test_record_multiple_polls(self):
        """Multiple polls accumulate correctly."""
        collector = MetricsCollector()

        collector.record_poll(duration_ms=40.0, sessions_polled=5, changes=1)
        collector.record_poll(duration_ms=60.0, sessions_polled=5, changes=2)

        assert collector.metrics.poll_count == 2
        assert collector.metrics.sessions_polled == 10
        assert collector.metrics.output_changes == 3
        assert collector.metrics.avg_poll_duration_ms == 50.0  # (40 + 60) / 2

    def test_record_error(self):
        """Record error increments error count."""
        collector = MetricsCollector()

        collector.record_error()
        collector.record_error()

        assert collector.metrics.errors == 2

    def test_reset(self):
        """Reset clears all metrics."""
        collector = MetricsCollector()
        collector.record_poll(duration_ms=50.0, sessions_polled=5, changes=2)
        collector.record_error()

        collector.reset()

        assert collector.metrics.poll_count == 0
        assert collector.metrics.sessions_polled == 0
        assert collector.metrics.output_changes == 0
        assert collector.metrics.errors == 0
        assert collector.metrics.avg_poll_duration_ms == 0.0

    def test_avg_duration_limits_history(self):
        """Average duration only considers last 100 samples."""
        collector = MetricsCollector()

        # Record 150 polls with duration 100ms
        for _ in range(150):
            collector.record_poll(duration_ms=100.0, sessions_polled=1, changes=0)

        # Record 50 more with duration 200ms
        for _ in range(50):
            collector.record_poll(duration_ms=200.0, sessions_polled=1, changes=0)

        # Average should be based on last 100:
        # 50 samples of 100ms + 50 samples of 200ms = 150ms average
        assert collector.metrics.avg_poll_duration_ms == 150.0


class TestOutputChange:
    """Test OutputChange dataclass."""

    def test_output_change_creation(self):
        """OutputChange can be created with all fields."""
        change = OutputChange(
            session_id="session-1",
            old_output="old",
            new_output="new",
            changed=True,
        )

        assert change.session_id == "session-1"
        assert change.old_output == "old"
        assert change.new_output == "new"
        assert change.changed is True

    def test_output_change_none_old(self):
        """OutputChange can have None old_output."""
        change = OutputChange(
            session_id="session-1",
            old_output=None,
            new_output="first output",
            changed=True,
        )

        assert change.old_output is None
