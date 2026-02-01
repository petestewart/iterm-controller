"""gh CLI wrapper with graceful degradation.

This module provides GitHub integration via the gh CLI tool with graceful
degradation when gh is unavailable or unauthenticated.
"""

from __future__ import annotations

from dataclasses import dataclass

from iterm_controller.models import GitHubStatus


@dataclass
class GitHubIntegration:
    """GitHub integration with graceful degradation.

    Wraps the gh CLI to provide GitHub status and PR information.
    Degrades gracefully when gh is not installed or not authenticated.
    """

    available: bool = False
    error_message: str | None = None
    cached_status: GitHubStatus | None = None

    async def initialize(self) -> None:
        """Check gh CLI availability and authentication.

        Sets available=True if gh is installed and authenticated.
        """
        self.available, self.error_message = await self._check_gh_available()

    async def _check_gh_available(self) -> tuple[bool, str | None]:
        """Check if gh CLI is available and authenticated.

        Returns:
            Tuple of (available, error_message).
        """
        import asyncio

        try:
            proc = await asyncio.create_subprocess_exec(
                "gh",
                "auth",
                "status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode == 0:
                return (True, None)

            stderr_text = stderr.decode() if stderr else ""
            if "not logged in" in stderr_text.lower():
                return (False, "Not authenticated. Run: gh auth login")
            return (False, f"gh auth failed: {stderr_text}")

        except FileNotFoundError:
            return (False, "gh CLI not installed")
        except Exception as e:
            return (False, str(e))

    async def get_status(self, project_path: str | None = None) -> GitHubStatus | None:
        """Get GitHub status for a project.

        Args:
            project_path: Path to the project directory.

        Returns:
            GitHubStatus if available, None otherwise.
        """
        if not self.available:
            return None

        # For now, return a placeholder status
        # Full implementation will be in Phase 7 (GitHub Integration)
        status = GitHubStatus(available=True)
        self.cached_status = status
        return status
