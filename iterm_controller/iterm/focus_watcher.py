"""Focus watcher for detecting when the TUI's tab becomes active.

This module provides a FocusWatcher class that monitors iTerm2 focus
changes and notifies the application when its tab is selected, enabling
automatic refresh of screen content.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable
from typing import TYPE_CHECKING

import iterm2

if TYPE_CHECKING:
    from iterm_controller.iterm.connection import ItermController

logger = logging.getLogger(__name__)


# Type alias for the callback when our tab becomes focused
TabFocusedCallback = Callable[[], None]


class FocusWatcher:
    """Watches for focus changes and notifies when the TUI's tab is selected.

    This class uses iTerm2's FocusMonitor to detect when the tab containing
    the TUI application becomes active. When the user switches to the TUI's
    tab, a callback is invoked to trigger a screen refresh.

    The watcher identifies the TUI's tab by finding the session that contains
    the current Python process (or its parent process).

    Attributes:
        controller: The iTerm2 controller for API access.
        on_tab_focused: Callback to invoke when TUI's tab becomes active.
    """

    def __init__(
        self,
        controller: ItermController,
        on_tab_focused: TabFocusedCallback | None = None,
    ) -> None:
        """Initialize the focus watcher.

        Args:
            controller: The iTerm2 controller with active connection.
            on_tab_focused: Callback to invoke when TUI's tab becomes active.
        """
        self.controller = controller
        self.on_tab_focused = on_tab_focused
        self._our_tab_id: str | None = None
        self._our_session_id: str | None = None
        self._task: asyncio.Task | None = None
        self._running = False

    async def find_our_tab(self) -> str | None:
        """Find the tab containing this TUI application.

        Searches all iTerm2 sessions for one whose process tree contains
        the current Python process.

        Returns:
            The tab ID if found, None otherwise.
        """
        if not self.controller.app:
            logger.warning("Cannot find TUI tab: not connected to iTerm2")
            return None

        our_pid = os.getpid()
        parent_pids = self._get_parent_pids(our_pid)

        for window in self.controller.app.terminal_windows:
            for tab in window.tabs:
                for session in tab.sessions:
                    try:
                        session_pid = await session.async_get_variable("pid")
                        if session_pid and session_pid in parent_pids:
                            self._our_session_id = session.session_id
                            self._our_tab_id = tab.tab_id
                            logger.debug(
                                "Found TUI tab: tab_id=%s, session_id=%s, pid=%s",
                                tab.tab_id,
                                session.session_id,
                                session_pid,
                            )
                            return tab.tab_id
                    except Exception as e:
                        logger.debug("Error getting session pid: %s", e)
                        continue

        logger.warning(
            "Could not find TUI's tab (searched for pids: %s)",
            parent_pids[:5],  # Show first 5 pids
        )
        return None

    def _get_parent_pids(self, start_pid: int) -> list[int]:
        """Get the process ID chain from start_pid up to init.

        Args:
            start_pid: The process ID to start from.

        Returns:
            List of process IDs including start_pid and all parents.
        """
        pids = [start_pid]
        try:
            # Use psutil if available, otherwise try /proc
            try:
                import psutil

                current = start_pid
                while current > 1:
                    pids.append(current)
                    try:
                        parent = psutil.Process(current).ppid()
                        if parent == current:
                            break
                        current = parent
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        break
            except ImportError:
                # Fallback for systems without psutil (macOS has /proc-like)
                # On macOS we can use ps command
                import subprocess

                result = subprocess.run(
                    ["ps", "-o", "ppid=", "-p", str(start_pid)],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0 and result.stdout.strip():
                    parent_pid = int(result.stdout.strip())
                    if parent_pid > 1 and parent_pid != start_pid:
                        pids.append(parent_pid)
                        # Get grandparent
                        result = subprocess.run(
                            ["ps", "-o", "ppid=", "-p", str(parent_pid)],
                            capture_output=True,
                            text=True,
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            grandparent = int(result.stdout.strip())
                            if grandparent > 1:
                                pids.append(grandparent)
        except Exception as e:
            logger.debug("Error getting parent pids: %s", e)

        return pids

    async def start(self) -> None:
        """Start watching for focus changes.

        This method spawns a background task that monitors iTerm2 focus
        changes. When the TUI's tab becomes active, the callback is invoked.
        """
        if self._running:
            logger.debug("Focus watcher already running")
            return

        if not self.controller.is_connected or not self.controller.connection:
            logger.warning("Cannot start focus watcher: not connected to iTerm2")
            return

        # Find our tab first
        await self.find_our_tab()
        if not self._our_tab_id:
            logger.warning("Focus watcher disabled: could not find TUI's tab")
            return

        self._running = True
        self._task = asyncio.create_task(self._watch_loop())
        logger.info("Focus watcher started for tab: %s", self._our_tab_id)

    async def stop(self) -> None:
        """Stop watching for focus changes."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Focus watcher stopped")

    async def _watch_loop(self) -> None:
        """Main loop that watches for focus changes using FocusMonitor."""
        if not self.controller.connection:
            logger.error("No iTerm2 connection for focus watcher")
            return

        try:
            async with iterm2.FocusMonitor(self.controller.connection) as monitor:
                while self._running:
                    try:
                        update = await asyncio.wait_for(
                            monitor.async_get_next_update(),
                            timeout=5.0,  # Check running flag periodically
                        )

                        if update.selected_tab_changed:
                            tab_id = update.selected_tab_changed.tab_id
                            logger.debug("Tab selection changed to: %s", tab_id)

                            if tab_id == self._our_tab_id:
                                logger.info("TUI tab became active, triggering refresh")
                                if self.on_tab_focused:
                                    self.on_tab_focused()

                    except TimeoutError:
                        # Just a timeout, check if we should continue
                        continue

        except asyncio.CancelledError:
            logger.debug("Focus watcher cancelled")
            raise
        except Exception as e:
            logger.error("Focus watcher error: %s", e)
            self._running = False

    @property
    def is_running(self) -> bool:
        """Check if the focus watcher is currently running."""
        return self._running and self._task is not None
