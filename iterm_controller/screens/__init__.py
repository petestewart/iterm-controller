"""Screen components for the TUI.

This package contains all Textual screens for the iTerm Controller application.
"""

from iterm_controller.screens.control_room import ControlRoomScreen
from iterm_controller.screens.mission_control import MissionControlScreen
from iterm_controller.screens.mode_screen import ModeScreen
from iterm_controller.screens.modes import (
    DocsModeScreen,
    PlanModeScreen,
    TestModeScreen,
    WorkModeScreen,
)
from iterm_controller.screens.new_project import NewProjectScreen
from iterm_controller.screens.project_dashboard import ProjectDashboardScreen
from iterm_controller.screens.project_list import ProjectListScreen
from iterm_controller.screens.project_screen import ProjectScreen
from iterm_controller.screens.settings import SettingsScreen

__all__ = [
    "ControlRoomScreen",
    "DocsModeScreen",
    "MissionControlScreen",
    "ModeScreen",
    "NewProjectScreen",
    "PlanModeScreen",
    "ProjectDashboardScreen",
    "ProjectListScreen",
    "ProjectScreen",
    "SettingsScreen",
    "TestModeScreen",
    "WorkModeScreen",
]
