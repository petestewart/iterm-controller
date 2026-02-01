"""Output polling and attention state detection for terminal sessions.

This module provides the core monitoring capabilities for tracking session
output and detecting when sessions need user attention.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Callable

from iterm_controller.models import AttentionState

if TYPE_CHECKING:
    from iterm_controller.iterm import ItermController, SessionSpawner
    from iterm_controller.models import ManagedSession

logger = logging.getLogger(__name__)


# =============================================================================
# Buffer Size Limits
# =============================================================================

# Maximum size for stored session output (100KB)
# This prevents memory bloat from long-running sessions
MAX_OUTPUT_BUFFER_BYTES = 100 * 1024  # 100KB


def truncate_output(output: str, max_bytes: int = MAX_OUTPUT_BUFFER_BYTES) -> str:
    """Truncate output to stay within the buffer size limit.

    Truncation is done from the beginning to preserve the most recent output,
    which is more relevant for attention state detection.

    Args:
        output: The output string to truncate.
        max_bytes: Maximum size in bytes.

    Returns:
        The truncated output string.
    """
    if len(output.encode("utf-8")) <= max_bytes:
        return output

    # Binary search for the right truncation point
    # We want to keep the end of the string (most recent output)
    encoded = output.encode("utf-8")
    if len(encoded) <= max_bytes:
        return output

    # Truncate from the beginning
    truncated_bytes = encoded[-max_bytes:]

    # Decode, handling potential incomplete UTF-8 sequences at the start
    # by using 'ignore' errors to skip incomplete characters
    result = truncated_bytes.decode("utf-8", errors="ignore")

    # Try to start at a newline for cleaner truncation
    newline_idx = result.find("\n")
    if newline_idx > 0 and newline_idx < len(result) // 4:
        # Only skip to newline if it's in the first quarter
        result = result[newline_idx + 1 :]

    return result


# =============================================================================
# Attention Detection Patterns
# =============================================================================

# Claude-specific patterns for WAITING state
CLAUDE_WAITING_PATTERNS = [
    r"\?\s*$",  # Ends with question mark
    r"I have a question",
    r"Before I proceed",
    r"Could you clarify",
    r"Which would you prefer",
    r"Should I",
    r"Do you want me to",
    r"Please confirm",
    r"\[yes/no\]",
    r"\(y/n\)",
]

# Claude patterns indicating WORKING state
CLAUDE_WORKING_PATTERNS = [
    r"^Reading ",
    r"^Writing ",
    r"^Searching ",
    r"^Running ",
    r"Creating .+\.\.\.",
    r"Analyzing ",
]

# Shell prompt patterns indicating IDLE state
SHELL_PROMPT_PATTERNS = [
    r"^\$\s*$",  # Basic $ prompt
    r"^❯\s*$",  # Starship prompt
    r"^%\s*$",  # Zsh prompt
    r"^>\s*$",  # Simple prompt
    r"^\[\w+@\w+\s*\]",  # [user@host] style
]

# Confirmation prompt patterns
CONFIRMATION_PATTERNS = [
    r"\[y/N\]",
    r"\[Y/n\]",
    r"\(yes/no\)",
    r"Continue\?",
    r"Press Enter",
    r"Press any key",
    r"Are you sure",
]


# =============================================================================
# Attention Detector
# =============================================================================


class AttentionDetector:
    """Detects session attention state from output using pattern matching.

    The detector applies patterns in priority order:
    1. WAITING patterns (highest priority) - session needs user input
    2. Shell prompt patterns - session is idle at prompt
    3. WORKING patterns - session is actively processing
    4. Time-based heuristic - recent activity means working

    This allows accurate detection of Claude prompts, shell prompts,
    and activity states.
    """

    def __init__(self, activity_threshold_seconds: float = 2.0) -> None:
        """Initialize the attention detector.

        Args:
            activity_threshold_seconds: Time threshold for considering
                a session as "working" based on recent output.
        """
        self.activity_threshold = timedelta(seconds=activity_threshold_seconds)

        # Pre-compile patterns for performance
        self._waiting_patterns = [
            re.compile(p, re.IGNORECASE | re.MULTILINE)
            for p in CLAUDE_WAITING_PATTERNS + CONFIRMATION_PATTERNS
        ]
        self._working_patterns = [
            re.compile(p, re.IGNORECASE | re.MULTILINE) for p in CLAUDE_WORKING_PATTERNS
        ]
        self._prompt_patterns = [
            re.compile(p, re.MULTILINE) for p in SHELL_PROMPT_PATTERNS
        ]

    def determine_state(
        self,
        session: ManagedSession,
        new_output: str,
    ) -> AttentionState:
        """Determine attention state from session output.

        Args:
            session: The managed session being analyzed.
            new_output: The recent output from the session.

        Returns:
            The detected attention state.
        """
        # Check for waiting patterns first (highest priority)
        for pattern in self._waiting_patterns:
            if pattern.search(new_output):
                return AttentionState.WAITING

        # Check if at shell prompt
        if self._is_shell_prompt(new_output):
            return AttentionState.IDLE

        # Check for working patterns
        for pattern in self._working_patterns:
            if pattern.search(new_output):
                return AttentionState.WORKING

        # Recent output means working
        if session.last_activity:
            elapsed = datetime.now() - session.last_activity
            if elapsed < self.activity_threshold:
                return AttentionState.WORKING

        return AttentionState.IDLE

    def _is_shell_prompt(self, output: str) -> bool:
        """Check if output ends with a shell prompt.

        Args:
            output: The output text to check.

        Returns:
            True if the last line matches a shell prompt pattern.
        """
        # Get last non-empty line
        lines = output.strip().split("\n")
        if not lines:
            return False

        last_line = lines[-1].strip()
        if not last_line:
            return False

        for pattern in self._prompt_patterns:
            if pattern.match(last_line):
                return True

        return False

    def get_pattern_match(self, output: str) -> tuple[AttentionState, str | None]:
        """Determine state and return the matched pattern.

        Useful for debugging and logging.

        Args:
            output: The output text to analyze.

        Returns:
            Tuple of (state, pattern_string) where pattern_string is
            the pattern that matched, or None if no pattern matched.
        """
        for pattern in self._waiting_patterns:
            match = pattern.search(output)
            if match:
                return AttentionState.WAITING, pattern.pattern

        if self._is_shell_prompt(output):
            return AttentionState.IDLE, "shell_prompt"

        for pattern in self._working_patterns:
            match = pattern.search(output)
            if match:
                return AttentionState.WORKING, pattern.pattern

        return AttentionState.IDLE, None


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
# Adaptive Poller
# =============================================================================


class AdaptivePoller:
    """Adjusts polling rate based on session activity.

    The adaptive poller dynamically adjusts polling intervals per-session:
    - When output is detected, the interval decreases (faster polling)
    - When no output is detected, the interval increases (slower polling)
    - On attention state changes, interval adjusts based on the new state:
      - WAITING: slow down (user needs to respond)
      - WORKING: speed up (catch changes quickly)
      - IDLE: return to default

    This balances responsiveness with resource efficiency.
    """

    def __init__(
        self,
        min_interval_ms: int = 100,
        max_interval_ms: int = 2000,
        default_interval_ms: int = 500,
    ) -> None:
        """Initialize the adaptive poller.

        Args:
            min_interval_ms: Minimum polling interval (fastest rate).
            max_interval_ms: Maximum polling interval (slowest rate).
            default_interval_ms: Default interval for new sessions.
        """
        self.min_interval_ms = min_interval_ms
        self.max_interval_ms = max_interval_ms
        self.default_interval_ms = default_interval_ms
        self._session_intervals: dict[str, int] = {}

    def get_interval_ms(self, session_id: str) -> int:
        """Get polling interval for a session in milliseconds.

        Args:
            session_id: The session ID.

        Returns:
            The polling interval in milliseconds.
        """
        return self._session_intervals.get(session_id, self.default_interval_ms)

    def get_interval(self, session_id: str) -> float:
        """Get polling interval for a session in seconds.

        Args:
            session_id: The session ID.

        Returns:
            The polling interval in seconds.
        """
        return self.get_interval_ms(session_id) / 1000

    def on_output(self, session_id: str, had_output: bool) -> int:
        """Adjust polling based on output activity.

        When output is detected, increase polling rate (decrease interval).
        When no output, decrease polling rate (increase interval).

        Args:
            session_id: The session ID.
            had_output: Whether new output was detected.

        Returns:
            The new polling interval in milliseconds.
        """
        current = self.get_interval_ms(session_id)

        if had_output:
            # Increase polling rate (halve the interval)
            new_interval = max(self.min_interval_ms, current // 2)
        else:
            # Decrease polling rate (increase by 1.5x)
            new_interval = min(self.max_interval_ms, int(current * 1.5))

        self._session_intervals[session_id] = new_interval
        return new_interval

    def on_state_change(self, session_id: str, new_state: AttentionState) -> int:
        """Adjust polling based on attention state change.

        Args:
            session_id: The session ID.
            new_state: The new attention state.

        Returns:
            The new polling interval in milliseconds.
        """
        if new_state == AttentionState.WAITING:
            # User needs to respond - slow down polling
            new_interval = self.max_interval_ms
        elif new_state == AttentionState.WORKING:
            # Session is active - speed up to catch changes
            new_interval = self.min_interval_ms
        else:
            # IDLE - return to default
            new_interval = self.default_interval_ms

        self._session_intervals[session_id] = new_interval
        return new_interval

    def reset_session(self, session_id: str) -> None:
        """Reset interval for a session to default.

        Args:
            session_id: The session ID.
        """
        self._session_intervals.pop(session_id, None)

    def reset_all(self) -> None:
        """Reset all session intervals to default."""
        self._session_intervals.clear()

    @property
    def session_intervals(self) -> dict[str, int]:
        """Get a copy of all session intervals."""
        return dict(self._session_intervals)


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
    """Processes session output and detects changes.

    Stored output is truncated to MAX_OUTPUT_BUFFER_BYTES to prevent
    memory bloat from long-running sessions.
    """

    def __init__(self, max_buffer_bytes: int = MAX_OUTPUT_BUFFER_BYTES) -> None:
        self._last_output: dict[str, str] = {}
        self._max_buffer_bytes = max_buffer_bytes

    def extract_new_output(self, session_id: str, current_output: str) -> OutputChange:
        """Extract new output since last poll.

        Args:
            session_id: The session ID.
            current_output: The current full output buffer.

        Returns:
            OutputChange with information about what changed.
        """
        old_output = self._last_output.get(session_id)

        # Truncate current output for storage (preserve recent content)
        truncated_current = truncate_output(current_output, self._max_buffer_bytes)

        if old_output is None:
            # First time seeing this session
            self._last_output[session_id] = truncated_current
            return OutputChange(
                session_id=session_id,
                old_output=None,
                new_output=current_output,
                changed=True,
            )

        if old_output == truncated_current:
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

        self._last_output[session_id] = truncated_current
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

    # Output buffer limit (prevents memory bloat from long-running sessions)
    max_output_buffer_bytes: int = MAX_OUTPUT_BUFFER_BYTES

    # Adaptive polling settings
    adaptive_polling_enabled: bool = False
    adaptive_min_interval_ms: int = 100
    adaptive_max_interval_ms: int = 2000
    adaptive_default_interval_ms: int = 500


OutputCallback = Callable[["ManagedSession", str, bool], None]
AttentionStateCallback = Callable[["ManagedSession", AttentionState, AttentionState], None]


class SessionMonitor:
    """Polls session output at configurable intervals.

    This class implements the core polling loop that checks all managed
    sessions for new output. It uses batching and caching for efficiency.

    Attention state detection is integrated to determine when sessions
    need user attention (WAITING), are actively processing (WORKING),
    or are idle at a prompt (IDLE).
    """

    def __init__(
        self,
        controller: ItermController,
        spawner: SessionSpawner,
        config: MonitorConfig | None = None,
        on_output: OutputCallback | None = None,
        on_attention_state_change: AttentionStateCallback | None = None,
    ) -> None:
        """Initialize the session monitor.

        Args:
            controller: The iTerm2 controller for API access.
            spawner: The session spawner that tracks managed sessions.
            config: Monitor configuration (uses defaults if not provided).
            on_output: Callback invoked when new output is detected.
                      Signature: (session, new_output, had_change)
            on_attention_state_change: Callback invoked when attention state changes.
                      Signature: (session, old_state, new_state)
        """
        self.controller = controller
        self.spawner = spawner
        self.config = config or MonitorConfig()
        self.on_output = on_output
        self.on_attention_state_change = on_attention_state_change

        # Components
        self._reader = BatchOutputReader(controller, self.config.lines_to_read)
        self._processor = OutputProcessor(self.config.max_output_buffer_bytes)
        self._cache = OutputCache(self.config.cache_max_entries)
        self._throttle = OutputThrottle(self.config.throttle_interval_ms)
        self._detector = AttentionDetector()
        self._adaptive_poller = AdaptivePoller(
            min_interval_ms=self.config.adaptive_min_interval_ms,
            max_interval_ms=self.config.adaptive_max_interval_ms,
            default_interval_ms=self.config.adaptive_default_interval_ms,
        )

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
        """Main polling loop.

        When adaptive polling is enabled, the loop uses the minimum interval
        from all active sessions. Otherwise, it uses the fixed polling interval.
        """
        while self._running:
            try:
                await self._poll_all_sessions()
                self._poll_count += 1
            except Exception as e:
                logger.error(f"Error in poll loop: {e}")

            # Determine sleep interval
            interval = self._get_next_poll_interval()
            await asyncio.sleep(interval)

    def _get_next_poll_interval(self) -> float:
        """Get the next poll interval in seconds.

        When adaptive polling is enabled, returns the minimum interval across
        all managed sessions (to ensure responsive polling for active sessions).
        Otherwise, returns the fixed polling interval.

        Returns:
            The interval in seconds to wait before the next poll.
        """
        if not self.config.adaptive_polling_enabled:
            return self.config.polling_interval_ms / 1000

        sessions = list(self.spawner.managed_sessions.values())
        if not sessions:
            return self.config.polling_interval_ms / 1000

        # Use minimum interval across all sessions for responsiveness
        min_interval_ms = min(
            self._adaptive_poller.get_interval_ms(s.id) for s in sessions
        )
        return min_interval_ms / 1000

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
                # Update adaptive polling to slow down
                if self.config.adaptive_polling_enabled:
                    self._adaptive_poller.on_output(session.id, had_output=False)
                continue

            # Update cache
            self._cache.set(session.id, output)

            # Extract changes
            change = self._processor.extract_new_output(session.id, output)
            self._throttle.mark_processed(session.id)

            if change.changed:
                changes[session.id] = change
                # Update session state (truncate to prevent memory bloat)
                session.last_output = truncate_output(
                    change.new_output, self.config.max_output_buffer_bytes
                )
                session.last_activity = datetime.now()

                # Update adaptive polling for output activity
                if self.config.adaptive_polling_enabled:
                    self._adaptive_poller.on_output(session.id, had_output=True)

                # Detect attention state
                old_state = session.attention_state
                new_state = self._detector.determine_state(session, change.new_output)

                if old_state != new_state:
                    session.attention_state = new_state
                    logger.debug(
                        f"Session {session.id} attention state: {old_state.value} -> {new_state.value}"
                    )

                    # Update adaptive polling for state change
                    if self.config.adaptive_polling_enabled:
                        self._adaptive_poller.on_state_change(session.id, new_state)

                    # Invoke attention state callback
                    if self.on_attention_state_change:
                        try:
                            self.on_attention_state_change(session, old_state, new_state)
                        except Exception as e:
                            logger.error(f"Error in attention state callback: {e}")

                # Invoke output callback
                if self.on_output:
                    try:
                        self.on_output(session, change.new_output, True)
                    except Exception as e:
                        logger.error(f"Error in output callback: {e}")
            else:
                # No output change - update adaptive polling for idle
                if self.config.adaptive_polling_enabled:
                    self._adaptive_poller.on_output(session.id, had_output=False)

        return changes

    def clear_session(self, session_id: str) -> None:
        """Clear all cached state for a session.

        Call this when a session is closed or reset.
        """
        self._cache.invalidate(session_id)
        self._processor.clear(session_id)
        self._throttle.clear(session_id)
        self._adaptive_poller.reset_session(session_id)

    def clear_all(self) -> None:
        """Clear all cached state."""
        self._cache.clear()
        self._processor.clear()
        self._throttle.clear()
        self._adaptive_poller.reset_all()

    def get_session_poll_interval(self, session_id: str) -> float:
        """Get the current polling interval for a session.

        When adaptive polling is enabled, returns the session's dynamic
        interval. Otherwise, returns the fixed polling interval.

        Args:
            session_id: The session ID.

        Returns:
            The polling interval in seconds.
        """
        if self.config.adaptive_polling_enabled:
            return self._adaptive_poller.get_interval(session_id)
        return self.config.polling_interval_ms / 1000

    def detect_attention_state(self, session: ManagedSession, output: str) -> AttentionState:
        """Manually detect attention state for output.

        This is useful for testing or external detection.

        Args:
            session: The session to analyze.
            output: The output text to check.

        Returns:
            The detected attention state.
        """
        return self._detector.determine_state(session, output)

    @property
    def detector(self) -> AttentionDetector:
        """Access the attention detector for advanced use."""
        return self._detector

    @property
    def adaptive_poller(self) -> AdaptivePoller:
        """Access the adaptive poller for advanced use."""
        return self._adaptive_poller

    @property
    def is_adaptive_polling_enabled(self) -> bool:
        """Check if adaptive polling is enabled."""
        return self.config.adaptive_polling_enabled


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
