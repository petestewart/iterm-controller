"""Workflow mode screens.

This package contains the Test mode screen. Plan, Docs, and Work modes
were removed in task 27.9.3 as part of the unified ProjectScreen refactor.
The TestModeScreen is retained for test plan management.
"""

from iterm_controller.screens.modes.test_mode import TestModeScreen

__all__ = [
    "TestModeScreen",
]
