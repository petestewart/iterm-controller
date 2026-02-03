"""Git operations service for iTerm Controller.

Provides git status checking, staging, committing, pushing, and other common
git workflows. Supports caching to avoid excessive git calls.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .exceptions import (
    GitCommandError,
    GitNetworkError,
    GitNotARepoError,
    GitPushRejectedError,
)
from .models import GitCommit, GitConfig, GitFileStatus, GitStatus

logger = logging.getLogger(__name__)

# Default cache TTL
DEFAULT_CACHE_TTL = timedelta(seconds=5)


@dataclass
class CachedStatus:
    """Cached git status with timestamp."""

    status: GitStatus
    cached_at: datetime


class GitService:
    """Handles all git operations for projects.

    Provides methods for:
    - Status checking with caching
    - Staging and unstaging files
    - Committing changes
    - Pushing and pulling
    - Fetching
    - Getting commit history
    - Stashing

    Attributes:
        cache_ttl: Time-to-live for cached status.
    """

    def __init__(self, cache_ttl: timedelta = DEFAULT_CACHE_TTL) -> None:
        """Initialize the git service.

        Args:
            cache_ttl: How long to cache git status results.
        """
        self.cache_ttl = cache_ttl
        self._status_cache: dict[str, CachedStatus] = {}

    async def get_status(
        self,
        project_path: Path,
        use_cache: bool = True,
    ) -> GitStatus:
        """Get current git status for a project.

        Runs: git status --porcelain=v2 --branch
        Parses output into GitStatus model.

        Args:
            project_path: Path to the git repository.
            use_cache: Whether to use cached status if available.

        Returns:
            GitStatus with current repository state.

        Raises:
            GitNotARepoError: If path is not a git repository.
            GitCommandError: If git command fails.
        """
        cache_key = str(project_path.resolve())

        if use_cache and cache_key in self._status_cache:
            cached = self._status_cache[cache_key]
            if datetime.now() - cached.cached_at < self.cache_ttl:
                logger.debug("Using cached git status for %s", project_path)
                return cached.status

        output = await self._run_git(
            project_path, "status", "--porcelain=v2", "--branch"
        )
        status = self._parse_status(output)
        status.fetched_at = datetime.now()

        # Get last commit info
        try:
            log_output = await self._run_git(
                project_path, "log", "-1", "--format=%H|%s"
            )
            if log_output.strip():
                parts = log_output.strip().split("|", 1)
                if len(parts) == 2:
                    status.last_commit_sha = parts[0]
                    status.last_commit_message = parts[1]
        except GitCommandError:
            # No commits yet or other error
            pass

        self._status_cache[cache_key] = CachedStatus(
            status=status, cached_at=datetime.now()
        )
        logger.debug("Refreshed git status for %s", project_path)
        return status

    async def get_diff(
        self,
        project_path: Path,
        staged_only: bool = False,
        base_branch: str | None = None,
    ) -> str:
        """Get diff output.

        Args:
            project_path: Path to the git repository.
            staged_only: If True, show only staged changes.
            base_branch: If provided, diff against this branch.

        Returns:
            Diff output as string.

        Raises:
            GitNotARepoError: If path is not a git repository.
            GitCommandError: If git command fails.
        """
        args = ["diff"]

        if staged_only:
            args.append("--cached")
        elif base_branch:
            args.append(f"{base_branch}...HEAD")

        return await self._run_git(project_path, *args)

    async def stage_files(
        self,
        project_path: Path,
        files: list[str] | None = None,
    ) -> None:
        """Stage files for commit.

        Args:
            project_path: Path to the git repository.
            files: List of files to stage, or None to stage all.

        Raises:
            GitNotARepoError: If path is not a git repository.
            GitCommandError: If git command fails.
        """
        if files:
            await self._run_git(project_path, "add", "--", *files)
        else:
            await self._run_git(project_path, "add", "-A")

        self._invalidate_cache(project_path)

    async def unstage_files(
        self,
        project_path: Path,
        files: list[str] | None = None,
    ) -> None:
        """Unstage files.

        Args:
            project_path: Path to the git repository.
            files: List of files to unstage, or None to unstage all.

        Raises:
            GitNotARepoError: If path is not a git repository.
            GitCommandError: If git command fails.
        """
        if files:
            await self._run_git(project_path, "restore", "--staged", "--", *files)
        else:
            await self._run_git(project_path, "restore", "--staged", ".")

        self._invalidate_cache(project_path)

    async def commit(
        self,
        project_path: Path,
        message: str,
        amend: bool = False,
    ) -> str:
        """Create a commit.

        Args:
            project_path: Path to the git repository.
            message: Commit message.
            amend: If True, amend the previous commit.

        Returns:
            SHA of the created commit.

        Raises:
            GitNotARepoError: If path is not a git repository.
            GitCommandError: If git command fails.
        """
        args = ["commit", "-m", message]
        if amend:
            args.append("--amend")

        await self._run_git(project_path, *args)
        self._invalidate_cache(project_path)

        # Get the SHA of the new commit
        sha = await self._run_git(project_path, "rev-parse", "HEAD")
        return sha.strip()

    async def push(
        self,
        project_path: Path,
        remote: str = "origin",
        branch: str | None = None,
        force: bool = False,
        set_upstream: bool = False,
    ) -> None:
        """Push to remote.

        Args:
            project_path: Path to the git repository.
            remote: Remote name.
            branch: Branch to push, or None for current branch.
            force: If True, use --force-with-lease.
            set_upstream: If True, set upstream tracking.

        Raises:
            GitNotARepoError: If path is not a git repository.
            GitPushRejectedError: If push is rejected by remote.
            GitNetworkError: If network operation fails.
            GitCommandError: If git command fails.
        """
        args = ["push", remote]

        if branch:
            args.append(branch)

        if force:
            args.append("--force-with-lease")

        if set_upstream:
            args.append("-u")

        try:
            await self._run_git(project_path, *args)
        except GitCommandError as e:
            error_msg = str(e).lower()
            if "rejected" in error_msg:
                raise GitPushRejectedError(str(e)) from e
            if "network" in error_msg or "could not resolve" in error_msg:
                raise GitNetworkError(str(e)) from e
            raise

    async def pull(
        self,
        project_path: Path,
        remote: str = "origin",
        branch: str | None = None,
    ) -> None:
        """Pull from remote.

        Args:
            project_path: Path to the git repository.
            remote: Remote name.
            branch: Branch to pull, or None for current branch.

        Raises:
            GitNotARepoError: If path is not a git repository.
            GitNetworkError: If network operation fails.
            GitCommandError: If git command fails.
        """
        args = ["pull", remote]
        if branch:
            args.append(branch)

        try:
            await self._run_git(project_path, *args)
        except GitCommandError as e:
            error_msg = str(e).lower()
            if "network" in error_msg or "could not resolve" in error_msg:
                raise GitNetworkError(str(e)) from e
            raise

        self._invalidate_cache(project_path)

    async def fetch(
        self,
        project_path: Path,
        remote: str = "origin",
    ) -> None:
        """Fetch from remote.

        Args:
            project_path: Path to the git repository.
            remote: Remote name.

        Raises:
            GitNotARepoError: If path is not a git repository.
            GitNetworkError: If network operation fails.
            GitCommandError: If git command fails.
        """
        try:
            await self._run_git(project_path, "fetch", remote)
        except GitCommandError as e:
            error_msg = str(e).lower()
            if "network" in error_msg or "could not resolve" in error_msg:
                raise GitNetworkError(str(e)) from e
            raise

    async def get_log(
        self,
        project_path: Path,
        limit: int = 10,
        since_branch: str | None = None,
    ) -> list[GitCommit]:
        """Get recent commits.

        Args:
            project_path: Path to the git repository.
            limit: Maximum number of commits to return.
            since_branch: If provided, show commits since diverging from this branch.

        Returns:
            List of GitCommit objects.

        Raises:
            GitNotARepoError: If path is not a git repository.
            GitCommandError: If git command fails.
        """
        args = [
            "log",
            f"-{limit}",
            "--format=%H|%h|%an|%aI|%s",
        ]

        if since_branch:
            args.append(f"{since_branch}..HEAD")

        output = await self._run_git(project_path, *args)

        commits = []
        for line in output.strip().split("\n"):
            if not line:
                continue
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append(
                    GitCommit(
                        sha=parts[0],
                        short_sha=parts[1],
                        author=parts[2],
                        date=datetime.fromisoformat(parts[3]),
                        message=parts[4],
                    )
                )

        return commits

    async def get_current_branch(self, project_path: Path) -> str:
        """Get current branch name.

        Args:
            project_path: Path to the git repository.

        Returns:
            Current branch name.

        Raises:
            GitNotARepoError: If path is not a git repository.
            GitCommandError: If git command fails.
        """
        output = await self._run_git(project_path, "branch", "--show-current")
        return output.strip()

    async def stash(
        self,
        project_path: Path,
        message: str | None = None,
    ) -> None:
        """Stash current changes.

        Args:
            project_path: Path to the git repository.
            message: Optional stash message.

        Raises:
            GitNotARepoError: If path is not a git repository.
            GitCommandError: If git command fails.
        """
        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])

        await self._run_git(project_path, *args)
        self._invalidate_cache(project_path)

    async def stash_pop(self, project_path: Path) -> None:
        """Pop most recent stash.

        Args:
            project_path: Path to the git repository.

        Raises:
            GitNotARepoError: If path is not a git repository.
            GitCommandError: If git command fails.
        """
        await self._run_git(project_path, "stash", "pop")
        self._invalidate_cache(project_path)

    async def is_git_repo(self, project_path: Path) -> bool:
        """Check if path is a git repository.

        Args:
            project_path: Path to check.

        Returns:
            True if path is a git repository.
        """
        try:
            await self._run_git(project_path, "rev-parse", "--git-dir")
            return True
        except GitNotARepoError:
            return False
        except GitCommandError:
            return False

    def _invalidate_cache(self, project_path: Path) -> None:
        """Invalidate cached status for a project.

        Args:
            project_path: Path to the git repository.
        """
        cache_key = str(project_path.resolve())
        self._status_cache.pop(cache_key, None)

    def clear_cache(self) -> None:
        """Clear all cached status entries."""
        self._status_cache.clear()

    def _parse_status(self, output: str) -> GitStatus:
        """Parse git status --porcelain=v2 output.

        Args:
            output: Raw output from git status command.

        Returns:
            Parsed GitStatus object.
        """
        status = GitStatus(branch="HEAD")
        staged: list[GitFileStatus] = []
        unstaged: list[GitFileStatus] = []
        untracked: list[GitFileStatus] = []

        for line in output.strip().split("\n"):
            if not line:
                continue

            if line.startswith("# branch.head "):
                status.branch = line.split(" ", 2)[2]
            elif line.startswith("# branch.upstream "):
                # Could store upstream if needed
                pass
            elif line.startswith("# branch.ab "):
                parts = line.split(" ")
                for part in parts:
                    if part.startswith("+"):
                        status.ahead = int(part[1:])
                    elif part.startswith("-"):
                        status.behind = int(part[1:])
            elif line.startswith("1 ") or line.startswith("2 "):
                # Changed entry (1 = ordinary, 2 = rename/copy)
                parts = line.split(" ")
                xy = parts[1]  # XY status
                path = parts[-1]

                index_status = xy[0]
                worktree_status = xy[1]

                if index_status != ".":
                    staged.append(
                        GitFileStatus(
                            path=path,
                            status=index_status,
                            staged=True,
                        )
                    )
                if worktree_status != ".":
                    unstaged.append(
                        GitFileStatus(
                            path=path,
                            status=worktree_status,
                            staged=False,
                        )
                    )

                # Check for conflicts
                if "U" in xy:
                    status.has_conflicts = True

            elif line.startswith("? "):
                # Untracked file
                path = line[2:]
                untracked.append(
                    GitFileStatus(
                        path=path,
                        status="?",
                        staged=False,
                    )
                )

        status.staged = staged if staged else None
        status.unstaged = unstaged if unstaged else None
        status.untracked = untracked if untracked else None

        return status

    async def _run_git(self, project_path: Path, *args: str) -> str:
        """Run a git command.

        Args:
            project_path: Path to the git repository.
            *args: Git command arguments.

        Returns:
            Command stdout.

        Raises:
            GitNotARepoError: If path is not a git repository.
            GitCommandError: If command fails.
        """
        try:
            result = await asyncio.create_subprocess_exec(
                "git",
                "-C",
                str(project_path),
                *args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                error = stderr.decode()
                if "not a git repository" in error.lower():
                    raise GitNotARepoError(
                        f"Not a git repository: {project_path}",
                        project_path=str(project_path),
                    )
                raise GitCommandError(
                    f"Git command failed: {error.strip()}",
                    command=" ".join(args),
                    returncode=result.returncode,
                )

            return stdout.decode()

        except FileNotFoundError as e:
            raise GitCommandError(
                "git not found in PATH",
                cause=e,
            ) from e
