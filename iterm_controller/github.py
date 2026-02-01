"""gh CLI wrapper with graceful degradation.

This module provides GitHub integration via the gh CLI tool with graceful
degradation when gh is unavailable or unauthenticated.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime

from iterm_controller.exceptions import (
    GitHubError,
    NetworkError as BaseNetworkError,
    RateLimitError as BaseRateLimitError,
    record_error,
)
from iterm_controller.models import GitHubStatus, PullRequest

logger = logging.getLogger(__name__)


class RateLimitError(BaseRateLimitError):
    """Raised when GitHub API rate limit is hit."""

    pass


class NetworkError(BaseNetworkError):
    """Raised when network connection fails."""

    pass


@dataclass
class GitHubIntegration:
    """GitHub integration with graceful degradation.

    Wraps the gh CLI to provide GitHub status and PR information.
    Degrades gracefully when gh is not installed or not authenticated.
    """

    available: bool = False
    error_message: str | None = None
    cached_status: dict[str, GitHubStatus] = field(default_factory=dict)

    async def initialize(self) -> bool:
        """Check gh CLI availability and authentication.

        Sets available=True if gh is installed and authenticated.

        Returns:
            True if GitHub integration is available, False otherwise.
        """
        self.available, self.error_message = await self._check_gh_available()
        if self.available:
            logger.info("GitHub integration initialized successfully")
        else:
            logger.info("GitHub integration unavailable: %s", self.error_message)
        return self.available

    async def _check_gh_available(self) -> tuple[bool, str | None]:
        """Check if gh CLI is available and authenticated.

        Returns:
            Tuple of (available, error_message).
        """
        try:
            logger.debug("Checking gh CLI availability")
            proc = await asyncio.create_subprocess_exec(
                "gh",
                "auth",
                "status",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode == 0:
                logger.debug("gh CLI is available and authenticated")
                return (True, None)

            stderr_text = stderr.decode() if stderr else ""
            if "not logged in" in stderr_text.lower():
                logger.debug("gh CLI is installed but not authenticated")
                return (False, "Not authenticated. Run: gh auth login")
            logger.debug("gh auth check failed: %s", stderr_text)
            return (False, f"gh auth failed: {stderr_text}")

        except FileNotFoundError:
            logger.debug("gh CLI not found")
            return (False, "gh CLI not installed")
        except Exception as e:
            logger.warning("Error checking gh availability: %s", e)
            record_error(e)
            return (False, str(e))

    async def get_status(self, project_path: str) -> GitHubStatus | None:
        """Get GitHub status for a project.

        Args:
            project_path: Path to the project directory.

        Returns:
            GitHubStatus if available, None otherwise.
            Returns cached status on error.
        """
        if not self.available:
            return None

        try:
            logger.debug("Fetching GitHub status for %s", project_path)
            status = await self._fetch_status(project_path)
            self.cached_status[project_path] = status
            logger.debug(
                "GitHub status: branch=%s, ahead=%d, behind=%d",
                status.current_branch,
                status.ahead,
                status.behind,
            )
            return status
        except RateLimitError as e:
            # Return cached with rate limit indicator
            logger.warning("GitHub rate limited: %s", e)
            record_error(e)
            cached = self.cached_status.get(project_path)
            if cached:
                cached.rate_limited = True
            return cached
        except NetworkError as e:
            # Return cached with offline indicator
            logger.warning("GitHub network error: %s", e)
            record_error(e)
            cached = self.cached_status.get(project_path)
            if cached:
                cached.offline = True
            return cached
        except Exception as e:
            logger.error("Unexpected error fetching GitHub status: %s", e)
            record_error(e)
            return self.cached_status.get(project_path)

    async def _fetch_status(self, path: str) -> GitHubStatus:
        """Fetch current GitHub status.

        Args:
            path: Path to the project directory.

        Returns:
            GitHubStatus with current branch, sync, and PR info.
        """
        status = GitHubStatus(available=True)

        # Get current branch
        status.current_branch = await self._get_current_branch(path)

        # Get default branch
        status.default_branch = await self._get_default_branch(path)

        # Get ahead/behind counts
        ahead, behind = await self._get_sync_status(path)
        status.ahead = ahead
        status.behind = behind

        # Get PR info
        status.pr = await self._get_pr_info(path)

        status.last_updated = datetime.now()
        return status

    async def _get_current_branch(self, path: str) -> str:
        """Get current git branch.

        Args:
            path: Path to the project directory.

        Returns:
            Current branch name.
        """
        result = await self._run_git(path, "branch", "--show-current")
        return result.strip()

    async def _get_default_branch(self, path: str) -> str:
        """Get the default branch (main/master) for the repo.

        Args:
            path: Path to the project directory.

        Returns:
            Default branch name, defaults to 'main' if detection fails.
        """
        try:
            # Try to get from remote HEAD
            result = await self._run_git(
                path, "symbolic-ref", "refs/remotes/origin/HEAD", "--short"
            )
            # Result is like "origin/main", extract branch name
            branch = result.strip().split("/")[-1]
            if branch:
                return branch
        except Exception as e:
            logger.debug("Could not get default branch from remote HEAD: %s", e)

        # Fallback: check if main or master exists
        try:
            result = await self._run_git(path, "branch", "-l", "main")
            if "main" in result:
                return "main"
        except Exception as e:
            logger.debug("Could not check for 'main' branch: %s", e)

        try:
            result = await self._run_git(path, "branch", "-l", "master")
            if "master" in result:
                return "master"
        except Exception as e:
            logger.debug("Could not check for 'master' branch: %s", e)

        return "main"

    async def _get_sync_status(self, path: str) -> tuple[int, int]:
        """Get ahead/behind commit counts.

        Args:
            path: Path to the project directory.

        Returns:
            Tuple of (ahead, behind) commit counts.
        """
        try:
            result = await self._run_git(
                path, "rev-list", "--left-right", "--count", "HEAD...@{upstream}"
            )
            parts = result.strip().split()
            if len(parts) >= 2:
                ahead = int(parts[0])
                behind = int(parts[1])
                return ahead, behind
        except Exception as e:
            logger.debug("Could not get sync status: %s", e)
        return 0, 0

    async def _get_pr_info(self, path: str) -> PullRequest | None:
        """Get PR info for current branch.

        Args:
            path: Path to the project directory.

        Returns:
            PullRequest if one exists for the current branch, None otherwise.
        """
        try:
            result = await self._run_gh(
                path,
                "pr",
                "view",
                "--json",
                "number,title,url,state,isDraft,comments,reviewDecision",
            )
            data = json.loads(result)

            # Count pending reviews from reviewDecision
            review_decision = data.get("reviewDecision", "")
            reviews_pending = 0
            if review_decision == "REVIEW_REQUIRED":
                reviews_pending = 1  # At least one review required

            pr = PullRequest(
                number=data["number"],
                title=data["title"],
                url=data["url"],
                state=data["state"],
                draft=data.get("isDraft", False),
                comments=len(data.get("comments", [])),
                merged=data["state"] == "MERGED",
                reviews_pending=reviews_pending,
                checks_passing=await self._get_checks_status(path),
            )
            logger.debug("Found PR #%d: %s", pr.number, pr.title)
            return pr
        except Exception as e:
            # No PR for this branch is expected, so only log at debug level
            logger.debug("No PR found for current branch: %s", e)
            return None

    async def _get_checks_status(self, path: str) -> bool | None:
        """Get status of PR checks.

        Args:
            path: Path to the project directory.

        Returns:
            True if all checks pass, False if any fail, None if unknown.
        """
        try:
            result = await self._run_gh(path, "pr", "checks")
            # Parse checks output
            if "All checks were successful" in result:
                return True
            elif "Some checks were not successful" in result:
                return False
            # Check for individual check statuses in the output
            lines = result.strip().split("\n")
            has_failure = False
            has_checks = False
            for line in lines:
                if "fail" in line.lower() or "✗" in line:
                    has_failure = True
                    has_checks = True
                elif "pass" in line.lower() or "✓" in line:
                    has_checks = True
            if has_failure:
                return False
            if has_checks:
                return True
            return None
        except Exception:
            return None

    async def _run_git(
        self, path: str, *args: str, timeout: float = 30.0
    ) -> str:
        """Run a git command.

        Args:
            path: Working directory for the command.
            *args: Git subcommand and arguments.
            timeout: Command timeout in seconds (default 30).

        Returns:
            Command stdout as string.

        Raises:
            GitHubError: If command fails or times out.
        """
        logger.debug("Running git %s", " ".join(args))
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                "-C",
                path,
                *args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("git %s timed out after %.1fs", args[0], timeout)
            raise GitHubError(
                f"git {args[0]} timed out after {timeout}s",
                context={"timeout": timeout, "command": f"git {' '.join(args)}"},
            )

        if proc.returncode != 0:
            error = stderr.decode() if stderr else "Unknown git error"
            logger.debug("git command failed: %s", error)
            raise GitHubError(f"git {args[0]} failed: {error}")

        return stdout.decode()

    async def _run_gh(
        self, path: str, *args: str, timeout: float = 30.0
    ) -> str:
        """Run a gh command.

        Args:
            path: Working directory for the command.
            *args: gh subcommand and arguments.
            timeout: Command timeout in seconds (default 30).

        Returns:
            Command stdout as string.

        Raises:
            RateLimitError: If rate limited.
            NetworkError: If network error occurs.
            GitHubError: For other errors or timeout.
        """
        logger.debug("Running gh %s", " ".join(args))
        try:
            proc = await asyncio.create_subprocess_exec(
                "gh",
                *args,
                cwd=path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("gh %s timed out after %.1fs", args[0], timeout)
            raise NetworkError(
                f"gh {args[0]} timed out after {timeout}s",
                url="github.com",
            )

        if proc.returncode != 0:
            error = stderr.decode() if stderr else ""

            if "rate limit" in error.lower():
                logger.warning("GitHub rate limit hit")
                raise RateLimitError(error)
            if "network" in error.lower() or "connection" in error.lower():
                logger.warning("GitHub network error: %s", error)
                raise NetworkError(error, url="github.com")
            if "could not resolve" in error.lower():
                logger.warning("GitHub DNS resolution failed")
                raise NetworkError(error, url="github.com")

            logger.debug("gh command failed: %s", error)
            raise GitHubError(f"gh {args[0]} failed: {error}")

        return stdout.decode()

    async def get_workflow_runs(
        self, path: str, limit: int = 10
    ) -> list[dict[str, str | int | None]]:
        """Get recent GitHub Actions workflow runs.

        Args:
            path: Path to the project directory.
            limit: Maximum number of runs to fetch.

        Returns:
            List of workflow run dictionaries.
        """
        if not self.available:
            return []

        try:
            logger.debug("Fetching workflow runs for %s", path)
            result = await self._run_gh(
                path,
                "run",
                "list",
                "--limit",
                str(limit),
                "--json",
                "databaseId,name,status,conclusion,createdAt,headBranch",
            )
            data = json.loads(result)
            runs = [
                {
                    "id": r["databaseId"],
                    "name": r["name"],
                    "status": r["status"],
                    "conclusion": r.get("conclusion"),
                    "created_at": r["createdAt"],
                    "branch": r["headBranch"],
                }
                for r in data
            ]
            logger.debug("Found %d workflow runs", len(runs))
            return runs
        except Exception as e:
            logger.warning("Failed to fetch workflow runs: %s", e)
            record_error(e)
            return []

    def clear_cache(self, project_path: str | None = None) -> None:
        """Clear cached status.

        Args:
            project_path: If provided, clear only that project's cache.
                         If None, clear all cached status.
        """
        if project_path:
            self.cached_status.pop(project_path, None)
        else:
            self.cached_status.clear()
