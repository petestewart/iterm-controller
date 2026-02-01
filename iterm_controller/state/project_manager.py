"""Project state manager.

Handles project-related state operations including opening, closing,
and updating projects.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from iterm_controller.models import Project

logger = logging.getLogger(__name__)
from iterm_controller.state.events import (
    ProjectClosed,
    ProjectOpened,
)

if TYPE_CHECKING:
    from textual.app import App


class ProjectStateManager:
    """Manages project-related state.

    Handles:
    - Loading projects from config
    - Opening and closing projects
    - Tracking active project
    - Persisting project updates
    """

    def __init__(self) -> None:
        """Initialize the project state manager."""
        self.projects: dict[str, Project] = {}
        self.active_project_id: str | None = None
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

    def load_projects(self, projects: list[Project]) -> None:
        """Load projects from config.

        Args:
            projects: List of projects from the configuration.
        """
        self.projects = {p.id: p for p in projects}

    @property
    def active_project(self) -> Project | None:
        """Get currently active project."""
        if self.active_project_id:
            return self.projects.get(self.active_project_id)
        return None

    async def open_project(self, project_id: str) -> None:
        """Open a project.

        Args:
            project_id: The ID of the project to open.
        """
        if project_id not in self.projects:
            return

        project = self.projects[project_id]
        project.is_open = True
        self.active_project_id = project_id
        self._post_message(ProjectOpened(project))

    async def close_project(self, project_id: str) -> None:
        """Close a project.

        Args:
            project_id: The ID of the project to close.
        """
        if project_id in self.projects:
            self.projects[project_id].is_open = False

        self._post_message(ProjectClosed(project_id))

        if self.active_project_id == project_id:
            self.active_project_id = None

    def update_project(
        self,
        project: Project,
        persist: bool = True,
        config: Any = None,
        save_callback: Callable[[Any], None] | None = None,
    ) -> None:
        """Update a project in the state.

        Args:
            project: The project with updated fields.
            persist: If True, save the updated config to disk.
            config: The app config object (needed for persistence).
            save_callback: Function to save the config to disk.
        """
        self.projects[project.id] = project

        if persist and config and save_callback:
            # Find and update the project in config.projects
            for i, config_project in enumerate(config.projects):
                if config_project.id == project.id:
                    config.projects[i] = project
                    break
            else:
                # Project not found in config, add it
                config.projects.append(project)

            try:
                save_callback(config)
            except Exception as e:
                # Log but don't crash on save errors
                logger.warning("Failed to save project config: %s", e)

    def get_project(self, project_id: str) -> Project | None:
        """Get a project by ID.

        Args:
            project_id: The project ID.

        Returns:
            The project if found, None otherwise.
        """
        return self.projects.get(project_id)
