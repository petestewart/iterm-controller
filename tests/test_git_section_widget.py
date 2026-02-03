"""Tests for the GitSection widget."""

from unittest.mock import patch

import pytest

from iterm_controller.models import GitFileStatus, GitStatus, Project
from iterm_controller.widgets.git_section import GitSection


def make_project(path: str = "/tmp/test-project") -> Project:
    """Create a test project."""
    return Project(
        id="project-1",
        name="Test Project",
        path=path,
    )


def make_git_status(
    branch: str = "main",
    ahead: int = 0,
    behind: int = 0,
    staged: list[GitFileStatus] | None = None,
    unstaged: list[GitFileStatus] | None = None,
    untracked: list[GitFileStatus] | None = None,
    has_conflicts: bool = False,
) -> GitStatus:
    """Create a test git status."""
    return GitStatus(
        branch=branch,
        ahead=ahead,
        behind=behind,
        staged=staged,
        unstaged=unstaged,
        untracked=untracked,
        has_conflicts=has_conflicts,
    )


def make_file_status(
    path: str,
    status: str = "M",
    staged: bool = False,
) -> GitFileStatus:
    """Create a test file status."""
    return GitFileStatus(
        path=path,
        status=status,
        staged=staged,
    )


class TestGitSectionInit:
    """Tests for GitSection initialization."""

    def test_init_without_project(self) -> None:
        """Test widget initializes without a project."""
        widget = GitSection()

        assert widget.project is None
        assert widget.collapsed is False
        assert widget.git_status is None

    def test_init_with_project(self) -> None:
        """Test widget initializes with a project."""
        project = make_project()
        widget = GitSection(project=project)

        assert widget.project == project

    def test_init_collapsed(self) -> None:
        """Test widget initializes collapsed."""
        widget = GitSection(collapsed=True)

        assert widget.collapsed is True


class TestGitSectionToggle:
    """Tests for section collapse toggle."""

    def test_toggle_collapsed(self) -> None:
        """Test toggling collapsed state."""
        widget = GitSection()

        assert widget.collapsed is False

        with patch.object(widget, "refresh"):
            widget.toggle_collapsed()

        assert widget.collapsed is True

        with patch.object(widget, "refresh"):
            widget.toggle_collapsed()

        assert widget.collapsed is False


class TestGitSectionNavigation:
    """Tests for file navigation."""

    def test_selected_file_initial(self) -> None:
        """Test initial selection is first file."""
        project = make_project()
        status = make_git_status(
            staged=[make_file_status("src/auth.py", staged=True)],
        )

        widget = GitSection(project=project)
        widget.set_git_status(status)

        assert widget.selected_file is not None
        assert widget.selected_file[0] == "src/auth.py"
        assert widget.selected_file[2] is True  # staged

    def test_select_next(self) -> None:
        """Test selecting next file."""
        project = make_project()
        status = make_git_status(
            staged=[
                make_file_status("src/auth.py", staged=True),
                make_file_status("src/users.py", staged=True),
            ],
        )

        widget = GitSection(project=project)
        widget.set_git_status(status)

        with patch.object(widget, "refresh"):
            widget.select_next()

        assert widget.selected_file is not None
        assert widget.selected_file[0] == "src/users.py"

    def test_select_previous(self) -> None:
        """Test selecting previous file."""
        project = make_project()
        status = make_git_status(
            staged=[
                make_file_status("src/auth.py", staged=True),
                make_file_status("src/users.py", staged=True),
            ],
        )

        widget = GitSection(project=project)
        widget.set_git_status(status)

        with patch.object(widget, "refresh"):
            widget.select_next()  # Now at users.py
            widget.select_previous()  # Back to auth.py

        assert widget.selected_file is not None
        assert widget.selected_file[0] == "src/auth.py"

    def test_select_previous_at_start(self) -> None:
        """Test select_previous doesn't go below zero."""
        project = make_project()
        status = make_git_status(
            staged=[make_file_status("src/auth.py", staged=True)],
        )

        widget = GitSection(project=project)
        widget.set_git_status(status)

        with patch.object(widget, "refresh"):
            widget.select_previous()

        assert widget.selected_file is not None
        assert widget.selected_file[0] == "src/auth.py"

    def test_select_next_at_end(self) -> None:
        """Test select_next doesn't exceed list bounds."""
        project = make_project()
        status = make_git_status(
            staged=[make_file_status("src/auth.py", staged=True)],
        )

        widget = GitSection(project=project)
        widget.set_git_status(status)

        with patch.object(widget, "refresh"):
            for _ in range(10):
                widget.select_next()

        assert widget.selected_file is not None
        assert widget.selected_file[0] == "src/auth.py"

    def test_select_when_collapsed_returns_none(self) -> None:
        """Test selected_file is None when collapsed."""
        project = make_project()
        status = make_git_status(
            staged=[make_file_status("src/auth.py", staged=True)],
        )

        widget = GitSection(project=project, collapsed=True)
        widget.set_git_status(status)

        assert widget.selected_file is None

    def test_navigation_across_categories(self) -> None:
        """Test navigating from staged to unstaged files."""
        project = make_project()
        status = make_git_status(
            staged=[make_file_status("src/auth.py", staged=True)],
            unstaged=[make_file_status("README.md", staged=False)],
        )

        widget = GitSection(project=project)
        widget.set_git_status(status)

        # First file is staged
        assert widget.selected_file[2] is True

        with patch.object(widget, "refresh"):
            widget.select_next()

        # Second file is unstaged
        assert widget.selected_file[0] == "README.md"
        assert widget.selected_file[2] is False


class TestGitSectionStatus:
    """Tests for status-related properties."""

    def test_has_staged_changes_true(self) -> None:
        """Test has_staged_changes when there are staged files."""
        status = make_git_status(
            staged=[make_file_status("src/auth.py", staged=True)],
        )

        widget = GitSection()
        widget.set_git_status(status)

        assert widget.has_staged_changes is True

    def test_has_staged_changes_false(self) -> None:
        """Test has_staged_changes when no staged files."""
        status = make_git_status(
            unstaged=[make_file_status("README.md", staged=False)],
        )

        widget = GitSection()
        widget.set_git_status(status)

        assert widget.has_staged_changes is False

    def test_has_changes_true(self) -> None:
        """Test has_changes when there are any changes."""
        status = make_git_status(
            unstaged=[make_file_status("README.md", staged=False)],
        )

        widget = GitSection()
        widget.set_git_status(status)

        assert widget.has_changes is True

    def test_has_changes_false(self) -> None:
        """Test has_changes when no changes."""
        status = make_git_status()

        widget = GitSection()
        widget.set_git_status(status)

        assert widget.has_changes is False

    def test_can_push_true(self) -> None:
        """Test can_push when ahead of remote."""
        status = make_git_status(ahead=2)

        widget = GitSection()
        widget.set_git_status(status)

        assert widget.can_push is True

    def test_can_push_false(self) -> None:
        """Test can_push when not ahead of remote."""
        status = make_git_status(ahead=0)

        widget = GitSection()
        widget.set_git_status(status)

        assert widget.can_push is False


class TestGitSectionMessages:
    """Tests for message posting."""

    def test_file_selected_message(self) -> None:
        """Test FileSelected message."""
        msg = GitSection.FileSelected(
            file_path="src/auth.py",
            status="M",
            staged=True,
        )

        assert msg.file_path == "src/auth.py"
        assert msg.status == "M"
        assert msg.staged is True

    def test_commit_requested_message(self) -> None:
        """Test CommitRequested message."""
        msg = GitSection.CommitRequested(
            staged_files=["src/auth.py", "src/users.py"],
        )

        assert msg.staged_files == ["src/auth.py", "src/users.py"]

    def test_push_requested_message(self) -> None:
        """Test PushRequested message."""
        msg = GitSection.PushRequested(
            branch="main",
            ahead=3,
        )

        assert msg.branch == "main"
        assert msg.ahead == 3

    def test_refresh_requested_message(self) -> None:
        """Test RefreshRequested message."""
        msg = GitSection.RefreshRequested()

        assert isinstance(msg, GitSection.RefreshRequested)

    def test_stage_file_requested_message(self) -> None:
        """Test StageFileRequested message."""
        msg = GitSection.StageFileRequested(
            file_path="README.md",
        )

        assert msg.file_path == "README.md"

    def test_unstage_file_requested_message(self) -> None:
        """Test UnstageFileRequested message."""
        msg = GitSection.UnstageFileRequested(
            file_path="src/auth.py",
        )

        assert msg.file_path == "src/auth.py"


class TestGitSectionRendering:
    """Tests for rendering methods."""

    def test_render_branch_info_basic(self) -> None:
        """Test _render_branch_info with basic status."""
        status = make_git_status(branch="main")

        widget = GitSection()
        widget.set_git_status(status)

        text = widget._render_branch_info()
        rendered = str(text)

        assert "main" in rendered

    def test_render_branch_info_ahead(self) -> None:
        """Test _render_branch_info with commits ahead."""
        status = make_git_status(branch="main", ahead=2)

        widget = GitSection()
        widget.set_git_status(status)

        text = widget._render_branch_info()
        rendered = str(text)

        assert "↑2" in rendered

    def test_render_branch_info_behind(self) -> None:
        """Test _render_branch_info with commits behind."""
        status = make_git_status(branch="main", behind=3)

        widget = GitSection()
        widget.set_git_status(status)

        text = widget._render_branch_info()
        rendered = str(text)

        assert "↓3" in rendered

    def test_render_branch_info_conflicts(self) -> None:
        """Test _render_branch_info with conflicts."""
        status = make_git_status(branch="main", has_conflicts=True)

        widget = GitSection()
        widget.set_git_status(status)

        text = widget._render_branch_info()
        rendered = str(text)

        assert "CONFLICTS" in rendered

    def test_render_file_row_modified(self) -> None:
        """Test _render_file_row for modified file."""
        widget = GitSection()

        text = widget._render_file_row(
            file_path="src/auth.py",
            status="M",
            staged=False,
            is_selected=False,
        )
        rendered = str(text)

        assert "src/auth.py" in rendered
        assert "M" in rendered

    def test_render_file_row_added(self) -> None:
        """Test _render_file_row for added file."""
        widget = GitSection()

        text = widget._render_file_row(
            file_path="src/users.py",
            status="A",
            staged=True,
            is_selected=False,
        )
        rendered = str(text)

        assert "src/users.py" in rendered
        assert "A" in rendered

    def test_render_file_row_deleted(self) -> None:
        """Test _render_file_row for deleted file."""
        widget = GitSection()

        text = widget._render_file_row(
            file_path="old_file.py",
            status="D",
            staged=False,
            is_selected=False,
        )
        rendered = str(text)

        assert "old_file.py" in rendered
        assert "D" in rendered

    def test_render_file_row_untracked(self) -> None:
        """Test _render_file_row for untracked file."""
        widget = GitSection()

        text = widget._render_file_row(
            file_path=".env.example",
            status="?",
            staged=False,
            is_selected=False,
        )
        rendered = str(text)

        assert ".env.example" in rendered
        assert "?" in rendered

    def test_render_file_row_selected(self) -> None:
        """Test _render_file_row shows selection indicator."""
        widget = GitSection()

        text = widget._render_file_row(
            file_path="src/auth.py",
            status="M",
            staged=False,
            is_selected=True,
        )
        rendered = str(text)

        assert ">" in rendered  # Selection indicator
        assert "[s]tage" in rendered  # Stage hint for unstaged file

    def test_render_file_row_selected_staged(self) -> None:
        """Test _render_file_row shows unstage hint for staged file."""
        widget = GitSection()

        text = widget._render_file_row(
            file_path="src/auth.py",
            status="M",
            staged=True,
            is_selected=True,
        )
        rendered = str(text)

        assert ">" in rendered  # Selection indicator
        assert "[u]nstage" in rendered  # Unstage hint for staged file


class TestGitSectionCounts:
    """Tests for count methods."""

    def test_get_staged_count(self) -> None:
        """Test get_staged_count returns correct count."""
        status = make_git_status(
            staged=[
                make_file_status("src/auth.py", staged=True),
                make_file_status("src/users.py", staged=True),
            ],
        )

        widget = GitSection()
        widget.set_git_status(status)

        assert widget.get_staged_count() == 2

    def test_get_staged_count_empty(self) -> None:
        """Test get_staged_count returns 0 when no staged files."""
        status = make_git_status()

        widget = GitSection()
        widget.set_git_status(status)

        assert widget.get_staged_count() == 0

    def test_get_unstaged_count(self) -> None:
        """Test get_unstaged_count returns correct count."""
        status = make_git_status(
            unstaged=[
                make_file_status("README.md", staged=False),
            ],
        )

        widget = GitSection()
        widget.set_git_status(status)

        assert widget.get_unstaged_count() == 1

    def test_get_untracked_count(self) -> None:
        """Test get_untracked_count returns correct count."""
        status = make_git_status(
            untracked=[
                make_file_status(".env.example", status="?", staged=False),
                make_file_status("notes.txt", status="?", staged=False),
                make_file_status("temp.log", status="?", staged=False),
            ],
        )

        widget = GitSection()
        widget.set_git_status(status)

        assert widget.get_untracked_count() == 3

    def test_get_total_changes_count(self) -> None:
        """Test get_total_changes_count returns sum of all changes."""
        status = make_git_status(
            staged=[make_file_status("src/auth.py", staged=True)],
            unstaged=[make_file_status("README.md", staged=False)],
            untracked=[make_file_status(".env", status="?", staged=False)],
        )

        widget = GitSection()
        widget.set_git_status(status)

        assert widget.get_total_changes_count() == 3


class TestGitSectionSetProject:
    """Tests for set_project method."""

    def test_set_project_clears_status(self) -> None:
        """Test set_project clears git status."""
        status = make_git_status(
            staged=[make_file_status("src/auth.py", staged=True)],
        )

        widget = GitSection()
        widget.set_git_status(status)
        assert widget.git_status is not None

        with patch.object(widget, "refresh"):
            widget.set_project(make_project())

        assert widget.git_status is None

    def test_set_project_resets_selection(self) -> None:
        """Test set_project resets selection index."""
        status = make_git_status(
            staged=[
                make_file_status("src/auth.py", staged=True),
                make_file_status("src/users.py", staged=True),
            ],
        )

        widget = GitSection()
        widget.set_git_status(status)

        with patch.object(widget, "refresh"):
            widget.select_next()  # Move to second file

        assert widget._selected_index == 1

        with patch.object(widget, "refresh"):
            widget.set_project(make_project())

        assert widget._selected_index == 0


class TestGitSectionStatusIndicators:
    """Tests for status indicator constants."""

    def test_all_status_indicators_defined(self) -> None:
        """Test all expected status indicators are defined."""
        from iterm_controller.widgets.git_section import STATUS_INDICATORS

        expected_statuses = ["M", "A", "D", "R", "C", "U", "?"]

        for status in expected_statuses:
            assert status in STATUS_INDICATORS

    def test_status_indicator_format(self) -> None:
        """Test status indicator format is (char, color, description)."""
        from iterm_controller.widgets.git_section import STATUS_INDICATORS

        for status, (char, color, desc) in STATUS_INDICATORS.items():
            assert isinstance(char, str)
            assert len(char) == 1
            assert isinstance(color, str)
            assert isinstance(desc, str)


class TestGitSectionNoStatus:
    """Tests for widget behavior with no git status."""

    def test_selected_file_none_without_status(self) -> None:
        """Test selected_file is None when no git status."""
        widget = GitSection()

        assert widget.selected_file is None

    def test_has_staged_changes_false_without_status(self) -> None:
        """Test has_staged_changes is False when no git status."""
        widget = GitSection()

        assert widget.has_staged_changes is False

    def test_has_changes_false_without_status(self) -> None:
        """Test has_changes is False when no git status."""
        widget = GitSection()

        assert widget.has_changes is False

    def test_can_push_false_without_status(self) -> None:
        """Test can_push is False when no git status."""
        widget = GitSection()

        assert widget.can_push is False

    def test_counts_zero_without_status(self) -> None:
        """Test all counts are 0 when no git status."""
        widget = GitSection()

        assert widget.get_staged_count() == 0
        assert widget.get_unstaged_count() == 0
        assert widget.get_untracked_count() == 0
        assert widget.get_total_changes_count() == 0
