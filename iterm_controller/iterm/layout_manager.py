"""Window layout persistence for iTerm2.

This module provides functionality for managing window layout persistence,
including saving, loading, and capturing layouts.
"""

from __future__ import annotations

import logging

import iterm2

from iterm_controller.iterm.connection import ItermController
from iterm_controller.models import (
    SessionLayout,
    TabLayout,
    WindowLayout,
)

logger = logging.getLogger(__name__)


class WindowLayoutManager:
    """Manages window layout persistence.

    Provides functionality to save, load, delete, and list window layouts.
    Also supports capturing the current window state as a new layout.
    """

    def __init__(self, controller: ItermController) -> None:
        """Initialize the layout manager.

        Args:
            controller: The iTerm controller for session operations.
        """
        self.controller = controller
        self._layouts: dict[str, WindowLayout] = {}

    def load_from_config(self, layouts: list[WindowLayout]) -> None:
        """Load layouts from configuration.

        Args:
            layouts: List of WindowLayout objects from AppConfig.
        """
        self._layouts = {layout.id: layout for layout in layouts}
        logger.debug(f"Loaded {len(self._layouts)} window layouts")

    def list_layouts(self) -> list[WindowLayout]:
        """List all available layouts.

        Returns:
            List of all stored WindowLayout objects.
        """
        return list(self._layouts.values())

    def get_layout(self, layout_id: str) -> WindowLayout | None:
        """Get a layout by ID.

        Args:
            layout_id: The unique identifier of the layout.

        Returns:
            The WindowLayout if found, None otherwise.
        """
        return self._layouts.get(layout_id)

    def save_layout(self, layout: WindowLayout) -> None:
        """Save or update a layout.

        If a layout with the same ID exists, it will be replaced.

        Args:
            layout: The WindowLayout to save.
        """
        self._layouts[layout.id] = layout
        logger.info(f"Saved layout '{layout.name}' with ID '{layout.id}'")

    def delete_layout(self, layout_id: str) -> bool:
        """Delete a layout by ID.

        Args:
            layout_id: The unique identifier of the layout to delete.

        Returns:
            True if the layout was deleted, False if not found.
        """
        if layout_id in self._layouts:
            del self._layouts[layout_id]
            logger.info(f"Deleted layout '{layout_id}'")
            return True
        return False

    def get_layouts_for_config(self) -> list[WindowLayout]:
        """Get all layouts for saving to configuration.

        Returns:
            List of WindowLayout objects to be saved to AppConfig.
        """
        return list(self._layouts.values())

    async def capture_current_layout(
        self,
        layout_id: str,
        layout_name: str,
        window: iterm2.Window | None = None,
    ) -> WindowLayout | None:
        """Capture the current window state as a new layout.

        Captures the tab and session structure of a window, inferring
        split directions from session positions.

        Args:
            layout_id: Unique identifier for the new layout.
            layout_name: Display name for the layout.
            window: The window to capture, or None for current window.

        Returns:
            The captured WindowLayout, or None if capture failed.
        """
        self.controller.require_connection()

        if not self.controller.app:
            return None

        try:
            if window is None:
                window = self.controller.app.current_terminal_window

            if window is None:
                logger.warning("No window available to capture")
                return None

            tabs: list[TabLayout] = []

            for tab in window.tabs:
                tab_layout = await self._capture_tab(tab)
                if tab_layout:
                    tabs.append(tab_layout)

            layout = WindowLayout(
                id=layout_id,
                name=layout_name,
                tabs=tabs,
            )

            logger.info(
                f"Captured layout '{layout_name}' with {len(tabs)} tabs "
                f"from window {window.window_id}"
            )

            return layout

        except Exception as e:
            logger.error(f"Failed to capture layout: {e}")
            return None

    async def _capture_tab(self, tab: iterm2.Tab) -> TabLayout | None:
        """Capture a single tab's layout.

        Args:
            tab: The iTerm2 tab to capture.

        Returns:
            TabLayout for the tab, or None if capture failed.
        """
        try:
            title = await tab.async_get_variable("title") or ""
            sessions: list[SessionLayout] = []

            for i, session in enumerate(tab.sessions):
                session_layout = await self._capture_session(session, i)
                sessions.append(session_layout)

            return TabLayout(
                name=title,
                sessions=sessions,
            )

        except Exception as e:
            logger.error(f"Failed to capture tab: {e}")
            return None

    async def _capture_session(
        self,
        session: iterm2.Session,
        index: int,
    ) -> SessionLayout:
        """Capture a single session's layout.

        Since we can't determine the exact template that created a session,
        we use a placeholder template ID that should be mapped when the
        layout is reused.

        Args:
            session: The iTerm2 session to capture.
            index: The position of this session in the tab.

        Returns:
            SessionLayout for the session.
        """
        # Determine split direction based on session position
        # First session has no split, subsequent sessions are splits
        if index == 0:
            split = "none"
        else:
            # Try to infer split direction from session layout
            # This is a best-effort approach; iTerm2 doesn't expose this directly
            split = await self._infer_split_direction(session)

        # Use a placeholder template ID - the user should map this
        # to an actual template when reusing the layout
        template_id = f"session_{index}"

        return SessionLayout(
            template_id=template_id,
            split=split,
            size_percent=50,  # Default size
        )

    async def _infer_split_direction(self, session: iterm2.Session) -> str:
        """Infer the split direction for a session.

        Attempts to determine if a session was created via horizontal or
        vertical split by examining its position relative to siblings.

        Args:
            session: The session to analyze.

        Returns:
            "horizontal" or "vertical" (defaults to vertical).
        """
        try:
            # Get frame to determine split direction
            # If the session is wider than it is tall relative to neighbors,
            # it was likely a horizontal split
            frame = await session.async_get_property("frame")
            if frame:
                # Frame is a dict with 'origin' and 'size'
                size = frame.get("size", {})
                width = size.get("width", 0)
                height = size.get("height", 0)

                # Heuristic: if aspect ratio suggests horizontal split
                if width > height * 1.5:
                    return "horizontal"

            return "vertical"
        except Exception:
            return "vertical"

    async def capture_and_save(
        self,
        layout_id: str,
        layout_name: str,
        window: iterm2.Window | None = None,
    ) -> WindowLayout | None:
        """Capture the current window layout and save it.

        Convenience method that captures and saves in one step.

        Args:
            layout_id: Unique identifier for the new layout.
            layout_name: Display name for the layout.
            window: The window to capture, or None for current window.

        Returns:
            The captured and saved WindowLayout, or None if capture failed.
        """
        layout = await self.capture_current_layout(layout_id, layout_name, window)
        if layout:
            self.save_layout(layout)
        return layout
