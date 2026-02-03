# Session Monitor

## Overview

Output polling and attention state detection for terminal sessions.

The session monitor performs two key functions:
1. **Attention state detection** - Classifies sessions as WAITING, WORKING, or IDLE based on output patterns
2. **Output streaming** - Streams terminal output to TUI subscribers in real-time

## Polling Architecture

```python
import asyncio
from datetime import datetime, timedelta

class SessionMonitor:
    """Polls session output and detects attention states."""

    def __init__(
        self,
        controller: "ItermController",
        state: "AppState",
        polling_interval_ms: int = 500
    ):
        self.controller = controller
        self.state = state
        self.polling_interval = polling_interval_ms / 1000
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        """Start the monitoring loop."""
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self):
        """Stop the monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self):
        """Main polling loop."""
        while self._running:
            await self._poll_all_sessions()
            await asyncio.sleep(self.polling_interval)

    async def _poll_all_sessions(self):
        """Poll output from all managed sessions."""
        sessions = list(self.state.sessions.values())

        # Poll in batches for better performance
        batch_size = 10
        for i in range(0, len(sessions), batch_size):
            batch = sessions[i:i + batch_size]
            await asyncio.gather(
                *[self._poll_session(s) for s in batch],
                return_exceptions=True
            )

    async def _poll_session(self, session: "ManagedSession"):
        """Poll a single session for output."""
        try:
            iterm_session = await self.controller.app.get_session_by_id(session.id)
            if not iterm_session:
                return

            # Get recent output
            output = await iterm_session.async_get_contents(
                first_line=-50,  # Last 50 lines
                number_of_lines=50
            )

            new_output = self._extract_new_output(session, output)
            if new_output:
                await self._process_output(session, new_output)

        except Exception as e:
            # Session may have closed
            pass

    def _extract_new_output(
        self,
        session: "ManagedSession",
        output: str
    ) -> str:
        """Extract only new output since last poll."""
        if not session.last_output:
            return output

        # Find where new content starts
        if session.last_output in output:
            idx = output.index(session.last_output) + len(session.last_output)
            return output[idx:]

        return output

    async def _process_output(
        self,
        session: "ManagedSession",
        new_output: str
    ):
        """Process new output and update attention state."""
        old_state = session.attention_state

        # Update session
        session.last_output = new_output
        session.last_activity = datetime.now()

        # Determine new attention state
        new_state = self._determine_attention_state(session, new_output)
        session.attention_state = new_state

        # Emit event if state changed
        if old_state != new_state:
            self.state.emit(
                StateEvent.SESSION_STATUS_CHANGED,
                session=session,
                old_state=old_state,
                new_state=new_state
            )
```

## Attention State Detection

```python
import re

class AttentionState(Enum):
    WAITING = "waiting"   # Needs user input (highest priority)
    WORKING = "working"   # Actively producing output
    IDLE = "idle"         # At prompt, not doing anything

# Claude-specific patterns for WAITING state
CLAUDE_WAITING_PATTERNS = [
    r"\?\s*$",                          # Ends with question mark
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
    r"^\$\s*$",           # Basic $ prompt
    r"^❯\s*$",            # Starship prompt
    r"^%\s*$",            # Zsh prompt
    r"^>\s*$",            # Simple prompt
    r"^\[\w+@\w+\s*\]",   # [user@host] style
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

class AttentionDetector:
    """Detects session attention state from output."""

    def __init__(self):
        self.waiting_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in CLAUDE_WAITING_PATTERNS + CONFIRMATION_PATTERNS
        ]
        self.working_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in CLAUDE_WORKING_PATTERNS
        ]
        self.prompt_patterns = [
            re.compile(p, re.MULTILINE)
            for p in SHELL_PROMPT_PATTERNS
        ]

    def determine_state(
        self,
        session: "ManagedSession",
        new_output: str
    ) -> AttentionState:
        """Determine attention state from output."""
        # Check for waiting patterns first (highest priority)
        for pattern in self.waiting_patterns:
            if pattern.search(new_output):
                return AttentionState.WAITING

        # Check if at shell prompt
        if self._is_shell_prompt(new_output):
            return AttentionState.IDLE

        # Check for working patterns
        for pattern in self.working_patterns:
            if pattern.search(new_output):
                return AttentionState.WORKING

        # Recent output means working
        if session.last_activity:
            elapsed = datetime.now() - session.last_activity
            if elapsed < timedelta(seconds=2):
                return AttentionState.WORKING

        return AttentionState.IDLE

    def _is_shell_prompt(self, output: str) -> bool:
        """Check if output ends with a shell prompt."""
        # Get last non-empty line
        lines = output.strip().split('\n')
        if not lines:
            return False

        last_line = lines[-1].strip()

        for pattern in self.prompt_patterns:
            if pattern.match(last_line):
                return True

        return False
```

## Adaptive Polling

```python
class AdaptivePoller:
    """Adjusts polling rate based on activity."""

    def __init__(
        self,
        min_interval_ms: int = 100,
        max_interval_ms: int = 2000,
        default_interval_ms: int = 500
    ):
        self.min_interval = min_interval_ms
        self.max_interval = max_interval_ms
        self.default_interval = default_interval_ms
        self.session_intervals: dict[str, int] = {}

    def get_interval(self, session_id: str) -> int:
        """Get polling interval for a session in ms."""
        return self.session_intervals.get(session_id, self.default_interval)

    def on_output(self, session: "ManagedSession", had_output: bool):
        """Adjust polling based on output activity."""
        current = self.get_interval(session.id)

        if had_output:
            # Increase polling rate (decrease interval)
            new_interval = max(self.min_interval, current // 2)
        else:
            # Decrease polling rate (increase interval)
            new_interval = min(self.max_interval, int(current * 1.5))

        self.session_intervals[session.id] = new_interval

    def on_state_change(
        self,
        session: "ManagedSession",
        new_state: AttentionState
    ):
        """Adjust polling based on state."""
        if new_state == AttentionState.WAITING:
            # Slow down - user needs to respond
            self.session_intervals[session.id] = self.max_interval
        elif new_state == AttentionState.WORKING:
            # Speed up to catch changes
            self.session_intervals[session.id] = self.min_interval
```

## Batch Reading

```python
class BatchOutputReader:
    """Efficiently reads output from multiple sessions."""

    def __init__(self, controller: "ItermController"):
        self.controller = controller

    async def read_batch(
        self,
        session_ids: list[str]
    ) -> dict[str, str]:
        """Read output from multiple sessions concurrently."""
        tasks = [
            self._read_one(session_id)
            for session_id in session_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        output = {}
        for session_id, result in zip(session_ids, results):
            if isinstance(result, str):
                output[session_id] = result

        return output

    async def _read_one(self, session_id: str) -> str:
        """Read output from a single session."""
        session = await self.controller.app.get_session_by_id(session_id)
        if not session:
            raise SessionNotFoundError(session_id)

        return await session.async_get_contents(
            first_line=-50,
            number_of_lines=50
        )
```

## Performance Optimization

### Output Caching

```python
class OutputCache:
    """Caches session output to reduce redundant processing."""

    def __init__(self, max_entries: int = 100):
        self.cache: dict[str, tuple[str, datetime]] = {}
        self.max_entries = max_entries

    def get(self, session_id: str) -> str | None:
        """Get cached output."""
        if session_id in self.cache:
            output, timestamp = self.cache[session_id]
            return output
        return None

    def set(self, session_id: str, output: str):
        """Cache output."""
        # Evict old entries if needed
        if len(self.cache) >= self.max_entries:
            oldest = min(self.cache.items(), key=lambda x: x[1][1])
            del self.cache[oldest[0]]

        self.cache[session_id] = (output, datetime.now())

    def invalidate(self, session_id: str):
        """Invalidate cached output."""
        self.cache.pop(session_id, None)
```

### Throttling

```python
class OutputThrottle:
    """Throttles output processing to prevent overload."""

    def __init__(self, min_process_interval_ms: int = 100):
        self.min_interval = min_process_interval_ms / 1000
        self.last_process: dict[str, datetime] = {}

    def should_process(self, session_id: str) -> bool:
        """Check if enough time has passed to process again."""
        last = self.last_process.get(session_id)
        if not last:
            return True

        elapsed = (datetime.now() - last).total_seconds()
        return elapsed >= self.min_interval

    def mark_processed(self, session_id: str):
        """Mark session as just processed."""
        self.last_process[session_id] = datetime.now()
```

## Integration Example

```python
class SessionMonitorService:
    """Complete session monitoring service."""

    def __init__(
        self,
        controller: "ItermController",
        state: "AppState",
        notifier: "Notifier"
    ):
        self.controller = controller
        self.state = state

        # Components
        self.detector = AttentionDetector()
        self.adaptive_poller = AdaptivePoller()
        self.batch_reader = BatchOutputReader(controller)
        self.output_cache = OutputCache()
        self.throttle = OutputThrottle()

        # Notification integration
        self.notifier = notifier

    async def start(self):
        """Start monitoring all sessions."""
        while True:
            sessions = list(self.state.sessions.values())

            if sessions:
                await self._monitor_batch(sessions)

            # Use adaptive interval based on activity
            await asyncio.sleep(0.5)

    async def _monitor_batch(self, sessions: list["ManagedSession"]):
        """Monitor a batch of sessions."""
        # Filter to sessions ready for polling
        ready = [
            s for s in sessions
            if self.throttle.should_process(s.id)
        ]

        if not ready:
            return

        # Batch read output
        outputs = await self.batch_reader.read_batch([s.id for s in ready])

        # Process each
        for session in ready:
            output = outputs.get(session.id)
            if output:
                await self._process_session(session, output)
                self.throttle.mark_processed(session.id)

    async def _process_session(
        self,
        session: "ManagedSession",
        output: str
    ):
        """Process session output."""
        cached = self.output_cache.get(session.id)

        # Check for new output
        if output == cached:
            self.adaptive_poller.on_output(session, had_output=False)
            return

        self.output_cache.set(session.id, output)
        self.adaptive_poller.on_output(session, had_output=True)

        # Detect state
        old_state = session.attention_state
        new_state = self.detector.determine_state(session, output)

        if old_state != new_state:
            session.attention_state = new_state
            self.adaptive_poller.on_state_change(session, new_state)

            # Notify if needed
            if new_state == AttentionState.WAITING:
                project = self.state.projects.get(session.project_id)
                if project:
                    await self.notifier.notify_session_waiting(session, project)
```

## Output Streaming

The session monitor now streams output to subscribers in real-time, not just for attention detection.

### SessionOutputStream

```python
class SessionOutputStream:
    """Manages output streaming for a single session"""

    def __init__(self, session_id: str, max_buffer: int = 100):
        self.session_id = session_id
        self.output_buffer: deque[str] = deque(maxlen=max_buffer)
        self.subscribers: list[Callable[[str], Awaitable[None]]] = []

    async def push_output(self, chunk: str) -> None:
        """Push new output to buffer and notify subscribers"""
        lines = chunk.split('\n')
        self.output_buffer.extend(lines)

        for subscriber in self.subscribers:
            await subscriber(chunk)

    def subscribe(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Add a subscriber for output updates"""
        self.subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[str], Awaitable[None]]) -> None:
        """Remove a subscriber"""
        self.subscribers.remove(callback)

    def get_recent_output(self, lines: int = 10) -> list[str]:
        """Get the most recent N lines from buffer"""
        return list(self.output_buffer)[-lines:]
```

### Integration with Polling Loop

The existing polling loop now also streams output:

```python
async def _poll_session(self, session: ManagedSession):
    output = await self._get_session_output(session)

    # Existing: classify attention state
    state = self._classify_attention_state(output)
    if state != session.attention_state:
        session.attention_state = state
        self.post_message(SessionStatusChanged(session.id, state))

    # NEW: stream output to subscribers
    if output and output != session.last_output:
        new_content = self._extract_new_content(output, session.last_output)
        if new_content:
            stream = self._get_output_stream(session.id)
            await stream.push_output(new_content)
            self.post_message(SessionOutputUpdated(session.id, new_content))

    session.last_output = output
```

### SessionOutputUpdated Event

```python
class SessionOutputUpdated(Message):
    """Posted when new output is available for a session"""
    session_id: str
    output: str  # The new content (not full buffer)
```

### Buffer Management

- Default buffer: 100 lines per session
- ANSI escape codes preserved for color
- Truncation: oldest lines dropped when buffer full
- Clear on session close

### TUI Subscription

Mission Control subscribes to output updates:

```python
class MissionControlScreen(Screen):
    async def on_mount(self):
        # Subscribe to output updates
        for session in self.app.state.sessions.values():
            self.app.session_monitor.subscribe_output(
                session.id,
                self._on_session_output
            )

    async def _on_session_output(self, session_id: str, output: str):
        # Update the session card
        card = self.query_one(f"#session-{session_id}", SessionCard)
        card.update_output(output)
```

### Performance Considerations

- Batch small updates (< 100ms apart) to reduce UI refreshes
- Throttle updates for very fast output (e.g., build logs)
- Only send to subscribed screens (don't stream if no one's watching)
