# Notifications

## Overview

macOS notification integration using `terminal-notifier` for alerting users when sessions need attention.

## Requirements

- **Latency SLA**: Notifications must fire within 5 seconds of session entering WAITING state
- **Graceful degradation**: App works without notifications if terminal-notifier unavailable
- **Configurable**: Can be disabled in settings

## terminal-notifier Integration

```python
import asyncio
import subprocess
import shutil

class Notifier:
    """macOS notification sender using terminal-notifier."""

    def __init__(self):
        self.available = False
        self.enabled = True

    async def initialize(self):
        """Check if terminal-notifier is available."""
        self.available = shutil.which("terminal-notifier") is not None
        return self.available

    async def notify(
        self,
        title: str,
        message: str,
        subtitle: str = "",
        sound: str = "default",
        group: str = "iterm-controller"
    ):
        """Send a macOS notification.

        Args:
            title: Notification title
            message: Notification body
            subtitle: Optional subtitle
            sound: Sound name or "default"
            group: Notification group for collapsing
        """
        if not self.available or not self.enabled:
            return

        args = [
            "terminal-notifier",
            "-title", title,
            "-message", message,
            "-group", group,
        ]

        if subtitle:
            args.extend(["-subtitle", subtitle])
        if sound:
            args.extend(["-sound", sound])

        try:
            await asyncio.create_subprocess_exec(
                *args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass  # Silent failure

    async def notify_session_waiting(
        self,
        session: "ManagedSession",
        project: "Project"
    ):
        """Notify that a session needs attention."""
        await self.notify(
            title=f"{project.name}",
            subtitle=session.template_id,
            message="Session needs your attention",
            group=f"session-{session.id}"
        )

    async def clear_session_notification(self, session: "ManagedSession"):
        """Clear notification for a session."""
        if not self.available:
            return

        try:
            await asyncio.create_subprocess_exec(
                "terminal-notifier",
                "-remove", f"session-{session.id}",
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass
```

## Notification Triggers

```python
class NotificationManager:
    """Manages notification timing and triggers."""

    def __init__(self, notifier: Notifier, state: "AppState"):
        self.notifier = notifier
        self.state = state
        self._pending_notifications: dict[str, asyncio.Task] = {}

    async def on_session_state_change(
        self,
        session: "ManagedSession",
        old_state: "AttentionState",
        new_state: "AttentionState"
    ):
        """Handle session state change for notifications."""
        project = self.state.projects.get(session.project_id)
        if not project:
            return

        if new_state == AttentionState.WAITING:
            # Cancel any pending clear
            if session.id in self._pending_notifications:
                self._pending_notifications[session.id].cancel()

            # Send notification immediately
            await self.notifier.notify_session_waiting(session, project)

        elif old_state == AttentionState.WAITING:
            # Clear notification when no longer waiting
            await self.notifier.clear_session_notification(session)
```

## Notification Latency Verification

```python
import time

class NotificationLatencyTracker:
    """Tracks notification latency for SLA verification."""

    def __init__(self):
        self.state_change_times: dict[str, float] = {}
        self.notification_times: dict[str, float] = {}

    def record_state_change(self, session_id: str):
        """Record when a session entered WAITING state."""
        self.state_change_times[session_id] = time.monotonic()

    def record_notification_sent(self, session_id: str):
        """Record when notification was sent."""
        self.notification_times[session_id] = time.monotonic()

    def get_latency(self, session_id: str) -> float | None:
        """Get latency for a session in seconds."""
        change_time = self.state_change_times.get(session_id)
        notify_time = self.notification_times.get(session_id)

        if change_time and notify_time:
            return notify_time - change_time
        return None

    def check_sla(self, session_id: str, max_seconds: float = 5.0) -> bool:
        """Check if notification met SLA."""
        latency = self.get_latency(session_id)
        return latency is not None and latency <= max_seconds

    def get_stats(self) -> dict:
        """Get latency statistics."""
        latencies = [
            self.get_latency(sid)
            for sid in self.state_change_times
            if self.get_latency(sid) is not None
        ]

        if not latencies:
            return {"count": 0}

        return {
            "count": len(latencies),
            "min": min(latencies),
            "max": max(latencies),
            "avg": sum(latencies) / len(latencies),
            "sla_met": sum(1 for l in latencies if l <= 5.0),
            "sla_violated": sum(1 for l in latencies if l > 5.0),
        }
```

## Integration with Session Monitor

```python
class SessionMonitorWithNotifications:
    """Session monitor integrated with notifications."""

    def __init__(
        self,
        monitor: "SessionMonitor",
        notifier: Notifier,
        state: "AppState"
    ):
        self.monitor = monitor
        self.notification_manager = NotificationManager(notifier, state)
        self.latency_tracker = NotificationLatencyTracker()

    async def on_attention_change(
        self,
        session: "ManagedSession",
        old_state: "AttentionState",
        new_state: "AttentionState"
    ):
        """Handle attention state change."""
        if new_state == AttentionState.WAITING:
            # Track timing
            self.latency_tracker.record_state_change(session.id)

            # Send notification
            await self.notification_manager.on_session_state_change(
                session, old_state, new_state
            )

            # Record notification time
            self.latency_tracker.record_notification_sent(session.id)

            # Verify SLA
            if not self.latency_tracker.check_sla(session.id):
                latency = self.latency_tracker.get_latency(session.id)
                logging.warning(
                    f"Notification SLA violated for {session.id}: {latency:.2f}s > 5s"
                )
```

## Settings Integration

```python
@dataclass
class NotificationSettings:
    enabled: bool = True
    sound_enabled: bool = True
    sound_name: str = "default"  # Default sound for general notifications

    # Per-event toggles
    on_session_waiting: bool = True
    on_session_idle: bool = False
    on_review_failed: bool = True
    on_task_complete: bool = False
    on_phase_complete: bool = True
    on_orchestrator_done: bool = True

    # Quiet hours
    quiet_hours_start: str | None = None  # e.g., "22:00"
    quiet_hours_end: str | None = None    # e.g., "08:00"

    def is_quiet_time(self) -> bool:
        """Check if currently in quiet hours."""
        if not self.quiet_hours_start or not self.quiet_hours_end:
            return False

        now = datetime.now().time()
        start = datetime.strptime(self.quiet_hours_start, "%H:%M").time()
        end = datetime.strptime(self.quiet_hours_end, "%H:%M").time()

        if start <= end:
            return start <= now <= end
        else:
            # Spans midnight
            return now >= start or now <= end
```

## Degradation

When `terminal-notifier` is not installed:

1. `Notifier.initialize()` sets `available = False`
2. All `notify()` calls return immediately
3. No errors shown to user
4. App functions normally without notifications
5. Settings screen shows "Notifications unavailable - install terminal-notifier"

## Sound Support

Notifications can now include sounds using macOS system sounds.

### notify_with_sound Method

```python
async def notify_with_sound(
    self,
    title: str,
    message: str,
    sound: str = "default",
    subtitle: str | None = None
) -> None:
    """Send a notification with sound"""
    cmd = [
        "terminal-notifier",
        "-title", title,
        "-message", message,
        "-sound", sound
    ]
    if subtitle:
        cmd.extend(["-subtitle", subtitle])

    await asyncio.create_subprocess_exec(*cmd)
```

### Available macOS Sounds

| Sound | Use Case |
|-------|----------|
| `default` | Standard notification |
| `Basso` | Error/failure (low, serious tone) |
| `Blow` | Warning |
| `Bottle` | Gentle notification |
| `Frog` | Playful alert |
| `Funk` | Attention needed |
| `Glass` | Success/completion |
| `Hero` | Major achievement |
| `Morse` | Urgent |
| `Ping` | Quick notification |
| `Pop` | Light notification |
| `Purr` | Gentle reminder |
| `Sosumi` | Classic Mac alert |
| `Submarine` | Deep notification |
| `Tink` | Subtle |

### play_sound Method

```python
async def play_sound(self, sound: str = "default") -> None:
    """Play just a sound without notification"""
    sound_path = f"/System/Library/Sounds/{sound}.aiff"
    await asyncio.create_subprocess_exec("afplay", sound_path)
```

## New Event Types

### Review Events

| Event | Sound | Message |
|-------|-------|---------|
| Review failed (max attempts) | Basso | "Task {title} needs human review after {n} attempts" |
| Review rejected | Basso | "Task {title} was rejected: {summary}" |

### Task Events

| Event | Sound | Message |
|-------|-------|---------|
| Task complete | Glass | "Task {title} completed" |
| Phase complete | Hero | "Phase {title} completed" |

### Orchestrator Events

| Event | Sound | Message |
|-------|-------|---------|
| Orchestrator done | Hero | "All tasks in {phase} completed" |
| Orchestrator paused | Funk | "Orchestrator paused: {reason}" |

## Configuration

```json
{
  "settings": {
    "notifications": {
      "enabled": true,
      "sound_enabled": true,
      "sound_name": "Ping",
      "on_session_waiting": true,
      "on_review_failed": true,
      "on_phase_complete": true,
      "on_orchestrator_done": true
    }
  }
}
```

## Notification Priority

When multiple events happen, prioritize:
1. Review failed (blocking)
2. Session waiting
3. Phase/orchestrator complete
4. Task complete

Debounce: Don't send duplicate notifications within 5 seconds.
