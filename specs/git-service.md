# Git Service

## Overview

Service handling all git operations for projects. Provides status checking, staging, committing, pushing, and other common git workflows directly from the TUI.

## Data Models

```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

class FileStatus(Enum):
    """Status of a file in git."""
    MODIFIED = "M"
    ADDED = "A"
    DELETED = "D"
    RENAMED = "R"
    COPIED = "C"
    UNTRACKED = "?"
    IGNORED = "!"

@dataclass
class ChangedFile:
    """A file with changes in git."""
    path: str
    status: FileStatus
    staged: bool
    old_path: str | None = None  # For renames

@dataclass
class GitStatus:
    """Current git status for a repository."""
    branch: str
    upstream: str | None = None
    ahead: int = 0
    behind: int = 0
    staged: list[ChangedFile] = field(default_factory=list)
    unstaged: list[ChangedFile] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    has_conflicts: bool = False
    is_rebasing: bool = False
    is_merging: bool = False

@dataclass
class GitCommit:
    """A git commit."""
    sha: str
    short_sha: str
    author: str
    date: datetime
    message: str

@dataclass
class GitConfig:
    """Per-project git configuration."""
    auto_stage: bool = False        # Auto-stage before commit
    default_branch: str = "main"
    remote: str = "origin"
```

## GitService Class

```python
import asyncio
import subprocess

class GitService:
    """Handles all git operations for projects."""

    def __init__(self, notifier: "Notifier | None" = None):
        self.notifier = notifier
        self._status_cache: dict[str, tuple[GitStatus, datetime]] = {}
        self._cache_ttl = timedelta(seconds=5)

    async def get_status(
        self,
        project_path: Path,
        use_cache: bool = True
    ) -> GitStatus:
        """Get current git status for a project.

        Runs: git status --porcelain=v2 --branch
        Parses output into GitStatus model.

        Args:
            project_path: Path to the git repository
            use_cache: Whether to use cached status if available

        Returns:
            GitStatus with current repository state
        """
        cache_key = str(project_path)

        if use_cache and cache_key in self._status_cache:
            status, cached_at = self._status_cache[cache_key]
            if datetime.now() - cached_at < self._cache_ttl:
                return status

        output = await self._run_git(
            project_path,
            "status", "--porcelain=v2", "--branch"
        )
        status = self._parse_status(output)

        self._status_cache[cache_key] = (status, datetime.now())
        return status

    async def get_diff(
        self,
        project_path: Path,
        staged_only: bool = False,
        base_branch: str | None = None
    ) -> str:
        """Get diff output.

        Args:
            project_path: Path to the git repository
            staged_only: If True, show only staged changes
            base_branch: If provided, diff against this branch

        Returns:
            Diff output as string
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
        files: list[str] | None = None
    ) -> None:
        """Stage files for commit.

        Args:
            project_path: Path to the git repository
            files: List of files to stage, or None to stage all
        """
        if files:
            await self._run_git(project_path, "add", "--", *files)
        else:
            await self._run_git(project_path, "add", "-A")

        self._invalidate_cache(project_path)

    async def unstage_files(
        self,
        project_path: Path,
        files: list[str] | None = None
    ) -> None:
        """Unstage files.

        Args:
            project_path: Path to the git repository
            files: List of files to unstage, or None to unstage all
        """
        if files:
            await self._run_git(
                project_path, "restore", "--staged", "--", *files
            )
        else:
            await self._run_git(project_path, "restore", "--staged", ".")

        self._invalidate_cache(project_path)

    async def commit(
        self,
        project_path: Path,
        message: str,
        amend: bool = False
    ) -> str:
        """Create a commit.

        Args:
            project_path: Path to the git repository
            message: Commit message
            amend: If True, amend the previous commit

        Returns:
            SHA of the created commit
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
        force: bool = False
    ) -> None:
        """Push to remote.

        Args:
            project_path: Path to the git repository
            remote: Remote name
            branch: Branch to push, or None for current branch
            force: If True, use --force-with-lease
        """
        args = ["push", remote]

        if branch:
            args.append(branch)

        if force:
            args.append("--force-with-lease")

        try:
            await self._run_git(project_path, *args)
        except GitCommandError as e:
            if "rejected" in str(e).lower():
                raise GitPushRejectedError(str(e)) from e
            raise

    async def pull(
        self,
        project_path: Path,
        remote: str = "origin",
        branch: str | None = None
    ) -> None:
        """Pull from remote.

        Args:
            project_path: Path to the git repository
            remote: Remote name
            branch: Branch to pull, or None for current branch
        """
        args = ["pull", remote]
        if branch:
            args.append(branch)

        try:
            await self._run_git(project_path, *args)
        except GitCommandError as e:
            if "network" in str(e).lower() or "could not resolve" in str(e).lower():
                raise GitNetworkError(str(e)) from e
            raise

        self._invalidate_cache(project_path)

    async def fetch(
        self,
        project_path: Path,
        remote: str = "origin"
    ) -> None:
        """Fetch from remote.

        Args:
            project_path: Path to the git repository
            remote: Remote name
        """
        try:
            await self._run_git(project_path, "fetch", remote)
        except GitCommandError as e:
            if "network" in str(e).lower() or "could not resolve" in str(e).lower():
                raise GitNetworkError(str(e)) from e
            raise

    async def get_log(
        self,
        project_path: Path,
        limit: int = 10,
        since_branch: str | None = None
    ) -> list[GitCommit]:
        """Get recent commits.

        Args:
            project_path: Path to the git repository
            limit: Maximum number of commits to return
            since_branch: If provided, show commits since diverging from this branch

        Returns:
            List of GitCommit objects
        """
        args = [
            "log",
            f"-{limit}",
            "--format=%H|%h|%an|%aI|%s"
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
                commits.append(GitCommit(
                    sha=parts[0],
                    short_sha=parts[1],
                    author=parts[2],
                    date=datetime.fromisoformat(parts[3]),
                    message=parts[4]
                ))

        return commits

    async def get_current_branch(self, project_path: Path) -> str:
        """Get current branch name.

        Args:
            project_path: Path to the git repository

        Returns:
            Current branch name
        """
        output = await self._run_git(
            project_path, "branch", "--show-current"
        )
        return output.strip()

    async def stash(
        self,
        project_path: Path,
        message: str | None = None
    ) -> None:
        """Stash current changes.

        Args:
            project_path: Path to the git repository
            message: Optional stash message
        """
        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])

        await self._run_git(project_path, *args)
        self._invalidate_cache(project_path)

    async def stash_pop(self, project_path: Path) -> None:
        """Pop most recent stash.

        Args:
            project_path: Path to the git repository
        """
        await self._run_git(project_path, "stash", "pop")
        self._invalidate_cache(project_path)

    def _invalidate_cache(self, project_path: Path) -> None:
        """Invalidate cached status for a project."""
        cache_key = str(project_path)
        self._status_cache.pop(cache_key, None)

    def _parse_status(self, output: str) -> GitStatus:
        """Parse git status --porcelain=v2 output."""
        status = GitStatus(branch="HEAD")

        for line in output.strip().split("\n"):
            if not line:
                continue

            if line.startswith("# branch.head "):
                status.branch = line.split(" ", 2)[2]
            elif line.startswith("# branch.upstream "):
                status.upstream = line.split(" ", 2)[2]
            elif line.startswith("# branch.ab "):
                parts = line.split(" ")
                for part in parts:
                    if part.startswith("+"):
                        status.ahead = int(part[1:])
                    elif part.startswith("-"):
                        status.behind = int(part[1:])
            elif line.startswith("1 ") or line.startswith("2 "):
                # Changed entry
                parts = line.split(" ")
                xy = parts[1]
                path = parts[-1]

                index_status = xy[0]
                worktree_status = xy[1]

                if index_status != ".":
                    status.staged.append(ChangedFile(
                        path=path,
                        status=FileStatus(index_status),
                        staged=True
                    ))
                if worktree_status != ".":
                    status.unstaged.append(ChangedFile(
                        path=path,
                        status=FileStatus(worktree_status),
                        staged=False
                    ))

                # Check for conflicts
                if "U" in xy:
                    status.has_conflicts = True

            elif line.startswith("? "):
                # Untracked file
                status.untracked.append(line[2:])

        return status

    async def _run_git(self, project_path: Path, *args) -> str:
        """Run a git command.

        Args:
            project_path: Path to the git repository
            *args: Git command arguments

        Returns:
            Command stdout

        Raises:
            GitNotARepoError: If path is not a git repository
            GitCommandError: If command fails
        """
        try:
            result = await asyncio.create_subprocess_exec(
                "git", "-C", str(project_path), *args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                error = stderr.decode()
                if "not a git repository" in error.lower():
                    raise GitNotARepoError(str(project_path))
                raise GitCommandError(error)

            return stdout.decode()

        except FileNotFoundError:
            raise GitCommandError("git not found in PATH")
```

## Status Parsing

The `git status --porcelain=v2 --branch` output format:

| Line prefix | Description |
|-------------|-------------|
| `# branch.oid <sha>` | Current commit SHA |
| `# branch.head <name>` | Current branch name |
| `# branch.upstream <remote/branch>` | Upstream tracking branch |
| `# branch.ab +<ahead> -<behind>` | Commits ahead/behind upstream |
| `1 <XY> ...` | Ordinary changed entry |
| `2 <XY> ...` | Renamed/copied entry |
| `? <path>` | Untracked file |

The XY status codes:
- First character: index (staged) status
- Second character: worktree (unstaged) status
- `.` = unchanged, `M` = modified, `A` = added, `D` = deleted, `R` = renamed, `U` = unmerged

## Caching

- Cache status for 5 seconds by default (configurable via `_cache_ttl`)
- Invalidate cache on any write operation (stage, unstage, commit, pull, stash)
- Use `use_cache=False` to force refresh

## Error Handling

```python
class GitError(Exception):
    """Base class for git errors."""
    pass

class GitNotARepoError(GitError):
    """Raised when path is not a git repository."""
    pass

class GitCommandError(GitError):
    """Raised when a git command fails."""
    pass

class GitPushRejectedError(GitError):
    """Raised when push is rejected by remote."""
    pass

class GitNetworkError(GitError):
    """Raised when network operation fails."""
    pass
```

| Error | Handling |
|-------|----------|
| Not a git repo | Raise `GitNotARepoError` |
| Merge conflicts | Set `GitStatus.has_conflicts = True` |
| Push rejected | Raise `GitPushRejectedError` with details |
| Network error | Raise `GitNetworkError` |
| Command failed | Raise `GitCommandError` with stderr |

## GitStateManager

```python
from textual.message import Message

class GitStatusChanged(Message):
    """Posted when git status changes for a project."""

    def __init__(self, project_id: str, status: GitStatus):
        super().__init__()
        self.project_id = project_id
        self.status = status

class GitStateManager:
    """Manages git status for all open projects."""

    def __init__(self, git_service: GitService):
        self.git_service = git_service
        self.statuses: dict[str, GitStatus] = {}  # project_id -> GitStatus
        self._projects: dict[str, Path] = {}  # project_id -> project_path

    def register_project(self, project_id: str, project_path: Path) -> None:
        """Register a project for git management."""
        self._projects[project_id] = project_path

    def unregister_project(self, project_id: str) -> None:
        """Unregister a project."""
        self._projects.pop(project_id, None)
        self.statuses.pop(project_id, None)

    async def refresh(self, project_id: str) -> GitStatus:
        """Refresh git status for a project.

        Returns:
            Updated GitStatus

        Posts:
            GitStatusChanged message if status changed
        """
        project_path = self._projects.get(project_id)
        if not project_path:
            raise ValueError(f"Unknown project: {project_id}")

        status = await self.git_service.get_status(
            project_path, use_cache=False
        )

        old_status = self.statuses.get(project_id)
        self.statuses[project_id] = status

        # Post message if status changed
        if old_status != status:
            return GitStatusChanged(project_id, status)

        return status

    async def stage_files(
        self,
        project_id: str,
        files: list[str]
    ) -> None:
        """Stage files for a project."""
        project_path = self._projects.get(project_id)
        if not project_path:
            raise ValueError(f"Unknown project: {project_id}")

        await self.git_service.stage_files(project_path, files)
        await self.refresh(project_id)

    async def commit(
        self,
        project_id: str,
        message: str
    ) -> str:
        """Create a commit for a project.

        Returns:
            SHA of the created commit
        """
        project_path = self._projects.get(project_id)
        if not project_path:
            raise ValueError(f"Unknown project: {project_id}")

        sha = await self.git_service.commit(project_path, message)
        await self.refresh(project_id)
        return sha

    async def push(self, project_id: str) -> None:
        """Push current branch for a project."""
        project_path = self._projects.get(project_id)
        if not project_path:
            raise ValueError(f"Unknown project: {project_id}")

        await self.git_service.push(project_path)
        await self.refresh(project_id)

    async def pull(self, project_id: str) -> None:
        """Pull current branch for a project."""
        project_path = self._projects.get(project_id)
        if not project_path:
            raise ValueError(f"Unknown project: {project_id}")

        await self.git_service.pull(project_path)
        await self.refresh(project_id)
```

## TUI Integration

### Git Section Widget

```python
from textual.widgets import Static

class GitSection(Static):
    """Displays git status summary."""

    def __init__(self, project_id: str):
        super().__init__()
        self.project_id = project_id

    def render(self) -> str:
        status = self.app.git_state.statuses.get(self.project_id)
        if not status:
            return "[dim]Git: Not a repository[/dim]"

        parts = [f"[bold]{status.branch}[/bold]"]

        if status.upstream:
            sync = []
            if status.ahead:
                sync.append(f"[green]+{status.ahead}[/green]")
            if status.behind:
                sync.append(f"[red]-{status.behind}[/red]")
            if sync:
                parts.append(" ".join(sync))

        if status.has_conflicts:
            parts.append("[red]CONFLICTS[/red]")

        staged_count = len(status.staged)
        unstaged_count = len(status.unstaged)
        untracked_count = len(status.untracked)

        if staged_count:
            parts.append(f"[green]{staged_count} staged[/green]")
        if unstaged_count:
            parts.append(f"[yellow]{unstaged_count} modified[/yellow]")
        if untracked_count:
            parts.append(f"[dim]{untracked_count} untracked[/dim]")

        return " | ".join(parts)
```

### Git File List Widget

```python
from textual.widgets import OptionList
from textual.widgets.option_list import Option

class GitFileList(OptionList):
    """Shows changed files with checkboxes for staging."""

    def __init__(self, project_id: str):
        super().__init__()
        self.project_id = project_id
        self.selected_files: set[str] = set()

    def update_files(self, status: GitStatus) -> None:
        """Update the file list from git status."""
        self.clear_options()

        # Staged files
        for file in status.staged:
            icon = "[green]S[/green]"
            self.add_option(Option(
                f"{icon} {file.status.value} {file.path}",
                id=f"staged:{file.path}"
            ))

        # Unstaged files
        for file in status.unstaged:
            icon = "[yellow]M[/yellow]"
            self.add_option(Option(
                f"{icon} {file.status.value} {file.path}",
                id=f"unstaged:{file.path}"
            ))

        # Untracked files
        for path in status.untracked:
            icon = "[dim]?[/dim]"
            self.add_option(Option(
                f"{icon} ? {path}",
                id=f"untracked:{path}"
            ))
```

### Git Actions Widget

```python
from textual.widgets import Static, Button
from textual.containers import Horizontal

class GitActions(Horizontal):
    """Provides Commit and Push buttons."""

    def compose(self):
        yield Button("Commit", id="git-commit", variant="primary")
        yield Button("Push", id="git-push")
        yield Button("Pull", id="git-pull")
        yield Button("Stash", id="git-stash")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "git-commit":
            self.app.push_screen(CommitModal())
        elif event.button.id == "git-push":
            await self.app.git_state.push(self.app.current_project_id)
        elif event.button.id == "git-pull":
            await self.app.git_state.pull(self.app.current_project_id)
```

### Commit Modal

```python
from textual.screen import ModalScreen
from textual.widgets import Input, Button, Label
from textual.containers import Vertical

class CommitModal(ModalScreen):
    """Modal for entering commit message."""

    BINDINGS = [
        ("escape", "dismiss", "Cancel"),
    ]

    def compose(self):
        yield Vertical(
            Label("Commit Message"),
            Input(id="commit-message", placeholder="Enter commit message..."),
            Horizontal(
                Button("Commit", id="confirm", variant="primary"),
                Button("Cancel", id="cancel"),
            ),
            classes="modal-content"
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            message = self.query_one("#commit-message", Input).value
            if message.strip():
                await self.app.git_state.commit(
                    self.app.current_project_id,
                    message
                )
                self.dismiss()
        elif event.button.id == "cancel":
            self.dismiss()
```

## Configuration

Per-project `GitConfig` in project configuration:

```python
@dataclass
class GitConfig:
    """Git configuration for a project."""
    auto_stage: bool = False        # Auto-stage all changes before commit
    default_branch: str = "main"    # Default branch name
    remote: str = "origin"          # Default remote name
```

Example project config:

```json
{
  "git": {
    "auto_stage": false,
    "default_branch": "main",
    "remote": "origin"
  }
}
```
