"""Tests for GitHub integration via gh CLI."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iterm_controller.github import (
    GitHubIntegration,
    NetworkError,
    RateLimitError,
)
from iterm_controller.models import GitHubStatus, PullRequest


class TestGitHubIntegrationInitialize:
    """Tests for GitHubIntegration initialization."""

    @pytest.fixture
    def integration(self):
        """Create a fresh GitHubIntegration instance."""
        return GitHubIntegration()

    @pytest.mark.asyncio
    async def test_initialize_gh_available(self, integration):
        """Test successful initialization when gh is available."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await integration.initialize()

        assert result is True
        assert integration.available is True
        assert integration.error_message is None

    @pytest.mark.asyncio
    async def test_initialize_gh_not_installed(self, integration):
        """Test initialization when gh CLI is not installed."""
        with patch(
            "asyncio.create_subprocess_exec", side_effect=FileNotFoundError()
        ):
            result = await integration.initialize()

        assert result is False
        assert integration.available is False
        assert integration.error_message == "gh CLI not installed"

    @pytest.mark.asyncio
    async def test_initialize_gh_not_authenticated(self, integration):
        """Test initialization when gh is not authenticated."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"You are not logged in to any GitHub hosts.")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await integration.initialize()

        assert result is False
        assert integration.available is False
        assert "Not authenticated" in integration.error_message

    @pytest.mark.asyncio
    async def test_initialize_gh_auth_error(self, integration):
        """Test initialization with other gh auth errors."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"Some other error occurred")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await integration.initialize()

        assert result is False
        assert integration.available is False
        assert "gh auth failed" in integration.error_message

    @pytest.mark.asyncio
    async def test_initialize_general_exception(self, integration):
        """Test initialization with unexpected exception."""
        with patch(
            "asyncio.create_subprocess_exec",
            side_effect=Exception("Unexpected error"),
        ):
            result = await integration.initialize()

        assert result is False
        assert integration.available is False
        assert integration.error_message == "Unexpected error"


class TestGitHubIntegrationGetStatus:
    """Tests for get_status method."""

    @pytest.fixture
    def integration(self):
        """Create an initialized GitHubIntegration."""
        gh = GitHubIntegration()
        gh.available = True
        return gh

    @pytest.mark.asyncio
    async def test_get_status_not_available(self):
        """Test get_status returns None when gh is not available."""
        integration = GitHubIntegration()
        integration.available = False

        result = await integration.get_status("/path/to/project")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_status_success(self, integration):
        """Test successful status fetch."""
        with patch.object(
            integration,
            "_fetch_status",
            new_callable=AsyncMock,
            return_value=GitHubStatus(
                available=True,
                current_branch="feature-branch",
                default_branch="main",
                ahead=2,
                behind=1,
            ),
        ):
            result = await integration.get_status("/path/to/project")

        assert result is not None
        assert result.current_branch == "feature-branch"
        assert result.ahead == 2
        assert result.behind == 1
        # Check it was cached
        assert "/path/to/project" in integration.cached_status

    @pytest.mark.asyncio
    async def test_get_status_rate_limit_returns_cached(self, integration):
        """Test rate limit error returns cached status with indicator."""
        # Pre-populate cache
        cached = GitHubStatus(available=True, current_branch="main")
        integration.cached_status["/path/to/project"] = cached

        with patch.object(
            integration,
            "_fetch_status",
            new_callable=AsyncMock,
            side_effect=RateLimitError("rate limited"),
        ):
            result = await integration.get_status("/path/to/project")

        assert result is not None
        assert result.rate_limited is True

    @pytest.mark.asyncio
    async def test_get_status_network_error_returns_cached(self, integration):
        """Test network error returns cached status with indicator."""
        # Pre-populate cache
        cached = GitHubStatus(available=True, current_branch="main")
        integration.cached_status["/path/to/project"] = cached

        with patch.object(
            integration,
            "_fetch_status",
            new_callable=AsyncMock,
            side_effect=NetworkError("connection failed"),
        ):
            result = await integration.get_status("/path/to/project")

        assert result is not None
        assert result.offline is True

    @pytest.mark.asyncio
    async def test_get_status_general_error_returns_cached(self, integration):
        """Test general error returns cached status."""
        # Pre-populate cache
        cached = GitHubStatus(available=True, current_branch="main")
        integration.cached_status["/path/to/project"] = cached

        with patch.object(
            integration,
            "_fetch_status",
            new_callable=AsyncMock,
            side_effect=Exception("unknown error"),
        ):
            result = await integration.get_status("/path/to/project")

        assert result is not None
        assert result.current_branch == "main"

    @pytest.mark.asyncio
    async def test_get_status_error_no_cache(self, integration):
        """Test error with no cached status returns None."""
        with patch.object(
            integration,
            "_fetch_status",
            new_callable=AsyncMock,
            side_effect=Exception("unknown error"),
        ):
            result = await integration.get_status("/path/to/project")

        assert result is None


class TestGitHubIntegrationRunGit:
    """Tests for _run_git method."""

    @pytest.fixture
    def integration(self):
        """Create a GitHubIntegration instance."""
        return GitHubIntegration()

    @pytest.mark.asyncio
    async def test_run_git_success(self, integration):
        """Test successful git command."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b"main\n", b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await integration._run_git(
                "/path/to/project", "branch", "--show-current"
            )

        assert result == "main\n"

    @pytest.mark.asyncio
    async def test_run_git_failure(self, integration):
        """Test git command failure raises exception."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"fatal: not a git repository")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(Exception) as exc_info:
                await integration._run_git("/path/to/project", "status")

        assert "not a git repository" in str(exc_info.value)


class TestGitHubIntegrationRunGh:
    """Tests for _run_gh method."""

    @pytest.fixture
    def integration(self):
        """Create a GitHubIntegration instance."""
        return GitHubIntegration()

    @pytest.mark.asyncio
    async def test_run_gh_success(self, integration):
        """Test successful gh command."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(b'{"number": 123}', b""))

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await integration._run_gh("/path", "pr", "view", "--json", "number")

        assert result == '{"number": 123}'

    @pytest.mark.asyncio
    async def test_run_gh_rate_limit_error(self, integration):
        """Test gh command raises RateLimitError on rate limit."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"API rate limit exceeded")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(RateLimitError):
                await integration._run_gh("/path", "pr", "view")

    @pytest.mark.asyncio
    async def test_run_gh_network_error_connection(self, integration):
        """Test gh command raises NetworkError on connection error."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"connection refused")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(NetworkError):
                await integration._run_gh("/path", "pr", "view")

    @pytest.mark.asyncio
    async def test_run_gh_network_error_resolve(self, integration):
        """Test gh command raises NetworkError on DNS resolution failure."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"Could not resolve host: api.github.com")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(NetworkError):
                await integration._run_gh("/path", "pr", "view")

    @pytest.mark.asyncio
    async def test_run_gh_general_error(self, integration):
        """Test gh command raises Exception on other errors."""
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"Some other error")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(Exception) as exc_info:
                await integration._run_gh("/path", "pr", "view")

        assert "Some other error" in str(exc_info.value)
        assert not isinstance(exc_info.value, (RateLimitError, NetworkError))


class TestGitHubIntegrationBranchMethods:
    """Tests for branch-related methods."""

    @pytest.fixture
    def integration(self):
        """Create a GitHubIntegration instance."""
        return GitHubIntegration()

    @pytest.mark.asyncio
    async def test_get_current_branch(self, integration):
        """Test getting current branch."""
        with patch.object(
            integration,
            "_run_git",
            new_callable=AsyncMock,
            return_value="feature/my-branch\n",
        ):
            result = await integration._get_current_branch("/path")

        assert result == "feature/my-branch"

    @pytest.mark.asyncio
    async def test_get_default_branch_from_remote(self, integration):
        """Test getting default branch from remote HEAD."""
        with patch.object(
            integration,
            "_run_git",
            new_callable=AsyncMock,
            return_value="origin/main\n",
        ):
            result = await integration._get_default_branch("/path")

        assert result == "main"

    @pytest.mark.asyncio
    async def test_get_default_branch_fallback_main(self, integration):
        """Test fallback to main when remote HEAD fails."""
        async def mock_run_git(path, *args):
            if "symbolic-ref" in args:
                raise Exception("no remote HEAD")
            if args == ("branch", "-l", "main"):
                return "  main\n"
            return ""

        with patch.object(integration, "_run_git", side_effect=mock_run_git):
            result = await integration._get_default_branch("/path")

        assert result == "main"

    @pytest.mark.asyncio
    async def test_get_default_branch_fallback_master(self, integration):
        """Test fallback to master when main doesn't exist."""
        async def mock_run_git(path, *args):
            if "symbolic-ref" in args:
                raise Exception("no remote HEAD")
            if args == ("branch", "-l", "main"):
                return ""  # main doesn't exist
            if args == ("branch", "-l", "master"):
                return "  master\n"
            return ""

        with patch.object(integration, "_run_git", side_effect=mock_run_git):
            result = await integration._get_default_branch("/path")

        assert result == "master"

    @pytest.mark.asyncio
    async def test_get_default_branch_default(self, integration):
        """Test default to 'main' when all detection fails."""
        with patch.object(
            integration,
            "_run_git",
            new_callable=AsyncMock,
            side_effect=Exception("failed"),
        ):
            result = await integration._get_default_branch("/path")

        assert result == "main"

    @pytest.mark.asyncio
    async def test_get_sync_status(self, integration):
        """Test getting ahead/behind status."""
        with patch.object(
            integration,
            "_run_git",
            new_callable=AsyncMock,
            return_value="5\t3\n",
        ):
            ahead, behind = await integration._get_sync_status("/path")

        assert ahead == 5
        assert behind == 3

    @pytest.mark.asyncio
    async def test_get_sync_status_no_upstream(self, integration):
        """Test sync status when no upstream is set."""
        with patch.object(
            integration,
            "_run_git",
            new_callable=AsyncMock,
            side_effect=Exception("no upstream"),
        ):
            ahead, behind = await integration._get_sync_status("/path")

        assert ahead == 0
        assert behind == 0


class TestGitHubIntegrationPRMethods:
    """Tests for PR-related methods."""

    @pytest.fixture
    def integration(self):
        """Create a GitHubIntegration instance."""
        return GitHubIntegration()

    @pytest.mark.asyncio
    async def test_get_pr_info_success(self, integration):
        """Test getting PR info successfully."""
        pr_data = {
            "number": 123,
            "title": "Add feature X",
            "url": "https://github.com/owner/repo/pull/123",
            "state": "OPEN",
            "isDraft": False,
            "comments": [{"body": "comment 1"}, {"body": "comment 2"}],
            "reviewDecision": "REVIEW_REQUIRED",
        }

        with patch.object(
            integration,
            "_run_gh",
            new_callable=AsyncMock,
            return_value=json.dumps(pr_data),
        ):
            with patch.object(
                integration,
                "_get_checks_status",
                new_callable=AsyncMock,
                return_value=True,
            ):
                result = await integration._get_pr_info("/path")

        assert result is not None
        assert result.number == 123
        assert result.title == "Add feature X"
        assert result.url == "https://github.com/owner/repo/pull/123"
        assert result.state == "OPEN"
        assert result.draft is False
        assert result.comments == 2
        assert result.reviews_pending == 1
        assert result.checks_passing is True

    @pytest.mark.asyncio
    async def test_get_pr_info_merged(self, integration):
        """Test getting merged PR info."""
        pr_data = {
            "number": 456,
            "title": "Fix bug",
            "url": "https://github.com/owner/repo/pull/456",
            "state": "MERGED",
            "isDraft": False,
            "comments": [],
            "reviewDecision": "",
        }

        with patch.object(
            integration,
            "_run_gh",
            new_callable=AsyncMock,
            return_value=json.dumps(pr_data),
        ):
            with patch.object(
                integration,
                "_get_checks_status",
                new_callable=AsyncMock,
                return_value=True,
            ):
                result = await integration._get_pr_info("/path")

        assert result is not None
        assert result.merged is True
        assert result.state == "MERGED"

    @pytest.mark.asyncio
    async def test_get_pr_info_draft(self, integration):
        """Test getting draft PR info."""
        pr_data = {
            "number": 789,
            "title": "WIP: New feature",
            "url": "https://github.com/owner/repo/pull/789",
            "state": "OPEN",
            "isDraft": True,
            "comments": [],
            "reviewDecision": "",
        }

        with patch.object(
            integration,
            "_run_gh",
            new_callable=AsyncMock,
            return_value=json.dumps(pr_data),
        ):
            with patch.object(
                integration,
                "_get_checks_status",
                new_callable=AsyncMock,
                return_value=None,
            ):
                result = await integration._get_pr_info("/path")

        assert result is not None
        assert result.draft is True

    @pytest.mark.asyncio
    async def test_get_pr_info_no_pr(self, integration):
        """Test getting PR info when no PR exists."""
        with patch.object(
            integration,
            "_run_gh",
            new_callable=AsyncMock,
            side_effect=Exception("no pull requests found"),
        ):
            result = await integration._get_pr_info("/path")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_checks_status_all_pass(self, integration):
        """Test checks status when all pass."""
        with patch.object(
            integration,
            "_run_gh",
            new_callable=AsyncMock,
            return_value="All checks were successful",
        ):
            result = await integration._get_checks_status("/path")

        assert result is True

    @pytest.mark.asyncio
    async def test_get_checks_status_some_fail(self, integration):
        """Test checks status when some fail."""
        with patch.object(
            integration,
            "_run_gh",
            new_callable=AsyncMock,
            return_value="Some checks were not successful",
        ):
            result = await integration._get_checks_status("/path")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_checks_status_individual_pass(self, integration):
        """Test checks status parsing individual check lines."""
        output = """build\tpass\t1m2s
lint\tpass\t30s
test\tpass\t5m"""

        with patch.object(
            integration,
            "_run_gh",
            new_callable=AsyncMock,
            return_value=output,
        ):
            result = await integration._get_checks_status("/path")

        assert result is True

    @pytest.mark.asyncio
    async def test_get_checks_status_individual_fail(self, integration):
        """Test checks status with failing check in output."""
        output = """build\tpass\t1m2s
lint\tfail\t30s
test\tpass\t5m"""

        with patch.object(
            integration,
            "_run_gh",
            new_callable=AsyncMock,
            return_value=output,
        ):
            result = await integration._get_checks_status("/path")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_checks_status_error(self, integration):
        """Test checks status on error."""
        with patch.object(
            integration,
            "_run_gh",
            new_callable=AsyncMock,
            side_effect=Exception("no checks"),
        ):
            result = await integration._get_checks_status("/path")

        assert result is None


class TestGitHubIntegrationWorkflowRuns:
    """Tests for workflow runs."""

    @pytest.fixture
    def integration(self):
        """Create an initialized GitHubIntegration."""
        gh = GitHubIntegration()
        gh.available = True
        return gh

    @pytest.mark.asyncio
    async def test_get_workflow_runs_not_available(self):
        """Test workflow runs when gh not available."""
        integration = GitHubIntegration()
        integration.available = False

        result = await integration.get_workflow_runs("/path")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_workflow_runs_success(self, integration):
        """Test getting workflow runs successfully."""
        runs_data = [
            {
                "databaseId": 123,
                "name": "CI",
                "status": "completed",
                "conclusion": "success",
                "createdAt": "2024-01-15T10:00:00Z",
                "headBranch": "main",
            },
            {
                "databaseId": 124,
                "name": "Deploy",
                "status": "in_progress",
                "conclusion": None,
                "createdAt": "2024-01-15T10:05:00Z",
                "headBranch": "main",
            },
        ]

        with patch.object(
            integration,
            "_run_gh",
            new_callable=AsyncMock,
            return_value=json.dumps(runs_data),
        ):
            result = await integration.get_workflow_runs("/path", limit=5)

        assert len(result) == 2
        assert result[0]["id"] == 123
        assert result[0]["name"] == "CI"
        assert result[0]["status"] == "completed"
        assert result[0]["conclusion"] == "success"
        assert result[1]["conclusion"] is None

    @pytest.mark.asyncio
    async def test_get_workflow_runs_error(self, integration):
        """Test workflow runs on error returns empty list."""
        with patch.object(
            integration,
            "_run_gh",
            new_callable=AsyncMock,
            side_effect=Exception("failed"),
        ):
            result = await integration.get_workflow_runs("/path")

        assert result == []


class TestGitHubIntegrationCache:
    """Tests for cache management."""

    @pytest.fixture
    def integration(self):
        """Create a GitHubIntegration with cached data."""
        gh = GitHubIntegration()
        gh.cached_status = {
            "/path/project1": GitHubStatus(current_branch="main"),
            "/path/project2": GitHubStatus(current_branch="develop"),
        }
        return gh

    def test_clear_cache_specific_project(self, integration):
        """Test clearing cache for specific project."""
        integration.clear_cache("/path/project1")

        assert "/path/project1" not in integration.cached_status
        assert "/path/project2" in integration.cached_status

    def test_clear_cache_all(self, integration):
        """Test clearing all cache."""
        integration.clear_cache()

        assert len(integration.cached_status) == 0

    def test_clear_cache_nonexistent_project(self, integration):
        """Test clearing cache for non-existent project doesn't error."""
        integration.clear_cache("/path/nonexistent")

        # Original entries should still exist
        assert len(integration.cached_status) == 2


class TestFetchStatus:
    """Tests for _fetch_status integration."""

    @pytest.fixture
    def integration(self):
        """Create a GitHubIntegration instance."""
        return GitHubIntegration()

    @pytest.mark.asyncio
    async def test_fetch_status_full_flow(self, integration):
        """Test full status fetch flow."""
        with patch.object(
            integration,
            "_get_current_branch",
            new_callable=AsyncMock,
            return_value="feature-x",
        ):
            with patch.object(
                integration,
                "_get_default_branch",
                new_callable=AsyncMock,
                return_value="main",
            ):
                with patch.object(
                    integration,
                    "_get_sync_status",
                    new_callable=AsyncMock,
                    return_value=(3, 1),
                ):
                    with patch.object(
                        integration,
                        "_get_pr_info",
                        new_callable=AsyncMock,
                        return_value=PullRequest(
                            number=100,
                            title="Feature X",
                            url="https://github.com/o/r/pull/100",
                            state="OPEN",
                        ),
                    ):
                        result = await integration._fetch_status("/path")

        assert result.available is True
        assert result.current_branch == "feature-x"
        assert result.default_branch == "main"
        assert result.ahead == 3
        assert result.behind == 1
        assert result.pr is not None
        assert result.pr.number == 100
        assert result.last_updated is not None


class TestGracefulDegradation:
    """Tests for graceful degradation behavior."""

    @pytest.mark.asyncio
    async def test_degradation_gh_not_installed(self):
        """Test app works when gh is not installed."""
        integration = GitHubIntegration()

        with patch(
            "asyncio.create_subprocess_exec", side_effect=FileNotFoundError()
        ):
            await integration.initialize()

        assert integration.available is False
        assert integration.error_message == "gh CLI not installed"

        # Should return None, not raise
        result = await integration.get_status("/path")
        assert result is None

    @pytest.mark.asyncio
    async def test_degradation_gh_not_authenticated(self):
        """Test app works when gh is not authenticated."""
        integration = GitHubIntegration()

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(
            return_value=(b"", b"not logged in")
        )

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            await integration.initialize()

        assert integration.available is False
        assert "Not authenticated" in integration.error_message

        # Should return None, not raise
        result = await integration.get_status("/path")
        assert result is None

    @pytest.mark.asyncio
    async def test_degradation_rate_limited_with_cache(self):
        """Test returns cached data when rate limited."""
        integration = GitHubIntegration()
        integration.available = True

        # Pre-populate cache
        cached = GitHubStatus(
            available=True,
            current_branch="main",
            ahead=5,
        )
        integration.cached_status["/path"] = cached

        with patch.object(
            integration,
            "_fetch_status",
            new_callable=AsyncMock,
            side_effect=RateLimitError("limited"),
        ):
            result = await integration.get_status("/path")

        assert result is not None
        assert result.current_branch == "main"
        assert result.ahead == 5
        assert result.rate_limited is True

    @pytest.mark.asyncio
    async def test_degradation_offline_with_cache(self):
        """Test returns cached data when offline."""
        integration = GitHubIntegration()
        integration.available = True

        # Pre-populate cache
        cached = GitHubStatus(
            available=True,
            current_branch="develop",
        )
        integration.cached_status["/path"] = cached

        with patch.object(
            integration,
            "_fetch_status",
            new_callable=AsyncMock,
            side_effect=NetworkError("offline"),
        ):
            result = await integration.get_status("/path")

        assert result is not None
        assert result.current_branch == "develop"
        assert result.offline is True
