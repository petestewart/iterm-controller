"""Tests for GitService."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iterm_controller.exceptions import (
    GitCommandError,
    GitNetworkError,
    GitNotARepoError,
    GitPushRejectedError,
)
from iterm_controller.git_service import GitService
from iterm_controller.models import GitCommit, GitFileStatus, GitStatus


class TestGitServiceStatus:
    """Tests for git status functionality."""

    @pytest.fixture
    def service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    @pytest.mark.asyncio
    async def test_get_status_parses_branch(self, service: GitService, tmp_path: Path):
        """Test parsing branch name from status."""
        porcelain_output = "# branch.head main\n# branch.ab +0 -0\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            status = await service.get_status(tmp_path)

            assert status.branch == "main"
            assert status.ahead == 0
            assert status.behind == 0

    @pytest.mark.asyncio
    async def test_get_status_parses_ahead_behind(
        self, service: GitService, tmp_path: Path
    ):
        """Test parsing ahead/behind counts."""
        porcelain_output = "# branch.head feature\n# branch.ab +5 -3\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            status = await service.get_status(tmp_path)

            assert status.branch == "feature"
            assert status.ahead == 5
            assert status.behind == 3

    @pytest.mark.asyncio
    async def test_get_status_parses_staged_files(
        self, service: GitService, tmp_path: Path
    ):
        """Test parsing staged files."""
        porcelain_output = """# branch.head main
# branch.ab +0 -0
1 M. N... 100644 100644 100644 abc123 def456 staged_file.py
"""

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            status = await service.get_status(tmp_path)

            assert status.staged is not None
            assert len(status.staged) == 1
            assert status.staged[0].path == "staged_file.py"
            assert status.staged[0].status == "M"
            assert status.staged[0].staged is True

    @pytest.mark.asyncio
    async def test_get_status_parses_unstaged_files(
        self, service: GitService, tmp_path: Path
    ):
        """Test parsing unstaged files."""
        porcelain_output = """# branch.head main
# branch.ab +0 -0
1 .M N... 100644 100644 100644 abc123 def456 modified_file.py
"""

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            status = await service.get_status(tmp_path)

            assert status.unstaged is not None
            assert len(status.unstaged) == 1
            assert status.unstaged[0].path == "modified_file.py"
            assert status.unstaged[0].status == "M"
            assert status.unstaged[0].staged is False

    @pytest.mark.asyncio
    async def test_get_status_parses_untracked_files(
        self, service: GitService, tmp_path: Path
    ):
        """Test parsing untracked files."""
        porcelain_output = """# branch.head main
# branch.ab +0 -0
? new_file.py
"""

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            status = await service.get_status(tmp_path)

            assert status.untracked is not None
            assert len(status.untracked) == 1
            assert status.untracked[0].path == "new_file.py"
            assert status.untracked[0].status == "?"

    @pytest.mark.asyncio
    async def test_get_status_parses_mixed_changes(
        self, service: GitService, tmp_path: Path
    ):
        """Test parsing a mix of staged, unstaged, and untracked files."""
        porcelain_output = """# branch.head develop
# branch.ab +2 -1
1 A. N... 100644 100644 100644 abc123 def456 new_staged.py
1 .M N... 100644 100644 100644 ghi789 jkl012 modified.py
1 MM N... 100644 100644 100644 mno345 pqr678 both_changed.py
? untracked.txt
"""

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            status = await service.get_status(tmp_path)

            assert status.branch == "develop"
            assert status.ahead == 2
            assert status.behind == 1

            # Staged files
            assert status.staged is not None
            assert len(status.staged) == 2  # new_staged.py and both_changed.py (index)

            # Unstaged files
            assert status.unstaged is not None
            assert len(status.unstaged) == 2  # modified.py and both_changed.py (worktree)

            # Untracked files
            assert status.untracked is not None
            assert len(status.untracked) == 1

    @pytest.mark.asyncio
    async def test_get_status_detects_conflicts(
        self, service: GitService, tmp_path: Path
    ):
        """Test detecting merge conflicts."""
        porcelain_output = """# branch.head main
# branch.ab +0 -0
1 UU N... 100644 100644 100644 abc123 def456 conflicted.py
"""

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            status = await service.get_status(tmp_path)

            assert status.has_conflicts is True

    @pytest.mark.asyncio
    async def test_get_status_uses_cache(self, service: GitService, tmp_path: Path):
        """Test that status is cached."""
        porcelain_output = "# branch.head main\n# branch.ab +0 -0\n"
        log_output = "abc123|First commit\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [porcelain_output, log_output]  # status + log

            # First call
            await service.get_status(tmp_path)
            # Second call should use cache
            await service.get_status(tmp_path)

            # Only two git commands for first call (status + log), none for second (cached)
            assert mock_run.call_count == 2

    @pytest.mark.asyncio
    async def test_get_status_bypasses_cache(self, service: GitService, tmp_path: Path):
        """Test that cache can be bypassed."""
        porcelain_output = "# branch.head main\n# branch.ab +0 -0\n"
        log_output = "abc123|First commit\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                porcelain_output,
                log_output,
                porcelain_output,
                log_output,
            ]

            # First call
            await service.get_status(tmp_path)
            # Second call with use_cache=False
            await service.get_status(tmp_path, use_cache=False)

            # Four git commands: status + log for each call (cache bypassed)
            assert mock_run.call_count == 4

    @pytest.mark.asyncio
    async def test_get_status_cache_expires(self, tmp_path: Path):
        """Test that cache expires after TTL."""
        service = GitService(cache_ttl=timedelta(seconds=0))  # Immediate expiry
        porcelain_output = "# branch.head main\n# branch.ab +0 -0\n"
        log_output = "abc123|First commit\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                porcelain_output,
                log_output,
                porcelain_output,
                log_output,
            ]

            await service.get_status(tmp_path)
            await service.get_status(tmp_path)

            # Both calls should hit git since cache expired (status + log each)
            assert mock_run.call_count == 4


class TestGitServiceOperations:
    """Tests for git operations."""

    @pytest.fixture
    def service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    @pytest.mark.asyncio
    async def test_stage_files_specific(self, service: GitService, tmp_path: Path):
        """Test staging specific files."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""

            await service.stage_files(tmp_path, ["file1.py", "file2.py"])

            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            assert "add" in args
            assert "--" in args
            assert "file1.py" in args
            assert "file2.py" in args

    @pytest.mark.asyncio
    async def test_stage_files_all(self, service: GitService, tmp_path: Path):
        """Test staging all files."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""

            await service.stage_files(tmp_path)

            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            assert "add" in args
            assert "-A" in args

    @pytest.mark.asyncio
    async def test_stage_files_invalidates_cache(
        self, service: GitService, tmp_path: Path
    ):
        """Test that staging invalidates status cache."""
        porcelain_output = "# branch.head main\n# branch.ab +0 -0\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            # Populate cache
            await service.get_status(tmp_path)
            assert len(service._status_cache) == 1

            # Stage files
            mock_run.return_value = ""
            await service.stage_files(tmp_path, ["file.py"])

            # Cache should be invalidated
            cache_key = str(tmp_path.resolve())
            assert cache_key not in service._status_cache

    @pytest.mark.asyncio
    async def test_unstage_files_specific(self, service: GitService, tmp_path: Path):
        """Test unstaging specific files."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""

            await service.unstage_files(tmp_path, ["file1.py"])

            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            assert "restore" in args
            assert "--staged" in args
            assert "file1.py" in args

    @pytest.mark.asyncio
    async def test_unstage_files_all(self, service: GitService, tmp_path: Path):
        """Test unstaging all files."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""

            await service.unstage_files(tmp_path)

            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            assert "restore" in args
            assert "--staged" in args
            assert "." in args

    @pytest.mark.asyncio
    async def test_commit(self, service: GitService, tmp_path: Path):
        """Test creating a commit."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                "",  # commit command
                "abc123def456\n",  # rev-parse HEAD
            ]

            sha = await service.commit(tmp_path, "Test commit")

            assert sha == "abc123def456"
            assert mock_run.call_count == 2

    @pytest.mark.asyncio
    async def test_commit_amend(self, service: GitService, tmp_path: Path):
        """Test amending a commit."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                "",  # commit command
                "abc123\n",  # rev-parse HEAD
            ]

            await service.commit(tmp_path, "Amended message", amend=True)

            args = mock_run.call_args_list[0][0]
            assert "--amend" in args

    @pytest.mark.asyncio
    async def test_push(self, service: GitService, tmp_path: Path):
        """Test pushing to remote."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""

            await service.push(tmp_path)

            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            assert "push" in args
            assert "origin" in args

    @pytest.mark.asyncio
    async def test_push_force(self, service: GitService, tmp_path: Path):
        """Test force pushing."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""

            await service.push(tmp_path, force=True)

            args = mock_run.call_args[0]
            assert "--force-with-lease" in args

    @pytest.mark.asyncio
    async def test_push_set_upstream(self, service: GitService, tmp_path: Path):
        """Test pushing with set upstream."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""

            await service.push(tmp_path, set_upstream=True)

            args = mock_run.call_args[0]
            assert "-u" in args

    @pytest.mark.asyncio
    async def test_push_rejected_error(self, service: GitService, tmp_path: Path):
        """Test handling push rejection."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = GitCommandError("Push rejected: non-fast-forward")

            with pytest.raises(GitPushRejectedError):
                await service.push(tmp_path)

    @pytest.mark.asyncio
    async def test_pull(self, service: GitService, tmp_path: Path):
        """Test pulling from remote."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""

            await service.pull(tmp_path)

            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            assert "pull" in args
            assert "origin" in args

    @pytest.mark.asyncio
    async def test_pull_network_error(self, service: GitService, tmp_path: Path):
        """Test handling network errors during pull."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = GitCommandError("Network is unreachable")

            with pytest.raises(GitNetworkError):
                await service.pull(tmp_path)

    @pytest.mark.asyncio
    async def test_fetch(self, service: GitService, tmp_path: Path):
        """Test fetching from remote."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""

            await service.fetch(tmp_path)

            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            assert "fetch" in args
            assert "origin" in args

    @pytest.mark.asyncio
    async def test_get_log(self, service: GitService, tmp_path: Path):
        """Test getting commit log."""
        log_output = """abc123full|abc123|John Doe|2024-01-15T10:30:00+00:00|First commit
def456full|def456|Jane Smith|2024-01-16T11:45:00+00:00|Second commit"""

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = log_output

            commits = await service.get_log(tmp_path, limit=5)

            assert len(commits) == 2
            assert commits[0].sha == "abc123full"
            assert commits[0].short_sha == "abc123"
            assert commits[0].author == "John Doe"
            assert commits[0].message == "First commit"
            assert commits[1].message == "Second commit"

    @pytest.mark.asyncio
    async def test_get_log_since_branch(self, service: GitService, tmp_path: Path):
        """Test getting log since a branch."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""

            await service.get_log(tmp_path, since_branch="main")

            args = mock_run.call_args[0]
            assert "main..HEAD" in args

    @pytest.mark.asyncio
    async def test_get_current_branch(self, service: GitService, tmp_path: Path):
        """Test getting current branch name."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "feature-branch\n"

            branch = await service.get_current_branch(tmp_path)

            assert branch == "feature-branch"

    @pytest.mark.asyncio
    async def test_stash(self, service: GitService, tmp_path: Path):
        """Test stashing changes."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""

            await service.stash(tmp_path, message="WIP: testing")

            args = mock_run.call_args[0]
            assert "stash" in args
            assert "push" in args
            assert "-m" in args
            assert "WIP: testing" in args

    @pytest.mark.asyncio
    async def test_stash_pop(self, service: GitService, tmp_path: Path):
        """Test popping stash."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""

            await service.stash_pop(tmp_path)

            args = mock_run.call_args[0]
            assert "stash" in args
            assert "pop" in args

    @pytest.mark.asyncio
    async def test_is_git_repo_true(self, service: GitService, tmp_path: Path):
        """Test detecting a git repository."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ".git\n"

            result = await service.is_git_repo(tmp_path)

            assert result is True

    @pytest.mark.asyncio
    async def test_is_git_repo_false(self, service: GitService, tmp_path: Path):
        """Test detecting a non-repository."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = GitNotARepoError("Not a git repo")

            result = await service.is_git_repo(tmp_path)

            assert result is False


class TestGitServiceErrors:
    """Tests for error handling."""

    @pytest.fixture
    def service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    @pytest.mark.asyncio
    async def test_not_a_repo_error(self, service: GitService, tmp_path: Path):
        """Test GitNotARepoError is raised for non-repos."""
        with patch(
            "asyncio.create_subprocess_exec", new_callable=AsyncMock
        ) as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 128
            mock_process.communicate.return_value = (
                b"",
                b"fatal: not a git repository",
            )
            mock_exec.return_value = mock_process

            with pytest.raises(GitNotARepoError):
                await service.get_status(tmp_path)

    @pytest.mark.asyncio
    async def test_command_error(self, service: GitService, tmp_path: Path):
        """Test GitCommandError is raised for failed commands."""
        with patch(
            "asyncio.create_subprocess_exec", new_callable=AsyncMock
        ) as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate.return_value = (b"", b"fatal: some error")
            mock_exec.return_value = mock_process

            with pytest.raises(GitCommandError):
                await service.get_status(tmp_path)

    @pytest.mark.asyncio
    async def test_git_not_found_error(self, service: GitService, tmp_path: Path):
        """Test GitCommandError when git is not installed."""
        with patch(
            "asyncio.create_subprocess_exec", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.side_effect = FileNotFoundError("git not found")

            with pytest.raises(GitCommandError) as exc_info:
                await service.get_status(tmp_path)

            assert "not found" in str(exc_info.value).lower()


class TestGitServiceDiff:
    """Tests for diff functionality."""

    @pytest.fixture
    def service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    @pytest.mark.asyncio
    async def test_get_diff_all(self, service: GitService, tmp_path: Path):
        """Test getting all diff."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "diff output"

            diff = await service.get_diff(tmp_path)

            assert diff == "diff output"
            args = mock_run.call_args[0]
            assert "diff" in args

    @pytest.mark.asyncio
    async def test_get_diff_staged(self, service: GitService, tmp_path: Path):
        """Test getting staged diff."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "staged diff"

            diff = await service.get_diff(tmp_path, staged_only=True)

            assert diff == "staged diff"
            args = mock_run.call_args[0]
            assert "--cached" in args

    @pytest.mark.asyncio
    async def test_get_diff_against_branch(self, service: GitService, tmp_path: Path):
        """Test getting diff against a branch."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = "branch diff"

            diff = await service.get_diff(tmp_path, base_branch="main")

            assert diff == "branch diff"
            args = mock_run.call_args[0]
            assert "main...HEAD" in args


class TestGitServiceCacheManagement:
    """Tests for cache management."""

    @pytest.fixture
    def service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    @pytest.mark.asyncio
    async def test_clear_cache(self, service: GitService, tmp_path: Path):
        """Test clearing all cache."""
        porcelain_output = "# branch.head main\n# branch.ab +0 -0\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            await service.get_status(tmp_path)
            assert len(service._status_cache) == 1

            service.clear_cache()
            assert len(service._status_cache) == 0

    @pytest.mark.asyncio
    async def test_invalidate_cache(self, service: GitService, tmp_path: Path):
        """Test invalidating cache for specific path."""
        porcelain_output = "# branch.head main\n# branch.ab +0 -0\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            await service.get_status(tmp_path)
            cache_key = str(tmp_path.resolve())
            assert cache_key in service._status_cache

            service._invalidate_cache(tmp_path)
            assert cache_key not in service._status_cache


class TestGitServiceLastCommit:
    """Tests for last commit info in status."""

    @pytest.fixture
    def service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    @pytest.mark.asyncio
    async def test_get_status_includes_last_commit(
        self, service: GitService, tmp_path: Path
    ):
        """Test that get_status includes last commit info."""
        porcelain_output = "# branch.head main\n# branch.ab +0 -0\n"
        log_output = "abc123def456789|Fix important bug\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [porcelain_output, log_output]

            status = await service.get_status(tmp_path)

            assert status.last_commit_sha == "abc123def456789"
            assert status.last_commit_message == "Fix important bug"

    @pytest.mark.asyncio
    async def test_get_status_handles_no_commits(
        self, service: GitService, tmp_path: Path
    ):
        """Test that get_status handles empty repos with no commits."""
        porcelain_output = "# branch.head main\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            # First call is status, second is log which fails for empty repo
            mock_run.side_effect = [
                porcelain_output,
                GitCommandError("fatal: your current branch 'main' does not have any commits yet"),
            ]

            status = await service.get_status(tmp_path)

            assert status.branch == "main"
            assert status.last_commit_sha is None
            assert status.last_commit_message is None

    @pytest.mark.asyncio
    async def test_get_status_sets_fetched_at(
        self, service: GitService, tmp_path: Path
    ):
        """Test that get_status sets fetched_at timestamp."""
        porcelain_output = "# branch.head main\n# branch.ab +0 -0\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            status = await service.get_status(tmp_path)

            assert status.fetched_at is not None
            # Fetched time should be recent (within last second)
            assert (datetime.now() - status.fetched_at).total_seconds() < 1


class TestGitServiceNetworkErrors:
    """Tests for network error handling."""

    @pytest.fixture
    def service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    @pytest.mark.asyncio
    async def test_fetch_network_error_could_not_resolve(
        self, service: GitService, tmp_path: Path
    ):
        """Test handling 'could not resolve' network errors during fetch."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = GitCommandError(
                "fatal: Could not resolve host: github.com"
            )

            with pytest.raises(GitNetworkError):
                await service.fetch(tmp_path)

    @pytest.mark.asyncio
    async def test_push_network_error(self, service: GitService, tmp_path: Path):
        """Test handling network errors during push."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = GitCommandError(
                "fatal: unable to access 'https://github.com/repo.git/': "
                "Could not resolve host: github.com"
            )

            with pytest.raises(GitNetworkError):
                await service.push(tmp_path)

    @pytest.mark.asyncio
    async def test_pull_could_not_resolve_error(
        self, service: GitService, tmp_path: Path
    ):
        """Test handling 'could not resolve' errors during pull."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = GitCommandError(
                "fatal: Could not resolve host: github.com"
            )

            with pytest.raises(GitNetworkError):
                await service.pull(tmp_path)


class TestGitServicePushBranch:
    """Tests for push with specific branch."""

    @pytest.fixture
    def service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    @pytest.mark.asyncio
    async def test_push_specific_branch(self, service: GitService, tmp_path: Path):
        """Test pushing a specific branch."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""

            await service.push(tmp_path, branch="feature-branch")

            args = mock_run.call_args[0]
            assert "push" in args
            assert "origin" in args
            assert "feature-branch" in args

    @pytest.mark.asyncio
    async def test_push_custom_remote(self, service: GitService, tmp_path: Path):
        """Test pushing to a custom remote."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""

            await service.push(tmp_path, remote="upstream")

            args = mock_run.call_args[0]
            assert "push" in args
            assert "upstream" in args

    @pytest.mark.asyncio
    async def test_pull_specific_branch(self, service: GitService, tmp_path: Path):
        """Test pulling a specific branch."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""

            await service.pull(tmp_path, branch="main")

            args = mock_run.call_args[0]
            assert "pull" in args
            assert "origin" in args
            assert "main" in args

    @pytest.mark.asyncio
    async def test_pull_invalidates_cache(self, service: GitService, tmp_path: Path):
        """Test that pull invalidates status cache."""
        porcelain_output = "# branch.head main\n# branch.ab +0 -0\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            # Populate cache
            await service.get_status(tmp_path)
            assert len(service._status_cache) == 1

            # Pull
            mock_run.return_value = ""
            await service.pull(tmp_path)

            # Cache should be invalidated
            cache_key = str(tmp_path.resolve())
            assert cache_key not in service._status_cache


class TestGitServiceStashWithoutMessage:
    """Tests for stash without message."""

    @pytest.fixture
    def service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    @pytest.mark.asyncio
    async def test_stash_without_message(self, service: GitService, tmp_path: Path):
        """Test stashing without a message."""
        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = ""

            await service.stash(tmp_path)

            args = mock_run.call_args[0]
            assert "stash" in args
            assert "push" in args
            assert "-m" not in args

    @pytest.mark.asyncio
    async def test_stash_invalidates_cache(self, service: GitService, tmp_path: Path):
        """Test that stash invalidates status cache."""
        porcelain_output = "# branch.head main\n# branch.ab +0 -0\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            # Populate cache
            await service.get_status(tmp_path)
            cache_key = str(tmp_path.resolve())
            assert cache_key in service._status_cache

            # Stash
            mock_run.return_value = ""
            await service.stash(tmp_path)

            # Cache should be invalidated
            assert cache_key not in service._status_cache

    @pytest.mark.asyncio
    async def test_stash_pop_invalidates_cache(
        self, service: GitService, tmp_path: Path
    ):
        """Test that stash pop invalidates status cache."""
        porcelain_output = "# branch.head main\n# branch.ab +0 -0\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            # Populate cache
            await service.get_status(tmp_path)
            cache_key = str(tmp_path.resolve())
            assert cache_key in service._status_cache

            # Stash pop
            mock_run.return_value = ""
            await service.stash_pop(tmp_path)

            # Cache should be invalidated
            assert cache_key not in service._status_cache


class TestGitServiceStatusEdgeCases:
    """Tests for edge cases in status parsing."""

    @pytest.fixture
    def service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    @pytest.mark.asyncio
    async def test_get_status_empty_output(self, service: GitService, tmp_path: Path):
        """Test parsing empty status output (clean repo)."""
        porcelain_output = "# branch.head main\n# branch.ab +0 -0\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            status = await service.get_status(tmp_path)

            assert status.branch == "main"
            assert status.staged is None
            assert status.unstaged is None
            assert status.untracked is None
            assert status.has_conflicts is False

    @pytest.mark.asyncio
    async def test_get_status_detached_head(self, service: GitService, tmp_path: Path):
        """Test parsing status for detached HEAD."""
        porcelain_output = "# branch.head (detached)\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            status = await service.get_status(tmp_path)

            assert status.branch == "(detached)"

    @pytest.mark.asyncio
    async def test_get_status_added_file(self, service: GitService, tmp_path: Path):
        """Test parsing added file."""
        porcelain_output = """# branch.head main
# branch.ab +0 -0
1 A. N... 000000 100644 100644 0000000 abc1234 new_file.py
"""

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            status = await service.get_status(tmp_path)

            assert status.staged is not None
            assert len(status.staged) == 1
            assert status.staged[0].status == "A"
            assert status.staged[0].path == "new_file.py"

    @pytest.mark.asyncio
    async def test_get_status_deleted_file(self, service: GitService, tmp_path: Path):
        """Test parsing deleted file."""
        porcelain_output = """# branch.head main
# branch.ab +0 -0
1 D. N... 100644 000000 000000 abc1234 0000000 deleted_file.py
"""

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            status = await service.get_status(tmp_path)

            assert status.staged is not None
            assert len(status.staged) == 1
            assert status.staged[0].status == "D"
            assert status.staged[0].path == "deleted_file.py"

    @pytest.mark.asyncio
    async def test_get_status_rename_entry(self, service: GitService, tmp_path: Path):
        """Test parsing renamed file (type 2 entry)."""
        # Type 2 entries are for renames/copies
        porcelain_output = """# branch.head main
# branch.ab +0 -0
2 R. N... 100644 100644 100644 abc1234 def5678 R100 new_name.py	old_name.py
"""

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            status = await service.get_status(tmp_path)

            assert status.staged is not None
            assert len(status.staged) == 1
            assert status.staged[0].status == "R"

    @pytest.mark.asyncio
    async def test_get_status_multiple_conflict_types(
        self, service: GitService, tmp_path: Path
    ):
        """Test detecting various conflict states."""
        # AU = Added by us, unmerged
        porcelain_output = """# branch.head main
# branch.ab +0 -0
1 AU N... 100644 100644 100644 abc1234 def5678 conflict.py
"""

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            status = await service.get_status(tmp_path)

            assert status.has_conflicts is True


class TestGitServiceUnstageInvalidatesCache:
    """Tests for unstage cache invalidation."""

    @pytest.fixture
    def service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    @pytest.mark.asyncio
    async def test_unstage_invalidates_cache(
        self, service: GitService, tmp_path: Path
    ):
        """Test that unstaging invalidates status cache."""
        porcelain_output = "# branch.head main\n# branch.ab +0 -0\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            # Populate cache
            await service.get_status(tmp_path)
            cache_key = str(tmp_path.resolve())
            assert cache_key in service._status_cache

            # Unstage files
            mock_run.return_value = ""
            await service.unstage_files(tmp_path, ["file.py"])

            # Cache should be invalidated
            assert cache_key not in service._status_cache


class TestGitServiceCommitInvalidatesCache:
    """Tests for commit cache invalidation."""

    @pytest.fixture
    def service(self) -> GitService:
        """Create a GitService instance."""
        return GitService()

    @pytest.mark.asyncio
    async def test_commit_invalidates_cache(
        self, service: GitService, tmp_path: Path
    ):
        """Test that committing invalidates status cache."""
        porcelain_output = "# branch.head main\n# branch.ab +0 -0\n"

        with patch.object(service, "_run_git", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = porcelain_output

            # Populate cache
            await service.get_status(tmp_path)
            cache_key = str(tmp_path.resolve())
            assert cache_key in service._status_cache

            # Commit
            mock_run.side_effect = ["", "abc123\n"]  # commit + rev-parse
            await service.commit(tmp_path, "Test commit")

            # Cache should be invalidated
            assert cache_key not in service._status_cache
