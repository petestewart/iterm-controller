"""GitHub panel widget with graceful degradation.

Displays GitHub status including branch info, sync status, and PR details.
Handles unavailable/unauthenticated states gracefully.
"""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.widgets import Static

from iterm_controller.models import GitHubStatus, PullRequest


class GitHubPanelWidget(Static):
    """Displays GitHub status with graceful degradation.

    This widget shows GitHub information when available:
    - Current branch and sync status (ahead/behind)
    - PR information (number, title, status, checks)
    - Rate limit and offline indicators

    Degrades gracefully when gh CLI is unavailable or not authenticated.

    Example display (available):
        Branch: feature-branch
        ↑2 ↓1 from main

        PR #123: Add feature X
        ● Checks passing

    Example display (unavailable):
        GitHub: gh CLI not installed

    Attributes:
        DEFAULT_CSS: Widget styling.
    """

    DEFAULT_CSS = """
    GitHubPanelWidget {
        height: auto;
        min-height: 1;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        status: GitHubStatus | None = None,
        error_message: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the GitHub panel widget.

        Args:
            status: Initial GitHub status to display.
            error_message: Error message when GitHub is unavailable.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self._status = status
        self._error_message = error_message

    def on_mount(self) -> None:
        """Initialize the GitHub panel content when mounted."""
        self.update(self._render_panel())

    @property
    def status(self) -> GitHubStatus | None:
        """Get the current GitHub status."""
        return self._status

    @property
    def is_available(self) -> bool:
        """Check if GitHub integration is available."""
        return self._status is not None and self._status.available

    def update_status(self, status: GitHubStatus | None) -> None:
        """Update the GitHub status and refresh display.

        Args:
            status: New GitHub status to display.
        """
        self._status = status
        self._error_message = None
        self.update(self._render_panel())

    def set_error(self, message: str) -> None:
        """Set an error message and refresh display.

        Args:
            message: Error message to display.
        """
        self._status = None
        self._error_message = message
        self.update(self._render_panel())

    def set_unavailable(self, message: str | None = None) -> None:
        """Mark GitHub as unavailable.

        Args:
            message: Optional message explaining why unavailable.
        """
        self._status = GitHubStatus(available=False, error_message=message)
        self._error_message = message
        self.update(self._render_panel())

    def _render_warning_indicators(self) -> Text | None:
        """Render rate limit or offline warning indicators.

        Returns:
            Text with warning indicator or None if no warnings.
        """
        if not self._status:
            return None

        if self._status.rate_limited:
            return Text("Rate limited - showing cached data", style="yellow")
        elif self._status.offline:
            return Text("Offline - showing cached data", style="yellow")

        return None

    def _render_branch_info(self) -> Text:
        """Render branch and sync status.

        Returns:
            Text with branch and sync information.
        """
        text = Text()

        if self._status and self._status.current_branch:
            text.append("Branch: ")
            text.append(self._status.current_branch, style="bold")

        return text

    def _render_sync_status(self) -> Text | None:
        """Render ahead/behind sync status.

        Returns:
            Text with sync status or None if in sync.
        """
        if not self._status:
            return None

        parts = []
        if self._status.ahead > 0:
            parts.append(f"\u2191{self._status.ahead}")
        if self._status.behind > 0:
            parts.append(f"\u2193{self._status.behind}")

        if not parts:
            return None

        text = Text()
        text.append(" ".join(parts))
        text.append(f" from {self._status.default_branch}", style="dim")
        return text

    def _render_pr_info(self) -> Text | None:
        """Render PR information.

        Returns:
            Text with PR details or None if no PR.
        """
        if not self._status or not self._status.pr:
            return None

        pr = self._status.pr
        text = Text()

        # PR title line
        title = f"PR #{pr.number}: {pr.title}"
        if pr.draft:
            text.append(title)
            text.append(" [Draft]", style="dim")
        else:
            text.append(title)

        return text

    def _render_pr_status(self) -> Text | None:
        """Render PR status (merged, checks, reviews).

        Returns:
            Text with PR status indicators or None if no PR.
        """
        if not self._status or not self._status.pr:
            return None

        pr = self._status.pr
        text = Text()

        # Merged status
        if pr.merged:
            text.append("\u2713 Merged", style="green")
            return text

        # Check status
        if pr.checks_passing is True:
            text.append("\u2713 Checks passing", style="green")
        elif pr.checks_passing is False:
            text.append("\u2717 Checks failing", style="red")

        # Review status
        if pr.reviews_pending > 0:
            if len(text) > 0:
                text.append(" | ")
            review_text = (
                "1 review pending"
                if pr.reviews_pending == 1
                else f"{pr.reviews_pending} reviews pending"
            )
            text.append(review_text, style="yellow")

        # Comment count
        if pr.comments > 0:
            if len(text) > 0:
                text.append(" | ")
            comment_text = (
                "1 comment" if pr.comments == 1 else f"{pr.comments} comments"
            )
            text.append(comment_text, style="dim")

        return text if len(text) > 0 else None

    def _render_unavailable(self) -> Text:
        """Render unavailable state.

        Returns:
            Text indicating GitHub is not available.
        """
        text = Text()

        if self._error_message:
            text.append("GitHub: ", style="dim")
            text.append(self._error_message, style="dim")
        elif self._status and self._status.error_message:
            text.append("GitHub: ", style="dim")
            text.append(self._status.error_message, style="dim")
        else:
            text.append("GitHub: Not available", style="dim")

        return text

    def _render_panel(self) -> Text:
        """Render the complete GitHub panel.

        Returns:
            Text object containing the full panel.
        """
        # Not available - show error message
        if not self._status or not self._status.available:
            return self._render_unavailable()

        lines: list[Text] = []

        # Warning indicators (rate limit, offline)
        warning = self._render_warning_indicators()
        if warning:
            lines.append(warning)

        # Branch info
        branch = self._render_branch_info()
        if len(branch) > 0:
            lines.append(branch)

        # Sync status
        sync = self._render_sync_status()
        if sync:
            lines.append(sync)

        # PR info
        pr_info = self._render_pr_info()
        if pr_info:
            # Add blank line before PR section
            if lines:
                lines.append(Text())
            lines.append(pr_info)

            # PR status
            pr_status = self._render_pr_status()
            if pr_status:
                lines.append(pr_status)

        # Join all lines
        if not lines:
            return Text("GitHub: No data", style="dim")

        result = Text()
        for i, line in enumerate(lines):
            if i > 0:
                result.append("\n")
            result.append_text(line)

        return result

    def render(self) -> Text:
        """Render the widget content.

        Returns:
            Text object to display.
        """
        return self._render_panel()

    def has_pr(self) -> bool:
        """Check if there's a PR for the current branch.

        Returns:
            True if there's a PR, False otherwise.
        """
        return self._status is not None and self._status.pr is not None

    def get_pr_url(self) -> str | None:
        """Get the PR URL if available.

        Returns:
            PR URL or None.
        """
        if self._status and self._status.pr:
            return self._status.pr.url
        return None

    def is_checks_passing(self) -> bool | None:
        """Check if PR checks are passing.

        Returns:
            True if passing, False if failing, None if unknown.
        """
        if self._status and self._status.pr:
            return self._status.pr.checks_passing
        return None

    def is_pr_merged(self) -> bool:
        """Check if PR is merged.

        Returns:
            True if merged, False otherwise.
        """
        if self._status and self._status.pr:
            return self._status.pr.merged
        return False
