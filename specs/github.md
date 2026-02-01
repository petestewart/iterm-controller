# GitHub Integration

## Overview

Integration with GitHub via the `gh` CLI for branch sync status, PR information, and workflow runs.

## Design Principles

1. **Graceful degradation** - App works without GitHub integration
2. **No token management** - Leverages existing `gh auth`
3. **Caching** - Show stale data during errors/rate limits
4. **Minimal API calls** - Respect rate limits

## Availability Check

```python
import asyncio
import subprocess
import json

async def check_gh_available() -> tuple[bool, str | None]:
    """Check if gh CLI is available and authenticated.

    Returns:
        (available, error_message) tuple
    """
    try:
        result = await asyncio.create_subprocess_exec(
            "gh", "auth", "status",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await result.communicate()

        if result.returncode == 0:
            return (True, None)
        return (False, "Not authenticated. Run: gh auth login")
    except FileNotFoundError:
        return (False, "gh CLI not installed")
    except Exception as e:
        return (False, str(e))
```

## GitHub Integration Class

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class GitHubIntegration:
    """Wrapper for GitHub operations via gh CLI."""

    available: bool = False
    error_message: str | None = None
    cached_status: dict[str, "GitHubStatus"] = None

    def __post_init__(self):
        self.cached_status = {}

    async def initialize(self) -> bool:
        """Initialize integration, checking availability."""
        self.available, self.error_message = await check_gh_available()
        return self.available

    async def get_status(self, project: "Project") -> "GitHubStatus | None":
        """Get GitHub status for a project.

        Returns cached status on error.
        """
        if not self.available:
            return None

        try:
            status = await self._fetch_status(project)
            self.cached_status[project.id] = status
            return status
        except RateLimitError:
            # Return cached with rate limit indicator
            cached = self.cached_status.get(project.id)
            if cached:
                cached.rate_limited = True
            return cached
        except NetworkError:
            # Return cached with offline indicator
            cached = self.cached_status.get(project.id)
            if cached:
                cached.offline = True
            return cached
        except Exception as e:
            return self.cached_status.get(project.id)

    async def _fetch_status(self, project: "Project") -> "GitHubStatus":
        """Fetch current GitHub status."""
        status = GitHubStatus(available=True)

        # Get current branch
        status.current_branch = await self._get_current_branch(project.path)

        # Get ahead/behind counts
        ahead, behind = await self._get_sync_status(project.path)
        status.ahead = ahead
        status.behind = behind

        # Get PR info
        status.pr = await self._get_pr_info(project.path)

        status.last_updated = datetime.now()
        return status

    async def _get_current_branch(self, path: str) -> str:
        """Get current git branch."""
        result = await self._run_git(path, "branch", "--show-current")
        return result.strip()

    async def _get_sync_status(self, path: str) -> tuple[int, int]:
        """Get ahead/behind commit counts."""
        try:
            result = await self._run_git(
                path, "rev-list", "--left-right", "--count", "HEAD...@{upstream}"
            )
            ahead, behind = result.strip().split("\t")
            return int(ahead), int(behind)
        except:
            return 0, 0

    async def _get_pr_info(self, path: str) -> "PullRequest | None":
        """Get PR info for current branch."""
        try:
            result = await self._run_gh(
                path,
                "pr", "view", "--json",
                "number,title,url,state,isDraft,comments,reviewDecision"
            )
            data = json.loads(result)

            return PullRequest(
                number=data["number"],
                title=data["title"],
                url=data["url"],
                state=data["state"],
                draft=data.get("isDraft", False),
                comments=len(data.get("comments", [])),
                merged=data["state"] == "MERGED",
                checks_passing=await self._get_checks_status(path)
            )
        except:
            return None

    async def _get_checks_status(self, path: str) -> bool | None:
        """Get status of PR checks."""
        try:
            result = await self._run_gh(path, "pr", "checks")
            # Parse checks output
            if "All checks were successful" in result:
                return True
            elif "Some checks were not successful" in result:
                return False
            return None
        except:
            return None

    async def _run_git(self, path: str, *args) -> str:
        """Run a git command."""
        result = await asyncio.create_subprocess_exec(
            "git", "-C", path, *args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, _ = await result.communicate()
        return stdout.decode()

    async def _run_gh(self, path: str, *args) -> str:
        """Run a gh command."""
        result = await asyncio.create_subprocess_exec(
            "gh", *args,
            cwd=path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = await result.communicate()

        if result.returncode != 0:
            error = stderr.decode()
            if "rate limit" in error.lower():
                raise RateLimitError(error)
            raise Exception(error)

        return stdout.decode()
```

## Degradation Behavior

| State | UI Behavior |
|-------|-------------|
| `gh` not installed | GitHub panel hidden, no errors shown |
| `gh` not authenticated | GitHub panel shows "Not authenticated" with hint |
| `gh` authenticated | Full functionality |
| API rate limited | Show cached data with "Rate limited" indicator |
| Network error | Show cached data with "Offline" indicator |

## GitHub Status Widget

```python
class GitHubPanelWidget(Static):
    """Displays GitHub status with graceful degradation."""

    def render(self) -> str:
        status = self.app.state.github_status

        # Not available - hide panel
        if not status or not status.available:
            if status and status.error_message:
                return f"[dim]GitHub: {status.error_message}[/dim]"
            return ""

        lines = []

        # Status indicators
        if status.rate_limited:
            lines.append("[yellow]⚠ Rate limited - showing cached data[/yellow]")
        elif status.offline:
            lines.append("[yellow]⚠ Offline - showing cached data[/yellow]")

        # Branch info
        lines.append(f"Branch: {status.current_branch}")

        sync = []
        if status.ahead:
            sync.append(f"↑{status.ahead}")
        if status.behind:
            sync.append(f"↓{status.behind}")
        if sync:
            lines.append(f"{' '.join(sync)} from {status.default_branch}")

        # PR info
        if status.pr:
            lines.append("")
            pr = status.pr

            title = f"PR #{pr.number}: {pr.title}"
            if pr.draft:
                title += " [Draft]"
            lines.append(title)

            if pr.merged:
                lines.append("[green]✓ Merged[/green]")
            elif pr.checks_passing is True:
                lines.append("[green]● Checks passing[/green]")
            elif pr.checks_passing is False:
                lines.append("[red]✗ Checks failing[/red]")

            if pr.reviews_pending:
                lines.append(f"{pr.reviews_pending} reviews pending")

        return "\n".join(lines)
```

## GitHub Actions Modal

```python
class GitHubActionsModal(ModalScreen):
    """View GitHub Actions workflow runs."""

    BINDINGS = [
        ("r", "refresh", "Refresh"),
        ("escape", "dismiss", "Close"),
    ]

    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        self.runs: list[WorkflowRun] = []

    async def on_mount(self):
        await self.load_runs()

    async def load_runs(self):
        """Load recent workflow runs."""
        try:
            result = await self.app.github._run_gh(
                self.project.path,
                "run", "list", "--limit", "10", "--json",
                "databaseId,name,status,conclusion,createdAt,headBranch"
            )
            data = json.loads(result)
            self.runs = [
                WorkflowRun(
                    id=r["databaseId"],
                    name=r["name"],
                    status=r["status"],
                    conclusion=r.get("conclusion"),
                    created_at=r["createdAt"],
                    branch=r["headBranch"]
                )
                for r in data
            ]
            self.refresh()
        except Exception as e:
            self.notify(f"Failed to load runs: {e}", severity="error")

    def compose(self) -> ComposeResult:
        yield Container(
            Static("GitHub Actions", classes="modal-title"),
            DataTable(id="runs-table"),
            Horizontal(
                Button("[R] Refresh", id="refresh"),
                Button("[Esc] Close", id="close"),
            ),
            classes="modal-content"
        )

    def on_mount(self):
        table = self.query_one("#runs-table", DataTable)
        table.add_columns("Workflow", "Branch", "Status", "Time")

        for run in self.runs:
            status_icon = {
                "success": "[green]✓[/green]",
                "failure": "[red]✗[/red]",
                "in_progress": "[yellow]●[/yellow]",
            }.get(run.conclusion or run.status, "○")

            table.add_row(
                run.name,
                run.branch,
                status_icon,
                run.created_at
            )

@dataclass
class WorkflowRun:
    """GitHub Actions workflow run."""
    id: int
    name: str
    status: str
    conclusion: str | None
    created_at: str
    branch: str
```

## Error Types

```python
class RateLimitError(Exception):
    """Raised when GitHub API rate limit is hit."""
    pass

class NetworkError(Exception):
    """Raised when network connection fails."""
    pass
```
