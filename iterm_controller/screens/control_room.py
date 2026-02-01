"""Main dashboard showing all sessions.

The Control Room is the main screen showing all active sessions across all projects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from iterm_controller.state import (
    SessionClosed,
    SessionSpawned,
    SessionStatusChanged,
)

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp


class ControlRoomScreen(Screen):
    """Main control room showing all active sessions."""

    BINDINGS = [
        Binding("n", "new_session", "New Session"),
        Binding("k", "kill_session", "Kill Session"),
        Binding("enter", "focus_session", "Focus"),
        Binding("p", "app.push_screen('project_list')", "Projects"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            Static("Sessions", id="sessions-header", classes="section-header"),
            Static("No active sessions", id="sessions-list", classes="sessions-list"),
            Horizontal(
                Static("[dim]Planning → Execute → Review → PR → Done[/dim]", id="workflow"),
                Static("[dim]No health checks[/dim]", id="health"),
                id="status-bar",
            ),
            id="main",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Load sessions when screen mounts."""
        await self.refresh_sessions()

    async def refresh_sessions(self) -> None:
        """Refresh session list from state."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        sessions = list(app.state.sessions.values())

        sessions_list = self.query_one("#sessions-list", Static)
        if sessions:
            lines = []
            for session in sessions:
                icon = {
                    "waiting": "[yellow]⧖[/yellow]",
                    "working": "[green]●[/green]",
                    "idle": "[dim]○[/dim]",
                }.get(session.attention_state.value, "○")
                lines.append(f"{icon} {session.template_id:<30} {session.attention_state.value.title()}")
            sessions_list.update("\n".join(lines))
        else:
            sessions_list.update("No active sessions")

    def action_new_session(self) -> None:
        """Spawn a new session."""
        self.notify("New session: Not implemented yet")

    def action_kill_session(self) -> None:
        """Kill the selected session."""
        self.notify("Kill session: Not implemented yet")

    def action_focus_session(self) -> None:
        """Focus the selected session in iTerm2."""
        self.notify("Focus session: Not implemented yet")

    # =========================================================================
    # State Event Handlers
    # =========================================================================

    def on_session_spawned(self, event: SessionSpawned) -> None:
        """Handle session spawned event."""
        self.call_later(self.refresh_sessions)

    def on_session_closed(self, event: SessionClosed) -> None:
        """Handle session closed event."""
        self.call_later(self.refresh_sessions)

    def on_session_status_changed(self, event: SessionStatusChanged) -> None:
        """Handle session status change event."""
        self.call_later(self.refresh_sessions)
