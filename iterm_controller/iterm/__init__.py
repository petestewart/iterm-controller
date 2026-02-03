"""iTerm2 integration package.

This package provides all iTerm2 integration functionality split into
focused modules:

- connection: Connection lifecycle management (ItermController, with_reconnect)
- spawner: Session creation (SessionSpawner, SpawnResult)
- terminator: Session termination (SessionTerminator, CloseResult)
- tracker: Window/tab state tracking (WindowTracker, TabState, WindowState)
- layout_spawner: Window layout spawning (WindowLayoutSpawner, LayoutSpawnResult)
- layout_manager: Window layout persistence (WindowLayoutManager)
- adapter: Protocol adapters for terminal abstraction (ItermTerminalProvider)
- focus_watcher: Tab focus monitoring for screen refresh (FocusWatcher)
"""

from iterm_controller.iterm.adapter import (
    ItermConnectionAdapter,
    ItermOutputReaderAdapter,
    ItermSpawnerAdapter,
    ItermTerminalProvider,
    ItermTerminatorAdapter,
    ItermTrackerAdapter,
)
from iterm_controller.iterm.connection import (
    ItermController,
    with_reconnect,
)
from iterm_controller.iterm.focus_watcher import (
    FocusWatcher,
)
from iterm_controller.iterm.layout_manager import WindowLayoutManager
from iterm_controller.iterm.layout_spawner import (
    LayoutSpawnResult,
    WindowLayoutSpawner,
)
from iterm_controller.iterm.spawner import (
    SessionSpawner,
    SpawnResult,
)
from iterm_controller.iterm.terminator import (
    CloseResult,
    SessionTerminator,
)
from iterm_controller.iterm.tracker import (
    TabState,
    WindowState,
    WindowTracker,
)

__all__ = [
    # Connection
    "ItermController",
    "with_reconnect",
    # Spawner
    "SessionSpawner",
    "SpawnResult",
    # Terminator
    "SessionTerminator",
    "CloseResult",
    # Tracker
    "WindowTracker",
    "TabState",
    "WindowState",
    # Layouts
    "WindowLayoutSpawner",
    "WindowLayoutManager",
    "LayoutSpawnResult",
    # Focus
    "FocusWatcher",
    # Protocol Adapters
    "ItermTerminalProvider",
    "ItermConnectionAdapter",
    "ItermSpawnerAdapter",
    "ItermTerminatorAdapter",
    "ItermOutputReaderAdapter",
    "ItermTrackerAdapter",
]
