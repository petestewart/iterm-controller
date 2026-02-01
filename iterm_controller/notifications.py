"""macOS notification sender and manager.

This module provides macOS notification integration via terminal-notifier.
It includes latency tracking to verify the 5-second SLA for notifications.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from iterm_controller.models import AttentionState, ManagedSession, Project
    from iterm_controller.state import AppState

logger = logging.getLogger(__name__)


# =============================================================================
# Notifier (terminal-notifier wrapper)
# =============================================================================


@dataclass
class Notifier:
    """macOS notification sender using terminal-notifier.

    Provides notification support with graceful degradation when
    terminal-notifier is not installed.
    """

    available: bool = False
    enabled: bool = True
    error_message: str | None = None

    async def initialize(self) -> bool:
        """Check terminal-notifier availability.

        Sets available=True if terminal-notifier is installed.

        Returns:
            True if terminal-notifier is available.
        """
        self.available, self.error_message = await self._check_available()
        return self.available

    async def _check_available(self) -> tuple[bool, str | None]:
        """Check if terminal-notifier is available.

        Returns:
            Tuple of (available, error_message).
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "which",
                "terminal-notifier",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            if proc.returncode == 0 and stdout.strip():
                return (True, None)
            return (False, "terminal-notifier not found")

        except Exception as e:
            return (False, str(e))

    async def notify(
        self,
        title: str,
        message: str,
        subtitle: str | None = None,
        sound: str | None = "default",
        group: str = "iterm-controller",
    ) -> bool:
        """Send a macOS notification.

        Args:
            title: The notification title.
            message: The notification body text.
            subtitle: Optional subtitle.
            sound: Sound to play (default, or None for silent).
            group: Notification group for collapsing.

        Returns:
            True if notification was sent successfully.
        """
        if not self.available or not self.enabled:
            return False

        try:
            args = [
                "terminal-notifier",
                "-title",
                title,
                "-message",
                message,
                "-group",
                group,
            ]

            if subtitle:
                args.extend(["-subtitle", subtitle])

            if sound:
                args.extend(["-sound", sound])

            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0

        except Exception as e:
            logger.debug(f"Failed to send notification: {e}")
            return False

    async def notify_session_waiting(
        self,
        session: ManagedSession,
        project: Project,
    ) -> bool:
        """Send notification that a session needs attention.

        Args:
            session: The session that needs attention.
            project: The project the session belongs to.

        Returns:
            True if notification was sent successfully.
        """
        return await self.notify(
            title=project.name,
            subtitle=session.template_id,
            message="Session needs your attention",
            group=f"session-{session.id}",
        )

    async def clear_session_notification(self, session: ManagedSession) -> bool:
        """Clear notification for a session.

        Args:
            session: The session to clear notification for.

        Returns:
            True if the clear was successful.
        """
        if not self.available:
            return False

        try:
            proc = await asyncio.create_subprocess_exec(
                "terminal-notifier",
                "-remove",
                f"session-{session.id}",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except Exception:
            return False


# =============================================================================
# Notification Latency Tracker
# =============================================================================


@dataclass
class NotificationLatencyTracker:
    """Tracks notification latency for SLA verification.

    The SLA requires notifications to fire within 5 seconds of a session
    entering the WAITING state.
    """

    sla_seconds: float = 5.0
    state_change_times: dict[str, float] = field(default_factory=dict)
    notification_times: dict[str, float] = field(default_factory=dict)

    def record_state_change(self, session_id: str) -> None:
        """Record when a session entered WAITING state.

        Args:
            session_id: The session ID.
        """
        self.state_change_times[session_id] = time.monotonic()

    def record_notification_sent(self, session_id: str) -> None:
        """Record when notification was sent.

        Args:
            session_id: The session ID.
        """
        self.notification_times[session_id] = time.monotonic()

    def get_latency(self, session_id: str) -> float | None:
        """Get latency for a session in seconds.

        Args:
            session_id: The session ID.

        Returns:
            The latency in seconds, or None if not available.
        """
        change_time = self.state_change_times.get(session_id)
        notify_time = self.notification_times.get(session_id)

        if change_time is not None and notify_time is not None:
            return notify_time - change_time
        return None

    def check_sla(self, session_id: str) -> bool:
        """Check if notification met SLA.

        Args:
            session_id: The session ID.

        Returns:
            True if the notification met the SLA, False otherwise.
        """
        latency = self.get_latency(session_id)
        return latency is not None and latency <= self.sla_seconds

    def get_stats(self) -> dict:
        """Get latency statistics.

        Returns:
            Dictionary with latency statistics including count, min, max,
            avg, and SLA compliance counts.
        """
        latencies = [
            lat
            for sid in self.state_change_times
            if (lat := self.get_latency(sid)) is not None
        ]

        if not latencies:
            return {"count": 0}

        return {
            "count": len(latencies),
            "min": min(latencies),
            "max": max(latencies),
            "avg": sum(latencies) / len(latencies),
            "sla_met": sum(1 for lat in latencies if lat <= self.sla_seconds),
            "sla_violated": sum(1 for lat in latencies if lat > self.sla_seconds),
        }

    def clear_session(self, session_id: str) -> None:
        """Clear tracking data for a session.

        Args:
            session_id: The session ID.
        """
        self.state_change_times.pop(session_id, None)
        self.notification_times.pop(session_id, None)

    def clear_all(self) -> None:
        """Clear all tracking data."""
        self.state_change_times.clear()
        self.notification_times.clear()


# =============================================================================
# Notification Settings
# =============================================================================


@dataclass
class NotificationSettings:
    """Notification-related settings."""

    enabled: bool = True
    sound: str = "default"
    quiet_hours_start: str | None = None  # e.g., "22:00"
    quiet_hours_end: str | None = None  # e.g., "08:00"

    def is_quiet_time(self) -> bool:
        """Check if currently in quiet hours.

        Returns:
            True if currently in quiet hours.
        """
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


# =============================================================================
# Notification Manager
# =============================================================================


class NotificationManager:
    """Manages notification timing and triggers.

    Integrates with the session monitor to send notifications when sessions
    enter the WAITING state and clear them when they leave.
    """

    def __init__(
        self,
        notifier: Notifier,
        state: AppState,
        settings: NotificationSettings | None = None,
    ) -> None:
        """Initialize the notification manager.

        Args:
            notifier: The notifier to send notifications with.
            state: The application state for looking up projects.
            settings: Optional notification settings.
        """
        self.notifier = notifier
        self.state = state
        self.settings = settings or NotificationSettings()
        self.latency_tracker = NotificationLatencyTracker()
        self._pending_notifications: dict[str, asyncio.Task] = {}

    async def on_session_state_change(
        self,
        session: ManagedSession,
        old_state: AttentionState,
        new_state: AttentionState,
    ) -> None:
        """Handle session state change for notifications.

        Sends a notification when a session enters WAITING state and
        clears it when the session leaves WAITING state.

        Args:
            session: The session that changed state.
            old_state: The previous attention state.
            new_state: The new attention state.
        """
        from iterm_controller.models import AttentionState

        # Check if notifications are enabled and not in quiet hours
        if not self.settings.enabled or self.settings.is_quiet_time():
            return

        project = self.state.projects.get(session.project_id)
        if not project:
            return

        if new_state == AttentionState.WAITING:
            # Cancel any pending clear
            if session.id in self._pending_notifications:
                self._pending_notifications[session.id].cancel()
                del self._pending_notifications[session.id]

            # Record state change time for latency tracking
            self.latency_tracker.record_state_change(session.id)

            # Send notification
            success = await self.notifier.notify_session_waiting(session, project)

            # Record notification time
            if success:
                self.latency_tracker.record_notification_sent(session.id)

                # Check SLA
                if not self.latency_tracker.check_sla(session.id):
                    latency = self.latency_tracker.get_latency(session.id)
                    logger.warning(
                        f"Notification SLA violated for session {session.id}: "
                        f"{latency:.2f}s > {self.latency_tracker.sla_seconds}s"
                    )
                else:
                    latency = self.latency_tracker.get_latency(session.id)
                    logger.debug(
                        f"Notification sent for session {session.id} in {latency:.2f}s"
                    )

        elif old_state == AttentionState.WAITING:
            # Clear notification when no longer waiting
            await self.notifier.clear_session_notification(session)
            self.latency_tracker.clear_session(session.id)

    def get_latency_stats(self) -> dict:
        """Get notification latency statistics.

        Returns:
            Dictionary with latency statistics.
        """
        return self.latency_tracker.get_stats()

    def cleanup_session(self, session_id: str) -> None:
        """Clean up tracking data for a closed session.

        Args:
            session_id: The session ID.
        """
        if session_id in self._pending_notifications:
            self._pending_notifications[session_id].cancel()
            del self._pending_notifications[session_id]
        self.latency_tracker.clear_session(session_id)


# =============================================================================
# Session Monitor Integration
# =============================================================================


class SessionMonitorWithNotifications:
    """Wrapper that adds notification support to the session monitor.

    This class provides a callback that can be registered with the
    SessionMonitor to handle attention state changes and send notifications.
    """

    def __init__(
        self,
        notifier: Notifier,
        state: AppState,
        settings: NotificationSettings | None = None,
    ) -> None:
        """Initialize the notification-enabled monitor wrapper.

        Args:
            notifier: The notifier to use.
            state: The application state.
            settings: Optional notification settings.
        """
        self.notification_manager = NotificationManager(notifier, state, settings)

    async def on_attention_change(
        self,
        session: ManagedSession,
        old_state: AttentionState,
        new_state: AttentionState,
    ) -> None:
        """Handle attention state change from the session monitor.

        This method should be registered as the on_attention_state_change
        callback for the SessionMonitor.

        Args:
            session: The session that changed state.
            old_state: The previous attention state.
            new_state: The new attention state.
        """
        await self.notification_manager.on_session_state_change(
            session, old_state, new_state
        )

    def get_latency_stats(self) -> dict:
        """Get notification latency statistics.

        Returns:
            Dictionary with latency statistics.
        """
        return self.notification_manager.get_latency_stats()

    def cleanup_session(self, session_id: str) -> None:
        """Clean up tracking data for a closed session.

        Args:
            session_id: The session ID.
        """
        self.notification_manager.cleanup_session(session_id)
