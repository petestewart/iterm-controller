"""Session card widget for Mission Control.

Displays a single session with header, optional progress bar, and live output log.
This is the primary widget for viewing session activity in Mission Control.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Static

from iterm_controller.models import AttentionState, ManagedSession, SessionProgress, SessionType
from iterm_controller.status_display import get_attention_color, get_attention_icon

if TYPE_CHECKING:
    from textual.app import ComposeResult


# Constants for output log sizing
COLLAPSED_OUTPUT_LINES = 4
EXPANDED_OUTPUT_LINES = 20
MAX_OUTPUT_BUFFER_LINES = 100


class SessionCardHeader(Static):
    """Header row for a session card.

    Displays: project name | session type/name | status | duration

    Example:
        Project A | Claude: Creating PLAN.md | WORKING | 00:03:42
    """

    DEFAULT_CSS = """
    SessionCardHeader {
        height: auto;
        padding: 0 1;
    }

    SessionCardHeader .header-row {
        layout: horizontal;
        height: auto;
    }

    SessionCardHeader .project-name {
        width: auto;
        text-style: bold;
    }

    SessionCardHeader .session-info {
        width: 1fr;
        padding-left: 1;
    }

    SessionCardHeader .status {
        width: 10;
        text-align: right;
    }

    SessionCardHeader .status.waiting {
        color: $warning;
    }

    SessionCardHeader .status.working {
        color: $success;
    }

    SessionCardHeader .status.idle {
        color: $text-muted;
    }

    SessionCardHeader .duration {
        width: 10;
        text-align: right;
        color: $text-muted;
    }
    """

    def __init__(self, session: ManagedSession, **kwargs: Any) -> None:
        """Initialize the session card header.

        Args:
            session: The session to display.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self.session = session

    def compose(self) -> ComposeResult:
        """Compose the header layout."""
        yield Static(
            self._render_header(),
            classes="header-row",
        )

    def _render_header(self) -> Text:
        """Render the header as Rich Text.

        Returns:
            Rich Text object containing the header content.
        """
        text = Text()

        # Project name
        project_name = self.session.project_id
        text.append(project_name, style="bold")
        text.append(" | ", style="dim")

        # Session info (type + activity)
        session_info = self._get_session_info()
        text.append(session_info)
        text.append(" | ", style="dim")

        # Status with color
        status = self.session.attention_state.value.upper()
        status_color = get_attention_color(self.session.attention_state)
        text.append(f"{status:>10}", style=status_color)
        text.append(" | ", style="dim")

        # Duration
        duration = self._format_duration()
        text.append(duration, style="dim")

        return text

    def _get_session_info(self) -> str:
        """Get session type and current activity description.

        Returns:
            Formatted string like "Claude: Creating PLAN.md"
        """
        # Use display_name if set, otherwise use template_id with type prefix
        if self.session.display_name:
            return self.session.display_name

        type_names = {
            SessionType.CLAUDE_TASK: "Claude",
            SessionType.ORCHESTRATOR: "Orchestrator",
            SessionType.REVIEW: "Review",
            SessionType.TEST_RUNNER: "Tests",
            SessionType.SCRIPT: "Script",
            SessionType.SERVER: "Server",
            SessionType.SHELL: "Shell",
        }
        type_name = type_names.get(self.session.session_type, "Session")

        # Add task info if linked
        if self.session.task_id:
            task_title = self.session.metadata.get("task_title", self.session.task_id)
            return f"{type_name}: {task_title}"

        return f"{type_name}: {self.session.template_id}"

    def _format_duration(self) -> str:
        """Format elapsed time as HH:MM:SS.

        Returns:
            Formatted duration string.
        """
        elapsed = (datetime.now() - self.session.spawned_at).total_seconds()
        hours, remainder = divmod(int(elapsed), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def update_session(self, session: ManagedSession) -> None:
        """Update the session and refresh the display.

        Args:
            session: Updated session data.
        """
        self.session = session
        # Re-render the header content
        header_static = self.query_one(".header-row", Static)
        header_static.update(self._render_header())


class OrchestratorProgress(Static):
    """Progress bar widget for orchestrator sessions.

    Shows completed/total tasks with a visual progress bar and current task info.

    Example:
        Progress: ########........ 3/6 tasks
        [2.3] Adding user authentication
    """

    DEFAULT_CSS = """
    OrchestratorProgress {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
    }
    """

    # Width of the progress bar in characters
    PROGRESS_BAR_WIDTH = 16

    def __init__(self, progress: SessionProgress | None = None, **kwargs: Any) -> None:
        """Initialize the orchestrator progress widget.

        Args:
            progress: Progress data to display.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self.progress = progress

    def render(self) -> Text:
        """Render the progress bar with task counts.

        Returns:
            Rich Text object containing progress display.
        """
        if not self.progress:
            return Text("No progress data", style="dim")

        completed = self.progress.completed_tasks
        total = self.progress.total_tasks

        # Calculate progress bar
        if total > 0:
            filled = int((completed / total) * self.PROGRESS_BAR_WIDTH)
            bar = "#" * filled + "." * (self.PROGRESS_BAR_WIDTH - filled)
        else:
            bar = "." * self.PROGRESS_BAR_WIDTH

        text = Text()
        text.append("Progress: ", style="dim")
        text.append(bar, style="cyan")
        text.append(f" {completed}/{total} tasks", style="dim")

        # Add current task info if available
        if self.progress.current_task_id:
            task_title = self.progress.current_task_title or self.progress.current_task_id
            text.append("\n")
            text.append(f"[{self.progress.current_task_id}] ", style="bold cyan")
            text.append(task_title)

        return text

    def update_progress(self, progress: SessionProgress | None) -> None:
        """Update progress data and refresh display.

        Args:
            progress: New progress data.
        """
        self.progress = progress
        self.refresh()


class OutputLog(Static):
    """Scrollable output display with ANSI color support.

    Displays the last N lines of session output, with collapsed (4 lines)
    and expanded (20 lines) modes.

    Features:
    - Rolling buffer of output lines (max 100)
    - ANSI color preservation
    - Auto-scroll to newest content
    - Line prefix with ">" indicator
    """

    DEFAULT_CSS = """
    OutputLog {
        height: 4;
        overflow-y: auto;
    }

    OutputLog.expanded {
        height: 20;
    }
    """

    def __init__(
        self,
        session: ManagedSession | None = None,
        expanded: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the output log widget.

        Args:
            session: Session to display output from.
            expanded: Whether to show expanded view (20 lines vs 4).
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self.session = session
        self.expanded = expanded
        self._lines: deque[str] = deque(maxlen=MAX_OUTPUT_BUFFER_LINES)

        if expanded:
            self.add_class("expanded")

    @property
    def max_display_lines(self) -> int:
        """Get the maximum number of lines to display.

        Returns:
            Number of lines based on expanded state.
        """
        return EXPANDED_OUTPUT_LINES if self.expanded else COLLAPSED_OUTPUT_LINES

    def render(self) -> Text:
        """Render the last N lines of output.

        Returns:
            Rich Text object with output content.
        """
        if not self._lines:
            return Text("Waiting for output...", style="dim italic")

        output_lines = list(self._lines)[-self.max_display_lines :]

        text = Text()
        for i, line in enumerate(output_lines):
            if i > 0:
                text.append("\n")
            # Prefix each line with indicator
            text.append("> ", style="dim")
            text.append(line)

        return text

    def append_output(self, output: str) -> None:
        """Append new output and refresh display.

        Splits multi-line output and adds each non-empty line to the buffer.

        Args:
            output: New output text (may contain newlines).
        """
        for line in output.split("\n"):
            if line.strip():
                self._lines.append(line)
        self.refresh()

    def set_expanded(self, expanded: bool) -> None:
        """Set the expanded state.

        Args:
            expanded: Whether to show expanded view.
        """
        self.expanded = expanded
        if expanded:
            self.add_class("expanded")
        else:
            self.remove_class("expanded")
        self.refresh()

    def clear(self) -> None:
        """Clear all output lines."""
        self._lines.clear()
        self.refresh()

    def get_all_output(self) -> list[str]:
        """Get all buffered output lines.

        Returns:
            List of all output lines in buffer.
        """
        return list(self._lines)


class SessionCard(Static, can_focus=True):
    """Card displaying a session with header, progress bar, and live output.

    The main widget for viewing session activity in Mission Control.
    Each session gets a card showing:
    - Header with project name, session info, status, duration
    - Progress bar (only for orchestrator sessions)
    - Live output log

    Cards can be expanded/collapsed to show more or less output.
    The card's border color indicates the attention state.
    """

    DEFAULT_CSS = """
    SessionCard {
        border: solid $primary;
        margin: 1;
        padding: 1;
        height: auto;
    }

    SessionCard:focus {
        border: double $accent;
    }

    SessionCard.waiting {
        border: solid $warning;
    }

    SessionCard.working {
        border: solid $success;
    }

    SessionCard.idle {
        border: solid $surface-lighten-2;
    }

    SessionCard > .separator {
        color: $surface-lighten-2;
        margin-top: 1;
        margin-bottom: 1;
    }
    """

    class Selected(Message):
        """Posted when this card is selected/focused."""

        def __init__(self, session: ManagedSession) -> None:
            super().__init__()
            self.session = session

    class ExpandToggled(Message):
        """Posted when expanded state is toggled."""

        def __init__(self, session_id: str, expanded: bool) -> None:
            super().__init__()
            self.session_id = session_id
            self.expanded = expanded

    def __init__(
        self,
        session: ManagedSession,
        expanded: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the session card.

        Args:
            session: The session to display.
            expanded: Whether to show expanded output view.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self.session = session
        self.expanded = expanded

        # Set ID for easy lookup
        self.id = f"session-{session.id}"

        # Add attention state class for border color
        self._update_attention_class()

    def compose(self) -> ComposeResult:
        """Compose the card layout."""
        yield SessionCardHeader(self.session, id="header")

        # Show progress bar for orchestrator sessions
        if self.session.session_type == SessionType.ORCHESTRATOR:
            yield OrchestratorProgress(self.session.progress, id="progress")

        # Separator
        yield Static("─" * 70, classes="separator")

        # Output log
        yield OutputLog(session=self.session, expanded=self.expanded, id="output-log")

    def _update_attention_class(self) -> None:
        """Update CSS class based on attention state."""
        # Remove old state classes
        self.remove_class("waiting", "working", "idle")

        # Add current state class
        state_class = self.session.attention_state.value
        self.add_class(state_class)

    def update_session(self, session: ManagedSession) -> None:
        """Update session data and refresh display.

        Args:
            session: Updated session data.
        """
        self.session = session
        self._update_attention_class()

        # Update header
        try:
            header = self.query_one("#header", SessionCardHeader)
            header.update_session(session)
        except Exception:
            pass

        # Update progress if orchestrator
        if session.session_type == SessionType.ORCHESTRATOR:
            try:
                progress = self.query_one("#progress", OrchestratorProgress)
                progress.update_progress(session.progress)
            except Exception:
                pass

    def update_output(self, output: str) -> None:
        """Update the output log with new content.

        Args:
            output: New output text to append.
        """
        try:
            log = self.query_one("#output-log", OutputLog)
            log.append_output(output)
        except Exception:
            pass

    def toggle_expanded(self) -> None:
        """Toggle between expanded and collapsed views."""
        self.expanded = not self.expanded

        try:
            log = self.query_one("#output-log", OutputLog)
            log.set_expanded(self.expanded)
        except Exception:
            pass

        self.post_message(self.ExpandToggled(self.session.id, self.expanded))

    def on_focus(self) -> None:
        """Handle focus event."""
        self.post_message(self.Selected(self.session))

    def get_status_icon(self) -> str:
        """Get the status icon for this session.

        Returns:
            Unicode icon for the attention state.
        """
        return get_attention_icon(self.session.attention_state)

    def get_status_color(self) -> str:
        """Get the status color for this session.

        Returns:
            Color name for the attention state.
        """
        return get_attention_color(self.session.attention_state)
