"""Window layout management for iTerm2 - re-exports.

This module re-exports layout classes from their dedicated modules
for backward compatibility.
"""

from iterm_controller.iterm.layout_manager import WindowLayoutManager
from iterm_controller.iterm.layout_spawner import LayoutSpawnResult, WindowLayoutSpawner

__all__ = [
    "LayoutSpawnResult",
    "WindowLayoutSpawner",
    "WindowLayoutManager",
]
