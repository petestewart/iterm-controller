#!/usr/bin/env python3
"""
iTerm2 Controller Prototype
===========================
A TUI that demonstrates spawning and monitoring iTerm2 sessions.

Run this script from within iTerm2. It will:
- Display a control panel with buttons to spawn processes
- Create new tabs/panes when you click buttons
- Monitor the status of spawned sessions
- Show real-time output snippets

Requirements:
    pip install iterm2 textual

Usage:
    python controller.py
"""

import asyncio
import iterm2
from iterm2 import notifications as iterm2_notifications
from datetime import datetime
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import Button, Static, Header, Footer, Log, Label
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.binding import Binding
from textual import work


class SessionCard(Static):
    """A card showing the status of a managed session."""

    status = reactive("pending")
    last_output = reactive("")

    def __init__(self, session_id: str, session_name: str, command: str, **kwargs):
        super().__init__(**kwargs)
        self.session_id = session_id
        self.session_name = session_name
        self.command = command
        self.created_at = datetime.now()

    def compose(self) -> ComposeResult:
        yield Static(f"[bold]{self.session_name}[/bold]", classes="card-title")
        yield Static(f"[dim]$ {self.command}[/dim]", classes="card-command")
        yield Static("", id=f"status-{self.session_id}", classes="card-status")
        yield Static("", id=f"output-{self.session_id}", classes="card-output")

    def update_status(self, status: str):
        self.status = status
        status_widget = self.query_one(f"#status-{self.session_id}", Static)

        status_colors = {
            "running": "[green]● Running[/green]",
            "ready": "[blue]● Ready[/blue]",
            "exited": "[red]● Exited[/red]",
            "starting": "[yellow]● Starting...[/yellow]",
        }
        status_widget.update(status_colors.get(status, f"● {status}"))

    def update_output(self, text: str):
        self.last_output = text
        output_widget = self.query_one(f"#output-{self.session_id}", Static)
        # Show last 4 non-empty lines of output, truncated
        lines = [l for l in text.strip().split('\n') if l.strip()][-4:]
        preview = '\n'.join(line[:70] + '...' if len(line) > 70 else line for line in lines)
        output_widget.update(f"[dim]{preview}[/dim]")


class QuitScreen(ModalScreen):
    """Modal screen for quit confirmation with tab options."""

    CSS = """
    QuitScreen {
        align: center middle;
    }

    #quit-dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: round $primary;
    }

    #quit-dialog Label {
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    #quit-dialog .tab-list {
        height: auto;
        max-height: 10;
        margin: 1 0;
        padding: 1;
        background: $surface-darken-1;
    }

    #quit-dialog Button {
        width: 100%;
        margin-top: 1;
    }
    """

    def __init__(self, tabs: list, managed_ids: set, **kwargs):
        super().__init__(**kwargs)
        self.tabs = tabs
        self.managed_ids = managed_ids

    def compose(self) -> ComposeResult:
        with Vertical(id="quit-dialog"):
            yield Label(f"[bold]Quit Controller[/bold]")
            yield Label(f"There are {len(self.tabs)} tab(s) open:")

            # List tabs
            tab_list = []
            for tab in self.tabs:
                marker = "●" if tab['id'] in self.managed_ids else "○"
                tab_list.append(f"  {marker} {tab['title']}")
            yield Static("\n".join(tab_list[:8]) + ("\n  ..." if len(tab_list) > 8 else ""), classes="tab-list")

            yield Static("[dim]● = managed by controller  ○ = external[/dim]")

            yield Button("Close All Tabs & Quit", id="close-all", variant="error")
            yield Button("Close Managed Tabs & Quit", id="close-managed", variant="warning")
            yield Button("Keep All Tabs & Quit", id="keep-all", variant="default")
            yield Button("Cancel", id="cancel", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id)


class ControllerApp(App):
    """Main TUI application for controlling iTerm2 sessions."""

    CSS = """
    #content {
        height: 1fr;
        width: 100%;
    }

    #sidebar {
        width: 30;
        height: 100%;
        background: $surface;
        border-right: tall $primary;
        padding: 1;
    }

    #main {
        width: 1fr;
        height: 100%;
        padding: 1;
        background: $surface-darken-1;
    }

    .spawn-button {
        width: 100%;
        margin-bottom: 1;
    }

    .card {
        background: $surface;
        border: round $primary;
        padding: 1;
        margin-bottom: 1;
        height: auto;
    }

    .card-title {
        text-style: bold;
    }

    .card-command {
        color: $text-muted;
    }

    .card-status {
        margin-top: 1;
    }

    .card-output {
        margin-top: 1;
        color: $text-muted;
        height: 5;
    }

    #log {
        height: 8;
        border: round $secondary;
        margin-top: 1;
    }

    #sessions-container {
        height: 1fr;
        border: round $primary;
    }
    """

    BINDINGS = [
        ("q", "request_quit", "Quit"),
        ("1", "spawn_server", "Spawn Server"),
        ("2", "spawn_watch", "Spawn Watch"),
        ("3", "spawn_shell", "Spawn Shell"),
        ("a", "spawn_article", "Claude Article"),
        ("4", "spawn_watcher_pair", "Watcher Pair"),
        ("5", "spawn_dev_layout", "Dev Layout"),
        ("w", "spawn_window", "New Window"),
        ("r", "refresh", "Refresh"),
    ]

    def __init__(self, iterm_connection=None):
        super().__init__()
        self.iterm_connection = iterm_connection
        self.managed_sessions: dict[str, dict] = {}
        self.session_cards: dict[str, SessionCard] = {}
        # Track specific tabs for "create or focus" behavior
        self.tracked_tabs: dict[str, dict] = {}  # name -> {"tab": Tab, "session_id": str}

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="content"):
            with Vertical(id="sidebar"):
                yield Label("[bold]Single Process[/bold]")
                yield Button("🚀 Dev Server (1)", id="spawn-server", classes="spawn-button")
                yield Button("👀 File Watcher (2)", id="spawn-watch", classes="spawn-button")
                yield Button("🐚 New Shell (3)", id="spawn-shell", classes="spawn-button")
                yield Button("📝 Claude Article (a)", id="spawn-article", classes="spawn-button")
                yield Static("")
                yield Label("[bold]Pane Layouts[/bold]")
                yield Button("👀👀 Watcher Pair (4)", id="spawn-watcher-pair", classes="spawn-button")
                yield Button("🔲 Dev Layout (5)", id="spawn-dev-layout", classes="spawn-button")
                yield Static("")
                yield Label("[bold]Windows[/bold]")
                yield Button("🪟 New Window (w)", id="spawn-window", classes="spawn-button")
                yield Static("")
                yield Label("[bold]Actions[/bold]")
                yield Button("🔄 Refresh All", id="refresh", classes="spawn-button", variant="default")
                yield Button("🛑 Kill All", id="kill-all", classes="spawn-button", variant="error")

            with Vertical(id="main"):
                yield Static("[bold]Managed Sessions[/bold]", id="sessions-label")
                with ScrollableContainer(id="sessions-container"):
                    yield Static("[dim]No sessions yet. Click a button to spawn.[/dim]", id="placeholder")
                yield Static("[bold]Log[/bold]")
                yield Log(id="log", highlight=True)

        yield Footer()

    def on_mount(self):
        self.log_message("Controller started. Click buttons or use keyboard shortcuts.")
        if not self.iterm_connection:
            self.log_message("[yellow]Warning: No iTerm2 connection. Running in demo mode.[/yellow]")
        else:
            self.log_message("[green]Connected to iTerm2[/green]")

    def log_message(self, msg: str):
        log = self.query_one("#log", Log)
        timestamp = datetime.now().strftime("%H:%M:%S")
        log.write_line(f"[{timestamp}] {msg}")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "spawn-server":
            await self.spawn_session("Dev Server", "echo 'Starting server...' && sleep 2 && echo 'Server running on :3000' && while true; do echo \"$(date): Heartbeat\"; sleep 5; done")
        elif button_id == "spawn-watch":
            await self.spawn_session("File Watcher", "echo 'Watching for changes...' && fswatch -r . 2>/dev/null || (echo 'fswatch not installed, simulating...' && while true; do echo \"$(date): Checking files...\"; sleep 3; done)")
        elif button_id == "spawn-shell":
            await self.spawn_or_focus_shell()
        elif button_id == "spawn-article":
            await self.spawn_session("Claude Article", "claude /article")
        elif button_id == "spawn-watcher-pair":
            await self.spawn_watcher_pair()
        elif button_id == "spawn-dev-layout":
            await self.spawn_dev_layout()
        elif button_id == "spawn-window":
            await self.spawn_new_window()
        elif button_id == "refresh":
            await self.refresh_all_sessions()
        elif button_id == "kill-all":
            await self.kill_all_sessions()

    def action_spawn_server(self):
        asyncio.create_task(self.spawn_session("Dev Server", "echo 'Starting...' && sleep 1 && echo 'Running on :3000'"))

    def action_spawn_watch(self):
        asyncio.create_task(self.spawn_session("Watcher", "echo 'Watching...'"))

    def action_spawn_shell(self):
        asyncio.create_task(self.spawn_or_focus_shell())

    def action_spawn_article(self):
        asyncio.create_task(self.spawn_session("Claude Article", "claude /article"))

    def action_spawn_watcher_pair(self):
        asyncio.create_task(self.spawn_watcher_pair())

    def action_spawn_dev_layout(self):
        asyncio.create_task(self.spawn_dev_layout())

    def action_spawn_window(self):
        asyncio.create_task(self.spawn_new_window())

    def action_refresh(self):
        asyncio.create_task(self.refresh_all_sessions())

    def action_request_quit(self):
        self.request_quit_with_confirmation()

    @work
    async def request_quit_with_confirmation(self):
        """Handle quit request with tab awareness (runs as worker)."""
        tabs = await self.get_all_tabs()

        # Get set of managed session IDs
        managed_session_ids = set(self.managed_sessions.keys())

        # Determine which tabs are managed (have at least one managed session)
        managed_tab_ids = set()
        for tab in tabs:
            for session_id in tab["session_ids"]:
                if session_id in managed_session_ids:
                    managed_tab_ids.add(tab["id"])
                    break

        # Store for use in callback
        self._managed_tab_ids_for_quit = managed_tab_ids

        # If there are tabs (other than possibly the controller itself), show dialog
        if len(tabs) > 1 or (len(tabs) == 1 and managed_session_ids):
            result = await self.push_screen_wait(
                QuitScreen(tabs, managed_tab_ids)
            )

            if result == "cancel":
                self.log_message("Quit cancelled")
                return
            elif result == "close-all":
                await self.close_all_tabs()
            elif result == "close-managed":
                await self.close_managed_tabs(managed_tab_ids)
            # "keep-all" - just quit without closing

        self.exit()

    async def get_all_tabs(self) -> list[dict]:
        """Get info about all tabs in the current window."""
        tabs = []
        if self.iterm_connection:
            try:
                app = await iterm2.async_get_app(self.iterm_connection)
                window = app.current_terminal_window
                if window:
                    for tab in window.tabs:
                        # Get tab title from first session
                        title = "Unknown"
                        if tab.sessions:
                            session = tab.sessions[0]
                            # Try to get the session name
                            try:
                                title = await session.async_get_variable("name") or "Shell"
                            except Exception:
                                title = "Shell"
                        tabs.append({
                            "id": tab.tab_id,
                            "title": title,
                            "session_ids": [s.session_id for s in tab.sessions]
                        })
            except Exception as e:
                self.log_message(f"[yellow]Could not get tabs: {e}[/yellow]")
        return tabs

    async def close_all_tabs(self):
        """Close all tabs in the window."""
        self.log_message("Closing all tabs...")
        if self.iterm_connection:
            try:
                app = await iterm2.async_get_app(self.iterm_connection)
                window = app.current_terminal_window
                if window:
                    # Close all tabs except possibly the last one (can't close all)
                    tabs = list(window.tabs)
                    for tab in tabs[:-1]:  # Leave one tab
                        try:
                            await tab.async_close()
                        except Exception:
                            pass
            except Exception as e:
                self.log_message(f"[red]Error closing tabs: {e}[/red]")

    async def close_managed_tabs(self, managed_tab_ids: set):
        """Close only tabs that were created by the controller."""
        self.log_message("Closing managed tabs...")
        if self.iterm_connection:
            try:
                app = await iterm2.async_get_app(self.iterm_connection)
                window = app.current_terminal_window
                if window:
                    for tab in window.tabs:
                        if tab.tab_id in managed_tab_ids:
                            try:
                                await tab.async_close()
                            except Exception:
                                pass
            except Exception as e:
                self.log_message(f"[red]Error closing tabs: {e}[/red]")

    async def spawn_or_focus_shell(self):
        """Spawn a new shell tab, or focus it if it already exists."""
        tab_name = "Shell"

        # Check if we already have this tab tracked
        if tab_name in self.tracked_tabs:
            tracked = self.tracked_tabs[tab_name]
            try:
                # Try to activate the existing tab
                tab = tracked["tab"]
                await tab.async_activate()
                self.log_message(f"[blue]Switched to existing {tab_name} tab[/blue]")
                return
            except Exception:
                # Tab was closed or invalid, remove from tracking
                self.log_message(f"[yellow]{tab_name} tab was closed, creating new one[/yellow]")
                del self.tracked_tabs[tab_name]

        # Create new tab
        self.log_message(f"Creating {tab_name} tab...")

        if self.iterm_connection:
            try:
                app = await iterm2.async_get_app(self.iterm_connection)
                window = app.current_terminal_window

                if window is None:
                    self.log_message("[red]No iTerm2 window found[/red]")
                    return

                # Create a new tab
                tab = await window.async_create_tab()
                session = tab.current_session
                session_id = session.session_id

                # Set the name
                await session.async_set_name(tab_name)

                # Track this tab for future focus
                self.tracked_tabs[tab_name] = {
                    "tab": tab,
                    "session_id": session_id
                }

                # Store session info
                self.managed_sessions[session_id] = {
                    "name": tab_name,
                    "command": "(interactive)",
                    "session": session,
                    "status": "running"
                }

                # Create UI card
                try:
                    placeholder = self.query_one("#placeholder", Static)
                    await placeholder.remove()
                except Exception:
                    pass

                card = SessionCard(session_id, tab_name, "(interactive)", classes="card")
                self.session_cards[session_id] = card
                container = self.query_one("#sessions-container", ScrollableContainer)
                await container.mount(card)
                card.update_status("running")

                asyncio.create_task(self.monitor_session(session_id))
                asyncio.create_task(self.watch_session_termination(session_id))

                self.log_message(f"[green]Created {tab_name} tab[/green]")

            except Exception as e:
                self.log_message(f"[red]Error: {e}[/red]")
        else:
            self.log_message(f"[yellow]Demo mode: would create {tab_name} tab[/yellow]")

    async def spawn_session(self, name: str, command: str):
        """Spawn a new iTerm2 session and start monitoring it."""
        self.log_message(f"Spawning: {name}")

        if self.iterm_connection:
            try:
                app = await iterm2.async_get_app(self.iterm_connection)
                window = app.current_terminal_window

                if window is None:
                    self.log_message("[red]No iTerm2 window found[/red]")
                    return

                # Create a new tab
                tab = await window.async_create_tab()
                session = tab.current_session
                session_id = session.session_id

                # Store session info
                self.managed_sessions[session_id] = {
                    "name": name,
                    "command": command,
                    "session": session,
                    "status": "starting"
                }

                # Create UI card
                self.log_message(f"Creating card for {session_id}...")

                # Remove placeholder if present
                try:
                    placeholder = self.query_one("#placeholder", Static)
                    await placeholder.remove()
                except Exception:
                    pass

                card = SessionCard(session_id, name, command or "(interactive)", classes="card")
                self.session_cards[session_id] = card
                container = self.query_one("#sessions-container", ScrollableContainer)
                await container.mount(card)
                card.update_status("starting")
                self.log_message(f"Card mounted for {name}")

                # Set the tab/session title
                await session.async_set_name(name)

                # Send command if provided
                if command:
                    await session.async_send_text(f"{command}\n")
                    self.log_message(f"Command sent to {name}")

                # Start monitoring this session
                asyncio.create_task(self.monitor_session(session_id))
                self.log_message(f"Monitoring started for {name}")

                # Subscribe to termination
                asyncio.create_task(self.watch_session_termination(session_id))

                self.log_message(f"[green]Created session: {session_id}[/green]")

            except Exception as e:
                self.log_message(f"[red]Error: {e}[/red]")
        else:
            # Demo mode - create fake session
            session_id = f"demo-{len(self.managed_sessions)}"
            self.managed_sessions[session_id] = {
                "name": name,
                "command": command,
                "session": None,
                "status": "running"
            }

            card = SessionCard(session_id, name, command or "(interactive)", classes="card")
            self.session_cards[session_id] = card
            container = self.query_one("#sessions-container", ScrollableContainer)
            await container.mount(card)
            card.update_status("running")
            card.update_output("(Demo mode - no real iTerm2 connection)")

            self.log_message(f"[yellow]Demo session created: {session_id}[/yellow]")

    async def spawn_watcher_pair(self):
        """Spawn two file watchers side by side in the same tab."""
        self.log_message("Spawning watcher pair (split panes)...")

        if self.iterm_connection:
            try:
                app = await iterm2.async_get_app(self.iterm_connection)
                window = app.current_terminal_window

                if window is None:
                    self.log_message("[red]No iTerm2 window found[/red]")
                    return

                # Create a new tab
                tab = await window.async_create_tab()
                left_session = tab.current_session

                # Split vertically to create right pane
                right_session = await left_session.async_split_pane(vertical=True)

                # Set up both watchers
                watcher1_cmd = "echo '👀 Watcher 1: Source files' && while true; do echo \"$(date '+%H:%M:%S'): Watching src/...\"; sleep 3; done"
                watcher2_cmd = "echo '👀 Watcher 2: Test files' && while true; do echo \"$(date '+%H:%M:%S'): Watching tests/...\"; sleep 4; done"

                # Set names and send commands
                await left_session.async_set_name("Watcher 1 (src)")
                await right_session.async_set_name("Watcher 2 (tests)")
                await left_session.async_send_text(f"{watcher1_cmd}\n")
                await right_session.async_send_text(f"{watcher2_cmd}\n")

                # Register both sessions
                for i, (session, name, cmd) in enumerate([
                    (left_session, "Watcher 1 (src)", watcher1_cmd),
                    (right_session, "Watcher 2 (tests)", watcher2_cmd)
                ]):
                    session_id = session.session_id
                    self.managed_sessions[session_id] = {
                        "name": name,
                        "command": cmd,
                        "session": session,
                        "status": "starting"
                    }

                    card = SessionCard(session_id, name, cmd[:40] + "...", classes="card")
                    self.session_cards[session_id] = card
                    container = self.query_one("#sessions-container", ScrollableContainer)
                    await container.mount(card)
                    card.update_status("running")

                    asyncio.create_task(self.monitor_session(session_id))
                    asyncio.create_task(self.watch_session_termination(session_id))

                self.log_message("[green]Created watcher pair in split panes[/green]")

            except Exception as e:
                self.log_message(f"[red]Error: {e}[/red]")
        else:
            self.log_message("[yellow]Demo mode: would create 2 side-by-side watchers[/yellow]")

    async def spawn_dev_layout(self):
        """Spawn a full dev layout: server top-left, logs top-right, watchers bottom."""
        self.log_message("Spawning dev layout (2x2 grid)...")

        if self.iterm_connection:
            try:
                app = await iterm2.async_get_app(self.iterm_connection)
                window = app.current_terminal_window

                if window is None:
                    self.log_message("[red]No iTerm2 window found[/red]")
                    return

                # Create a new tab
                tab = await window.async_create_tab()
                top_left = tab.current_session

                # Split to create 2x2 grid
                top_right = await top_left.async_split_pane(vertical=True)
                bottom_left = await top_left.async_split_pane(vertical=False)
                bottom_right = await top_right.async_split_pane(vertical=False)

                # Define commands for each pane
                panes = [
                    (top_left, "Server", "echo '🚀 Dev Server' && echo 'Starting...' && sleep 1 && while true; do echo \"$(date '+%H:%M:%S'): Server running on :3000\"; sleep 5; done"),
                    (top_right, "Logs", "echo '📝 Application Logs' && while true; do echo \"[$(date '+%H:%M:%S')] INFO: Request handled - $(( RANDOM % 100 ))ms\"; sleep 2; done"),
                    (bottom_left, "Watcher 1", "echo '👀 File Watcher (src)' && while true; do echo \"$(date '+%H:%M:%S'): Watching src/...\"; sleep 3; done"),
                    (bottom_right, "Watcher 2", "echo '👀 File Watcher (tests)' && while true; do echo \"$(date '+%H:%M:%S'): Watching tests/...\"; sleep 4; done"),
                ]

                # Set up each pane
                for session, name, cmd in panes:
                    await session.async_set_name(name)
                    await session.async_send_text(f"{cmd}\n")

                    session_id = session.session_id
                    self.managed_sessions[session_id] = {
                        "name": name,
                        "command": cmd,
                        "session": session,
                        "status": "starting"
                    }

                    card = SessionCard(session_id, name, cmd[:40] + "...", classes="card")
                    self.session_cards[session_id] = card
                    container = self.query_one("#sessions-container", ScrollableContainer)
                    await container.mount(card)
                    card.update_status("running")

                    asyncio.create_task(self.monitor_session(session_id))
                    asyncio.create_task(self.watch_session_termination(session_id))

                self.log_message("[green]Created dev layout (2x2 grid)[/green]")

            except Exception as e:
                self.log_message(f"[red]Error: {e}[/red]")
        else:
            self.log_message("[yellow]Demo mode: would create 2x2 dev layout[/yellow]")

    async def spawn_new_window(self):
        """Spawn a new iTerm2 window with a sample layout."""
        self.log_message("Spawning new window...")

        if self.iterm_connection:
            try:
                # Create a new window
                new_window = await iterm2.Window.async_create(self.iterm_connection)

                if new_window is None:
                    self.log_message("[red]Failed to create window[/red]")
                    return

                # Set window title
                await new_window.async_set_title("Managed Window")

                # Get the initial session in the new window
                initial_tab = new_window.current_tab
                left_session = initial_tab.current_session

                # Split into two panes
                right_session = await left_session.async_split_pane(vertical=True)

                # Set up both panes
                panes = [
                    (left_session, "Window - Left", "echo '🪟 New Window - Left Pane' && echo 'Window ID: ' && while true; do echo \"$(date '+%H:%M:%S'): Left pane active\"; sleep 3; done"),
                    (right_session, "Window - Right", "echo '🪟 New Window - Right Pane' && while true; do echo \"$(date '+%H:%M:%S'): Right pane active\"; sleep 4; done"),
                ]

                for session, name, cmd in panes:
                    await session.async_set_name(name)
                    await session.async_send_text(f"{cmd}\n")

                    session_id = session.session_id
                    self.managed_sessions[session_id] = {
                        "name": name,
                        "command": cmd,
                        "session": session,
                        "window_id": new_window.window_id,  # Track which window
                        "status": "starting"
                    }

                    card = SessionCard(session_id, name, cmd[:40] + "...", classes="card")
                    self.session_cards[session_id] = card
                    container = self.query_one("#sessions-container", ScrollableContainer)
                    await container.mount(card)
                    card.update_status("running")

                    asyncio.create_task(self.monitor_session(session_id))
                    asyncio.create_task(self.watch_session_termination(session_id))

                self.log_message(f"[green]Created new window: {new_window.window_id}[/green]")

            except Exception as e:
                import traceback
                self.log_message(f"[red]Error creating window: {e}[/red]")
                self.log_message(f"[red]{traceback.format_exc()[:200]}[/red]")
        else:
            self.log_message("[yellow]Demo mode: would create new window[/yellow]")

    async def monitor_session(self, session_id: str):
        """Monitor a session's screen output by polling."""
        if session_id not in self.managed_sessions:
            self.log_message(f"[yellow]Session {session_id} not in managed_sessions[/yellow]")
            return

        session = self.managed_sessions[session_id].get("session")
        if not session:
            self.log_message(f"[yellow]No session object for {session_id}[/yellow]")
            return

        name = self.managed_sessions[session_id].get("name", session_id)

        try:
            # Give it a moment to start
            await asyncio.sleep(0.5)

            # Update status to running
            if session_id in self.session_cards:
                self.session_cards[session_id].update_status("running")

            # Poll for screen contents (works better with TUI apps like Claude)
            self.log_message(f"Starting monitor for {name}...")
            update_count = 0
            while session_id in self.managed_sessions:
                try:
                    contents = await session.async_get_screen_contents()
                    if contents:
                        # Extract text from screen contents
                        lines = []
                        for i in range(contents.number_of_lines):
                            line = contents.line(i)
                            lines.append(line.string)

                        text = '\n'.join(lines)

                        if session_id in self.session_cards:
                            self.session_cards[session_id].update_output(text)
                            update_count += 1
                            if update_count == 1:
                                self.log_message(f"First output received from {name}")

                except Exception as poll_err:
                    # Session might have closed
                    if "invalid" in str(poll_err).lower():
                        break

                await asyncio.sleep(1.0)  # Poll every second

        except Exception as e:
            import traceback
            self.log_message(f"[red]Monitor error for {name}: {e}[/red]")
            self.log_message(f"[red]{traceback.format_exc()[:200]}[/red]")

    async def watch_session_termination(self, session_id: str):
        """Watch for session termination."""
        if not self.iterm_connection:
            return

        async def on_terminate(connection, notification):
            if notification.session_id == session_id:
                self.log_message(f"[red]Session terminated: {session_id}[/red]")
                if session_id in self.session_cards:
                    self.session_cards[session_id].update_status("exited")
                if session_id in self.managed_sessions:
                    del self.managed_sessions[session_id]

        try:
            await iterm2_notifications.async_subscribe_to_terminate_session_notification(
                self.iterm_connection, on_terminate
            )
        except Exception as e:
            self.log_message(f"[yellow]Could not watch termination: {e}[/yellow]")

    async def refresh_all_sessions(self):
        """Refresh status of all sessions."""
        self.log_message("Refreshing all sessions...")

        for session_id, info in list(self.managed_sessions.items()):
            session = info.get("session")
            if session:
                try:
                    contents = await session.async_get_screen_contents()
                    lines = []
                    for i in range(contents.number_of_lines):
                        line = contents.line(i)
                        lines.append(line.string)

                    if session_id in self.session_cards:
                        self.session_cards[session_id].update_output('\n'.join(lines))
                except Exception as e:
                    self.log_message(f"[yellow]Could not refresh {session_id}: {e}[/yellow]")

    async def kill_all_sessions(self):
        """Close all managed sessions."""
        self.log_message("[red]Killing all sessions...[/red]")

        for session_id, info in list(self.managed_sessions.items()):
            session = info.get("session")
            if session:
                try:
                    await session.async_close()
                    self.log_message(f"Closed: {session_id}")
                except Exception:
                    pass

            # Remove card from UI
            if session_id in self.session_cards:
                await self.session_cards[session_id].remove()
                del self.session_cards[session_id]

            del self.managed_sessions[session_id]

        self.log_message("[green]All sessions killed[/green]")


async def main_with_iterm(connection):
    """Run the controller with an iTerm2 connection."""
    app = ControllerApp(iterm_connection=connection)
    await app.run_async()


async def main_demo():
    """Run the controller in demo mode (no iTerm2)."""
    app = ControllerApp(iterm_connection=None)
    await app.run_async()


if __name__ == "__main__":
    import sys

    if "--demo" in sys.argv:
        print("Running in demo mode (no iTerm2 connection)")
        asyncio.run(main_demo())
    else:
        try:
            iterm2.run_until_complete(main_with_iterm)
        except Exception as e:
            print(f"Could not connect to iTerm2: {e}")
            print("Run with --demo flag for demo mode, or ensure:")
            print("  1. You're running this inside iTerm2")
            print("  2. Python API is enabled: Preferences > General > Magic > Enable Python API")
            sys.exit(1)
