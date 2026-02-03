"""Screen components for the TUI.

This package contains all Textual screens for the iTerm Controller application.

Screen Architecture (Phase 27 overhaul):
- MissionControlScreen: Main dashboard showing live output from all sessions
- ProjectScreen: Unified project view with planning, docs, git, env sections
- ProjectListScreen: Browse and select projects
- NewProjectScreen: Create projects from templates
- SettingsScreen: Configure app defaults
- TestModeScreen: Test plan management (accessed from ProjectScreen)

Deprecated screens (kept for backwards compatibility):
- ControlRoomScreen: Replaced by MissionControlScreen
- ProjectDashboardScreen: Replaced by ProjectScreen
"""

import warnings

from iterm_controller.screens.mission_control import MissionControlScreen
from iterm_controller.screens.mode_screen import ModeScreen
from iterm_controller.screens.modes import TestModeScreen
from iterm_controller.screens.new_project import NewProjectScreen
from iterm_controller.screens.project_list import ProjectListScreen
from iterm_controller.screens.project_screen import ProjectScreen
from iterm_controller.screens.settings import SettingsScreen


# Lazy imports for deprecated screens to avoid loading them unless needed
def __getattr__(name: str):
    """Lazy import deprecated screens with deprecation warnings."""
    if name == "ControlRoomScreen":
        warnings.warn(
            "ControlRoomScreen is deprecated. Use MissionControlScreen instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from iterm_controller.screens.control_room import ControlRoomScreen

        return ControlRoomScreen
    if name == "ProjectDashboardScreen":
        warnings.warn(
            "ProjectDashboardScreen is deprecated. Use ProjectScreen instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from iterm_controller.screens.project_dashboard import ProjectDashboardScreen

        return ProjectDashboardScreen
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Active screens
    "MissionControlScreen",
    "ModeScreen",
    "NewProjectScreen",
    "ProjectListScreen",
    "ProjectScreen",
    "SettingsScreen",
    "TestModeScreen",
    # Deprecated screens (lazy-loaded with warnings)
    "ControlRoomScreen",
    "ProjectDashboardScreen",
]
