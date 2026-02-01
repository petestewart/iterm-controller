"""Output polling and attention state detection for terminal sessions.

This module provides the core monitoring capabilities for tracking session
output and detecting when sessions need user attention.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from iterm_controller.iterm_api import ItermController, SessionSpawner
    from iterm_controller.models import ManagedSession

logger = logging.getLogger(__name__)


# =============================================================================
# Output Cache
# =============================================================================


@dataclass
class CachedOutput:
    """Cached output for a session."""

    content: str
    timestamp: datetime


class OutputCache:
    """Caches session output to reduce redundant processing."""

    def __init__(self, max_entries: int = 100) -> None:
        self._cache: dict[str, CachedOutput] = {}
        self.max_entries = max_entries

    def get(self, session_id: str) -> str | None:
        """Get cached output for a session."""
        cached = self._cache.get(session_id)
        if cached:
            return cached.content
        return None

    def set(self, session_id: str, output: str) -> None:
        """Cache output for a session."""
        # Evict oldest entry if at capacity
        if len(self._cache) >= self.max_entries and session_id not in self._cache:
            oldest_id = min(self._cache.keys(), key=lambda k: self._cache[k].timestamp)
            del self._cache[oldest_id]

        self._cache[session_id] = CachedOutput(content=output, timestamp=datetime.now())

    def invalidate(self, session_id: str) -> None:
        """Remove cached output for a session."""
        self._cache.pop(session_id, None)

    def clear(self) -> None:
        """Clear all cached output."""
        self._cache.clear()


# =============================================================================
# Output Throttle
# =============================================================================


class OutputThrottle:
    """Throttles output processing to prevent overload."""

    def __init__(self, min_process_interval_ms: int = 100) -> None:
        self.min_interval = min_process_interval_ms / 1000
        self._last_process: dict[str, datetime] = {}

    def should_process(self, session_id: str) -> bool:
        """Check if enough time has passed to process this session again."""
        last = self._last_process.get(session_id)
        if not last:
            return True

        elapsed = (datetime.now() - last).total_seconds()
        return elapsed >= self.min_interval

    def mark_processed(self, session_id: str) -> None:
        """Mark session as just processed."""
        self._last_process[session_id] = datetime.now()

    def clear(self, session_id: str | None = None) -> None:
        """Clear throttle state for a session or all sessions."""
        if session_id:
            self._last_process.pop(session_id, None)
        else:
            self._last_process.clear()


# =============================================================================
# Batch Output Reader
# =============================================================================


class SessionNotFoundError(Exception):
    """Raised when a session cannot be found."""

    pass


class BatchOutputReader:
    """Efficiently reads output from multiple sessions concurrently."""

    def __init__(self, controller: ItermController, lines_to_read: int = 50) -> None:
        self.controller = controller
        self.lines_to_read = lines_to_read

    async def read_batch(self, session_ids: list[str]) -> dict[str, str]:
        """Read output from multiple sessions concurrently.

        Args:
            session_ids: List of session IDs to read from.

        Returns:
            Dictionary mapping session_id to output content.
            Sessions that couldn't be read are omitted.
        """
        if not session_ids:
            return {}

        tasks = [self._read_one(session_id) for session_id in session_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output: dict[str, str] = {}
        for session_id, result in zip(session_ids, results):
            if isinstance(result, str):
                output[session_id] = result
            elif isinstance(result, Exception):
                # Log but don't fail the batch
                logger.debug(f"Failed to read session {session_id}: {result}")

        return output

    async def _read_one(self, session_id: str) -> str:
        """Read output from a single session.

        Args:
            session_id: The iTerm2 session ID.

        Returns:
            The session's recent output.

        Raises:
            SessionNotFoundError: If the session doesn't exist.
        """
        if not self.controller.app:
            raise SessionNotFoundError(f"Not connected to iTerm2")

        session = await self.controller.app.async_get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(f"Session {session_id} not found")

        # Get the last N lines of output
        # first_line=-N means start N lines from the end
        contents = await session.async_get_contents(
            first_line=-self.lines_to_read, number_of_lines=self.lines_to_read
        )

        return contents


# =============================================================================
# Output Processor
# =============================================================================


@dataclass
class OutputChange:
    """Represents a change in session output."""

    session_id: str
    old_output: str | None
    new_output: str
    changed: bool


class OutputProcessor:
    """Processes session output and detects changes."""

    def __init__(self) -> None:
        self._last_output: dict[str, str] = {}

    def extract_new_output(self, session_id: str, current_output: str) -> OutputChange:
        """Extract new output since last poll.

        Args:
            session_id: The session ID.
            current_output: The current full output buffer.

        Returns:
            OutputChange with information about what changed.
        """
        old_output = self._last_output.get(session_id)

        if old_output is None:
            # First time seeing this session
            self._last_output[session_id] = current_output
            return OutputChange(
                session_id=session_id,
                old_output=None,
                new_output=current_output,
                changed=True,
            )

        if old_output == current_output:
            # No change
            return OutputChange(
                session_id=session_id,
                old_output=old_output,
                new_output=current_output,
                changed=False,
            )

        # Find new content
        # Strategy: Look for where the old output ends in the new output
        new_content = current_output
        if old_output and old_output in current_output:
            idx = current_output.index(old_output) + len(old_output)
            new_content = current_output[idx:]
        elif old_output:
            # Output scrolled - old content no longer visible
            # Treat entire current output as new
            new_content = current_output

        self._last_output[session_id] = current_output
        return OutputChange(
            session_id=session_id,
            old_output=old_output,
            new_output=new_content,
            changed=True,
        )

    def clear(self, session_id: str | None = None) -> None:
        """Clear stored output for a session or all sessions."""
        if session_id:
            self._last_output.pop(session_id, None)
        else:
            self._last_output.clear()


# =============================================================================
# Session Monitor
# =============================================================================


@dataclass
class MonitorConfig:
    """Configuration for the session monitor."""

    polling_interval_ms: int = 500
    batch_size: int = 10
    lines_to_read: int = 50
    throttle_interval_ms: int = 100
    cache_max_entries: int = 100


OutputCallback = Callable[["ManagedSession", str, bool], None]


class SessionMonitor:
    """Polls session output at configurable intervals.

    This class implements the core polling loop that checks all managed
    sessions for new output. It uses batching and caching for efficiency.
    """

    def __init__(
        self,
        controller: ItermController,
        spawner: SessionSpawner,
        config: MonitorConfig | None = None,
        on_output: OutputCallback | None = None,
    ) -> None:
        """Initialize the session monitor.

        Args:
            controller: The iTerm2 controller for API access.
            spawner: The session spawner that tracks managed sessions.
            config: Monitor configuration (uses defaults if not provided).
            on_output: Callback invoked when new output is detected.
                      Signature: (session, new_output, had_change)
        """
        self.controller = controller
        self.spawner = spawner
        self.config = config or MonitorConfig()
        self.on_output = on_output

        # Components
        self._reader = BatchOutputReader(controller, self.config.lines_to_read)
        self._processor = OutputProcessor()
        self._cache = OutputCache(self.config.cache_max_entries)
        self._throttle = OutputThrottle(self.config.throttle_interval_ms)

        # State
        self._running = False
        self._task: asyncio.Task | None = None
        self._poll_count = 0

    @property
    def is_running(self) -> bool:
        """Check if the monitor is currently running."""
        return self._running

    @property
    def poll_count(self) -> int:
        """Number of poll cycles completed."""
        return self._poll_count

    async def start(self) -> None:
        """Start the monitoring loop."""
        if self._running:
            logger.warning("Monitor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Session monitor started")

    async def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("Session monitor stopped")

    async def poll_once(self) -> dict[str, OutputChange]:
        """Perform a single poll cycle.

        This is useful for testing or manual triggering.

        Returns:
            Dictionary mapping session_id to OutputChange for sessions
            that had new output.
        """
        return await self._poll_all_sessions()

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        interval = self.config.polling_interval_ms / 1000

        while self._running:
            try:
                await self._poll_all_sessions()
                self._poll_count += 1
            except Exception as e:
                logger.error(f"Error in poll loop: {e}")

            await asyncio.sleep(interval)

    async def _poll_all_sessions(self) -> dict[str, OutputChange]:
        """Poll output from all managed sessions.

        Returns:
            Dictionary of session changes.
        """
        sessions = list(self.spawner.managed_sessions.values())
        if not sessions:
            return {}

        changes: dict[str, OutputChange] = {}

        # Process in batches
        for i in range(0, len(sessions), self.config.batch_size):
            batch = sessions[i : i + self.config.batch_size]
            batch_changes = await self._poll_batch(batch)
            changes.update(batch_changes)

        return changes

    async def _poll_batch(self, sessions: list[ManagedSession]) -> dict[str, OutputChange]:
        """Poll a batch of sessions.

        Args:
            sessions: List of sessions to poll.

        Returns:
            Dictionary of session changes for this batch.
        """
        # Filter to sessions ready for polling
        ready = [s for s in sessions if self._throttle.should_process(s.id)]

        if not ready:
            return {}

        # Batch read output
        session_ids = [s.id for s in ready]
        outputs = await self._reader.read_batch(session_ids)

        changes: dict[str, OutputChange] = {}

        # Process each session
        for session in ready:
            output = outputs.get(session.id)
            if output is None:
                continue

            # Check cache first
            cached = self._cache.get(session.id)
            if cached == output:
                # No change since last poll
                self._throttle.mark_processed(session.id)
                continue

            # Update cache
            self._cache.set(session.id, output)

            # Extract changes
            change = self._processor.extract_new_output(session.id, output)
            self._throttle.mark_processed(session.id)

            if change.changed:
                changes[session.id] = change
                # Update session state
                session.last_output = change.new_output
                session.last_activity = datetime.now()

                # Invoke callback
                if self.on_output:
                    try:
                        self.on_output(session, change.new_output, True)
                    except Exception as e:
                        logger.error(f"Error in output callback: {e}")

        return changes

    def clear_session(self, session_id: str) -> None:
        """Clear all cached state for a session.

        Call this when a session is closed or reset.
        """
        self._cache.invalidate(session_id)
        self._processor.clear(session_id)
        self._throttle.clear(session_id)

    def clear_all(self) -> None:
        """Clear all cached state."""
        self._cache.clear()
        self._processor.clear()
        self._throttle.clear()


# =============================================================================
# Monitor Metrics
# =============================================================================


@dataclass
class MonitorMetrics:
    """Metrics about monitor performance."""

    poll_count: int = 0
    sessions_polled: int = 0
    output_changes: int = 0
    errors: int = 0
    avg_poll_duration_ms: float = 0.0


class MetricsCollector:
    """Collects performance metrics for the monitor."""

    def __init__(self) -> None:
        self._metrics = MonitorMetrics()
        self._poll_durations: list[float] = []
        self._max_history = 100

    def record_poll(self, duration_ms: float, sessions_polled: int, changes: int) -> None:
        """Record a poll cycle."""
        self._metrics.poll_count += 1
        self._metrics.sessions_polled += sessions_polled
        self._metrics.output_changes += changes

        self._poll_durations.append(duration_ms)
        if len(self._poll_durations) > self._max_history:
            self._poll_durations.pop(0)

        if self._poll_durations:
            self._metrics.avg_poll_duration_ms = sum(self._poll_durations) / len(
                self._poll_durations
            )

    def record_error(self) -> None:
        """Record an error."""
        self._metrics.errors += 1

    @property
    def metrics(self) -> MonitorMetrics:
        """Get current metrics."""
        return self._metrics

    def reset(self) -> None:
        """Reset all metrics."""
        self._metrics = MonitorMetrics()
        self._poll_durations.clear()
