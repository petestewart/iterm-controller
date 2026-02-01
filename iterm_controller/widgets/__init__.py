"""Widget components for the TUI."""

from iterm_controller.widgets.github_panel import GitHubPanelWidget
from iterm_controller.widgets.health_status import HealthStatusWidget
from iterm_controller.widgets.session_list import SessionListWidget
from iterm_controller.widgets.task_list import TaskListWidget
from iterm_controller.widgets.task_progress import TaskProgressWidget
from iterm_controller.widgets.workflow_bar import WorkflowBarWidget

__all__ = [
    "GitHubPanelWidget",
    "HealthStatusWidget",
    "SessionListWidget",
    "TaskListWidget",
    "TaskProgressWidget",
    "WorkflowBarWidget",
]
