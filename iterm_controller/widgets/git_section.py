"""Git section widget for Project Screen.

Displays collapsible section showing git status with branch info,
staged/unstaged/untracked files, and commit/push actions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Static

if TYPE_CHECKING:
    from iterm_controller.models import GitFileStatus, GitStatus, Project

logger = logging.getLogger(__name__)

# Status indicator characters
STATUS_INDICATORS = {
    "M": ("M", "yellow", "Modified"),
    "A": ("A", "green", "Added"),
    "D": ("D", "red", "Deleted"),
    "R": ("R", "cyan", "Renamed"),
    "C": ("C", "cyan", "Copied"),
    "U": ("U", "magenta", "Unmerged"),
    "?": ("?", "dim", "Untracked"),
}


class GitSection(Static):
    """Git status section with collapsible content.

    Displays a collapsible section showing:
    - Branch name with ahead/behind counts
    - Staged changes (green)
    - Unstaged changes (yellow)
    - Untracked files (dim)
    - Commit and push action buttons

    Example display:
        -- Git Status ----------------------------------------
          main ↑2 ↓0
        Staged:
        > M  src/auth.py
          A  src/users.py
        Unstaged:
          M  README.md
        Untracked:
          ?  .env.example
        [c] Commit  [p] Push  [r] Refresh
    """

    DEFAULT_CSS = """
    GitSection {
        height: auto;
        min-height: 6;
        padding: 0 1;
        border: solid $surface-lighten-1;
        margin-bottom: 1;
    }

    GitSection .section-header {
        color: $text;
        text-style: bold;
        margin-bottom: 1;
    }

    GitSection .section-header-collapsed {
        color: $text-muted;
        text-style: bold;
        margin-bottom: 0;
    }

    GitSection #git-container {
        height: auto;
        padding-left: 1;
    }

    GitSection #git-actions {
        margin-top: 1;
        height: auto;
    }

    GitSection #git-actions Button {
        margin-right: 1;
        width: auto;
        min-width: 10;
    }

    GitSection .branch-info {
        margin-bottom: 1;
    }

    GitSection .category-header {
        color: $text-muted;
        margin-top: 1;
    }

    GitSection .conflict-warning {
        color: $error;
        text-style: bold;
    }
    """

    class FileSelected(Message):
        """Posted when a file is selected."""

        def __init__(
            self,
            file_path: str,
            status: str,
            staged: bool,
        ) -> None:
            super().__init__()
            self.file_path = file_path
            self.status = status
            self.staged = staged

    class CommitRequested(Message):
        """Posted when user requests to commit."""

        def __init__(self, staged_files: list[str]) -> None:
            super().__init__()
            self.staged_files = staged_files

    class PushRequested(Message):
        """Posted when user requests to push."""

        def __init__(self, branch: str, ahead: int) -> None:
            super().__init__()
            self.branch = branch
            self.ahead = ahead

    class RefreshRequested(Message):
        """Posted when user requests to refresh git status."""

        pass

    class StageFileRequested(Message):
        """Posted when user wants to stage a file."""

        def __init__(self, file_path: str) -> None:
            super().__init__()
            self.file_path = file_path

    class UnstageFileRequested(Message):
        """Posted when user wants to unstage a file."""

        def __init__(self, file_path: str) -> None:
            super().__init__()
            self.file_path = file_path

    def __init__(
        self,
        project: Project | None = None,
        collapsed: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the git section widget.

        Args:
            project: Project to show git status for.
            collapsed: Whether to start collapsed.
            **kwargs: Additional arguments passed to Static.
        """
        self._project = project
        self._collapsed = collapsed
        self._git_status: GitStatus | None = None
        self._selected_index = 0
        self._all_files: list[tuple[str, str, bool]] = []  # (path, status, staged)
        super().__init__(**kwargs)

    @property
    def project(self) -> Project | None:
        """Get the current project."""
        return self._project

    @property
    def collapsed(self) -> bool:
        """Get collapsed state."""
        return self._collapsed

    @property
    def git_status(self) -> GitStatus | None:
        """Get the current git status."""
        return self._git_status

    @property
    def selected_file(self) -> tuple[str, str, bool] | None:
        """Get the currently selected file.

        Returns:
            Tuple of (path, status, staged) or None if no selection.
        """
        if not self._git_status or self._collapsed:
            return None
        if 0 <= self._selected_index < len(self._all_files):
            return self._all_files[self._selected_index]
        return None

    @property
    def has_staged_changes(self) -> bool:
        """Check if there are staged changes."""
        return bool(self._git_status and self._git_status.staged)

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        if not self._git_status:
            return False
        return bool(
            self._git_status.staged
            or self._git_status.unstaged
            or self._git_status.untracked
        )

    @property
    def can_push(self) -> bool:
        """Check if there are commits to push."""
        return bool(self._git_status and self._git_status.ahead > 0)

    def set_project(self, project: Project) -> None:
        """Set the project and clear git status.

        Args:
            project: Project to show git status for.
        """
        self._project = project
        self._git_status = None
        self._selected_index = 0
        self._all_files = []
        self.refresh()

    def set_git_status(self, status: GitStatus) -> None:
        """Update git status and refresh display.

        Args:
            status: New git status.
        """
        self._git_status = status
        self._rebuild_file_list()

        # Reset selection if out of bounds
        if self._selected_index >= len(self._all_files):
            self._selected_index = max(0, len(self._all_files) - 1)

        self.refresh()

    def _rebuild_file_list(self) -> None:
        """Rebuild the flat list of all files for navigation."""
        self._all_files = []
        if not self._git_status:
            return

        # Add staged files
        if self._git_status.staged:
            for f in self._git_status.staged:
                self._all_files.append((f.path, f.status, True))

        # Add unstaged files
        if self._git_status.unstaged:
            for f in self._git_status.unstaged:
                self._all_files.append((f.path, f.status, False))

        # Add untracked files
        if self._git_status.untracked:
            for f in self._git_status.untracked:
                self._all_files.append((f.path, f.status, False))

    def toggle_collapsed(self) -> None:
        """Toggle section collapsed state."""
        self._collapsed = not self._collapsed
        self.refresh()

    def select_next(self) -> None:
        """Select the next file."""
        if self._collapsed:
            return
        if self._all_files:
            self._selected_index = min(
                self._selected_index + 1, len(self._all_files) - 1
            )
            self.refresh()

    def select_previous(self) -> None:
        """Select the previous file."""
        if self._collapsed:
            return
        if self._selected_index > 0:
            self._selected_index -= 1
            self.refresh()

    def action_select_file(self) -> None:
        """Handle selection of current file."""
        selected = self.selected_file
        if selected:
            path, status, staged = selected
            self.post_message(self.FileSelected(path, status, staged))

    def action_stage_file(self) -> None:
        """Stage the currently selected file."""
        selected = self.selected_file
        if selected and not selected[2]:  # Not already staged
            self.post_message(self.StageFileRequested(selected[0]))

    def action_unstage_file(self) -> None:
        """Unstage the currently selected file."""
        selected = self.selected_file
        if selected and selected[2]:  # Currently staged
            self.post_message(self.UnstageFileRequested(selected[0]))

    def action_commit(self) -> None:
        """Handle commit request."""
        if self.has_staged_changes and self._git_status and self._git_status.staged:
            staged_files = [f.path for f in self._git_status.staged]
            self.post_message(self.CommitRequested(staged_files))

    def action_push(self) -> None:
        """Handle push request."""
        if self.can_push and self._git_status:
            self.post_message(
                self.PushRequested(
                    self._git_status.branch,
                    self._git_status.ahead,
                )
            )

    def action_refresh(self) -> None:
        """Handle refresh request."""
        self.post_message(self.RefreshRequested())

    def compose(self) -> "ComposeResult":  # type: ignore[name-defined]
        """Compose the widget content."""
        from textual.app import ComposeResult

        # Section header
        collapse_icon = ">" if self._collapsed else "v"
        header_class = (
            "section-header-collapsed" if self._collapsed else "section-header"
        )
        yield Static(
            f"{collapse_icon} Git Status", classes=header_class, id="section-header"
        )

        if not self._collapsed:
            # Pre-create the content Static to avoid remove/mount cycles
            yield Vertical(
                Static("", id="git-content"),
                id="git-container",
            )
            yield Horizontal(
                Button("[c] Commit", id="commit-btn"),
                Button("[p] Push", id="push-btn"),
                Button("[r] Refresh", id="refresh-btn"),
                id="git-actions",
            )

    def on_mount(self) -> None:
        """Initialize when mounted."""
        self.refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "commit-btn":
            self.action_commit()
        elif event.button.id == "push-btn":
            self.action_push()
        elif event.button.id == "refresh-btn":
            self.action_refresh()

    def _render_branch_info(self) -> Text:
        """Render branch information line.

        Returns:
            Rich Text object with branch info.
        """
        text = Text()

        if not self._git_status:
            text.append("No git status available", style="dim")
            return text

        # Branch name
        text.append(self._git_status.branch, style="bold cyan")

        # Ahead/behind indicators
        if self._git_status.ahead > 0:
            text.append(f" ↑{self._git_status.ahead}", style="green")
        if self._git_status.behind > 0:
            text.append(f" ↓{self._git_status.behind}", style="yellow")

        # Conflict warning
        if self._git_status.has_conflicts:
            text.append(" ⚠ CONFLICTS", style="bold red")

        return text

    def _render_file_row(
        self,
        file_path: str,
        status: str,
        staged: bool,
        is_selected: bool,
    ) -> Text:
        """Render a single file row.

        Args:
            file_path: Path to the file.
            status: Git status character.
            staged: Whether the file is staged.
            is_selected: Whether this file is selected.

        Returns:
            Rich Text object for the row.
        """
        text = Text()

        # Selection indicator
        if is_selected:
            text.append("> ", style="bold cyan")
        else:
            text.append("  ")

        # Status indicator
        indicator_info = STATUS_INDICATORS.get(status, (status, "white", "Unknown"))
        indicator_char, indicator_color, _ = indicator_info

        # Color based on staged vs unstaged
        if staged:
            color = "green"
        elif status == "?":
            color = "dim"
        else:
            color = indicator_color

        text.append(f"{indicator_char}  ", style=color)

        # File path
        path_style = "bold" if is_selected else ""
        text.append(file_path, style=path_style)

        # Action hints for selected item
        if is_selected:
            if staged:
                text.append(" [u]nstage", style="dim cyan")
            else:
                text.append(" [s]tage", style="dim cyan")

        return text

    def _build_git_content(self) -> Text:
        """Build the git status content text."""
        if not self._project:
            return Text("[dim]No project selected[/dim]")

        if not self._git_status:
            return Text("[dim]Loading git status...[/dim]")

        # Build content
        lines: list[Text] = []

        # Branch info
        lines.append(self._render_branch_info())

        # Build file index for selection tracking
        file_index = 0

        # Staged files
        if self._git_status.staged:
            lines.append(Text("Staged:", style="green bold"))
            for f in self._git_status.staged:
                is_selected = file_index == self._selected_index
                lines.append(self._render_file_row(f.path, f.status, True, is_selected))
                file_index += 1

        # Unstaged files
        if self._git_status.unstaged:
            lines.append(Text("Unstaged:", style="yellow bold"))
            for f in self._git_status.unstaged:
                is_selected = file_index == self._selected_index
                lines.append(
                    self._render_file_row(f.path, f.status, False, is_selected)
                )
                file_index += 1

        # Untracked files
        if self._git_status.untracked:
            lines.append(Text("Untracked:", style="dim bold"))
            for f in self._git_status.untracked:
                is_selected = file_index == self._selected_index
                lines.append(
                    self._render_file_row(f.path, f.status, False, is_selected)
                )
                file_index += 1

        # No changes message
        if not self.has_changes:
            lines.append(Text("No changes", style="dim"))

        # Combine into single content
        content = Text()
        for i, line in enumerate(lines):
            if i > 0:
                content.append("\n")
            content.append_text(line)

        return content

    def _update_git_display(self) -> None:
        """Update the git content using update() to avoid DOM thrashing."""
        try:
            content_widget = self.query_one("#git-content", Static)
            content_widget.update(self._build_git_content())
        except Exception:
            pass
        self._update_button_states()

    def _update_button_states(self) -> None:
        """Update button disabled states based on current status."""
        try:
            commit_btn = self.query_one("#commit-btn", Button)
            commit_btn.disabled = not self.has_staged_changes
        except Exception:
            pass

        try:
            push_btn = self.query_one("#push-btn", Button)
            push_btn.disabled = not self.can_push
        except Exception:
            pass

    def refresh(self, *args: Any, **kwargs: Any) -> None:
        """Override refresh to update git display."""
        # Update section header
        try:
            header = self.query_one("#section-header", Static)
            collapse_icon = ">" if self._collapsed else "v"
            header.update(f"{collapse_icon} Git Status")
            header.set_class(self._collapsed, "section-header-collapsed")
            header.set_class(not self._collapsed, "section-header")
        except Exception:
            pass

        # Update git status if not collapsed
        if not self._collapsed:
            self._update_git_display()

        super().refresh(*args, **kwargs)

    def get_staged_count(self) -> int:
        """Get count of staged files.

        Returns:
            Number of staged files.
        """
        if not self._git_status or not self._git_status.staged:
            return 0
        return len(self._git_status.staged)

    def get_unstaged_count(self) -> int:
        """Get count of unstaged files.

        Returns:
            Number of unstaged files.
        """
        if not self._git_status or not self._git_status.unstaged:
            return 0
        return len(self._git_status.unstaged)

    def get_untracked_count(self) -> int:
        """Get count of untracked files.

        Returns:
            Number of untracked files.
        """
        if not self._git_status or not self._git_status.untracked:
            return 0
        return len(self._git_status.untracked)

    def get_total_changes_count(self) -> int:
        """Get total count of all changes.

        Returns:
            Total number of changed files.
        """
        return (
            self.get_staged_count()
            + self.get_unstaged_count()
            + self.get_untracked_count()
        )
