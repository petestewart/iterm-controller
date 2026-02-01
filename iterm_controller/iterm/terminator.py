"""Session termination for iTerm2.

This module provides graceful session termination with timeout handling
and force-close fallback.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import iterm2

from iterm_controller.iterm.connection import ItermController
from iterm_controller.models import ManagedSession

if TYPE_CHECKING:
    from iterm_controller.iterm.spawner import SessionSpawner

logger = logging.getLogger(__name__)


@dataclass
class CloseResult:
    """Result of a session close operation."""

    session_id: str
    success: bool
    force_required: bool = False
    error: str | None = None


class SessionTerminator:
    """Handles graceful session termination.

    Provides methods for closing individual sessions, tabs, and bulk managed
    sessions with proper timeout handling and force-close fallback.
    """

    SIGTERM_TIMEOUT = 5.0  # Seconds to wait for graceful shutdown
    POLL_INTERVAL = 0.1  # Seconds between session state polls

    def __init__(self, controller: ItermController) -> None:
        """Initialize the terminator with an iTerm controller.

        Args:
            controller: The iTerm controller for session operations.
        """
        self.controller = controller

    async def close_session(
        self,
        session: iterm2.Session,
        force: bool = False,
    ) -> CloseResult:
        """Close a session, optionally with force.

        For graceful shutdown:
        1. Send Ctrl+C to interrupt any running process
        2. Wait briefly, then send "exit" command
        3. Wait up to SIGTERM_TIMEOUT for session to close
        4. Force close if timeout exceeded

        Args:
            session: The iTerm2 session to close.
            force: If True, skip graceful shutdown and force-close immediately.

        Returns:
            CloseResult with success status and details.
        """
        session_id = session.session_id

        try:
            if force:
                await session.async_close(force=True)
                logger.info(f"Force-closed session {session_id}")
                return CloseResult(
                    session_id=session_id,
                    success=True,
                    force_required=True,
                )

            # Try graceful shutdown
            # Send Ctrl+C to interrupt any running process
            await session.async_send_text("\x03")
            await asyncio.sleep(0.5)

            # Send exit command
            await session.async_send_text("exit\n")
            logger.debug(f"Sent exit command to session {session_id}")

            # Wait for session to close
            try:
                await asyncio.wait_for(
                    self._wait_for_close(session),
                    timeout=self.SIGTERM_TIMEOUT,
                )
                logger.info(f"Gracefully closed session {session_id}")
                return CloseResult(
                    session_id=session_id,
                    success=True,
                    force_required=False,
                )
            except asyncio.TimeoutError:
                # Graceful shutdown failed, force close
                logger.warning(
                    f"Graceful shutdown timed out for session {session_id}, forcing close"
                )
                await session.async_close(force=True)
                logger.info(f"Force-closed session {session_id} after timeout")
                return CloseResult(
                    session_id=session_id,
                    success=True,
                    force_required=True,
                )

        except Exception as e:
            logger.error(f"Failed to close session {session_id}: {e}")
            return CloseResult(
                session_id=session_id,
                success=False,
                error=str(e),
            )

    async def _wait_for_close(self, session: iterm2.Session) -> None:
        """Wait for a session to terminate.

        Polls the session state until it's no longer valid, indicating
        the session has closed.

        Args:
            session: The session to wait for.
        """
        while True:
            try:
                # Try to access session properties - raises if session is gone
                # We use async_get_screen_contents as a reliable way to check
                # if the session is still alive
                await session.async_get_screen_contents()
                await asyncio.sleep(self.POLL_INTERVAL)
            except Exception:
                # Session is gone (or inaccessible), which means it's closed
                break

    async def close_tab(self, tab: iterm2.Tab, force: bool = False) -> bool:
        """Close a tab and all its sessions.

        Args:
            tab: The iTerm2 tab to close.
            force: If True, force-close without asking for confirmation.

        Returns:
            True if the tab was closed successfully.
        """
        try:
            await tab.async_close(force=force)
            logger.info(f"Closed tab {tab.tab_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to close tab {tab.tab_id}: {e}")
            return False

    async def close_all_managed(
        self,
        sessions: list[ManagedSession],
        spawner: "SessionSpawner",
        force: bool = False,
    ) -> tuple[int, list[CloseResult]]:
        """Close all managed sessions, return count closed.

        Closes sessions in parallel for efficiency, then updates the spawner
        to untrack closed sessions.

        Args:
            sessions: List of managed sessions to close.
            spawner: The SessionSpawner to update for tracking cleanup.
            force: If True, force-close all sessions without graceful shutdown.

        Returns:
            Tuple of (count of successfully closed sessions, list of CloseResults).
        """
        if not sessions:
            return (0, [])

        self.controller.require_connection()

        if not self.controller.app:
            return (0, [])

        results: list[CloseResult] = []

        # Gather all close operations to run in parallel
        async def close_one(managed: ManagedSession) -> CloseResult:
            try:
                session = await self.controller.app.async_get_session_by_id(managed.id)
                if session:
                    result = await self.close_session(session, force=force)
                    if result.success:
                        spawner.untrack_session(managed.id)
                    return result
                else:
                    # Session not found - already closed
                    spawner.untrack_session(managed.id)
                    return CloseResult(
                        session_id=managed.id,
                        success=True,
                        error="Session not found (already closed)",
                    )
            except Exception as e:
                logger.error(f"Error closing managed session {managed.id}: {e}")
                return CloseResult(
                    session_id=managed.id,
                    success=False,
                    error=str(e),
                )

        # Run all close operations concurrently
        results = await asyncio.gather(*[close_one(s) for s in sessions])

        closed = sum(1 for r in results if r.success)
        logger.info(f"Closed {closed}/{len(sessions)} managed sessions")

        return (closed, list(results))
