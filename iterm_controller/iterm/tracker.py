"""Window and tab state tracking for iTerm2.

This module provides tracking of iTerm2 window and tab state,
including which tabs are managed by this application.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from iterm_controller.iterm.connection import ItermController

logger = logging.getLogger(__name__)


@dataclass
class TabState:
    """Tracks iTerm2 tab state."""

    tab_id: str
    title: str
    session_ids: list[str] = field(default_factory=list)
    is_managed: bool = False


@dataclass
class WindowState:
    """Tracks iTerm2 window state."""

    window_id: str
    tabs: list[TabState] = field(default_factory=list)
    managed_tab_ids: set[str] = field(default_factory=set)


class WindowTracker:
    """Tracks window and tab state across the application."""

    def __init__(self, controller: ItermController) -> None:
        self.controller = controller
        self.windows: dict[str, WindowState] = {}

    async def refresh(self) -> None:
        """Refresh window state from iTerm2."""
        self.controller.require_connection()
        self.windows.clear()

        if not self.controller.app:
            return

        for window in self.controller.app.terminal_windows:
            state = WindowState(window_id=window.window_id)

            for tab in window.tabs:
                try:
                    title = await tab.async_get_variable("title") or ""
                except Exception:
                    title = ""

                tab_state = TabState(
                    tab_id=tab.tab_id,
                    title=title,
                    session_ids=[s.session_id for s in tab.sessions],
                    is_managed=tab.tab_id in state.managed_tab_ids,
                )
                state.tabs.append(tab_state)

            self.windows[window.window_id] = state

    def mark_managed(self, tab_id: str, window_id: str) -> None:
        """Mark a tab as managed by this application."""
        if window_id in self.windows:
            self.windows[window_id].managed_tab_ids.add(tab_id)

    def get_managed_tab_ids(self, window_id: str | None = None) -> set[str]:
        """Get all managed tab IDs, optionally filtered by window."""
        if window_id:
            if window_id in self.windows:
                return self.windows[window_id].managed_tab_ids
            return set()

        all_managed: set[str] = set()
        for window_state in self.windows.values():
            all_managed.update(window_state.managed_tab_ids)
        return all_managed
