"""Health check state manager.

Handles health check status tracking and notifications.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from iterm_controller.models import HealthStatus
from iterm_controller.state.events import HealthStatusChanged

if TYPE_CHECKING:
    from textual.app import App


class HealthStateManager:
    """Manages health check state.

    Handles:
    - Tracking health check statuses by project and check name
    - Notifying about status changes
    - Clearing statuses when projects close
    """

    def __init__(self) -> None:
        """Initialize the health state manager."""
        # project_id -> {check_name -> HealthStatus}
        self._health_statuses: dict[str, dict[str, HealthStatus]] = {}
        self._app: App | None = None

    def connect_app(self, app: App) -> None:
        """Connect to a Textual App for message posting.

        Args:
            app: The Textual App instance.
        """
        self._app = app

    def _post_message(self, message: Any) -> None:
        """Post a message to the connected Textual app."""
        if self._app is not None:
            self._app.post_message(message)

    def update_health_status(
        self, project_id: str, check_name: str, status: HealthStatus
    ) -> None:
        """Update and notify about a health check status change.

        Args:
            project_id: The project ID.
            check_name: The name of the health check.
            status: The new health status.
        """
        if project_id not in self._health_statuses:
            self._health_statuses[project_id] = {}
        self._health_statuses[project_id][check_name] = status

        self._post_message(HealthStatusChanged(project_id, check_name, status.value))

    def get_health_statuses(self, project_id: str) -> dict[str, HealthStatus]:
        """Get all health check statuses for a project.

        Args:
            project_id: The project ID.

        Returns:
            Dictionary mapping check names to their health status.
        """
        return self._health_statuses.get(project_id, {}).copy()

    def clear_health_statuses(self, project_id: str) -> None:
        """Clear all health check statuses for a project.

        Args:
            project_id: The project ID.
        """
        self._health_statuses.pop(project_id, None)

    def get_all_statuses(self) -> dict[str, dict[str, HealthStatus]]:
        """Get all health statuses across all projects.

        Returns:
            Dictionary mapping project IDs to their health statuses.
        """
        return {k: dict(v) for k, v in self._health_statuses.items()}
