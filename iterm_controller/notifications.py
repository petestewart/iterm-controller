"""macOS notification sender.

This module provides macOS notification integration via terminal-notifier.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass


@dataclass
class Notifier:
    """macOS notification sender using terminal-notifier.

    Provides notification support with graceful degradation when
    terminal-notifier is not installed.
    """

    available: bool = False
    error_message: str | None = None

    async def initialize(self) -> None:
        """Check terminal-notifier availability.

        Sets available=True if terminal-notifier is installed.
        """
        self.available, self.error_message = await self._check_available()

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
    ) -> bool:
        """Send a macOS notification.

        Args:
            title: The notification title.
            message: The notification body text.
            subtitle: Optional subtitle.
            sound: Sound to play (default, or None for silent).

        Returns:
            True if notification was sent successfully.
        """
        if not self.available:
            return False

        try:
            args = [
                "terminal-notifier",
                "-title",
                title,
                "-message",
                message,
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

        except Exception:
            return False

    async def notify_session_waiting(
        self,
        session_name: str,
        project_name: str | None = None,
    ) -> bool:
        """Send notification that a session needs attention.

        Args:
            session_name: Name of the session that needs attention.
            project_name: Optional project name for context.

        Returns:
            True if notification was sent successfully.
        """
        title = "iTerm Controller"
        if project_name:
            message = f"{project_name}: {session_name} needs attention"
        else:
            message = f"{session_name} needs attention"

        return await self.notify(title=title, message=message)
