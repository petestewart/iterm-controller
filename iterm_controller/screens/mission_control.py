"""Mission Control screen for live session monitoring.

Mission Control is the main screen of the application, showing live output
streaming from all active sessions across all projects. It replaces the
previous Control Room which only showed session status indicators.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Footer, Header, Static

from iterm_controller.models import ManagedSession, SessionTemplate
from iterm_controller.state import (
    OrchestratorProgress,
    SessionClosed,
    SessionOutputUpdated,
    SessionSpawned,
    SessionStatusChanged,
)
from iterm_controller.widgets import SessionList

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp

logger = logging.getLogger(__name__)

# Debounce interval for UI refresh (in seconds)
REFRESH_DEBOUNCE_SECONDS = 0.1  # 100ms


class MissionControlScreen(Screen):
    """Main mission control showing live output from all active sessions.

    This screen displays live terminal output from all active sessions across
    all projects. Users can spawn new sessions, kill existing ones, focus
    sessions in iTerm2, and navigate to project details.

    Features:
    - Live output streaming from each session in real-time
    - Expand/collapse individual sessions for more detail
    - Session cards with status indicators (Working/Waiting/Idle)
    - Orchestrator progress bars for task-tracking sessions
    - Keyboard navigation (1-9 to focus, j/k to navigate)

    Layout:
    ┌─────────────────────────────────────────────────────────────────┐
    │ MISSION CONTROL                                  4 active sessions│
    │ ═══════════════════════════════════════════════════════════════ │
    │                                                                   │
    │ +- 1. Project A ---------------------------------------- WORKING │
    │ |  Claude: Creating PLAN.md                           00:03:42  │
    │ |  ------------------------------------------------------------ │
    │ |  > Analyzing the PRD structure...                             │
    │ |  > Creating Phase 1: Project Setup                            │
    │ |  > Adding task 1.1: Initialize repository_                    │
    │ +----------------------------------------------------------------│
    │                                                                   │
    │ +- 2. Project B ---------------------------------------- WAITING │
    │ |  Claude: Task 3.1                                   00:08:15  │
    │ |  ------------------------------------------------------------ │
    │ |  Should I proceed with the fix? [y/n]_                        │
    │ +----------------------------------------------------------------│
    │                                                                   │
    │ [1-9] Focus  [Enter] Open project  [n] New session  [?] Help     │
    └─────────────────────────────────────────────────────────────────┘
    """

    CSS = """
    MissionControlScreen {
        background: $surface;
    }

    MissionControlScreen #main {
        height: 1fr;
        padding: 1 2;
    }

    MissionControlScreen #header-row {
        height: 3;
        margin-bottom: 1;
    }

    MissionControlScreen #title {
        text-style: bold;
        color: $primary;
        width: 1fr;
    }

    MissionControlScreen #session-count {
        text-align: right;
        color: $text-muted;
        width: auto;
    }

    MissionControlScreen #separator {
        color: $primary;
        margin-bottom: 1;
    }

    MissionControlScreen #session-list-container {
        height: 1fr;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("n", "new_session", "New Session"),
        Binding("k", "kill_session", "Kill"),
        Binding("enter", "open_project", "Open Project"),
        Binding("x", "expand_collapse", "Expand"),
        Binding("f", "focus_iterm", "Focus iTerm"),
        Binding("p", "app.push_screen('project_list')", "Projects"),
        Binding("j", "move_down", "Down", show=False),
        Binding("up", "move_up", "Up", show=False),
        Binding("down", "move_down", "Down", show=False),
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
        Binding("question_mark", "show_help", "Help", key_display="?"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        """Initialize the mission control screen with debounce state."""
        super().__init__()
        # Debounce state for batching rapid UI updates
        self._refresh_timer: Timer | None = None
        self._refresh_pending: bool = False

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            Horizontal(
                Static("MISSION CONTROL", id="title"),
                Static("0 active sessions", id="session-count"),
                id="header-row",
            ),
            Static("═" * 70, id="separator"),
            Container(
                SessionList(id="session-list"),
                id="session-list-container",
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

        session_list = self.query_one("#session-list", SessionList)
        session_list.refresh_sessions(sessions)

        # Update session count
        count = len(sessions)
        count_text = f"{count} active session{'s' if count != 1 else ''}"
        self.query_one("#session-count", Static).update(count_text)

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
        """Get the currently selected session from the session list."""
        session_list = self.query_one("#session-list", SessionList)
        return session_list.selected_session

    # =========================================================================
    # Actions
    # =========================================================================

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
                self.notify(
                    "No projects configured. Create a project first.",
                    severity="warning",
                )
                return

            # Open project list to select a project
            self.notify("Select a project first", severity="warning")
            app.push_screen("project_list")
            return

        # Show script picker modal to select a template (or blank shell)
        from iterm_controller.screens.modals import ScriptPickerModal

        self.app.push_screen(ScriptPickerModal(), self._on_template_selected)

    async def _on_template_selected(
        self, template: SessionTemplate | None
    ) -> None:
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
            self.notify(
                f"Failed to spawn session: {result.error}", severity="error"
            )

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
            self.notify(
                f"Failed to close session: {result.error}", severity="error"
            )

    async def action_open_project(self) -> None:
        """Open the project for the selected session."""
        session = self.selected_session
        if not session:
            self.notify("No session selected", severity="warning")
            return

        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Get the project for this session
        project = app.state.projects.get(session.project_id)
        if not project:
            self.notify(
                f"Project not found: {session.project_id}", severity="error"
            )
            return

        # Set as active project and open project screen
        app.state.active_project_id = project.id

        # Use ProjectScreen directly since it requires a project_id argument
        from iterm_controller.screens.project_screen import ProjectScreen

        app.push_screen(ProjectScreen(project.id))

    def action_expand_collapse(self) -> None:
        """Toggle expand/collapse for the selected session."""
        session_list = self.query_one("#session-list", SessionList)
        session_list.action_toggle_expand()

    async def action_focus_iterm(self) -> None:
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
            self.notify(
                f"Error focusing session: {result.error}", severity="error"
            )

    def action_move_up(self) -> None:
        """Move selection up in session list."""
        session_list = self.query_one("#session-list", SessionList)
        session_list.action_cursor_up()

    def action_move_down(self) -> None:
        """Move selection down in session list."""
        session_list = self.query_one("#session-list", SessionList)
        session_list.action_cursor_down()

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
        session_list = self.query_one("#session-list", SessionList)

        # Get session by display index
        session = session_list.get_session_by_index(num)
        if not session:
            self.notify(f"No session #{num}", severity="warning")
            return

        # Select it in the list
        session_list.select_session(session.id)

        # Focus in iTerm2
        result = await app.api.focus_session(session.id)
        if result.success:
            self.notify(f"Focused session #{num}: {session.template_id}")
        else:
            self.notify(
                f"Error focusing session: {result.error}", severity="error"
            )

    def action_show_help(self) -> None:
        """Show help modal."""
        from iterm_controller.screens.modals import HelpModal

        self.app.push_screen(HelpModal())

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.action_request_quit()

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
        session_list = self.query_one("#session-list", SessionList)
        session_list.remove_session(event.session.id)

        # Update count
        count = session_list.session_count
        count_text = f"{count} active session{'s' if count != 1 else ''}"
        self.query_one("#session-count", Static).update(count_text)

    def on_session_status_changed(self, event: SessionStatusChanged) -> None:
        """Handle session status change event.

        Updates the specific session card without full refresh.
        """
        session_list = self.query_one("#session-list", SessionList)
        session_list.update_session(event.session)

    def on_session_output_updated(self, event: SessionOutputUpdated) -> None:
        """Handle live output updates from sessions.

        This is the key integration for live output streaming.
        Updates the output log of the specific session card.
        """
        try:
            session_list = self.query_one("#session-list", SessionList)
            session_list.update_session_output(event.session_id, event.output)
        except Exception as e:
            # Session card may not exist yet
            logger.debug(f"Could not update output for session: {e}")

    def on_orchestrator_progress(self, event: OrchestratorProgress) -> None:
        """Handle orchestrator progress updates.

        Updates the progress bar in the session card.
        """
        session_list = self.query_one("#session-list", SessionList)
        session = session_list.get_session_by_id(event.session_id)
        if session:
            # Update the session's progress and refresh the card
            session.progress = event.progress
            session_list.update_session(session)
