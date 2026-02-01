"""Window layout persistence for iTerm2.

This module provides functionality for managing window layout persistence,
including saving and loading layouts.
"""

from __future__ import annotations

import logging

from iterm_controller.iterm.connection import ItermController
from iterm_controller.models import WindowLayout

logger = logging.getLogger(__name__)


class WindowLayoutManager:
    """Manages window layout persistence.

    Provides functionality to save, load, delete, and list window layouts.
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
