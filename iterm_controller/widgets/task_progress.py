"""Task progress widget for displaying completion statistics.

Shows overall task completion progress with counts and optional breakdown
by status (pending, in progress, complete, skipped, blocked).
"""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.widgets import Static

from iterm_controller.models import Plan, TaskStatus
from iterm_controller.state import PlanReloaded


class TaskProgressWidget(Static):
    """Displays task progress statistics.

    Shows completion counts and percentages for tasks in a plan.

    Example displays:
        Compact: "3/5 tasks complete (60%)"
        Detailed:
            Progress: 3/5 tasks (60%)
            ● 1 in progress  ○ 1 pending  ⊘ 0 blocked
    """

    DEFAULT_CSS = """
    TaskProgressWidget {
        height: auto;
        min-height: 1;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        plan: Plan | None = None,
        show_breakdown: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the task progress widget.

        Args:
            plan: Initial plan to display progress for.
            show_breakdown: If True, show status breakdown (pending, in progress, etc.)
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self._plan = plan or Plan()
        self._show_breakdown = show_breakdown

    def on_mount(self) -> None:
        """Initialize the progress content when mounted."""
        self.update(self._render_progress())

    @property
    def plan(self) -> Plan:
        """Get the current plan."""
        return self._plan

    @property
    def show_breakdown(self) -> bool:
        """Get whether status breakdown is shown."""
        return self._show_breakdown

    @show_breakdown.setter
    def show_breakdown(self, value: bool) -> None:
        """Set whether to show status breakdown."""
        self._show_breakdown = value
        self.update(self._render_progress())

    def refresh_plan(self, plan: Plan) -> None:
        """Update the displayed plan.

        Args:
            plan: New plan to display progress for.
        """
        self._plan = plan
        self.update(self._render_progress())

    def get_progress_text(self) -> str:
        """Get a simple text representation of progress.

        Returns:
            String like "3/5 tasks complete" or "0 tasks" if empty.
        """
        tasks = self._plan.all_tasks
        if not tasks:
            return "0 tasks"

        completed = sum(
            1
            for t in tasks
            if t.status in (TaskStatus.COMPLETE, TaskStatus.SKIPPED)
        )
        total = len(tasks)
        return f"{completed}/{total} tasks complete"

    def get_progress_percentage(self) -> float:
        """Get the completion percentage.

        Returns:
            Percentage from 0.0 to 100.0
        """
        return self._plan.overall_progress

    def get_status_counts(self) -> dict[TaskStatus, int]:
        """Get counts for each status.

        Returns:
            Dictionary mapping TaskStatus to count.
        """
        counts = {status: 0 for status in TaskStatus}
        for task in self._plan.all_tasks:
            counts[task.status] += 1
        return counts

    def _render_progress(self) -> Text:
        """Render the progress display.

        Returns:
            Rich Text object with progress information.
        """
        tasks = self._plan.all_tasks
        if not tasks:
            return Text("No tasks", style="dim italic")

        # Calculate completion
        summary = self._plan.completion_summary
        completed = summary.get("complete", 0) + summary.get("skipped", 0)
        total = len(tasks)
        percent = self._plan.overall_progress

        text = Text()

        # Main progress line
        text.append(f"{completed}/{total} tasks complete", style="bold")
        text.append(f" ({percent:.0f}%)", style="dim")

        # Optional breakdown
        if self._show_breakdown:
            text.append("\n")
            self._append_breakdown(text, summary)

        return text

    def _append_breakdown(self, text: Text, summary: dict[str, int]) -> None:
        """Append status breakdown to text.

        Args:
            text: Text object to append to.
            summary: Status summary from plan.completion_summary.
        """
        parts = []

        # In progress
        in_progress = summary.get("in_progress", 0)
        if in_progress > 0:
            parts.append(("●", "yellow", f"{in_progress} in progress"))

        # Pending
        pending = summary.get("pending", 0)
        if pending > 0:
            parts.append(("○", "white", f"{pending} pending"))

        # Blocked
        blocked = summary.get("blocked", 0)
        if blocked > 0:
            parts.append(("⊘", "red", f"{blocked} blocked"))

        # Skipped
        skipped = summary.get("skipped", 0)
        if skipped > 0:
            parts.append(("⊖", "dim", f"{skipped} skipped"))

        for i, (icon, color, label) in enumerate(parts):
            if i > 0:
                text.append("  ")
            text.append(f"{icon} ", style=color)
            text.append(label, style="dim")

    def render(self) -> Text:
        """Render the widget content.

        Returns:
            Rich Text object to display.
        """
        return self._render_progress()

    def on_plan_reloaded(self, message: PlanReloaded) -> None:
        """Handle plan reloaded event.

        Args:
            message: The plan reloaded message.
        """
        self.refresh_plan(message.plan)
