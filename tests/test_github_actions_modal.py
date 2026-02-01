"""Tests for GitHubActionsModal."""

import pytest

from iterm_controller.models import WorkflowRun
from iterm_controller.screens.modals.github_actions import GitHubActionsModal


class TestWorkflowRunModel:
    """Tests for the WorkflowRun dataclass."""

    def test_create_workflow_run(self):
        """Test creating a WorkflowRun instance."""
        run = WorkflowRun(
            id=123,
            name="CI",
            status="completed",
            conclusion="success",
            created_at="2024-01-15T10:30:00Z",
            branch="main",
        )

        assert run.id == 123
        assert run.name == "CI"
        assert run.status == "completed"
        assert run.conclusion == "success"
        assert run.created_at == "2024-01-15T10:30:00Z"
        assert run.branch == "main"

    def test_create_workflow_run_in_progress(self):
        """Test creating an in-progress WorkflowRun."""
        run = WorkflowRun(
            id=456,
            name="Tests",
            status="in_progress",
            conclusion=None,
            created_at="2024-01-15T11:00:00Z",
            branch="feature",
        )

        assert run.status == "in_progress"
        assert run.conclusion is None


class TestGitHubActionsModalInit:
    """Tests for GitHubActionsModal initialization."""

    def test_init(self):
        """Test modal initialization."""
        modal = GitHubActionsModal(project_path="/path/to/project")

        assert modal._project_path == "/path/to/project"
        assert modal._runs == []
        assert modal._loading is True
        assert modal._error is None


class TestGitHubActionsModalStatusIcons:
    """Tests for status icon rendering."""

    @pytest.fixture
    def modal(self):
        """Create a modal instance for testing."""
        return GitHubActionsModal(project_path="/test")

    def test_status_icon_success(self, modal):
        """Test status icon for successful run."""
        run = WorkflowRun(
            id=1,
            name="CI",
            status="completed",
            conclusion="success",
            created_at="2024-01-15T10:00:00Z",
            branch="main",
        )

        icon = modal._get_status_icon(run)
        assert "[green]" in icon
        assert "✓" in icon

    def test_status_icon_failure(self, modal):
        """Test status icon for failed run."""
        run = WorkflowRun(
            id=2,
            name="CI",
            status="completed",
            conclusion="failure",
            created_at="2024-01-15T10:00:00Z",
            branch="main",
        )

        icon = modal._get_status_icon(run)
        assert "[red]" in icon
        assert "✗" in icon

    def test_status_icon_cancelled(self, modal):
        """Test status icon for cancelled run."""
        run = WorkflowRun(
            id=3,
            name="CI",
            status="completed",
            conclusion="cancelled",
            created_at="2024-01-15T10:00:00Z",
            branch="main",
        )

        icon = modal._get_status_icon(run)
        assert "[yellow]" in icon
        assert "○" in icon

    def test_status_icon_skipped(self, modal):
        """Test status icon for skipped run."""
        run = WorkflowRun(
            id=4,
            name="CI",
            status="completed",
            conclusion="skipped",
            created_at="2024-01-15T10:00:00Z",
            branch="main",
        )

        icon = modal._get_status_icon(run)
        assert "[dim]" in icon
        assert "⊘" in icon

    def test_status_icon_in_progress(self, modal):
        """Test status icon for in-progress run."""
        run = WorkflowRun(
            id=5,
            name="CI",
            status="in_progress",
            conclusion=None,
            created_at="2024-01-15T10:00:00Z",
            branch="main",
        )

        icon = modal._get_status_icon(run)
        assert "[yellow]" in icon
        assert "●" in icon

    def test_status_icon_queued(self, modal):
        """Test status icon for queued run."""
        run = WorkflowRun(
            id=6,
            name="CI",
            status="queued",
            conclusion=None,
            created_at="2024-01-15T10:00:00Z",
            branch="main",
        )

        icon = modal._get_status_icon(run)
        assert "[dim]" in icon
        assert "◌" in icon

    def test_status_icon_unknown_conclusion(self, modal):
        """Test status icon for unknown conclusion."""
        run = WorkflowRun(
            id=7,
            name="CI",
            status="completed",
            conclusion="unknown_status",
            created_at="2024-01-15T10:00:00Z",
            branch="main",
        )

        icon = modal._get_status_icon(run)
        assert "?" in icon


class TestGitHubActionsModalTimeFormatting:
    """Tests for time formatting."""

    @pytest.fixture
    def modal(self):
        """Create a modal instance for testing."""
        return GitHubActionsModal(project_path="/test")

    def test_format_time_z_suffix(self, modal):
        """Test formatting timestamp with Z suffix."""
        # This test may be timezone-sensitive but verifies basic functionality
        result = modal._format_time("2024-01-15T10:30:00Z")

        # Should be some time ago, not the raw timestamp
        assert result != "2024-01-15T10:30:00Z"
        # Should contain time unit
        assert any(unit in result for unit in ["just now", "m ago", "h ago", "d ago"])

    def test_format_time_offset_suffix(self, modal):
        """Test formatting timestamp with offset suffix."""
        result = modal._format_time("2024-01-15T10:30:00+00:00")

        # Should not be the raw timestamp
        assert result != "2024-01-15T10:30:00+00:00"

    def test_format_time_invalid(self, modal):
        """Test formatting invalid timestamp."""
        result = modal._format_time("not-a-timestamp")

        # Should return the original string on failure
        assert result == "not-a-timestamp"

    def test_format_time_empty(self, modal):
        """Test formatting empty timestamp."""
        result = modal._format_time("")

        # Should return the original string on failure
        assert result == ""


class TestGitHubActionsModalCSS:
    """Tests for modal CSS and bindings."""

    def test_bindings_defined(self):
        """Test that bindings are defined."""
        modal = GitHubActionsModal(project_path="/test")

        # Check that bindings exist
        binding_keys = [b.key for b in modal.BINDINGS]
        assert "r" in binding_keys
        assert "escape" in binding_keys

    def test_css_defined(self):
        """Test that CSS is defined."""
        assert GitHubActionsModal.DEFAULT_CSS is not None
        assert len(GitHubActionsModal.DEFAULT_CSS) > 0
        assert "GitHubActionsModal" in GitHubActionsModal.DEFAULT_CSS


class TestGitHubActionsModalExports:
    """Tests for module exports."""

    def test_modal_importable_from_modals(self):
        """Test that modal can be imported from modals package."""
        from iterm_controller.screens.modals import GitHubActionsModal

        assert GitHubActionsModal is not None

    def test_workflow_run_importable_from_models(self):
        """Test that WorkflowRun can be imported from models."""
        from iterm_controller.models import WorkflowRun

        assert WorkflowRun is not None
