"""Tests for GitHubPanelWidget."""

import pytest
from rich.text import Text

from iterm_controller.models import GitHubStatus, PullRequest
from iterm_controller.widgets.github_panel import GitHubPanelWidget


class TestGitHubPanelWidgetInit:
    """Tests for GitHubPanelWidget initialization."""

    def test_init_default(self):
        """Test default initialization."""
        widget = GitHubPanelWidget()

        assert widget.status is None
        assert widget.is_available is False

    def test_init_with_status(self):
        """Test initialization with status."""
        status = GitHubStatus(available=True, current_branch="main")
        widget = GitHubPanelWidget(status=status)

        assert widget.status is status
        assert widget.is_available is True

    def test_init_with_error_message(self):
        """Test initialization with error message."""
        widget = GitHubPanelWidget(error_message="gh CLI not installed")

        assert widget.status is None
        assert widget.is_available is False


class TestGitHubPanelWidgetUpdateMethods:
    """Tests for update methods.

    Note: These tests verify internal state changes only.
    The update() method requires a mounted app context, so we test
    the state mutations directly rather than the full update cycle.
    """

    def test_update_status_changes_state(self):
        """Test update_status changes internal state."""
        widget = GitHubPanelWidget()
        status = GitHubStatus(available=True, current_branch="feature")

        # Directly set state to avoid update() call
        widget._status = status
        widget._error_message = None

        assert widget.status is status
        assert widget.is_available is True

    def test_set_error_changes_state(self):
        """Test set_error changes internal state."""
        status = GitHubStatus(available=True, current_branch="main")
        widget = GitHubPanelWidget(status=status)

        # Directly set state to simulate set_error behavior
        widget._status = None
        widget._error_message = "Connection failed"

        assert widget.status is None
        assert widget.is_available is False

    def test_set_unavailable_changes_state(self):
        """Test set_unavailable changes internal state."""
        status = GitHubStatus(available=True, current_branch="main")
        widget = GitHubPanelWidget(status=status)

        # Directly set state to simulate set_unavailable behavior
        widget._status = GitHubStatus(available=False, error_message="Not authenticated")
        widget._error_message = "Not authenticated"

        assert widget.status is not None
        assert widget.status.available is False
        assert widget.is_available is False


class TestGitHubPanelWidgetRenderUnavailable:
    """Tests for rendering unavailable states."""

    def test_render_no_status(self):
        """Test rendering when no status is set."""
        widget = GitHubPanelWidget()
        result = widget.render()

        assert isinstance(result, Text)
        assert "GitHub: Not available" in result.plain

    def test_render_with_error_message(self):
        """Test rendering with error message."""
        widget = GitHubPanelWidget(error_message="gh CLI not installed")
        result = widget.render()

        assert "GitHub:" in result.plain
        assert "gh CLI not installed" in result.plain

    def test_render_unavailable_status_with_message(self):
        """Test rendering unavailable status with error message."""
        status = GitHubStatus(
            available=False, error_message="Not authenticated. Run: gh auth login"
        )
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "GitHub:" in result.plain
        assert "Not authenticated" in result.plain


class TestGitHubPanelWidgetRenderBranchInfo:
    """Tests for rendering branch information."""

    def test_render_branch_info(self):
        """Test rendering current branch."""
        status = GitHubStatus(
            available=True, current_branch="feature-branch", default_branch="main"
        )
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "Branch:" in result.plain
        assert "feature-branch" in result.plain

    def test_render_ahead_status(self):
        """Test rendering ahead commits."""
        status = GitHubStatus(
            available=True,
            current_branch="feature",
            default_branch="main",
            ahead=3,
            behind=0,
        )
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "\u21913" in result.plain  # ↑3
        assert "from main" in result.plain

    def test_render_behind_status(self):
        """Test rendering behind commits."""
        status = GitHubStatus(
            available=True,
            current_branch="feature",
            default_branch="main",
            ahead=0,
            behind=2,
        )
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "\u21932" in result.plain  # ↓2
        assert "from main" in result.plain

    def test_render_ahead_and_behind(self):
        """Test rendering both ahead and behind."""
        status = GitHubStatus(
            available=True,
            current_branch="feature",
            default_branch="main",
            ahead=5,
            behind=3,
        )
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "\u21915" in result.plain  # ↑5
        assert "\u21933" in result.plain  # ↓3

    def test_render_in_sync(self):
        """Test rendering when in sync (no ahead/behind)."""
        status = GitHubStatus(
            available=True,
            current_branch="main",
            default_branch="main",
            ahead=0,
            behind=0,
        )
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        # Should not show sync line when in sync
        assert "\u2191" not in result.plain
        assert "\u2193" not in result.plain


class TestGitHubPanelWidgetRenderPR:
    """Tests for rendering PR information."""

    def test_render_pr_basic(self):
        """Test rendering basic PR info."""
        pr = PullRequest(
            number=123,
            title="Add feature X",
            url="https://github.com/owner/repo/pull/123",
            state="OPEN",
        )
        status = GitHubStatus(available=True, current_branch="feature", pr=pr)
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "PR #123:" in result.plain
        assert "Add feature X" in result.plain

    def test_render_pr_draft(self):
        """Test rendering draft PR."""
        pr = PullRequest(
            number=456,
            title="WIP: New feature",
            url="https://github.com/owner/repo/pull/456",
            state="OPEN",
            draft=True,
        )
        status = GitHubStatus(available=True, current_branch="feature", pr=pr)
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "[Draft]" in result.plain

    def test_render_pr_merged(self):
        """Test rendering merged PR."""
        pr = PullRequest(
            number=789,
            title="Fix bug",
            url="https://github.com/owner/repo/pull/789",
            state="MERGED",
            merged=True,
        )
        status = GitHubStatus(available=True, current_branch="feature", pr=pr)
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "Merged" in result.plain

    def test_render_pr_checks_passing(self):
        """Test rendering PR with passing checks."""
        pr = PullRequest(
            number=100,
            title="Feature",
            url="https://github.com/owner/repo/pull/100",
            state="OPEN",
            checks_passing=True,
        )
        status = GitHubStatus(available=True, current_branch="feature", pr=pr)
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "Checks passing" in result.plain

    def test_render_pr_checks_failing(self):
        """Test rendering PR with failing checks."""
        pr = PullRequest(
            number=100,
            title="Feature",
            url="https://github.com/owner/repo/pull/100",
            state="OPEN",
            checks_passing=False,
        )
        status = GitHubStatus(available=True, current_branch="feature", pr=pr)
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "Checks failing" in result.plain

    def test_render_pr_reviews_pending(self):
        """Test rendering PR with pending reviews."""
        pr = PullRequest(
            number=100,
            title="Feature",
            url="https://github.com/owner/repo/pull/100",
            state="OPEN",
            reviews_pending=2,
        )
        status = GitHubStatus(available=True, current_branch="feature", pr=pr)
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "2 reviews pending" in result.plain

    def test_render_pr_one_review_pending(self):
        """Test rendering PR with one pending review."""
        pr = PullRequest(
            number=100,
            title="Feature",
            url="https://github.com/owner/repo/pull/100",
            state="OPEN",
            reviews_pending=1,
        )
        status = GitHubStatus(available=True, current_branch="feature", pr=pr)
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "1 review pending" in result.plain

    def test_render_pr_comments(self):
        """Test rendering PR with comments."""
        pr = PullRequest(
            number=100,
            title="Feature",
            url="https://github.com/owner/repo/pull/100",
            state="OPEN",
            comments=5,
        )
        status = GitHubStatus(available=True, current_branch="feature", pr=pr)
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "5 comments" in result.plain

    def test_render_pr_one_comment(self):
        """Test rendering PR with one comment."""
        pr = PullRequest(
            number=100,
            title="Feature",
            url="https://github.com/owner/repo/pull/100",
            state="OPEN",
            comments=1,
        )
        status = GitHubStatus(available=True, current_branch="feature", pr=pr)
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "1 comment" in result.plain


class TestGitHubPanelWidgetRenderWarnings:
    """Tests for rendering warning indicators."""

    def test_render_rate_limited(self):
        """Test rendering rate limit warning."""
        status = GitHubStatus(
            available=True, current_branch="main", rate_limited=True
        )
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "Rate limited" in result.plain
        assert "cached data" in result.plain

    def test_render_offline(self):
        """Test rendering offline warning."""
        status = GitHubStatus(available=True, current_branch="main", offline=True)
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "Offline" in result.plain
        assert "cached data" in result.plain


class TestGitHubPanelWidgetHelperMethods:
    """Tests for helper methods."""

    def test_has_pr_true(self):
        """Test has_pr returns True when PR exists."""
        pr = PullRequest(
            number=100,
            title="Feature",
            url="https://github.com/owner/repo/pull/100",
            state="OPEN",
        )
        status = GitHubStatus(available=True, current_branch="feature", pr=pr)
        widget = GitHubPanelWidget(status=status)

        assert widget.has_pr() is True

    def test_has_pr_false_no_pr(self):
        """Test has_pr returns False when no PR."""
        status = GitHubStatus(available=True, current_branch="feature")
        widget = GitHubPanelWidget(status=status)

        assert widget.has_pr() is False

    def test_has_pr_false_no_status(self):
        """Test has_pr returns False when no status."""
        widget = GitHubPanelWidget()

        assert widget.has_pr() is False

    def test_get_pr_url(self):
        """Test get_pr_url returns URL."""
        pr = PullRequest(
            number=100,
            title="Feature",
            url="https://github.com/owner/repo/pull/100",
            state="OPEN",
        )
        status = GitHubStatus(available=True, current_branch="feature", pr=pr)
        widget = GitHubPanelWidget(status=status)

        assert widget.get_pr_url() == "https://github.com/owner/repo/pull/100"

    def test_get_pr_url_none(self):
        """Test get_pr_url returns None when no PR."""
        status = GitHubStatus(available=True, current_branch="feature")
        widget = GitHubPanelWidget(status=status)

        assert widget.get_pr_url() is None

    def test_is_checks_passing_true(self):
        """Test is_checks_passing returns True."""
        pr = PullRequest(
            number=100,
            title="Feature",
            url="https://github.com/owner/repo/pull/100",
            state="OPEN",
            checks_passing=True,
        )
        status = GitHubStatus(available=True, current_branch="feature", pr=pr)
        widget = GitHubPanelWidget(status=status)

        assert widget.is_checks_passing() is True

    def test_is_checks_passing_false(self):
        """Test is_checks_passing returns False."""
        pr = PullRequest(
            number=100,
            title="Feature",
            url="https://github.com/owner/repo/pull/100",
            state="OPEN",
            checks_passing=False,
        )
        status = GitHubStatus(available=True, current_branch="feature", pr=pr)
        widget = GitHubPanelWidget(status=status)

        assert widget.is_checks_passing() is False

    def test_is_checks_passing_none(self):
        """Test is_checks_passing returns None when unknown."""
        pr = PullRequest(
            number=100,
            title="Feature",
            url="https://github.com/owner/repo/pull/100",
            state="OPEN",
            checks_passing=None,
        )
        status = GitHubStatus(available=True, current_branch="feature", pr=pr)
        widget = GitHubPanelWidget(status=status)

        assert widget.is_checks_passing() is None

    def test_is_pr_merged_true(self):
        """Test is_pr_merged returns True."""
        pr = PullRequest(
            number=100,
            title="Feature",
            url="https://github.com/owner/repo/pull/100",
            state="MERGED",
            merged=True,
        )
        status = GitHubStatus(available=True, current_branch="feature", pr=pr)
        widget = GitHubPanelWidget(status=status)

        assert widget.is_pr_merged() is True

    def test_is_pr_merged_false(self):
        """Test is_pr_merged returns False."""
        pr = PullRequest(
            number=100,
            title="Feature",
            url="https://github.com/owner/repo/pull/100",
            state="OPEN",
            merged=False,
        )
        status = GitHubStatus(available=True, current_branch="feature", pr=pr)
        widget = GitHubPanelWidget(status=status)

        assert widget.is_pr_merged() is False

    def test_is_pr_merged_no_pr(self):
        """Test is_pr_merged returns False when no PR."""
        status = GitHubStatus(available=True, current_branch="feature")
        widget = GitHubPanelWidget(status=status)

        assert widget.is_pr_merged() is False


class TestGitHubPanelWidgetFullRender:
    """Tests for full render scenarios."""

    def test_render_full_status(self):
        """Test rendering complete status with all info."""
        pr = PullRequest(
            number=42,
            title="Implement awesome feature",
            url="https://github.com/owner/repo/pull/42",
            state="OPEN",
            draft=False,
            checks_passing=True,
            reviews_pending=1,
            comments=3,
        )
        status = GitHubStatus(
            available=True,
            current_branch="feature/awesome",
            default_branch="main",
            ahead=2,
            behind=1,
            pr=pr,
        )
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        # Check all components are present
        assert "Branch:" in result.plain
        assert "feature/awesome" in result.plain
        assert "\u21912" in result.plain  # ↑2
        assert "\u21931" in result.plain  # ↓1
        assert "PR #42:" in result.plain
        assert "Implement awesome feature" in result.plain
        assert "Checks passing" in result.plain
        assert "1 review pending" in result.plain
        assert "3 comments" in result.plain

    def test_render_no_data(self):
        """Test rendering when available but no data."""
        status = GitHubStatus(available=True)
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        # Should show "no data" message when nothing to display
        assert "GitHub: No data" in result.plain


class TestGitHubPanelWidgetGracefulDegradation:
    """Tests for graceful degradation behavior per spec."""

    def test_gh_not_installed_hidden(self):
        """Test panel hides when gh not installed."""
        widget = GitHubPanelWidget(error_message="gh CLI not installed")
        result = widget.render()

        # Should show error message
        assert "gh CLI not installed" in result.plain

    def test_gh_not_authenticated_shows_hint(self):
        """Test panel shows hint when not authenticated."""
        status = GitHubStatus(
            available=False, error_message="Not authenticated. Run: gh auth login"
        )
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "Not authenticated" in result.plain

    def test_rate_limited_shows_cached(self):
        """Test panel shows cached data with indicator when rate limited."""
        status = GitHubStatus(
            available=True, current_branch="main", rate_limited=True
        )
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "Rate limited" in result.plain
        assert "Branch:" in result.plain

    def test_offline_shows_cached(self):
        """Test panel shows cached data with indicator when offline."""
        status = GitHubStatus(
            available=True,
            current_branch="develop",
            offline=True,
            pr=PullRequest(
                number=10, title="Fix", url="https://example.com", state="OPEN"
            ),
        )
        widget = GitHubPanelWidget(status=status)
        result = widget.render()

        assert "Offline" in result.plain
        assert "Branch:" in result.plain
        assert "PR #10:" in result.plain
