"""Tests for the GitStateManager."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iterm_controller.models import GitFileStatus, GitStatus, Project
from iterm_controller.state import AppState, GitStatusChanged
from iterm_controller.state.git_manager import GitStateManager


class TestGitStateManager:
    """Tests for GitStateManager."""

    def test_initialization_default_service(self) -> None:
        """Test that GitStateManager initializes with default GitService."""
        manager = GitStateManager()

        assert manager.git_service is not None
        assert manager.statuses == {}
        assert manager._app is None

    def test_initialization_with_custom_service(self) -> None:
        """Test that GitStateManager accepts custom GitService."""
        mock_service = MagicMock()
        manager = GitStateManager(git_service=mock_service)

        assert manager.git_service is mock_service

    def test_connect_app(self) -> None:
        """Test connecting a Textual app to manager."""
        manager = GitStateManager()
        mock_app = MagicMock()

        manager.connect_app(mock_app)

        assert manager._app is mock_app

    def test_get_returns_none_when_not_cached(self) -> None:
        """Test get() returns None for uncached project."""
        manager = GitStateManager()

        result = manager.get("nonexistent")

        assert result is None

    def test_get_returns_cached_status(self) -> None:
        """Test get() returns cached status when available."""
        manager = GitStateManager()
        status = GitStatus(branch="main")
        manager.statuses["p1"] = status

        result = manager.get("p1")

        assert result is status

    def test_clear_removes_cached_status(self) -> None:
        """Test clear() removes cached status for project."""
        manager = GitStateManager()
        manager.statuses["p1"] = GitStatus(branch="main")

        manager.clear("p1")

        assert "p1" not in manager.statuses

    def test_clear_nonexistent_no_error(self) -> None:
        """Test clear() doesn't error for nonexistent project."""
        manager = GitStateManager()

        manager.clear("nonexistent")  # Should not raise

    def test_clear_all_removes_all_statuses(self) -> None:
        """Test clear_all() removes all cached statuses."""
        manager = GitStateManager()
        mock_service = MagicMock()
        manager.git_service = mock_service

        manager.statuses["p1"] = GitStatus(branch="main")
        manager.statuses["p2"] = GitStatus(branch="develop")

        manager.clear_all()

        assert manager.statuses == {}
        mock_service.clear_cache.assert_called_once()

    def test_get_all_statuses(self) -> None:
        """Test get_all_statuses() returns copy of all statuses."""
        manager = GitStateManager()
        status1 = GitStatus(branch="main")
        status2 = GitStatus(branch="develop")
        manager.statuses["p1"] = status1
        manager.statuses["p2"] = status2

        result = manager.get_all_statuses()

        assert result == {"p1": status1, "p2": status2}
        # Verify it's a copy
        result["p3"] = GitStatus(branch="feature")
        assert "p3" not in manager.statuses


@pytest.mark.asyncio
class TestGitStateManagerAsync:
    """Async tests for GitStateManager."""

    async def test_refresh_returns_none_without_app(self) -> None:
        """Test refresh() returns None when no app connected."""
        manager = GitStateManager()

        result = await manager.refresh("p1")

        assert result is None

    async def test_refresh_returns_none_for_unknown_project(self) -> None:
        """Test refresh() returns None for unknown project."""
        manager = GitStateManager()
        mock_app = MagicMock()
        mock_app.state.projects = {}
        manager.connect_app(mock_app)

        result = await manager.refresh("unknown")

        assert result is None

    async def test_refresh_gets_status_and_posts_message(self) -> None:
        """Test refresh() gets status and posts GitStatusChanged."""
        manager = GitStateManager()
        mock_service = AsyncMock()
        manager.git_service = mock_service

        status = GitStatus(branch="main", ahead=2, behind=1)
        mock_service.get_status.return_value = status

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state.projects = {"p1": project}
        manager.connect_app(mock_app)

        result = await manager.refresh("p1")

        assert result is status
        assert manager.statuses["p1"] is status
        mock_service.get_status.assert_called_once()

        # Verify message was posted
        mock_app.post_message.assert_called_once()
        posted = mock_app.post_message.call_args[0][0]
        assert isinstance(posted, GitStatusChanged)
        assert posted.project_id == "p1"
        assert posted.status is status

    async def test_refresh_handles_service_error(self) -> None:
        """Test refresh() handles service errors gracefully."""
        manager = GitStateManager()
        mock_service = AsyncMock()
        mock_service.get_status.side_effect = Exception("Git error")
        manager.git_service = mock_service

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state.projects = {"p1": project}
        manager.connect_app(mock_app)

        result = await manager.refresh("p1")

        assert result is None
        mock_app.post_message.assert_not_called()

    async def test_stage_files_returns_false_without_app(self) -> None:
        """Test stage_files() returns False when no app connected."""
        manager = GitStateManager()

        result = await manager.stage_files("p1", ["file.py"])

        assert result is False

    async def test_stage_files_stages_and_refreshes(self) -> None:
        """Test stage_files() stages files and refreshes status."""
        manager = GitStateManager()
        mock_service = AsyncMock()
        manager.git_service = mock_service

        status = GitStatus(branch="main")
        mock_service.get_status.return_value = status

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state.projects = {"p1": project}
        manager.connect_app(mock_app)

        result = await manager.stage_files("p1", ["file.py"])

        assert result is True
        mock_service.stage_files.assert_called_once()
        mock_service.get_status.assert_called_once()

    async def test_stage_files_handles_error(self) -> None:
        """Test stage_files() handles errors gracefully."""
        manager = GitStateManager()
        mock_service = AsyncMock()
        mock_service.stage_files.side_effect = Exception("Staging error")
        manager.git_service = mock_service

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state.projects = {"p1": project}
        manager.connect_app(mock_app)

        result = await manager.stage_files("p1", ["file.py"])

        assert result is False

    async def test_unstage_files_unstages_and_refreshes(self) -> None:
        """Test unstage_files() unstages files and refreshes status."""
        manager = GitStateManager()
        mock_service = AsyncMock()
        manager.git_service = mock_service

        status = GitStatus(branch="main")
        mock_service.get_status.return_value = status

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state.projects = {"p1": project}
        manager.connect_app(mock_app)

        result = await manager.unstage_files("p1", ["file.py"])

        assert result is True
        mock_service.unstage_files.assert_called_once()
        mock_service.get_status.assert_called_once()

    async def test_commit_creates_commit_and_refreshes(self) -> None:
        """Test commit() creates commit and refreshes status."""
        manager = GitStateManager()
        mock_service = AsyncMock()
        mock_service.commit.return_value = "abc123"
        manager.git_service = mock_service

        status = GitStatus(branch="main")
        mock_service.get_status.return_value = status

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state.projects = {"p1": project}
        manager.connect_app(mock_app)

        result = await manager.commit("p1", "Test commit message")

        assert result == "abc123"
        mock_service.commit.assert_called_once()
        mock_service.get_status.assert_called_once()

    async def test_commit_returns_none_on_error(self) -> None:
        """Test commit() returns None on error."""
        manager = GitStateManager()
        mock_service = AsyncMock()
        mock_service.commit.side_effect = Exception("Commit error")
        manager.git_service = mock_service

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state.projects = {"p1": project}
        manager.connect_app(mock_app)

        result = await manager.commit("p1", "Test commit")

        assert result is None

    async def test_push_pushes_and_refreshes(self) -> None:
        """Test push() pushes and refreshes status."""
        manager = GitStateManager()
        mock_service = AsyncMock()
        manager.git_service = mock_service

        status = GitStatus(branch="main")
        mock_service.get_status.return_value = status

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state.projects = {"p1": project}
        manager.connect_app(mock_app)

        result = await manager.push("p1", force=True, set_upstream=True)

        assert result is True
        mock_service.push.assert_called_once()
        call_kwargs = mock_service.push.call_args[1]
        assert call_kwargs["force"] is True
        assert call_kwargs["set_upstream"] is True

    async def test_push_returns_false_on_error(self) -> None:
        """Test push() returns False on error."""
        manager = GitStateManager()
        mock_service = AsyncMock()
        mock_service.push.side_effect = Exception("Push rejected")
        manager.git_service = mock_service

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state.projects = {"p1": project}
        manager.connect_app(mock_app)

        result = await manager.push("p1")

        assert result is False

    async def test_pull_pulls_and_refreshes(self) -> None:
        """Test pull() pulls and refreshes status."""
        manager = GitStateManager()
        mock_service = AsyncMock()
        manager.git_service = mock_service

        status = GitStatus(branch="main")
        mock_service.get_status.return_value = status

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state.projects = {"p1": project}
        manager.connect_app(mock_app)

        result = await manager.pull("p1")

        assert result is True
        mock_service.pull.assert_called_once()
        mock_service.get_status.assert_called_once()

    async def test_fetch_fetches_and_refreshes(self) -> None:
        """Test fetch() fetches and refreshes status."""
        manager = GitStateManager()
        mock_service = AsyncMock()
        manager.git_service = mock_service

        status = GitStatus(branch="main")
        mock_service.get_status.return_value = status

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state.projects = {"p1": project}
        manager.connect_app(mock_app)

        result = await manager.fetch("p1")

        assert result is True
        mock_service.fetch.assert_called_once()
        mock_service.get_status.assert_called_once()

    async def test_get_diff_returns_diff(self) -> None:
        """Test get_diff() returns diff from service."""
        manager = GitStateManager()
        mock_service = AsyncMock()
        mock_service.get_diff.return_value = "diff --git a/file.py..."
        manager.git_service = mock_service

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state.projects = {"p1": project}
        manager.connect_app(mock_app)

        result = await manager.get_diff("p1", staged_only=True)

        assert result == "diff --git a/file.py..."
        mock_service.get_diff.assert_called_once()

    async def test_get_diff_returns_none_on_error(self) -> None:
        """Test get_diff() returns None on error."""
        manager = GitStateManager()
        mock_service = AsyncMock()
        mock_service.get_diff.side_effect = Exception("Diff error")
        manager.git_service = mock_service

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state.projects = {"p1": project}
        manager.connect_app(mock_app)

        result = await manager.get_diff("p1")

        assert result is None


class TestAppStateGitIntegration:
    """Tests for git operations via AppState."""

    def test_app_state_has_git_manager(self) -> None:
        """Test that AppState has git manager."""
        state = AppState()

        assert state.git is not None
        assert isinstance(state.git, GitStateManager)

    def test_app_state_connect_app_connects_git_manager(self) -> None:
        """Test that connect_app() connects the git manager."""
        state = AppState()
        mock_app = MagicMock()

        state.connect_app(mock_app)

        assert state._git_manager._app is mock_app

    def test_get_git_status_returns_cached(self) -> None:
        """Test get_git_status() returns cached status."""
        state = AppState()
        status = GitStatus(branch="main")
        state._git_manager.statuses["p1"] = status

        result = state.get_git_status("p1")

        assert result is status

    def test_get_git_status_returns_none_when_uncached(self) -> None:
        """Test get_git_status() returns None when not cached."""
        state = AppState()

        result = state.get_git_status("p1")

        assert result is None

    def test_clear_git_status_clears_cached(self) -> None:
        """Test clear_git_status() clears cached status."""
        state = AppState()
        state._git_manager.statuses["p1"] = GitStatus(branch="main")

        state.clear_git_status("p1")

        assert state.get_git_status("p1") is None


@pytest.mark.asyncio
class TestAppStateGitIntegrationAsync:
    """Async tests for git operations via AppState."""

    async def test_refresh_git_status(self) -> None:
        """Test refresh_git_status() refreshes status."""
        state = AppState()
        mock_service = AsyncMock()
        state._git_manager.git_service = mock_service

        status = GitStatus(branch="main")
        mock_service.get_status.return_value = status

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state = state
        state.projects["p1"] = project
        state.connect_app(mock_app)

        result = await state.refresh_git_status("p1")

        assert result is status

    async def test_stage_git_files(self) -> None:
        """Test stage_git_files() stages files."""
        state = AppState()
        mock_service = AsyncMock()
        state._git_manager.git_service = mock_service
        mock_service.get_status.return_value = GitStatus(branch="main")

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state = state
        state.projects["p1"] = project
        state.connect_app(mock_app)

        result = await state.stage_git_files("p1", ["file.py"])

        assert result is True
        mock_service.stage_files.assert_called_once()

    async def test_unstage_git_files(self) -> None:
        """Test unstage_git_files() unstages files."""
        state = AppState()
        mock_service = AsyncMock()
        state._git_manager.git_service = mock_service
        mock_service.get_status.return_value = GitStatus(branch="main")

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state = state
        state.projects["p1"] = project
        state.connect_app(mock_app)

        result = await state.unstage_git_files("p1", ["file.py"])

        assert result is True
        mock_service.unstage_files.assert_called_once()

    async def test_git_commit(self) -> None:
        """Test git_commit() creates commit."""
        state = AppState()
        mock_service = AsyncMock()
        mock_service.commit.return_value = "abc123"
        mock_service.get_status.return_value = GitStatus(branch="main")
        state._git_manager.git_service = mock_service

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state = state
        state.projects["p1"] = project
        state.connect_app(mock_app)

        result = await state.git_commit("p1", "Test commit")

        assert result == "abc123"
        mock_service.commit.assert_called_once()

    async def test_git_push(self) -> None:
        """Test git_push() pushes to remote."""
        state = AppState()
        mock_service = AsyncMock()
        mock_service.get_status.return_value = GitStatus(branch="main")
        state._git_manager.git_service = mock_service

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state = state
        state.projects["p1"] = project
        state.connect_app(mock_app)

        result = await state.git_push("p1", force=True)

        assert result is True
        mock_service.push.assert_called_once()

    async def test_git_pull(self) -> None:
        """Test git_pull() pulls from remote."""
        state = AppState()
        mock_service = AsyncMock()
        mock_service.get_status.return_value = GitStatus(branch="main")
        state._git_manager.git_service = mock_service

        mock_app = MagicMock()
        project = Project(id="p1", name="Test", path="/test/path")
        mock_app.state = state
        state.projects["p1"] = project
        state.connect_app(mock_app)

        result = await state.git_pull("p1")

        assert result is True
        mock_service.pull.assert_called_once()


class TestStateSnapshotGitStatus:
    """Tests for git status in StateSnapshot."""

    def test_snapshot_includes_git_statuses(self) -> None:
        """Test that snapshot includes git statuses."""
        state = AppState()
        status = GitStatus(branch="main", ahead=1)
        state._git_manager.statuses["p1"] = status

        snapshot = state.to_snapshot()

        assert snapshot.git_statuses == {"p1": status}

    def test_snapshot_get_git_status(self) -> None:
        """Test snapshot.get_git_status() returns status."""
        state = AppState()
        status = GitStatus(branch="main")
        state._git_manager.statuses["p1"] = status

        snapshot = state.to_snapshot()

        assert snapshot.get_git_status("p1") is status
        assert snapshot.get_git_status("unknown") is None
