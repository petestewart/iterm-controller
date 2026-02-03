"""Sessions panel widget for Project Screen.

Displays active sessions for the current project in a compact format with
mini session cards showing session info and last output line.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Static

from iterm_controller.models import AttentionState, ManagedSession, SessionType
from iterm_controller.state import SessionClosed, SessionOutputUpdated, SessionSpawned, SessionStatusChanged
from iterm_controller.status_display import get_attention_color, get_attention_icon

if TYPE_CHECKING:
    from textual.app import ComposeResult


# Constants for mini session display
MINI_SESSION_NAME_WIDTH = 30
MINI_OUTPUT_WIDTH = 40
MINI_OUTPUT_TRUNCATE = 45


class MiniSessionCard(Static):
    """Compact session card for project screen sessions panel.

    Displays a single session in a compact format with:
    - Index number for keyboard selection
    - Session type and current activity
    - Separator
    - Last line of output (truncated)

    Example:
        1. Claude: Task 2.1 │ > Creating User model...
    """

    DEFAULT_CSS = """
    MiniSessionCard {
        height: 1;
        padding: 0 1;
    }

    MiniSessionCard:hover {
        background: $surface-lighten-1;
    }

    MiniSessionCard.selected {
        background: $accent 20%;
    }
    """

    class Selected(Message):
        """Posted when this mini card is selected/clicked."""

        def __init__(self, session: ManagedSession) -> None:
            super().__init__()
            self.session = session

    def __init__(
        self,
        session: ManagedSession,
        index: int,
        selected: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the mini session card.

        Args:
            session: The session to display.
            index: The 1-based index for display and keyboard selection.
            selected: Whether this card is currently selected.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self.session = session
        self.index = index
        self._selected = selected

        if selected:
            self.add_class("selected")

    def render(self) -> Text:
        """Render the mini session card.

        Returns:
            Rich Text object containing the compact session display.
        """
        text = Text()

        # Status icon with color
        icon = get_attention_icon(self.session.attention_state)
        color = get_attention_color(self.session.attention_state)
        text.append(f"{icon} ", style=color)

        # Index
        text.append(f"{self.index}. ", style="bold" if self._selected else "")

        # Session info (type + activity/task)
        session_info = self._get_session_info()
        text.append(f"{session_info:<{MINI_SESSION_NAME_WIDTH}}", style="bold" if self._selected else "")

        # Separator
        text.append(" │ ", style="dim")

        # Last output line (truncated)
        last_output = self._get_last_output()
        text.append(last_output, style="dim")

        return text

    def _get_session_info(self) -> str:
        """Get session type and current activity description.

        Returns:
            Formatted string like "Claude: Task 2.1" or "Tests: pytest"
        """
        # Use display_name if set
        if self.session.display_name:
            return self.session.display_name[:MINI_SESSION_NAME_WIDTH]

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
            return f"{type_name}: {self.session.task_id}"

        return f"{type_name}: {self.session.template_id}"

    def _get_last_output(self) -> str:
        """Get the last line of output, truncated.

        Returns:
            Last output line with ">" prefix, or empty state message.
        """
        if not self.session.last_output:
            return ""

        # Get last non-empty line
        lines = self.session.last_output.strip().split("\n")
        last_line = ""
        for line in reversed(lines):
            if line.strip():
                last_line = line.strip()
                break

        if not last_line:
            return ""

        # Truncate and add prefix
        if len(last_line) > MINI_OUTPUT_TRUNCATE:
            return f"> {last_line[:MINI_OUTPUT_TRUNCATE]}..."

        return f"> {last_line}"

    def update_session(self, session: ManagedSession) -> None:
        """Update session data and refresh display.

        Args:
            session: Updated session data.
        """
        self.session = session
        self.refresh()

    def set_selected(self, selected: bool) -> None:
        """Set the selected state.

        Args:
            selected: Whether this card should appear selected.
        """
        self._selected = selected
        if selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")
        self.refresh()

    async def on_click(self) -> None:
        """Handle click events."""
        self.post_message(self.Selected(self.session))


class SessionsPanel(Static):
    """Active sessions panel for project screen.

    Shows all active sessions for the current project in a compact format.
    Each session is displayed as a MiniSessionCard with index, info, and output.

    Features:
    - Displays sessions for a specific project only
    - Shows empty state when no active sessions
    - Automatically refreshes on session events
    - Supports keyboard selection (1-9)
    """

    DEFAULT_CSS = """
    SessionsPanel {
        height: auto;
        min-height: 3;
        border: solid $primary-lighten-1;
        padding: 0;
    }

    SessionsPanel .section-header {
        text-style: bold;
        padding: 0 1;
        background: $primary-lighten-2;
    }

    SessionsPanel #session-list {
        height: auto;
        padding: 0;
    }

    SessionsPanel .empty-state {
        padding: 1 2;
        color: $text-muted;
        text-style: italic;
    }
    """

    class SessionSelected(Message):
        """Posted when a session is selected in the panel."""

        def __init__(self, session: ManagedSession) -> None:
            super().__init__()
            self.session = session

    def __init__(
        self,
        project_id: str | None = None,
        sessions: list[ManagedSession] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the sessions panel.

        Args:
            project_id: ID of the project to show sessions for.
            sessions: Initial list of sessions (optional).
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self.project_id = project_id
        self._sessions: list[ManagedSession] = sessions or []
        self._selected_index: int = 0

    def compose(self) -> ComposeResult:
        """Compose the panel layout."""
        yield Static("─ Active Sessions ─", classes="section-header")
        yield Vertical(id="session-list")

    async def on_mount(self) -> None:
        """Initialize the panel content when mounted."""
        await self._refresh_display()

    def set_project(self, project_id: str) -> None:
        """Set the project to display sessions for.

        Args:
            project_id: The project ID.
        """
        self.project_id = project_id
        self._selected_index = 0

    async def refresh_sessions(self, sessions: list[ManagedSession] | None = None) -> None:
        """Refresh the session list.

        Args:
            sessions: Optional new list of sessions. If not provided,
                     filters existing sessions for current project.
        """
        if sessions is not None:
            self._sessions = sessions
        await self._refresh_display()

    def get_project_sessions(self) -> list[ManagedSession]:
        """Get active sessions for the current project.

        Returns:
            List of active sessions belonging to this project.
        """
        if not self.project_id:
            return []

        return [
            s for s in self._sessions
            if s.project_id == self.project_id and s.is_active
        ]

    async def _refresh_display(self) -> None:
        """Refresh the display with current sessions."""
        try:
            container = self.query_one("#session-list", Vertical)
        except Exception:
            return

        await container.remove_children()

        sessions = self.get_project_sessions()

        if not sessions:
            await container.mount(
                Static("[dim]No active sessions[/dim]", classes="empty-state")
            )
            return

        # Keep selection in bounds
        if sessions:
            self._selected_index = min(self._selected_index, len(sessions) - 1)

        # Create mini cards for each session
        for i, session in enumerate(sessions, 1):
            is_selected = (i - 1) == self._selected_index
            card = MiniSessionCard(
                session=session,
                index=i,
                selected=is_selected,
                id=f"mini-session-{session.id}",
            )
            await container.mount(card)

    @property
    def selected_session(self) -> ManagedSession | None:
        """Get the currently selected session.

        Returns:
            The selected session, or None if no sessions.
        """
        sessions = self.get_project_sessions()
        if not sessions:
            return None
        if self._selected_index < 0 or self._selected_index >= len(sessions):
            return None
        return sessions[self._selected_index]

    def select_by_index(self, index: int) -> ManagedSession | None:
        """Select a session by 1-based index.

        Args:
            index: 1-based index (1-9 for keyboard selection).

        Returns:
            The selected session, or None if index out of range.
        """
        sessions = self.get_project_sessions()
        if not sessions or index < 1 or index > len(sessions):
            return None

        self._selected_index = index - 1

        # Update card selection states
        try:
            container = self.query_one("#session-list", Vertical)
            for i, child in enumerate(container.children):
                if isinstance(child, MiniSessionCard):
                    child.set_selected(i == self._selected_index)
        except Exception:
            pass

        return sessions[self._selected_index]

    def on_mini_session_card_selected(self, message: MiniSessionCard.Selected) -> None:
        """Handle mini card selection.

        Args:
            message: The selection message.
        """
        # Update selected index
        sessions = self.get_project_sessions()
        for i, session in enumerate(sessions):
            if session.id == message.session.id:
                self._selected_index = i
                break

        # Update card selection states
        try:
            container = self.query_one("#session-list", Vertical)
            for i, child in enumerate(container.children):
                if isinstance(child, MiniSessionCard):
                    child.set_selected(i == self._selected_index)
        except Exception:
            pass

        # Bubble up the event
        self.post_message(self.SessionSelected(message.session))

    async def on_session_spawned(self, message: SessionSpawned) -> None:
        """Handle session spawned event.

        Args:
            message: The session spawned message.
        """
        # Only care about sessions for our project
        if self.project_id and message.session.project_id == self.project_id:
            # Add session if not already present
            existing_ids = {s.id for s in self._sessions}
            if message.session.id not in existing_ids:
                self._sessions.append(message.session)
                await self._refresh_display()

    async def on_session_closed(self, message: SessionClosed) -> None:
        """Handle session closed event.

        Args:
            message: The session closed message.
        """
        self._sessions = [s for s in self._sessions if s.id != message.session.id]

        # Keep selection in bounds
        sessions = self.get_project_sessions()
        if sessions:
            self._selected_index = min(self._selected_index, len(sessions) - 1)
        else:
            self._selected_index = 0

        await self._refresh_display()

    async def on_session_status_changed(self, message: SessionStatusChanged) -> None:
        """Handle session status changed event.

        Args:
            message: The session status changed message.
        """
        # Update session in our list
        for i, session in enumerate(self._sessions):
            if session.id == message.session.id:
                self._sessions[i] = message.session
                break

        # Only refresh if it's our project's session
        if self.project_id and message.session.project_id == self.project_id:
            await self._refresh_display()

    async def on_session_output_updated(self, message: SessionOutputUpdated) -> None:
        """Handle session output update event.

        Args:
            message: The output update message.
        """
        # Update session in our list
        for i, session in enumerate(self._sessions):
            if session.id == message.session_id:
                # Update last_output field
                self._sessions[i].last_output = message.output
                break

        # Refresh the specific card instead of entire panel
        if self.project_id:
            try:
                card = self.query_one(f"#mini-session-{message.session_id}", MiniSessionCard)
                session = next((s for s in self._sessions if s.id == message.session_id), None)
                if session and session.project_id == self.project_id:
                    card.update_session(session)
            except Exception:
                pass

    def get_session_by_id(self, session_id: str) -> ManagedSession | None:
        """Get a session by its ID.

        Args:
            session_id: The session ID to look up.

        Returns:
            The session if found, None otherwise.
        """
        for session in self._sessions:
            if session.id == session_id:
                return session
        return None

    def get_active_count(self) -> int:
        """Get the count of active sessions for this project.

        Returns:
            Number of active sessions.
        """
        return len(self.get_project_sessions())
