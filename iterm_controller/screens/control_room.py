"""Main dashboard showing all sessions.

The Control Room is the main screen showing all active sessions across all projects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from iterm_controller.models import ManagedSession
from iterm_controller.state import (
    SessionClosed,
    SessionSpawned,
    SessionStatusChanged,
)
from iterm_controller.widgets import SessionListWidget, WorkflowBarWidget

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp


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
    ]

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

    @property
    def selected_session(self) -> ManagedSession | None:
        """Get the currently selected session, if any.

        For now, return the first WAITING session or the first session.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        sessions = list(app.state.sessions.values())

        if not sessions:
            return None

        # Prioritize WAITING sessions
        widget = self.query_one("#sessions", SessionListWidget)
        waiting = widget.get_waiting_sessions()
        if waiting:
            return waiting[0]

        return sessions[0]

    async def action_new_session(self) -> None:
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

        # Get session templates from config
        if not app.state.config or not app.state.config.session_templates:
            self.notify("No session templates configured", severity="warning")
            return

        # Show script picker modal to select a template
        from iterm_controller.screens.modals import ScriptPickerModal

        template = await self.app.push_screen_wait(ScriptPickerModal())
        if template is None:
            # User cancelled
            return

        try:
            from iterm_controller.iterm_api import SessionSpawner

            spawner = SessionSpawner(app.iterm)
            result = await spawner.spawn_session(template, project)

            if result.success:
                # Add session to state
                managed = spawner.get_session(result.session_id)
                if managed:
                    app.state.add_session(managed)
                self.notify(f"Spawned session: {template.name}")
            else:
                self.notify(f"Failed to spawn session: {result.error}", severity="error")
        except Exception as e:
            self.notify(f"Error spawning session: {e}", severity="error")

    async def action_kill_session(self) -> None:
        """Kill the selected session."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        session = self.selected_session
        if not session:
            self.notify("No session to kill", severity="warning")
            return

        if not app.iterm.is_connected:
            self.notify("Not connected to iTerm2", severity="error")
            return

        try:
            from iterm_controller.iterm_api import SessionTerminator

            terminator = SessionTerminator(app.iterm)

            # Get the actual iTerm2 session object
            iterm_session = await app.iterm.app.async_get_session_by_id(session.id)
            if not iterm_session:
                # Session already gone, just remove from state
                app.state.remove_session(session.id)
                self.notify(f"Session already closed: {session.template_id}")
                return

            result = await terminator.close_session(iterm_session)

            if result.success:
                app.state.remove_session(session.id)
                if result.force_required:
                    self.notify(f"Force-closed session: {session.template_id}")
                else:
                    self.notify(f"Closed session: {session.template_id}")
            else:
                self.notify(f"Failed to close session: {result.error}", severity="error")
        except Exception as e:
            self.notify(f"Error closing session: {e}", severity="error")

    async def action_focus_session(self) -> None:
        """Focus the selected session in iTerm2."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        session = self.selected_session
        if not session:
            self.notify("No session to focus", severity="warning")
            return

        if not app.iterm.is_connected:
            self.notify("Not connected to iTerm2", severity="error")
            return

        try:
            # Get the actual iTerm2 session object
            iterm_session = await app.iterm.app.async_get_session_by_id(session.id)
            if not iterm_session:
                self.notify(f"Session not found: {session.template_id}", severity="error")
                return

            # Activate the session (focus it)
            await iterm_session.async_activate()
            self.notify(f"Focused session: {session.template_id}")
        except Exception as e:
            self.notify(f"Error focusing session: {e}", severity="error")

    async def action_refresh(self) -> None:
        """Manually refresh the session list."""
        await self.refresh_sessions()
        self.notify("Refreshed sessions")

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
