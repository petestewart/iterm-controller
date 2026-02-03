"""Git state manager.

Manages git status for all open projects with caching and event dispatch.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from iterm_controller.git_service import GitService
from iterm_controller.models import GitStatus
from iterm_controller.state.events import GitStatusChanged

if TYPE_CHECKING:
    from textual.app import App

logger = logging.getLogger(__name__)


class GitStateManager:
    """Manages git status for all open projects.

    Provides methods for:
    - Refreshing git status (with caching via GitService)
    - Staging files
    - Committing changes
    - Pushing and pulling

    All operations post GitStatusChanged messages when status changes.

    Attributes:
        git_service: The underlying GitService for git operations.
        statuses: Cached git statuses by project ID.
    """

    def __init__(self, git_service: GitService | None = None) -> None:
        """Initialize the git state manager.

        Args:
            git_service: The GitService to use. If None, creates a new one.
        """
        self.git_service = git_service or GitService()
        self.statuses: dict[str, GitStatus] = {}
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

    def _get_project_path(self, project_id: str) -> Path | None:
        """Get the path for a project.

        Args:
            project_id: The project ID.

        Returns:
            The project path, or None if not found.
        """
        if self._app is None:
            logger.warning("No app connected, cannot get project path")
            return None

        # Access the app's state to get the project
        if not hasattr(self._app, "state"):
            logger.warning("App has no state attribute")
            return None

        project = self._app.state.projects.get(project_id)
        if project is None:
            logger.warning("Project %s not found", project_id)
            return None

        return Path(project.path)

    async def refresh(self, project_id: str, use_cache: bool = True) -> GitStatus | None:
        """Refresh git status for a project.

        Args:
            project_id: The project ID.
            use_cache: Whether to use cached status if available.

        Returns:
            The refreshed GitStatus, or None if project not found or not a git repo.
        """
        project_path = self._get_project_path(project_id)
        if project_path is None:
            return None

        try:
            status = await self.git_service.get_status(project_path, use_cache=use_cache)
            self.statuses[project_id] = status
            self._post_message(GitStatusChanged(project_id, status))
            return status
        except Exception as e:
            logger.warning("Failed to get git status for %s: %s", project_id, e)
            return None

    async def stage_files(
        self, project_id: str, files: list[str] | None = None
    ) -> bool:
        """Stage files and refresh status.

        Args:
            project_id: The project ID.
            files: List of files to stage, or None to stage all.

        Returns:
            True if successful, False otherwise.
        """
        project_path = self._get_project_path(project_id)
        if project_path is None:
            return False

        try:
            await self.git_service.stage_files(project_path, files)
            await self.refresh(project_id, use_cache=False)
            return True
        except Exception as e:
            logger.error("Failed to stage files for %s: %s", project_id, e)
            return False

    async def unstage_files(
        self, project_id: str, files: list[str] | None = None
    ) -> bool:
        """Unstage files and refresh status.

        Args:
            project_id: The project ID.
            files: List of files to unstage, or None to unstage all.

        Returns:
            True if successful, False otherwise.
        """
        project_path = self._get_project_path(project_id)
        if project_path is None:
            return False

        try:
            await self.git_service.unstage_files(project_path, files)
            await self.refresh(project_id, use_cache=False)
            return True
        except Exception as e:
            logger.error("Failed to unstage files for %s: %s", project_id, e)
            return False

    async def commit(self, project_id: str, message: str) -> str | None:
        """Create commit and refresh status.

        Args:
            project_id: The project ID.
            message: The commit message.

        Returns:
            The SHA of the created commit, or None on failure.
        """
        project_path = self._get_project_path(project_id)
        if project_path is None:
            return None

        try:
            sha = await self.git_service.commit(project_path, message)
            await self.refresh(project_id, use_cache=False)
            return sha
        except Exception as e:
            logger.error("Failed to commit for %s: %s", project_id, e)
            return None

    async def push(
        self,
        project_id: str,
        remote: str = "origin",
        branch: str | None = None,
        force: bool = False,
        set_upstream: bool = False,
    ) -> bool:
        """Push to remote and refresh status.

        Args:
            project_id: The project ID.
            remote: The remote name.
            branch: The branch to push, or None for current branch.
            force: Whether to force push (with --force-with-lease).
            set_upstream: Whether to set upstream tracking.

        Returns:
            True if successful, False otherwise.
        """
        project_path = self._get_project_path(project_id)
        if project_path is None:
            return False

        try:
            await self.git_service.push(
                project_path,
                remote=remote,
                branch=branch,
                force=force,
                set_upstream=set_upstream,
            )
            await self.refresh(project_id, use_cache=False)
            return True
        except Exception as e:
            logger.error("Failed to push for %s: %s", project_id, e)
            return False

    async def pull(
        self,
        project_id: str,
        remote: str = "origin",
        branch: str | None = None,
    ) -> bool:
        """Pull from remote and refresh status.

        Args:
            project_id: The project ID.
            remote: The remote name.
            branch: The branch to pull, or None for current branch.

        Returns:
            True if successful, False otherwise.
        """
        project_path = self._get_project_path(project_id)
        if project_path is None:
            return False

        try:
            await self.git_service.pull(project_path, remote=remote, branch=branch)
            await self.refresh(project_id, use_cache=False)
            return True
        except Exception as e:
            logger.error("Failed to pull for %s: %s", project_id, e)
            return False

    async def fetch(self, project_id: str, remote: str = "origin") -> bool:
        """Fetch from remote and refresh status.

        Args:
            project_id: The project ID.
            remote: The remote name.

        Returns:
            True if successful, False otherwise.
        """
        project_path = self._get_project_path(project_id)
        if project_path is None:
            return False

        try:
            await self.git_service.fetch(project_path, remote=remote)
            await self.refresh(project_id, use_cache=False)
            return True
        except Exception as e:
            logger.error("Failed to fetch for %s: %s", project_id, e)
            return False

    async def get_diff(
        self,
        project_id: str,
        staged_only: bool = False,
        base_branch: str | None = None,
    ) -> str | None:
        """Get diff output for a project.

        Args:
            project_id: The project ID.
            staged_only: Whether to show only staged changes.
            base_branch: If provided, diff against this branch.

        Returns:
            The diff output, or None on failure.
        """
        project_path = self._get_project_path(project_id)
        if project_path is None:
            return None

        try:
            return await self.git_service.get_diff(
                project_path, staged_only=staged_only, base_branch=base_branch
            )
        except Exception as e:
            logger.error("Failed to get diff for %s: %s", project_id, e)
            return None

    def get(self, project_id: str) -> GitStatus | None:
        """Get cached status for a project.

        Args:
            project_id: The project ID.

        Returns:
            The cached GitStatus, or None if not cached.
        """
        return self.statuses.get(project_id)

    def clear(self, project_id: str) -> None:
        """Clear cached status for a project.

        Args:
            project_id: The project ID.
        """
        self.statuses.pop(project_id, None)

    def clear_all(self) -> None:
        """Clear all cached statuses."""
        self.statuses.clear()
        self.git_service.clear_cache()

    def get_all_statuses(self) -> dict[str, GitStatus]:
        """Get all cached statuses.

        Returns:
            Dictionary mapping project IDs to their git statuses.
        """
        return dict(self.statuses)
