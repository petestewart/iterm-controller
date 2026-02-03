"""Main dashboard showing all sessions.

The Control Room is the main screen showing all active sessions across all projects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Footer, Header, Static

from iterm_controller.models import ManagedSession, SessionTemplate
from iterm_controller.state import (
    SessionClosed,
    SessionSpawned,
    SessionStatusChanged,
)
from iterm_controller.widgets import SessionListWidget, WorkflowBarWidget

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp

# Debounce interval for UI refresh (in seconds)
REFRESH_DEBOUNCE_SECONDS = 0.1  # 100ms


class ControlRoomScreen(Screen):
    """Main control room showing all active sessions.

    This screen displays all active sessions across all projects with status
    indicators, a workflow bar, and health check status. Users can spawn new
    sessions, kill existing ones, and focus sessions in iTerm2.

    Layout:
    ┌─────────────────────────────────────────────────────────────┐
    │ iTerm Controller                                  [?] Help   │
    ├─────────────────────────────────────────────────────────────┤
    │ Sessions                                                     │
    │ ● my-project/API Server         Working   [a]               │
    │ ⧖ my-project/Claude             Waiting   [c]               │
    │ ○ my-project/Tests              Idle      [t]               │
    │                                                              │
    │ ┌───────────────────────────┬──────────────────────────────┐│
    │ │ Planning → Execute → ...  │  API ● Web ● DB ○             ││
    │ └───────────────────────────┴──────────────────────────────┘│
    ├─────────────────────────────────────────────────────────────┤
    │ n New  k Kill  Enter Focus  p Projects  q Quit               │
    └─────────────────────────────────────────────────────────────┘
    """

    BINDINGS = [
        Binding("n", "new_session", "New Session"),
        Binding("k", "kill_session", "Kill Session"),
        Binding("enter", "focus_session", "Focus"),
        Binding("p", "app.push_screen('project_list')", "Projects"),
        Binding("r", "refresh", "Refresh"),
        # Number shortcuts for quick session focus (1-9)
        Binding("1", "focus_session_num(1)", "Focus #1", show=False),
        Binding("2", "focus_session_num(2)", "Focus #2", show=False),
        Binding("3", "focus_session_num(3)", "Focus #3", show=False),
        Binding("4", "focus_session_num(4)", "Focus #4", show=False),
        Binding("5", "focus_session_num(5)", "Focus #5", show=False),
        Binding("6", "focus_session_num(6)", "Focus #6", show=False),
        Binding("7", "focus_session_num(7)", "Focus #7", show=False),
        Binding("8", "focus_session_num(8)", "Focus #8", show=False),
        Binding("9", "focus_session_num(9)", "Focus #9", show=False),
    ]

    def __init__(self) -> None:
        """Initialize the control room screen with debounce state."""
        super().__init__()
        # Debounce state for batching rapid UI updates
        self._refresh_timer: Timer | None = None
        self._refresh_pending: bool = False

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            Static("Sessions", id="sessions-header", classes="section-header"),
            SessionListWidget(id="sessions", show_project=True),
            Horizontal(
                WorkflowBarWidget(id="workflow"),
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

        widget = self.query_one("#sessions", SessionListWidget)
        widget.refresh_sessions(sessions)
        # Clear pending flag after refresh completes
        self._refresh_pending = False

    def schedule_refresh(self) -> None:
        """Schedule a debounced refresh of the session list.

        Multiple calls within REFRESH_DEBOUNCE_SECONDS are batched into a single
        refresh. This prevents UI thrashing during rapid state changes (e.g.,
        multiple sessions updating status simultaneously).
        """
        # If a refresh is already pending, don't schedule another
        if self._refresh_pending:
            return

        self._refresh_pending = True

        # Cancel any existing timer
        if self._refresh_timer is not None:
            self._refresh_timer.stop()

        # Schedule the refresh with debounce delay
        self._refresh_timer = self.set_timer(
            REFRESH_DEBOUNCE_SECONDS,
            self._do_debounced_refresh,
        )

    def _do_debounced_refresh(self) -> None:
        """Execute the debounced refresh.

        Called by the timer after the debounce interval.
        """
        self._refresh_timer = None
        # Use call_later to run the async refresh
        self.call_later(self.refresh_sessions)

    @property
    def selected_session(self) -> ManagedSession | None:
        """Get the currently selected session from the widget."""
        widget = self.query_one("#sessions", SessionListWidget)
        return widget.selected_session

    def action_new_session(self) -> None:
        """Spawn a new session from template.

        Opens the script picker modal to select a session template,
        then spawns a new session in iTerm2.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Check if connected to iTerm2
        if not app.iterm.is_connected:
            self.notify("Not connected to iTerm2", severity="error")
            return

        # Get active project
        project = app.state.active_project
        if not project:
            # No active project - check if we have any projects at all
            if not app.state.projects:
                self.notify("No projects configured. Create a project first.", severity="warning")
                return

            # Open project list to select a project
            self.notify("Select a project first", severity="warning")
            app.push_screen("project_list")
            return

        # Show script picker modal to select a template (or blank shell)
        from iterm_controller.screens.modals import ScriptPickerModal

        self.app.push_screen(ScriptPickerModal(), self._on_template_selected)

    async def _on_template_selected(self, template: "SessionTemplate | None") -> None:
        """Handle template selection from script picker modal.

        Args:
            template: The selected template, or None if cancelled.
                     May be BLANK_SHELL_SENTINEL for a blank shell.
        """
        if template is None:
            # User cancelled
            return

        app: ItermControllerApp = self.app  # type: ignore[assignment]
        project = app.state.active_project

        if not project:
            self.notify("No active project", severity="error")
            return

        # Import BLANK_SHELL_SENTINEL for comparison
        from iterm_controller.screens.modals import BLANK_SHELL_SENTINEL

        # Check if blank shell was selected
        is_blank_shell = template.id == BLANK_SHELL_SENTINEL.id

        result = await app.api.spawn_session_with_template(project, template)
        if result.success:
            name = "Blank Shell" if is_blank_shell else template.name
            self.notify(f"Spawned session: {name}")
        else:
            self.notify(f"Failed to spawn session: {result.error}", severity="error")

    async def action_kill_session(self) -> None:
        """Kill the selected session."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        session = self.selected_session
        if not session:
            self.notify("No session to kill", severity="warning")
            return

        result = await app.api.kill_session(session.id)
        if result.success:
            self.notify(f"Closed session: {session.template_id}")
        else:
            self.notify(f"Failed to close session: {result.error}", severity="error")

    async def action_focus_session(self) -> None:
        """Focus the selected session in iTerm2."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        session = self.selected_session
        if not session:
            self.notify("No session to focus", severity="warning")
            return

        result = await app.api.focus_session(session.id)
        if result.success:
            self.notify(f"Focused session: {session.template_id}")
        else:
            self.notify(f"Error focusing session: {result.error}", severity="error")

    async def action_refresh(self) -> None:
        """Manually refresh the session list."""
        await self.refresh_sessions()
        self.notify("Refreshed sessions")

    async def action_focus_session_num(self, num: int) -> None:
        """Focus session by its display number (1-9).

        Args:
            num: The 1-based session number to focus.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Get sessions from the widget (sorted by priority to match display order)
        widget = self.query_one("#sessions", SessionListWidget)
        sessions = widget.get_sorted_sessions()

        # Convert to 0-based index
        index = num - 1
        if index >= len(sessions):
            self.notify(f"No session #{num}", severity="warning")
            return

        # Update widget selection to match
        widget.select_index(index)
        session = sessions[index]

        result = await app.api.focus_session(session.id)
        if result.success:
            self.notify(f"Focused session #{num}: {session.template_id}")
        else:
            self.notify(f"Error focusing session: {result.error}", severity="error")

    # =========================================================================
    # State Event Handlers
    # =========================================================================

    def on_session_spawned(self, event: SessionSpawned) -> None:
        """Handle session spawned event.

        Uses debounced refresh to batch multiple rapid events.
        """
        self.schedule_refresh()

    def on_session_closed(self, event: SessionClosed) -> None:
        """Handle session closed event.

        Uses debounced refresh to batch multiple rapid events.
        """
        self.schedule_refresh()

    def on_session_status_changed(self, event: SessionStatusChanged) -> None:
        """Handle session status change event.

        Uses debounced refresh to batch multiple rapid events.
        """
        self.schedule_refresh()
