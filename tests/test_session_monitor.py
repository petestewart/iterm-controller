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
    MetricsCollector,
    MonitorConfig,
    MonitorMetrics,
    OutputCache,
    OutputChange,
    OutputProcessor,
    OutputThrottle,
    SessionMonitor,
    SessionNotFoundError,
    SHELL_PROMPT_PATTERNS,
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
        controller.app.async_get_session_by_id = AsyncMock(
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
        controller.app.async_get_session_by_id = AsyncMock(
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
        controller.app.async_get_session_by_id = AsyncMock(
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
        controller.app.async_get_session_by_id = AsyncMock(
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

    def test_clear_session_resets_adaptive_poller(self):
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
        monitor.clear_session("session-1")

        # Should be back to default
        assert monitor._adaptive_poller.get_interval_ms("session-1") == 500

    def test_clear_all_resets_adaptive_poller(self):
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
        monitor.clear_all()

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
        controller.app.async_get_session_by_id = AsyncMock(
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
        controller.app.async_get_session_by_id = AsyncMock(
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
        controller.app.async_get_session_by_id = AsyncMock(
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
        controller.app.async_get_session_by_id = AsyncMock(
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
