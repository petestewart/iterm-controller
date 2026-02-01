"""Screen components for the TUI.

This package contains all Textual screens for the iTerm Controller application.
"""

from iterm_controller.screens.control_room import ControlRoomScreen
from iterm_controller.screens.new_project import NewProjectScreen
from iterm_controller.screens.project_dashboard import ProjectDashboardScreen
from iterm_controller.screens.project_list import ProjectListScreen
from iterm_controller.screens.settings import SettingsScreen

__all__ = [
    "ControlRoomScreen",
    "NewProjectScreen",
    "ProjectDashboardScreen",
    "ProjectListScreen",
    "SettingsScreen",
]
