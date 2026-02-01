"""Quit options: close all/managed/leave.

Modal dialog for quit confirmation with session handling options.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp


class QuitAction(Enum):
    """Actions available when quitting with active sessions."""

    CLOSE_ALL = "close_all"
    CLOSE_MANAGED = "close_managed"
    LEAVE_RUNNING = "leave_running"
    CANCEL = "cancel"


class QuitConfirmModal(ModalScreen[QuitAction]):
    """Modal for quit confirmation with session options."""

    BINDINGS = [
        Binding("c", "close_all", "Close All"),
        Binding("m", "close_managed", "Managed Only"),
        Binding("l", "leave_running", "Leave Running"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        yield Container(
            Static("Quit Application", id="title"),
            Vertical(
                Static("You have active sessions:", id="message"),
                Static("[dim]Loading sessions...[/dim]", id="session-list"),
                id="content",
            ),
            Vertical(
                Button("[C] Close all sessions and quit", id="close-all", variant="error"),
                Button("[M] Close managed sessions only", id="close-managed"),
                Button("[L] Leave sessions running", id="leave-running"),
                Button("Cancel", id="cancel", variant="default"),
                id="buttons",
            ),
            id="dialog",
        )

    async def on_mount(self) -> None:
        """Load session information."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        sessions = list(app.state.sessions.values())

        session_list = self.query_one("#session-list", Static)
        if sessions:
            lines = [f"  {s.template_id}" for s in sessions[:5]]
            if len(sessions) > 5:
                lines.append(f"  ... and {len(sessions) - 5} more")
            session_list.update("\n".join(lines))
        else:
            session_list.update("  No active sessions")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        actions = {
            "close-all": QuitAction.CLOSE_ALL,
            "close-managed": QuitAction.CLOSE_MANAGED,
            "leave-running": QuitAction.LEAVE_RUNNING,
            "cancel": QuitAction.CANCEL,
        }
        action = actions.get(event.button.id, QuitAction.CANCEL)
        self.dismiss(action)

    def action_close_all(self) -> None:
        """Close all sessions and quit."""
        self.dismiss(QuitAction.CLOSE_ALL)

    def action_close_managed(self) -> None:
        """Close managed sessions only."""
        self.dismiss(QuitAction.CLOSE_MANAGED)

    def action_leave_running(self) -> None:
        """Leave sessions running."""
        self.dismiss(QuitAction.LEAVE_RUNNING)

    def action_cancel(self) -> None:
        """Cancel quit."""
        self.dismiss(QuitAction.CANCEL)
