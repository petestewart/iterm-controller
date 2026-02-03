"""Tests for session monitor output polling system."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iterm_controller.models import AttentionState, ManagedSession
from iterm_controller.session_monitor import (
    AdaptivePoller,
    AttentionDetector,
    BatchOutputReader,
    CLAUDE_WAITING_PATTERNS,
    CLAUDE_WORKING_PATTERNS,
    CONFIRMATION_PATTERNS,
    MAX_OUTPUT_BUFFER_BYTES,
    MetricsCollector,
    MonitorConfig,
    MonitorMetrics,
    OutputCache,
    OutputChange,
    OutputProcessor,
    OutputStreamManager,
    OutputThrottle,
    SessionMonitor,
    SessionNotFoundError,
    SessionOutputStream,
    SHELL_PROMPT_PATTERNS,
    truncate_output,
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

        controller.app.get_session_by_id = MagicMock(return_value=mock_session)

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

        def get_session(session_id):
            return sessions.get(session_id)

        controller.app.get_session_by_id = MagicMock(side_effect=get_session)

        reader = BatchOutputReader(controller)
        result = await reader.read_batch(["session-1", "session-2"])

        assert result == {"session-1": "Output 1", "session-2": "Output 2"}

    @pytest.mark.asyncio
    async def test_read_batch_session_not_found(self):
        """Read batch omits sessions that aren't found."""
        controller = self.make_mock_controller()
        controller.app.get_session_by_id = MagicMock(return_value=None)

        reader = BatchOutputReader(controller)
        result = await reader.read_batch(["nonexistent"])

        assert result == {}

    @pytest.mark.asyncio
    async def test_read_batch_mixed_success_failure(self):
        """Read batch returns successful reads, omits failures."""
        controller = self.make_mock_controller()

        mock_session = MagicMock()
        mock_session.async_get_contents = AsyncMock(return_value="Good output")

        def get_session(session_id):
            if session_id == "good":
                return mock_session
            return None

        controller.app.get_session_by_id = MagicMock(side_effect=get_session)

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
        controller.app.get_session_by_id = MagicMock(return_value=None)

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
        controller.app.get_session_by_id = MagicMock(return_value=mock_session)

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
        controller.app.get_session_by_id = MagicMock(
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
        controller.app.get_session_by_id = MagicMock(
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
        controller.app.get_session_by_id = MagicMock(
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
        controller.app.get_session_by_id = MagicMock(
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
        controller.app.get_session_by_id = MagicMock(
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
        controller.app.get_session_by_id = MagicMock(
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

    @pytest.mark.asyncio
    async def test_clear_session(self):
        """Clear session removes all cached state for that session."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        # Pre-populate caches
        monitor._cache.set("session-1", "cached")
        monitor._processor._last_output["session-1"] = "output"
        monitor._throttle._last_process["session-1"] = datetime.now()

        await monitor.clear_session("session-1")

        assert monitor._cache.get("session-1") is None
        assert "session-1" not in monitor._processor._last_output
        assert "session-1" not in monitor._throttle._last_process

    @pytest.mark.asyncio
    async def test_clear_all(self):
        """Clear all removes all cached state."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        # Pre-populate caches
        monitor._cache.set("session-1", "cached")
        monitor._cache.set("session-2", "cached")
        monitor._processor._last_output["session-1"] = "output"
        monitor._throttle._last_process["session-1"] = datetime.now()

        await monitor.clear_all()

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


class TestAttentionDetector:
    """Test AttentionDetector pattern matching."""

    def make_session(self, session_id="session-1", last_activity=None):
        """Create a ManagedSession for testing."""
        session = ManagedSession(
            id=session_id,
            template_id="test-template",
            project_id="test-project",
            tab_id="tab-1",
        )
        session.last_activity = last_activity
        return session

    def test_init_defaults(self):
        """Detector initializes with correct defaults."""
        detector = AttentionDetector()
        assert detector.activity_threshold.total_seconds() == 2.0

    def test_init_custom_threshold(self):
        """Detector accepts custom activity threshold."""
        detector = AttentionDetector(activity_threshold_seconds=5.0)
        assert detector.activity_threshold.total_seconds() == 5.0

    # ==========================================================================
    # WAITING state detection
    # ==========================================================================

    def test_detects_question_mark_as_waiting(self):
        """Output ending with question mark is WAITING."""
        detector = AttentionDetector()
        session = self.make_session()

        output = "Should I use JWT for authentication?"
        state = detector.determine_state(session, output)

        assert state == AttentionState.WAITING

    def test_detects_question_mark_with_whitespace_as_waiting(self):
        """Question mark with trailing whitespace is WAITING."""
        detector = AttentionDetector()
        session = self.make_session()

        output = "Should I proceed?  \n"
        state = detector.determine_state(session, output)

        assert state == AttentionState.WAITING

    def test_detects_claude_question_patterns(self):
        """Claude question patterns are WAITING."""
        detector = AttentionDetector()
        session = self.make_session()

        patterns = [
            "I have a question about the API design",
            "Before I proceed, I need clarification",
            "Could you clarify what you mean?",
            "Which would you prefer: option A or B",
            "Should I add error handling here?",
            "Do you want me to refactor this?",
            "Please confirm you want to delete",
        ]

        for pattern in patterns:
            state = detector.determine_state(session, pattern)
            assert state == AttentionState.WAITING, f"Failed for: {pattern}"

    def test_detects_confirmation_prompts(self):
        """Confirmation prompts are WAITING."""
        detector = AttentionDetector()
        session = self.make_session()

        prompts = [
            "Delete file? [y/N]",
            "Continue? [Y/n]",
            "Are you sure (yes/no)?",
            "Continue? This may take a while",
            "Press Enter to continue",
            "Press any key to exit",
            "Are you sure you want to proceed?",
        ]

        for prompt in prompts:
            state = detector.determine_state(session, prompt)
            assert state == AttentionState.WAITING, f"Failed for: {prompt}"

    def test_detects_yes_no_brackets(self):
        """[yes/no] patterns are WAITING."""
        detector = AttentionDetector()
        session = self.make_session()

        output = "Overwrite existing file? [yes/no]"
        state = detector.determine_state(session, output)

        assert state == AttentionState.WAITING

    # ==========================================================================
    # IDLE state detection (shell prompts)
    # ==========================================================================

    def test_detects_dollar_prompt_as_idle(self):
        """$ prompt is IDLE."""
        detector = AttentionDetector()
        session = self.make_session()

        output = "previous output\n$ "
        state = detector.determine_state(session, output)

        assert state == AttentionState.IDLE

    def test_detects_starship_prompt_as_idle(self):
        """❯ prompt is IDLE."""
        detector = AttentionDetector()
        session = self.make_session()

        output = "some output\n❯ "
        state = detector.determine_state(session, output)

        assert state == AttentionState.IDLE

    def test_detects_zsh_prompt_as_idle(self):
        """% prompt is IDLE."""
        detector = AttentionDetector()
        session = self.make_session()

        output = "command completed\n% "
        state = detector.determine_state(session, output)

        assert state == AttentionState.IDLE

    def test_detects_simple_prompt_as_idle(self):
        """> prompt is IDLE."""
        detector = AttentionDetector()
        session = self.make_session()

        output = "Done!\n> "
        state = detector.determine_state(session, output)

        assert state == AttentionState.IDLE

    def test_detects_user_host_prompt_as_idle(self):
        """[user@host] style prompt is IDLE."""
        detector = AttentionDetector()
        session = self.make_session()

        output = "output\n[user@localhost]"
        state = detector.determine_state(session, output)

        assert state == AttentionState.IDLE

    # ==========================================================================
    # WORKING state detection
    # ==========================================================================

    def test_detects_reading_pattern_as_working(self):
        """Reading output is WORKING."""
        detector = AttentionDetector()
        session = self.make_session()

        output = "Reading file contents..."
        state = detector.determine_state(session, output)

        assert state == AttentionState.WORKING

    def test_detects_writing_pattern_as_working(self):
        """Writing output is WORKING."""
        detector = AttentionDetector()
        session = self.make_session()

        output = "Writing to disk..."
        state = detector.determine_state(session, output)

        assert state == AttentionState.WORKING

    def test_detects_searching_pattern_as_working(self):
        """Searching output is WORKING."""
        detector = AttentionDetector()
        session = self.make_session()

        output = "Searching for files..."
        state = detector.determine_state(session, output)

        assert state == AttentionState.WORKING

    def test_detects_running_pattern_as_working(self):
        """Running output is WORKING."""
        detector = AttentionDetector()
        session = self.make_session()

        output = "Running tests..."
        state = detector.determine_state(session, output)

        assert state == AttentionState.WORKING

    def test_detects_creating_pattern_as_working(self):
        """Creating ... output is WORKING."""
        detector = AttentionDetector()
        session = self.make_session()

        output = "Creating new component..."
        state = detector.determine_state(session, output)

        assert state == AttentionState.WORKING

    def test_detects_analyzing_pattern_as_working(self):
        """Analyzing output is WORKING."""
        detector = AttentionDetector()
        session = self.make_session()

        output = "Analyzing codebase structure"
        state = detector.determine_state(session, output)

        assert state == AttentionState.WORKING

    def test_recent_activity_means_working(self):
        """Recent activity (< 2s) makes session WORKING."""
        detector = AttentionDetector()
        session = self.make_session(last_activity=datetime.now())

        # Generic output that doesn't match patterns
        output = "some random text"
        state = detector.determine_state(session, output)

        assert state == AttentionState.WORKING

    def test_old_activity_means_idle(self):
        """Old activity (> 2s) makes session IDLE."""
        detector = AttentionDetector()
        old_time = datetime.now() - timedelta(seconds=5)
        session = self.make_session(last_activity=old_time)

        # Generic output that doesn't match patterns
        output = "some random text"
        state = detector.determine_state(session, output)

        assert state == AttentionState.IDLE

    # ==========================================================================
    # Priority ordering
    # ==========================================================================

    def test_waiting_takes_priority_over_working(self):
        """WAITING patterns take priority over WORKING patterns."""
        detector = AttentionDetector()
        session = self.make_session(last_activity=datetime.now())

        # Contains both working and waiting patterns
        output = "Running tests... Should I continue? [y/N]"
        state = detector.determine_state(session, output)

        assert state == AttentionState.WAITING

    def test_waiting_takes_priority_over_shell_prompt(self):
        """WAITING patterns take priority over shell prompt."""
        detector = AttentionDetector()
        session = self.make_session()

        # Ends with prompt but has question
        output = "Do you want to run the script?\n$ "
        state = detector.determine_state(session, output)

        # Question mark should be detected since it searches whole output
        assert state == AttentionState.WAITING

    def test_shell_prompt_takes_priority_over_recent_activity(self):
        """Shell prompt IDLE takes priority over recent activity WORKING."""
        detector = AttentionDetector()
        session = self.make_session(last_activity=datetime.now())

        output = "Command completed\n$ "
        state = detector.determine_state(session, output)

        assert state == AttentionState.IDLE

    # ==========================================================================
    # Edge cases
    # ==========================================================================

    def test_empty_output_is_idle(self):
        """Empty output returns IDLE."""
        detector = AttentionDetector()
        session = self.make_session()

        state = detector.determine_state(session, "")

        assert state == AttentionState.IDLE

    def test_whitespace_only_is_idle(self):
        """Whitespace-only output returns IDLE."""
        detector = AttentionDetector()
        session = self.make_session()

        state = detector.determine_state(session, "   \n  \n  ")

        assert state == AttentionState.IDLE

    def test_multiline_output_checks_whole_content(self):
        """Patterns are searched in entire output, not just last line."""
        detector = AttentionDetector()
        session = self.make_session()

        output = "Line 1\nLine 2\nShould I proceed?\nLine 4"
        state = detector.determine_state(session, output)

        assert state == AttentionState.WAITING

    def test_case_insensitive_waiting_patterns(self):
        """Waiting patterns are case insensitive."""
        detector = AttentionDetector()
        session = self.make_session()

        patterns = [
            "SHOULD I PROCEED?",
            "Do You Want Me To continue?",
            "PLEASE CONFIRM",
        ]

        for pattern in patterns:
            state = detector.determine_state(session, pattern)
            assert state == AttentionState.WAITING, f"Failed for: {pattern}"

    def test_case_insensitive_working_patterns(self):
        """Working patterns are case insensitive."""
        detector = AttentionDetector()
        session = self.make_session()

        patterns = [
            "READING file...",
            "WRITING to disk...",
            "ANALYZING code...",
        ]

        for pattern in patterns:
            state = detector.determine_state(session, pattern)
            assert state == AttentionState.WORKING, f"Failed for: {pattern}"

    # ==========================================================================
    # get_pattern_match method
    # ==========================================================================

    def test_get_pattern_match_returns_pattern(self):
        """get_pattern_match returns the matched pattern."""
        detector = AttentionDetector()

        state, pattern = detector.get_pattern_match("Should I proceed?")

        assert state == AttentionState.WAITING
        assert pattern is not None
        assert "?" in pattern or "Should I" in pattern

    def test_get_pattern_match_shell_prompt(self):
        """get_pattern_match returns 'shell_prompt' for prompts."""
        detector = AttentionDetector()

        state, pattern = detector.get_pattern_match("some output\n$ ")

        assert state == AttentionState.IDLE
        assert pattern == "shell_prompt"

    def test_get_pattern_match_no_match(self):
        """get_pattern_match returns None pattern when no match."""
        detector = AttentionDetector()

        state, pattern = detector.get_pattern_match("random text here")

        assert state == AttentionState.IDLE
        assert pattern is None

    # ==========================================================================
    # _is_shell_prompt method
    # ==========================================================================

    def test_is_shell_prompt_true_for_prompts(self):
        """_is_shell_prompt returns True for shell prompts."""
        detector = AttentionDetector()

        assert detector._is_shell_prompt("$ ") is True
        assert detector._is_shell_prompt("output\n$ ") is True
        assert detector._is_shell_prompt("% ") is True
        assert detector._is_shell_prompt("❯ ") is True

    def test_is_shell_prompt_false_for_non_prompts(self):
        """_is_shell_prompt returns False for non-prompts."""
        detector = AttentionDetector()

        assert detector._is_shell_prompt("some text") is False
        assert detector._is_shell_prompt("echo $PATH") is False
        assert detector._is_shell_prompt("output here") is False

    def test_is_shell_prompt_empty(self):
        """_is_shell_prompt returns False for empty input."""
        detector = AttentionDetector()

        assert detector._is_shell_prompt("") is False
        assert detector._is_shell_prompt("   ") is False
        assert detector._is_shell_prompt("\n\n") is False


class TestSessionMonitorAttentionIntegration:
    """Test SessionMonitor integration with AttentionDetector."""

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

    def test_monitor_has_detector(self):
        """SessionMonitor has an AttentionDetector."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        assert hasattr(monitor, "_detector")
        assert isinstance(monitor._detector, AttentionDetector)

    def test_monitor_exposes_detector(self):
        """SessionMonitor exposes detector via property."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        assert monitor.detector is monitor._detector

    def test_detect_attention_state_method(self):
        """detect_attention_state method works."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)
        session = self.make_session()

        state = monitor.detect_attention_state(session, "Should I proceed?")

        assert state == AttentionState.WAITING

    @pytest.mark.asyncio
    async def test_poll_updates_attention_state(self):
        """Poll updates session attention_state."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(
            return_value="Should I proceed?"
        )
        controller.app.get_session_by_id = MagicMock(
            return_value=mock_iterm_session
        )

        monitor = SessionMonitor(controller, spawner)
        await monitor.poll_once()

        assert session.attention_state == AttentionState.WAITING

    @pytest.mark.asyncio
    async def test_poll_invokes_attention_callback_on_change(self):
        """Poll invokes attention callback when state changes."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(
            return_value="Should I proceed?"
        )
        controller.app.get_session_by_id = MagicMock(
            return_value=mock_iterm_session
        )

        callback_calls = []

        def on_attention_change(sess, old_state, new_state):
            callback_calls.append((sess.id, old_state, new_state))

        monitor = SessionMonitor(
            controller, spawner, on_attention_state_change=on_attention_change
        )
        await monitor.poll_once()

        assert len(callback_calls) == 1
        assert callback_calls[0][0] == "session-1"
        assert callback_calls[0][1] == AttentionState.IDLE  # Initial state
        assert callback_calls[0][2] == AttentionState.WAITING

    @pytest.mark.asyncio
    async def test_poll_no_callback_when_state_unchanged(self):
        """Poll does not invoke callback when state unchanged."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        session.attention_state = AttentionState.IDLE
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        # Output that will be detected as IDLE (ends with shell prompt)
        mock_iterm_session.async_get_contents = AsyncMock(
            return_value="output\n$ "
        )
        controller.app.get_session_by_id = MagicMock(
            return_value=mock_iterm_session
        )

        callback_calls = []

        def on_attention_change(sess, old_state, new_state):
            callback_calls.append((sess.id, old_state, new_state))

        monitor = SessionMonitor(
            controller, spawner, on_attention_state_change=on_attention_change
        )
        await monitor.poll_once()

        # No callback because state was already IDLE
        assert len(callback_calls) == 0

    @pytest.mark.asyncio
    async def test_poll_handles_attention_callback_error(self):
        """Poll continues even if attention callback raises."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(
            return_value="Should I proceed?"
        )
        controller.app.get_session_by_id = MagicMock(
            return_value=mock_iterm_session
        )

        def bad_callback(sess, old_state, new_state):
            raise ValueError("Callback error")

        monitor = SessionMonitor(
            controller, spawner, on_attention_state_change=bad_callback
        )

        # Should not raise
        result = await monitor.poll_once()

        assert "session-1" in result
        assert session.attention_state == AttentionState.WAITING


class TestPatternLists:
    """Test that pattern lists are properly defined."""

    def test_claude_waiting_patterns_exist(self):
        """CLAUDE_WAITING_PATTERNS is defined and non-empty."""
        assert len(CLAUDE_WAITING_PATTERNS) > 0

    def test_claude_working_patterns_exist(self):
        """CLAUDE_WORKING_PATTERNS is defined and non-empty."""
        assert len(CLAUDE_WORKING_PATTERNS) > 0

    def test_shell_prompt_patterns_exist(self):
        """SHELL_PROMPT_PATTERNS is defined and non-empty."""
        assert len(SHELL_PROMPT_PATTERNS) > 0

    def test_confirmation_patterns_exist(self):
        """CONFIRMATION_PATTERNS is defined and non-empty."""
        assert len(CONFIRMATION_PATTERNS) > 0

    def test_patterns_are_valid_regex(self):
        """All patterns compile as valid regex."""
        import re

        all_patterns = (
            CLAUDE_WAITING_PATTERNS
            + CLAUDE_WORKING_PATTERNS
            + SHELL_PROMPT_PATTERNS
            + CONFIRMATION_PATTERNS
        )

        for pattern in all_patterns:
            try:
                re.compile(pattern)
            except re.error as e:
                pytest.fail(f"Invalid regex pattern '{pattern}': {e}")


class TestAdaptivePoller:
    """Test AdaptivePoller functionality."""

    def test_init_defaults(self):
        """Poller initializes with correct defaults."""
        poller = AdaptivePoller()

        assert poller.min_interval_ms == 100
        assert poller.max_interval_ms == 2000
        assert poller.default_interval_ms == 500

    def test_init_custom_values(self):
        """Poller accepts custom values."""
        poller = AdaptivePoller(
            min_interval_ms=50,
            max_interval_ms=5000,
            default_interval_ms=1000,
        )

        assert poller.min_interval_ms == 50
        assert poller.max_interval_ms == 5000
        assert poller.default_interval_ms == 1000

    def test_get_interval_ms_returns_default_for_unknown(self):
        """get_interval_ms returns default for unknown session."""
        poller = AdaptivePoller(default_interval_ms=500)

        result = poller.get_interval_ms("unknown-session")

        assert result == 500

    def test_get_interval_returns_seconds(self):
        """get_interval returns interval in seconds."""
        poller = AdaptivePoller(default_interval_ms=500)

        result = poller.get_interval("session-1")

        assert result == 0.5

    def test_on_output_with_output_decreases_interval(self):
        """on_output with had_output=True decreases interval."""
        poller = AdaptivePoller(
            min_interval_ms=100,
            max_interval_ms=2000,
            default_interval_ms=500,
        )

        new_interval = poller.on_output("session-1", had_output=True)

        # 500 // 2 = 250
        assert new_interval == 250
        assert poller.get_interval_ms("session-1") == 250

    def test_on_output_with_output_halves_interval(self):
        """on_output with had_output=True halves the interval."""
        poller = AdaptivePoller(min_interval_ms=100, default_interval_ms=1000)

        poller.on_output("session-1", had_output=True)
        assert poller.get_interval_ms("session-1") == 500  # 1000 // 2

        poller.on_output("session-1", had_output=True)
        assert poller.get_interval_ms("session-1") == 250  # 500 // 2

        poller.on_output("session-1", had_output=True)
        assert poller.get_interval_ms("session-1") == 125  # 250 // 2

        poller.on_output("session-1", had_output=True)
        assert poller.get_interval_ms("session-1") == 100  # min

    def test_on_output_respects_min_interval(self):
        """on_output never goes below min_interval."""
        poller = AdaptivePoller(min_interval_ms=100, default_interval_ms=150)

        poller.on_output("session-1", had_output=True)
        # 150 // 2 = 75, but min is 100
        assert poller.get_interval_ms("session-1") == 100

    def test_on_output_without_output_increases_interval(self):
        """on_output with had_output=False increases interval."""
        poller = AdaptivePoller(
            min_interval_ms=100,
            max_interval_ms=2000,
            default_interval_ms=500,
        )

        new_interval = poller.on_output("session-1", had_output=False)

        # 500 * 1.5 = 750
        assert new_interval == 750
        assert poller.get_interval_ms("session-1") == 750

    def test_on_output_without_output_increases_by_1_5x(self):
        """on_output with had_output=False increases by 1.5x."""
        poller = AdaptivePoller(max_interval_ms=2000, default_interval_ms=100)

        poller.on_output("session-1", had_output=False)
        assert poller.get_interval_ms("session-1") == 150  # 100 * 1.5

        poller.on_output("session-1", had_output=False)
        assert poller.get_interval_ms("session-1") == 225  # 150 * 1.5 = 225

        poller.on_output("session-1", had_output=False)
        assert poller.get_interval_ms("session-1") == 337  # 225 * 1.5 = 337.5 -> 337

    def test_on_output_respects_max_interval(self):
        """on_output never goes above max_interval."""
        poller = AdaptivePoller(max_interval_ms=2000, default_interval_ms=1500)

        poller.on_output("session-1", had_output=False)
        # 1500 * 1.5 = 2250, but max is 2000
        assert poller.get_interval_ms("session-1") == 2000

    def test_on_state_change_waiting_sets_max(self):
        """on_state_change with WAITING sets to max interval."""
        poller = AdaptivePoller(max_interval_ms=2000, default_interval_ms=500)

        new_interval = poller.on_state_change("session-1", AttentionState.WAITING)

        assert new_interval == 2000
        assert poller.get_interval_ms("session-1") == 2000

    def test_on_state_change_working_sets_min(self):
        """on_state_change with WORKING sets to min interval."""
        poller = AdaptivePoller(min_interval_ms=100, default_interval_ms=500)

        new_interval = poller.on_state_change("session-1", AttentionState.WORKING)

        assert new_interval == 100
        assert poller.get_interval_ms("session-1") == 100

    def test_on_state_change_idle_sets_default(self):
        """on_state_change with IDLE sets to default interval."""
        poller = AdaptivePoller(
            min_interval_ms=100,
            max_interval_ms=2000,
            default_interval_ms=500,
        )

        # First change to WORKING (min)
        poller.on_state_change("session-1", AttentionState.WORKING)
        assert poller.get_interval_ms("session-1") == 100

        # Then change to IDLE (default)
        new_interval = poller.on_state_change("session-1", AttentionState.IDLE)

        assert new_interval == 500
        assert poller.get_interval_ms("session-1") == 500

    def test_reset_session_removes_interval(self):
        """reset_session removes stored interval."""
        poller = AdaptivePoller(default_interval_ms=500)

        poller.on_output("session-1", had_output=True)
        assert poller.get_interval_ms("session-1") == 250

        poller.reset_session("session-1")

        assert poller.get_interval_ms("session-1") == 500  # back to default

    def test_reset_session_safe_for_unknown(self):
        """reset_session is safe for unknown session."""
        poller = AdaptivePoller()

        # Should not raise
        poller.reset_session("unknown")

    def test_reset_all_clears_all_sessions(self):
        """reset_all clears all stored intervals."""
        poller = AdaptivePoller(default_interval_ms=500)

        poller.on_output("session-1", had_output=True)
        poller.on_output("session-2", had_output=True)
        poller.on_output("session-3", had_output=True)

        poller.reset_all()

        assert poller.get_interval_ms("session-1") == 500
        assert poller.get_interval_ms("session-2") == 500
        assert poller.get_interval_ms("session-3") == 500

    def test_session_intervals_property(self):
        """session_intervals returns copy of all intervals."""
        poller = AdaptivePoller(default_interval_ms=500)

        poller.on_output("session-1", had_output=True)  # 250
        poller.on_output("session-2", had_output=False)  # 750

        intervals = poller.session_intervals

        assert intervals == {"session-1": 250, "session-2": 750}

    def test_session_intervals_returns_copy(self):
        """session_intervals returns a copy, not the internal dict."""
        poller = AdaptivePoller()

        poller.on_output("session-1", had_output=True)

        intervals = poller.session_intervals
        intervals["session-2"] = 999

        # Internal dict should not be modified
        assert "session-2" not in poller.session_intervals

    def test_independent_sessions(self):
        """Sessions have independent intervals."""
        poller = AdaptivePoller(
            min_interval_ms=100,
            max_interval_ms=2000,
            default_interval_ms=500,
        )

        poller.on_output("session-1", had_output=True)  # 250
        poller.on_output("session-2", had_output=False)  # 750
        poller.on_state_change("session-3", AttentionState.WAITING)  # 2000

        assert poller.get_interval_ms("session-1") == 250
        assert poller.get_interval_ms("session-2") == 750
        assert poller.get_interval_ms("session-3") == 2000


class TestSessionMonitorAdaptivePolling:
    """Test SessionMonitor adaptive polling integration."""

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

    def test_monitor_has_adaptive_poller(self):
        """SessionMonitor has an AdaptivePoller."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        assert hasattr(monitor, "_adaptive_poller")
        assert isinstance(monitor._adaptive_poller, AdaptivePoller)

    def test_monitor_exposes_adaptive_poller(self):
        """SessionMonitor exposes adaptive_poller via property."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        assert monitor.adaptive_poller is monitor._adaptive_poller

    def test_adaptive_polling_disabled_by_default(self):
        """Adaptive polling is disabled by default."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        assert monitor.is_adaptive_polling_enabled is False

    def test_adaptive_polling_enabled_via_config(self):
        """Adaptive polling can be enabled via config."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        config = MonitorConfig(adaptive_polling_enabled=True)
        monitor = SessionMonitor(controller, spawner, config=config)

        assert monitor.is_adaptive_polling_enabled is True

    def test_adaptive_poller_uses_config_values(self):
        """AdaptivePoller uses config values."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        config = MonitorConfig(
            adaptive_min_interval_ms=50,
            adaptive_max_interval_ms=3000,
            adaptive_default_interval_ms=1000,
        )
        monitor = SessionMonitor(controller, spawner, config=config)

        poller = monitor.adaptive_poller
        assert poller.min_interval_ms == 50
        assert poller.max_interval_ms == 3000
        assert poller.default_interval_ms == 1000

    def test_get_session_poll_interval_without_adaptive(self):
        """get_session_poll_interval returns fixed interval when disabled."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        config = MonitorConfig(
            polling_interval_ms=1000,
            adaptive_polling_enabled=False,
        )
        monitor = SessionMonitor(controller, spawner, config=config)

        interval = monitor.get_session_poll_interval("session-1")

        assert interval == 1.0

    def test_get_session_poll_interval_with_adaptive(self):
        """get_session_poll_interval returns adaptive interval when enabled."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        config = MonitorConfig(
            polling_interval_ms=1000,
            adaptive_polling_enabled=True,
            adaptive_default_interval_ms=500,
        )
        monitor = SessionMonitor(controller, spawner, config=config)

        interval = monitor.get_session_poll_interval("session-1")

        assert interval == 0.5

    @pytest.mark.asyncio
    async def test_clear_session_resets_adaptive_poller(self):
        """clear_session resets adaptive poller for that session."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        config = MonitorConfig(
            adaptive_polling_enabled=True,
            adaptive_default_interval_ms=500,
        )
        monitor = SessionMonitor(controller, spawner, config=config)

        # Change the interval
        monitor._adaptive_poller.on_output("session-1", had_output=True)
        assert monitor._adaptive_poller.get_interval_ms("session-1") == 250

        # Clear the session
        await monitor.clear_session("session-1")

        # Should be back to default
        assert monitor._adaptive_poller.get_interval_ms("session-1") == 500

    @pytest.mark.asyncio
    async def test_clear_all_resets_adaptive_poller(self):
        """clear_all resets all adaptive poller intervals."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        config = MonitorConfig(
            adaptive_polling_enabled=True,
            adaptive_default_interval_ms=500,
        )
        monitor = SessionMonitor(controller, spawner, config=config)

        # Change intervals for multiple sessions
        monitor._adaptive_poller.on_output("session-1", had_output=True)
        monitor._adaptive_poller.on_output("session-2", had_output=True)

        # Clear all
        await monitor.clear_all()

        # All should be back to default
        assert monitor._adaptive_poller.get_interval_ms("session-1") == 500
        assert monitor._adaptive_poller.get_interval_ms("session-2") == 500

    @pytest.mark.asyncio
    async def test_poll_updates_adaptive_poller_on_output(self):
        """Poll updates adaptive poller when output detected.

        Note: When new output is detected:
        1. on_output(had_output=True) is called, decreasing interval
        2. Attention state detection runs
        3. If state changes (e.g., to WORKING), on_state_change is called

        So the final interval depends on both the output and state change.
        """
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        # Output that ends with shell prompt (detected as IDLE)
        # This way the state stays IDLE and doesn't trigger on_state_change
        mock_iterm_session.async_get_contents = AsyncMock(return_value="Some output\n$ ")
        controller.app.get_session_by_id = MagicMock(
            return_value=mock_iterm_session
        )

        config = MonitorConfig(
            adaptive_polling_enabled=True,
            adaptive_default_interval_ms=500,
        )
        monitor = SessionMonitor(controller, spawner, config=config)

        await monitor.poll_once()

        # Should have decreased interval (output was detected)
        # State stays IDLE so no state change adjustment
        assert monitor._adaptive_poller.get_interval_ms("session-1") == 250

    @pytest.mark.asyncio
    async def test_poll_updates_adaptive_poller_on_no_change(self):
        """Poll updates adaptive poller when no output change."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        # Output that ends with shell prompt (detected as IDLE, no state change)
        mock_iterm_session.async_get_contents = AsyncMock(return_value="Output\n$ ")
        controller.app.get_session_by_id = MagicMock(
            return_value=mock_iterm_session
        )

        config = MonitorConfig(
            adaptive_polling_enabled=True,
            adaptive_default_interval_ms=500,
            throttle_interval_ms=1,
        )
        monitor = SessionMonitor(controller, spawner, config=config)

        # First poll - new output, state stays IDLE
        await monitor.poll_once()
        assert monitor._adaptive_poller.get_interval_ms("session-1") == 250

        # Wait for throttle
        await asyncio.sleep(0.01)

        # Second poll - same output (cached)
        await monitor.poll_once()
        # Should have increased interval (no change)
        assert monitor._adaptive_poller.get_interval_ms("session-1") == 375  # 250 * 1.5

    @pytest.mark.asyncio
    async def test_poll_updates_adaptive_poller_on_state_change(self):
        """Poll updates adaptive poller when attention state changes."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        # Output that triggers WAITING state
        mock_iterm_session.async_get_contents = AsyncMock(
            return_value="Should I proceed?"
        )
        controller.app.get_session_by_id = MagicMock(
            return_value=mock_iterm_session
        )

        config = MonitorConfig(
            adaptive_polling_enabled=True,
            adaptive_min_interval_ms=100,
            adaptive_max_interval_ms=2000,
            adaptive_default_interval_ms=500,
        )
        monitor = SessionMonitor(controller, spawner, config=config)

        await monitor.poll_once()

        # Should be at max interval (WAITING state)
        assert monitor._adaptive_poller.get_interval_ms("session-1") == 2000

    @pytest.mark.asyncio
    async def test_poll_no_adaptive_update_when_disabled(self):
        """Poll does not update adaptive poller when disabled."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(return_value="New output")
        controller.app.get_session_by_id = MagicMock(
            return_value=mock_iterm_session
        )

        config = MonitorConfig(
            adaptive_polling_enabled=False,  # Disabled
            adaptive_default_interval_ms=500,
        )
        monitor = SessionMonitor(controller, spawner, config=config)

        await monitor.poll_once()

        # Should still be at default (not updated)
        assert monitor._adaptive_poller.get_interval_ms("session-1") == 500

    def test_config_includes_adaptive_settings(self):
        """MonitorConfig includes adaptive polling settings."""
        config = MonitorConfig()

        assert hasattr(config, "adaptive_polling_enabled")
        assert hasattr(config, "adaptive_min_interval_ms")
        assert hasattr(config, "adaptive_max_interval_ms")
        assert hasattr(config, "adaptive_default_interval_ms")

    def test_config_adaptive_defaults(self):
        """MonitorConfig has correct adaptive defaults."""
        config = MonitorConfig()

        assert config.adaptive_polling_enabled is False
        assert config.adaptive_min_interval_ms == 100
        assert config.adaptive_max_interval_ms == 2000
        assert config.adaptive_default_interval_ms == 500


class TestTruncateOutput:
    """Test truncate_output function for buffer size limiting."""

    def test_short_output_unchanged(self):
        """Output shorter than limit is returned unchanged."""
        from iterm_controller.session_monitor import truncate_output

        short_output = "Hello World"
        result = truncate_output(short_output, max_bytes=1000)

        assert result == short_output

    def test_exactly_at_limit_unchanged(self):
        """Output exactly at limit is returned unchanged."""
        from iterm_controller.session_monitor import truncate_output

        # 10 ASCII characters = 10 bytes
        output = "0123456789"
        result = truncate_output(output, max_bytes=10)

        assert result == output

    def test_output_over_limit_truncated(self):
        """Output over limit is truncated from the beginning."""
        from iterm_controller.session_monitor import truncate_output

        output = "AAAA" + "BBBB"  # 8 bytes total
        result = truncate_output(output, max_bytes=4)

        # Should keep the end (most recent output)
        assert result == "BBBB"

    def test_truncation_preserves_end(self):
        """Truncation preserves the end of the output (most recent)."""
        from iterm_controller.session_monitor import truncate_output

        output = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        result = truncate_output(output, max_bytes=20)

        # Should keep the end, most recent lines
        assert "Line 5" in result

    def test_truncation_tries_to_start_at_newline(self):
        """Truncation tries to start at a newline for cleaner output."""
        from iterm_controller.session_monitor import truncate_output

        # Create output where truncation point is in middle of a line
        output = "X" * 10 + "\nLine after newline"
        result = truncate_output(output, max_bytes=25)

        # Should try to start at newline if it's in the first quarter
        # The exact behavior depends on where the newline falls
        assert len(result.encode("utf-8")) <= 25

    def test_handles_multibyte_characters(self):
        """Truncation handles multi-byte UTF-8 characters correctly."""
        from iterm_controller.session_monitor import truncate_output

        # Each emoji is 4 bytes in UTF-8
        output = "🎉🎊🎈🎁"  # 16 bytes
        result = truncate_output(output, max_bytes=8)

        # Should have 2 emojis (8 bytes)
        assert len(result.encode("utf-8")) <= 8
        # Should not have broken characters
        result.encode("utf-8")  # Should not raise

    def test_handles_incomplete_utf8_at_boundary(self):
        """Truncation handles incomplete UTF-8 sequences at truncation point."""
        from iterm_controller.session_monitor import truncate_output

        # Mix of ASCII and multi-byte to create potential boundary issues
        output = "AAA" + "日本語" + "BBB"
        result = truncate_output(output, max_bytes=10)

        # Should be valid UTF-8 regardless of where truncation happens
        result.encode("utf-8")  # Should not raise
        assert len(result.encode("utf-8")) <= 10

    def test_empty_output(self):
        """Empty output returns empty string."""
        from iterm_controller.session_monitor import truncate_output

        result = truncate_output("", max_bytes=100)

        assert result == ""

    def test_default_max_bytes(self):
        """Default max_bytes is MAX_OUTPUT_BUFFER_BYTES."""
        from iterm_controller.session_monitor import (
            MAX_OUTPUT_BUFFER_BYTES,
            truncate_output,
        )

        # Short output should be unchanged with default
        short_output = "Hello"
        result = truncate_output(short_output)
        assert result == short_output

        # Large output should be truncated with default
        large_output = "X" * (MAX_OUTPUT_BUFFER_BYTES + 1000)
        result = truncate_output(large_output)
        assert len(result.encode("utf-8")) <= MAX_OUTPUT_BUFFER_BYTES


class TestOutputProcessorBufferLimit:
    """Test OutputProcessor buffer size limiting."""

    def test_default_buffer_limit(self):
        """OutputProcessor uses MAX_OUTPUT_BUFFER_BYTES by default."""
        from iterm_controller.session_monitor import (
            MAX_OUTPUT_BUFFER_BYTES,
            OutputProcessor,
        )

        processor = OutputProcessor()
        assert processor._max_buffer_bytes == MAX_OUTPUT_BUFFER_BYTES

    def test_custom_buffer_limit(self):
        """OutputProcessor accepts custom buffer limit."""
        processor = OutputProcessor(max_buffer_bytes=1000)
        assert processor._max_buffer_bytes == 1000

    def test_stored_output_truncated(self):
        """Stored output is truncated to buffer limit."""
        processor = OutputProcessor(max_buffer_bytes=50)

        # First call stores truncated output
        large_output = "X" * 100
        processor.extract_new_output("session-1", large_output)

        # Check stored output is truncated
        stored = processor._last_output.get("session-1")
        assert stored is not None
        assert len(stored.encode("utf-8")) <= 50

    def test_new_output_returned_unchanged(self):
        """New output in change result is unchanged (for processing)."""
        processor = OutputProcessor(max_buffer_bytes=50)

        # Large output
        large_output = "X" * 100
        change = processor.extract_new_output("session-1", large_output)

        # The new_output field should have the full output for processing
        # (attention detection needs full output)
        assert change.new_output == large_output

    def test_multiple_updates_respect_limit(self):
        """Multiple updates continue to respect buffer limit."""
        processor = OutputProcessor(max_buffer_bytes=100)

        for i in range(10):
            output = f"Output batch {i}: " + "X" * 50
            processor.extract_new_output("session-1", output)

        # Stored output should stay within limit
        stored = processor._last_output.get("session-1")
        assert len(stored.encode("utf-8")) <= 100


class TestMonitorConfigBufferLimit:
    """Test MonitorConfig buffer limit setting."""

    def test_default_buffer_limit(self):
        """MonitorConfig has correct default buffer limit."""
        from iterm_controller.session_monitor import MAX_OUTPUT_BUFFER_BYTES

        config = MonitorConfig()
        assert config.max_output_buffer_bytes == MAX_OUTPUT_BUFFER_BYTES

    def test_custom_buffer_limit(self):
        """MonitorConfig accepts custom buffer limit."""
        config = MonitorConfig(max_output_buffer_bytes=50000)
        assert config.max_output_buffer_bytes == 50000


class TestSessionMonitorBufferLimit:
    """Test SessionMonitor buffer limiting integration."""

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

    def test_monitor_uses_config_buffer_limit(self):
        """SessionMonitor passes buffer limit to OutputProcessor."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        config = MonitorConfig(max_output_buffer_bytes=5000)

        monitor = SessionMonitor(controller, spawner, config=config)

        assert monitor._processor._max_buffer_bytes == 5000

    @pytest.mark.asyncio
    async def test_poll_truncates_session_last_output(self):
        """Poll truncates session.last_output to buffer limit."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        # Create large output
        large_output = "X" * 1000

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(return_value=large_output)
        controller.app.get_session_by_id = MagicMock(
            return_value=mock_iterm_session
        )

        config = MonitorConfig(max_output_buffer_bytes=100)
        monitor = SessionMonitor(controller, spawner, config=config)

        await monitor.poll_once()

        # session.last_output should be truncated
        assert len(session.last_output.encode("utf-8")) <= 100

    @pytest.mark.asyncio
    async def test_poll_truncates_preserves_recent_output(self):
        """Poll truncation preserves the most recent output."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        # Create output with identifiable recent portion
        old_output = "A" * 500
        recent_output = "RECENT_OUTPUT_HERE"
        combined = old_output + recent_output

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(return_value=combined)
        controller.app.get_session_by_id = MagicMock(
            return_value=mock_iterm_session
        )

        config = MonitorConfig(max_output_buffer_bytes=100)
        monitor = SessionMonitor(controller, spawner, config=config)

        await monitor.poll_once()

        # Recent output should be preserved in truncated result
        assert "RECENT_OUTPUT_HERE" in session.last_output


class TestMaxOutputBufferConstant:
    """Test MAX_OUTPUT_BUFFER_BYTES constant."""

    def test_constant_value(self):
        """MAX_OUTPUT_BUFFER_BYTES is 100KB."""
        from iterm_controller.session_monitor import MAX_OUTPUT_BUFFER_BYTES

        assert MAX_OUTPUT_BUFFER_BYTES == 100 * 1024  # 100KB

    def test_constant_is_reasonable(self):
        """MAX_OUTPUT_BUFFER_BYTES is a reasonable size."""
        from iterm_controller.session_monitor import MAX_OUTPUT_BUFFER_BYTES

        # Should be at least 10KB for useful output
        assert MAX_OUTPUT_BUFFER_BYTES >= 10 * 1024
        # Should be at most 1MB to prevent memory issues
        assert MAX_OUTPUT_BUFFER_BYTES <= 1024 * 1024


# =============================================================================
# Output Streaming Tests
# =============================================================================


class TestSessionOutputStream:
    """Test SessionOutputStream functionality."""

    def test_init(self):
        """Stream initializes with correct parameters."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1", max_buffer_lines=50, batch_interval_ms=200)

        assert stream.session_id == "session-1"
        assert stream.max_buffer_lines == 50
        assert stream._batch_interval_seconds == 0.2

    def test_init_defaults(self):
        """Stream initializes with correct defaults."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1")

        assert stream.max_buffer_lines == 100
        assert stream._batch_interval_seconds == 0.1

    @pytest.mark.asyncio
    async def test_push_output_adds_to_buffer(self):
        """push_output adds lines to buffer."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1")

        await stream.push_output("Line 1\nLine 2\nLine 3")

        buffer = stream.get_full_buffer()
        assert "Line 1" in buffer
        assert "Line 2" in buffer
        assert "Line 3" in buffer

    @pytest.mark.asyncio
    async def test_push_output_empty_does_nothing(self):
        """push_output with empty string does nothing."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1")

        await stream.push_output("")

        assert len(stream.get_full_buffer()) == 0

    @pytest.mark.asyncio
    async def test_buffer_respects_max_lines(self):
        """Buffer respects max_buffer_lines limit."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1", max_buffer_lines=5)

        # Push more lines than the limit
        for i in range(10):
            await stream.push_output(f"Line {i}")

        buffer = stream.get_full_buffer()
        # Should only have the last 5 lines
        assert len(buffer) == 5
        assert "Line 9" in buffer
        assert "Line 0" not in buffer

    @pytest.mark.asyncio
    async def test_subscribe_and_notify(self):
        """Subscribers are notified of output."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1", batch_interval_ms=1)
        received = []

        async def callback(output):
            received.append(output)

        stream.subscribe(callback)
        await stream.push_output("Hello")

        # Wait for flush
        await asyncio.sleep(0.1)

        assert len(received) > 0
        assert "Hello" in "".join(received)

    @pytest.mark.asyncio
    async def test_unsubscribe_stops_notifications(self):
        """Unsubscribed callbacks are not called."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1", batch_interval_ms=1)
        received = []

        async def callback(output):
            received.append(output)

        stream.subscribe(callback)
        stream.unsubscribe(callback)

        await stream.push_output("Hello")
        await asyncio.sleep(0.1)

        assert len(received) == 0

    def test_subscriber_count(self):
        """subscriber_count returns correct count."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1")

        async def callback1(output):
            pass

        async def callback2(output):
            pass

        assert stream.subscriber_count == 0

        stream.subscribe(callback1)
        assert stream.subscriber_count == 1

        stream.subscribe(callback2)
        assert stream.subscriber_count == 2

        stream.unsubscribe(callback1)
        assert stream.subscriber_count == 1

    def test_has_subscribers(self):
        """has_subscribers returns correct value."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1")

        async def callback(output):
            pass

        assert stream.has_subscribers is False

        stream.subscribe(callback)
        assert stream.has_subscribers is True

        stream.unsubscribe(callback)
        assert stream.has_subscribers is False

    @pytest.mark.asyncio
    async def test_get_recent_output(self):
        """get_recent_output returns specified number of lines."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1")

        for i in range(10):
            await stream.push_output(f"Line {i}")

        recent = stream.get_recent_output(3)
        assert len(recent) == 3
        assert recent[-1] == "Line 9"

    @pytest.mark.asyncio
    async def test_get_buffer_as_string(self):
        """get_buffer_as_string returns buffer as joined string."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1")

        await stream.push_output("Line 1\nLine 2\nLine 3")

        result = stream.get_buffer_as_string()
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    @pytest.mark.asyncio
    async def test_get_buffer_as_string_with_limit(self):
        """get_buffer_as_string with limit returns limited lines."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1")

        for i in range(10):
            await stream.push_output(f"Line {i}")

        result = stream.get_buffer_as_string(lines=3)
        assert "Line 9" in result
        assert "Line 0" not in result

    def test_clear(self):
        """clear empties the buffer."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1")

        # Need to run async in sync context
        asyncio.get_event_loop().run_until_complete(stream.push_output("Hello"))

        stream.clear()

        assert len(stream.get_full_buffer()) == 0

    @pytest.mark.asyncio
    async def test_close(self):
        """close cleans up and clears subscribers."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1")

        async def callback(output):
            pass

        stream.subscribe(callback)
        await stream.push_output("Hello")

        await stream.close()

        assert stream.subscriber_count == 0
        assert len(stream.get_full_buffer()) == 0


class TestOutputStreamManager:
    """Test OutputStreamManager functionality."""

    def test_init(self):
        """Manager initializes with correct parameters."""
        from iterm_controller.session_monitor import OutputStreamManager

        manager = OutputStreamManager(default_buffer_lines=50, batch_interval_ms=200)

        assert manager._default_buffer_lines == 50
        assert manager._batch_interval_ms == 200

    def test_init_defaults(self):
        """Manager initializes with correct defaults."""
        from iterm_controller.session_monitor import OutputStreamManager

        manager = OutputStreamManager()

        assert manager._default_buffer_lines == 100
        assert manager._batch_interval_ms == 100

    def test_get_stream_creates_new(self):
        """get_stream creates a new stream if none exists."""
        from iterm_controller.session_monitor import OutputStreamManager, SessionOutputStream

        manager = OutputStreamManager()

        stream = manager.get_stream("session-1")

        assert isinstance(stream, SessionOutputStream)
        assert stream.session_id == "session-1"

    def test_get_stream_returns_existing(self):
        """get_stream returns existing stream."""
        from iterm_controller.session_monitor import OutputStreamManager

        manager = OutputStreamManager()

        stream1 = manager.get_stream("session-1")
        stream2 = manager.get_stream("session-1")

        assert stream1 is stream2

    def test_has_stream(self):
        """has_stream returns correct value."""
        from iterm_controller.session_monitor import OutputStreamManager

        manager = OutputStreamManager()

        assert manager.has_stream("session-1") is False

        manager.get_stream("session-1")

        assert manager.has_stream("session-1") is True

    @pytest.mark.asyncio
    async def test_remove_stream(self):
        """remove_stream closes and removes stream."""
        from iterm_controller.session_monitor import OutputStreamManager

        manager = OutputStreamManager()

        manager.get_stream("session-1")
        assert manager.has_stream("session-1") is True

        await manager.remove_stream("session-1")

        assert manager.has_stream("session-1") is False

    @pytest.mark.asyncio
    async def test_push_output(self):
        """push_output creates stream and pushes output."""
        from iterm_controller.session_monitor import OutputStreamManager

        manager = OutputStreamManager()

        await manager.push_output("session-1", "Hello")

        stream = manager.get_stream("session-1")
        assert "Hello" in stream.get_full_buffer()

    def test_subscribe(self):
        """subscribe adds callback to stream."""
        from iterm_controller.session_monitor import OutputStreamManager

        manager = OutputStreamManager()

        async def callback(output):
            pass

        manager.subscribe("session-1", callback)

        assert manager.has_subscribers("session-1") is True

    def test_unsubscribe(self):
        """unsubscribe removes callback from stream."""
        from iterm_controller.session_monitor import OutputStreamManager

        manager = OutputStreamManager()

        async def callback(output):
            pass

        manager.subscribe("session-1", callback)
        manager.unsubscribe("session-1", callback)

        assert manager.has_subscribers("session-1") is False

    def test_get_recent_output(self):
        """get_recent_output returns output from stream."""
        from iterm_controller.session_monitor import OutputStreamManager

        manager = OutputStreamManager()

        # Empty for non-existent stream
        assert manager.get_recent_output("nonexistent") == []

        asyncio.get_event_loop().run_until_complete(
            manager.push_output("session-1", "Hello")
        )

        recent = manager.get_recent_output("session-1")
        assert "Hello" in recent

    @pytest.mark.asyncio
    async def test_clear_all(self):
        """clear_all removes all streams."""
        from iterm_controller.session_monitor import OutputStreamManager

        manager = OutputStreamManager()

        manager.get_stream("session-1")
        manager.get_stream("session-2")

        await manager.clear_all()

        assert manager.active_streams == []

    def test_active_streams(self):
        """active_streams returns list of session IDs."""
        from iterm_controller.session_monitor import OutputStreamManager

        manager = OutputStreamManager()

        manager.get_stream("session-1")
        manager.get_stream("session-2")

        active = manager.active_streams

        assert "session-1" in active
        assert "session-2" in active


class TestSessionMonitorOutputStreaming:
    """Test SessionMonitor output streaming integration."""

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

    def test_monitor_has_stream_manager(self):
        """SessionMonitor has an OutputStreamManager."""
        from iterm_controller.session_monitor import OutputStreamManager

        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        assert hasattr(monitor, "_stream_manager")
        assert isinstance(monitor._stream_manager, OutputStreamManager)

    def test_monitor_exposes_stream_manager(self):
        """SessionMonitor exposes stream_manager via property."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        assert monitor.stream_manager is monitor._stream_manager

    def test_streaming_enabled_by_default(self):
        """Streaming is enabled by default."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        assert monitor.is_streaming_enabled is True

    def test_streaming_can_be_disabled(self):
        """Streaming can be disabled via config."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        config = MonitorConfig(streaming_enabled=False)
        monitor = SessionMonitor(controller, spawner, config=config)

        assert monitor.is_streaming_enabled is False

    def test_config_includes_streaming_settings(self):
        """MonitorConfig includes streaming settings."""
        config = MonitorConfig()

        assert hasattr(config, "streaming_enabled")
        assert hasattr(config, "streaming_buffer_lines")
        assert hasattr(config, "streaming_batch_interval_ms")

    def test_config_streaming_defaults(self):
        """MonitorConfig has correct streaming defaults."""
        config = MonitorConfig()

        assert config.streaming_enabled is True
        assert config.streaming_buffer_lines == 100
        assert config.streaming_batch_interval_ms == 100

    def test_subscribe_output(self):
        """subscribe_output adds callback to stream."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        async def callback(output):
            pass

        monitor.subscribe_output("session-1", callback)

        assert monitor.has_output_subscribers("session-1") is True

    def test_unsubscribe_output(self):
        """unsubscribe_output removes callback from stream."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        async def callback(output):
            pass

        monitor.subscribe_output("session-1", callback)
        monitor.unsubscribe_output("session-1", callback)

        assert monitor.has_output_subscribers("session-1") is False

    def test_get_output_stream(self):
        """get_output_stream returns stream for session."""
        from iterm_controller.session_monitor import SessionOutputStream

        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        stream = monitor.get_output_stream("session-1")

        assert isinstance(stream, SessionOutputStream)
        assert stream.session_id == "session-1"

    def test_get_recent_output(self):
        """get_recent_output returns output from stream."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        # Empty for new session
        recent = monitor.get_recent_output("session-1")
        assert recent == []

    @pytest.mark.asyncio
    async def test_poll_streams_output_when_enabled(self):
        """Poll streams output when streaming is enabled."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(return_value="New output")
        controller.app.get_session_by_id = MagicMock(
            return_value=mock_iterm_session
        )

        config = MonitorConfig(streaming_enabled=True, streaming_batch_interval_ms=1)
        monitor = SessionMonitor(controller, spawner, config=config)

        received = []

        async def callback(output):
            received.append(output)

        monitor.subscribe_output("session-1", callback)
        await monitor.poll_once()

        # Wait for flush
        await asyncio.sleep(0.1)

        assert len(received) > 0
        assert "New output" in "".join(received)

    @pytest.mark.asyncio
    async def test_poll_does_not_stream_when_disabled(self):
        """Poll does not stream output when streaming is disabled."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(return_value="New output")
        controller.app.get_session_by_id = MagicMock(
            return_value=mock_iterm_session
        )

        config = MonitorConfig(streaming_enabled=False)
        monitor = SessionMonitor(controller, spawner, config=config)

        received = []

        async def callback(output):
            received.append(output)

        monitor.subscribe_output("session-1", callback)
        await monitor.poll_once()
        await asyncio.sleep(0.1)

        # No output because streaming is disabled
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_on_output_stream_callback_invoked(self):
        """on_output_stream callback is invoked with streaming."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(return_value="New output")
        controller.app.get_session_by_id = MagicMock(
            return_value=mock_iterm_session
        )

        received = []

        async def on_stream(session_id, output):
            received.append((session_id, output))

        config = MonitorConfig(streaming_enabled=True)
        monitor = SessionMonitor(
            controller, spawner, config=config, on_output_stream=on_stream
        )

        await monitor.poll_once()

        assert len(received) == 1
        assert received[0][0] == "session-1"
        assert received[0][1] == "New output"

    @pytest.mark.asyncio
    async def test_clear_session_removes_stream(self):
        """clear_session removes output stream for that session."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        # Create a stream
        monitor.get_output_stream("session-1")
        assert monitor._stream_manager.has_stream("session-1") is True

        await monitor.clear_session("session-1")

        assert monitor._stream_manager.has_stream("session-1") is False

    @pytest.mark.asyncio
    async def test_clear_all_removes_all_streams(self):
        """clear_all removes all output streams."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        # Create streams
        monitor.get_output_stream("session-1")
        monitor.get_output_stream("session-2")

        await monitor.clear_all()

        assert monitor._stream_manager.active_streams == []

    @pytest.mark.asyncio
    async def test_stop_clears_streams(self):
        """stop clears all output streams."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        # Create streams
        monitor.get_output_stream("session-1")
        monitor.get_output_stream("session-2")

        await monitor.start()
        await monitor.stop()

        assert monitor._stream_manager.active_streams == []


class TestSessionOutputUpdatedEvent:
    """Test SessionOutputUpdated event message."""

    def test_event_creation(self):
        """SessionOutputUpdated can be created."""
        from iterm_controller.state.events import SessionOutputUpdated

        event = SessionOutputUpdated("session-1", "New output")

        assert event.session_id == "session-1"
        assert event.output == "New output"

    def test_event_in_state_events(self):
        """SessionOutputUpdated is exported from state module."""
        from iterm_controller.state import SessionOutputUpdated

        event = SessionOutputUpdated("session-1", "output")
        assert event.session_id == "session-1"

    def test_state_event_enum_has_session_output_updated(self):
        """StateEvent enum has SESSION_OUTPUT_UPDATED."""
        from iterm_controller.state.events import StateEvent

        assert hasattr(StateEvent, "SESSION_OUTPUT_UPDATED")
        assert StateEvent.SESSION_OUTPUT_UPDATED.value == "session_output_updated"


# =============================================================================
# Integration Tests for Output Streaming
# =============================================================================


class TestOutputStreamingIntegration:
    """Integration tests for the output streaming subscriber pattern and buffer management."""

    # =========================================================================
    # Buffer Management Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_rolling_buffer_drops_oldest_lines(self):
        """Rolling buffer drops oldest lines when full."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1", max_buffer_lines=5)

        # Push 10 lines, buffer should only keep last 5
        for i in range(10):
            await stream.push_output(f"Line {i}\n")

        buffer = stream.get_full_buffer()

        # Buffer should contain only the last 5 lines
        # Note: each push_output splits by \n, so we get "Line X" and "" entries
        assert "Line 0" not in buffer
        assert "Line 9" in buffer or "Line 9\n" in "".join(buffer)

    @pytest.mark.asyncio
    async def test_buffer_preserves_ansi_escape_codes(self):
        """Buffer preserves ANSI escape codes for colors."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1")

        # Common ANSI codes
        red_text = "\033[31mRed text\033[0m"
        green_text = "\033[32mGreen text\033[0m"
        bold_text = "\033[1mBold text\033[0m"

        await stream.push_output(red_text)
        await stream.push_output(green_text)
        await stream.push_output(bold_text)

        buffer_content = stream.get_buffer_as_string()

        # ANSI codes should be preserved
        assert "\033[31m" in buffer_content  # Red
        assert "\033[32m" in buffer_content  # Green
        assert "\033[1m" in buffer_content   # Bold
        assert "\033[0m" in buffer_content   # Reset

    @pytest.mark.asyncio
    async def test_buffer_handles_multiline_output_correctly(self):
        """Buffer correctly handles multiline output."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1", max_buffer_lines=100)

        multiline = "Line 1\nLine 2\nLine 3\nLine 4"
        await stream.push_output(multiline)

        buffer = stream.get_full_buffer()

        # All lines should be present
        assert "Line 1" in buffer
        assert "Line 2" in buffer
        assert "Line 3" in buffer
        assert "Line 4" in buffer

    @pytest.mark.asyncio
    async def test_buffer_truncation_at_limit(self):
        """Buffer truncation happens at exactly the limit."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1", max_buffer_lines=3)

        await stream.push_output("A")
        await stream.push_output("B")
        await stream.push_output("C")

        assert len(stream.get_full_buffer()) == 3

        await stream.push_output("D")

        buffer = stream.get_full_buffer()
        assert len(buffer) == 3
        # First item should have been dropped
        assert "A" not in buffer
        assert "D" in buffer

    # =========================================================================
    # Batching Behavior Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_batching_combines_rapid_updates(self):
        """Rapid updates are batched together."""
        from iterm_controller.session_monitor import SessionOutputStream

        # Use longer batch interval to test batching
        stream = SessionOutputStream("session-1", batch_interval_ms=500)

        received = []

        async def callback(output):
            received.append(output)

        stream.subscribe(callback)

        # Push multiple outputs rapidly
        await stream.push_output("A")
        await stream.push_output("B")
        await stream.push_output("C")

        # Wait for batch to flush
        await asyncio.sleep(0.6)

        # Should receive batched output (fewer calls than individual pushes)
        assert len(received) <= 3
        combined = "".join(received)
        assert "A" in combined
        assert "B" in combined
        assert "C" in combined

    @pytest.mark.asyncio
    async def test_immediate_flush_on_first_output(self):
        """First output flushes immediately (no prior flush time)."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1", batch_interval_ms=1000)

        received = []

        async def callback(output):
            received.append(output)

        stream.subscribe(callback)

        await stream.push_output("First output")

        # Should flush immediately since no prior flush
        assert len(received) == 1
        assert received[0] == "First output"

    @pytest.mark.asyncio
    async def test_delayed_flush_for_subsequent_output(self):
        """Subsequent output is delayed for batching."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1", batch_interval_ms=200)

        received = []

        async def callback(output):
            received.append(output)

        stream.subscribe(callback)

        # First output flushes immediately
        await stream.push_output("First")
        assert len(received) == 1

        # Second output should be batched (within interval)
        await stream.push_output("Second")
        # Immediate check - should still be 1
        assert len(received) == 1

        # Wait for delayed flush
        await asyncio.sleep(0.3)
        assert len(received) == 2
        assert "Second" in received[1]

    # =========================================================================
    # Multiple Subscriber Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_multiple_subscribers_receive_output(self):
        """Multiple subscribers all receive the same output."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1", batch_interval_ms=1)

        received1 = []
        received2 = []
        received3 = []

        async def callback1(output):
            received1.append(output)

        async def callback2(output):
            received2.append(output)

        async def callback3(output):
            received3.append(output)

        stream.subscribe(callback1)
        stream.subscribe(callback2)
        stream.subscribe(callback3)

        await stream.push_output("Broadcast message")
        await asyncio.sleep(0.05)

        # All subscribers should receive the message
        assert "Broadcast message" in "".join(received1)
        assert "Broadcast message" in "".join(received2)
        assert "Broadcast message" in "".join(received3)

    @pytest.mark.asyncio
    async def test_subscriber_added_mid_stream(self):
        """Subscriber added mid-stream receives only new output."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1", batch_interval_ms=1)

        received = []

        async def callback(output):
            received.append(output)

        # Push output before subscribing
        await stream.push_output("Before subscribe")
        await asyncio.sleep(0.05)

        # Subscribe now
        stream.subscribe(callback)

        # Push output after subscribing
        await stream.push_output("After subscribe")
        await asyncio.sleep(0.05)

        # Should only receive output after subscription
        combined = "".join(received)
        assert "Before subscribe" not in combined
        assert "After subscribe" in combined

    @pytest.mark.asyncio
    async def test_subscriber_can_access_buffer_on_subscribe(self):
        """Subscriber can access buffer to get historical output."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1", batch_interval_ms=1)

        # Push output before subscribing
        await stream.push_output("Historical line 1")
        await stream.push_output("Historical line 2")
        await asyncio.sleep(0.05)

        received = []

        async def callback(output):
            received.append(output)

        # Subscribe and get historical data
        stream.subscribe(callback)
        historical = stream.get_full_buffer()

        # Historical data available
        assert "Historical line 1" in historical
        assert "Historical line 2" in historical

    @pytest.mark.asyncio
    async def test_unsubscribe_one_keeps_others(self):
        """Unsubscribing one callback keeps others active."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1", batch_interval_ms=1)

        received1 = []
        received2 = []

        async def callback1(output):
            received1.append(output)

        async def callback2(output):
            received2.append(output)

        stream.subscribe(callback1)
        stream.subscribe(callback2)

        await stream.push_output("First")
        await asyncio.sleep(0.05)

        # Unsubscribe callback1
        stream.unsubscribe(callback1)

        await stream.push_output("Second")
        await asyncio.sleep(0.05)

        # callback2 should still receive
        assert "First" in "".join(received2)
        assert "Second" in "".join(received2)

        # callback1 should only have first
        assert "First" in "".join(received1)
        assert "Second" not in "".join(received1)

    # =========================================================================
    # Concurrent Sessions Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_concurrent_sessions_independent_streams(self):
        """Multiple sessions have independent output streams."""
        from iterm_controller.session_monitor import OutputStreamManager

        manager = OutputStreamManager(batch_interval_ms=1)

        received1 = []
        received2 = []

        async def callback1(output):
            received1.append(output)

        async def callback2(output):
            received2.append(output)

        manager.subscribe("session-1", callback1)
        manager.subscribe("session-2", callback2)

        await manager.push_output("session-1", "Output for session 1")
        await manager.push_output("session-2", "Output for session 2")
        await asyncio.sleep(0.05)

        # Each session should only receive its own output
        assert "Output for session 1" in "".join(received1)
        assert "Output for session 2" not in "".join(received1)

        assert "Output for session 2" in "".join(received2)
        assert "Output for session 1" not in "".join(received2)

    @pytest.mark.asyncio
    async def test_concurrent_push_to_multiple_sessions(self):
        """Concurrent pushes to multiple sessions work correctly."""
        from iterm_controller.session_monitor import OutputStreamManager

        manager = OutputStreamManager(batch_interval_ms=1)

        received = {f"session-{i}": [] for i in range(5)}

        # Create callbacks using closures with default argument capture
        def make_callback(sid):
            async def callback(output):
                received[sid].append(output)
            return callback

        for i in range(5):
            session_id = f"session-{i}"
            manager.subscribe(session_id, make_callback(session_id))

        # Push to all sessions concurrently
        await asyncio.gather(*[
            manager.push_output(f"session-{i}", f"Output {i}")
            for i in range(5)
        ])

        await asyncio.sleep(0.1)

        # Each session should have received its output
        for i in range(5):
            assert len(received[f"session-{i}"]) > 0

    @pytest.mark.asyncio
    async def test_remove_one_session_keeps_others(self):
        """Removing one session's stream keeps others intact."""
        from iterm_controller.session_monitor import OutputStreamManager

        manager = OutputStreamManager(batch_interval_ms=1)

        manager.get_stream("session-1")
        manager.get_stream("session-2")
        manager.get_stream("session-3")

        await manager.remove_stream("session-2")

        assert manager.has_stream("session-1")
        assert not manager.has_stream("session-2")
        assert manager.has_stream("session-3")

    # =========================================================================
    # Error Handling Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_subscriber_exception_doesnt_break_others(self):
        """Exception in one subscriber doesn't affect others."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1", batch_interval_ms=1)

        received = []

        async def bad_callback(output):
            raise ValueError("Subscriber error")

        async def good_callback(output):
            received.append(output)

        stream.subscribe(bad_callback)
        stream.subscribe(good_callback)

        # Should not raise
        await stream.push_output("Test output")
        await asyncio.sleep(0.05)

        # Good callback should still receive output
        assert "Test output" in "".join(received)

    @pytest.mark.asyncio
    async def test_subscriber_exception_logged(self):
        """Exceptions in subscribers are logged."""
        from iterm_controller.session_monitor import SessionOutputStream
        import logging

        stream = SessionOutputStream("session-1", batch_interval_ms=1)

        async def bad_callback(output):
            raise ValueError("Test error")

        stream.subscribe(bad_callback)

        # Capture logs
        with patch("iterm_controller.session_monitor.logger") as mock_logger:
            await stream.push_output("Test")
            await asyncio.sleep(0.05)

            # Warning should have been logged
            assert mock_logger.warning.called

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_callback_safe(self):
        """Unsubscribing a callback that was never subscribed is safe."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1")

        async def never_subscribed(output):
            pass

        # Should not raise
        stream.unsubscribe(never_subscribed)

    @pytest.mark.asyncio
    async def test_push_to_closed_stream_safe(self):
        """Pushing to a closed stream doesn't raise."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1")

        await stream.close()

        # Should not raise
        await stream.push_output("After close")

    # =========================================================================
    # Session Monitor Integration Tests
    # =========================================================================

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

    @pytest.mark.asyncio
    async def test_monitor_streams_to_multiple_subscribers(self):
        """SessionMonitor streams output to multiple subscribers."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(return_value="Test output")
        controller.app.get_session_by_id = MagicMock(
            return_value=mock_iterm_session
        )

        config = MonitorConfig(streaming_enabled=True, streaming_batch_interval_ms=1)
        monitor = SessionMonitor(controller, spawner, config=config)

        received1 = []
        received2 = []

        async def callback1(output):
            received1.append(output)

        async def callback2(output):
            received2.append(output)

        monitor.subscribe_output("session-1", callback1)
        monitor.subscribe_output("session-1", callback2)

        await monitor.poll_once()
        await asyncio.sleep(0.1)

        # Both subscribers should receive output
        assert len(received1) > 0
        assert len(received2) > 0

    @pytest.mark.asyncio
    async def test_monitor_incremental_output(self):
        """SessionMonitor streams only new output incrementally."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        # Simulate output that grows
        call_count = 0
        outputs = ["Line 1", "Line 1\nLine 2", "Line 1\nLine 2\nLine 3"]

        async def mock_get_contents(*args, **kwargs):
            nonlocal call_count
            result = outputs[min(call_count, len(outputs) - 1)]
            call_count += 1
            return result

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(side_effect=mock_get_contents)
        controller.app.get_session_by_id = MagicMock(
            return_value=mock_iterm_session
        )

        config = MonitorConfig(
            streaming_enabled=True,
            streaming_batch_interval_ms=1,
            throttle_interval_ms=1,
        )
        monitor = SessionMonitor(controller, spawner, config=config)

        received = []

        async def callback(output):
            received.append(output)

        monitor.subscribe_output("session-1", callback)

        # Poll multiple times
        await monitor.poll_once()
        await asyncio.sleep(0.05)

        await monitor.poll_once()
        await asyncio.sleep(0.05)

        await monitor.poll_once()
        await asyncio.sleep(0.05)

        # Should have received output for each poll
        assert len(received) >= 1

    @pytest.mark.asyncio
    async def test_monitor_buffer_available_after_unsubscribe(self):
        """Buffer remains available after unsubscribing."""
        controller = self.make_mock_controller()

        session = self.make_session("session-1")
        spawner = self.make_mock_spawner({"session-1": session})

        mock_iterm_session = MagicMock()
        mock_iterm_session.async_get_contents = AsyncMock(return_value="Buffered output")
        controller.app.get_session_by_id = MagicMock(
            return_value=mock_iterm_session
        )

        config = MonitorConfig(streaming_enabled=True, streaming_batch_interval_ms=1)
        monitor = SessionMonitor(controller, spawner, config=config)

        async def callback(output):
            pass

        monitor.subscribe_output("session-1", callback)
        await monitor.poll_once()
        await asyncio.sleep(0.05)

        monitor.unsubscribe_output("session-1", callback)

        # Buffer should still be available
        recent = monitor.get_recent_output("session-1")
        assert "Buffered output" in recent or len(recent) > 0

    @pytest.mark.asyncio
    async def test_monitor_output_stream_callback(self):
        """Monitor invokes on_output_stream callback correctly."""
        controller = self.make_mock_controller()

        sessions = {
            f"session-{i}": self.make_session(f"session-{i}")
            for i in range(3)
        }
        spawner = self.make_mock_spawner(sessions)

        outputs = {
            "session-0": "Output 0",
            "session-1": "Output 1",
            "session-2": "Output 2",
        }

        def make_mock_iterm_session(session_id):
            mock = MagicMock()
            mock.async_get_contents = AsyncMock(return_value=outputs[session_id])
            return mock

        def get_session(session_id):
            return make_mock_iterm_session(session_id)

        controller.app.get_session_by_id = MagicMock(side_effect=get_session)

        received = []

        async def on_stream(session_id, output):
            received.append((session_id, output))

        config = MonitorConfig(streaming_enabled=True)
        monitor = SessionMonitor(
            controller, spawner, config=config, on_output_stream=on_stream
        )

        await monitor.poll_once()

        # All sessions should have triggered callback
        session_ids = [r[0] for r in received]
        assert "session-0" in session_ids
        assert "session-1" in session_ids
        assert "session-2" in session_ids

    @pytest.mark.asyncio
    async def test_monitor_session_lifecycle_stream_cleanup(self):
        """Stream is cleaned up when session is cleared."""
        controller = self.make_mock_controller()
        spawner = self.make_mock_spawner()
        monitor = SessionMonitor(controller, spawner)

        # Create stream and add subscriber
        async def callback(output):
            pass

        monitor.subscribe_output("session-1", callback)
        monitor.get_output_stream("session-1")

        assert monitor.has_output_subscribers("session-1")
        assert monitor._stream_manager.has_stream("session-1")

        # Clear session
        await monitor.clear_session("session-1")

        # Stream should be removed
        assert not monitor._stream_manager.has_stream("session-1")

    # =========================================================================
    # Performance Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_high_volume_output_performance(self):
        """High volume output doesn't cause issues."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1", max_buffer_lines=100, batch_interval_ms=10)

        received_count = 0

        async def callback(output):
            nonlocal received_count
            received_count += 1

        stream.subscribe(callback)

        # Push a lot of output rapidly
        for i in range(1000):
            await stream.push_output(f"Line {i}")

        # Wait for all flushes
        await asyncio.sleep(0.5)

        # Should have received some batched updates
        assert received_count > 0
        assert received_count < 1000  # Should be batched

        # Buffer should only keep max lines
        buffer = stream.get_full_buffer()
        assert len(buffer) <= 100

    @pytest.mark.asyncio
    async def test_no_streaming_when_no_subscribers(self):
        """No work is done when there are no subscribers."""
        from iterm_controller.session_monitor import SessionOutputStream

        stream = SessionOutputStream("session-1", batch_interval_ms=1)

        # Push output with no subscribers
        for i in range(100):
            await stream.push_output(f"Line {i}")

        # Pending output should be cleared since no subscribers
        assert len(stream._pending_output) == 0
