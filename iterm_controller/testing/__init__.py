"""Testing utilities for iterm_controller.

This package provides mock implementations of terminal protocols
for unit testing without requiring iTerm2 to be running.
"""

from iterm_controller.testing.mock_terminal import (
    MockConnection,
    MockOutputReader,
    MockSessionSpawner,
    MockSessionTerminator,
    MockTerminalProvider,
    MockWindowTracker,
)

__all__ = [
    "MockTerminalProvider",
    "MockConnection",
    "MockSessionSpawner",
    "MockSessionTerminator",
    "MockOutputReader",
    "MockWindowTracker",
]
