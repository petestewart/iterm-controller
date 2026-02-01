# iTerm2 Integration

## Overview

Integration with iTerm2's Python API for session management, output polling, and window/tab control.

## Constraints

### Platform Requirements
- **macOS only** - iTerm2 is macOS-specific
- **iTerm2 3.5+** - Required for Python scripting API
- **Python 3.11+** - For modern async features and typing

### iTerm2 API Limitations
- **No push notifications for output** - Must poll for session content
- **Cannot move tabs between existing windows** - Can only move to new window
- **Session IDs are stable** - Safe to store and reference later

## Connection Management

```python
import iterm2
from contextlib import asynccontextmanager

class ItermController:
    """Manages iTerm2 connection and session operations."""

    def __init__(self):
        self.connection: iterm2.Connection | None = None
        self.app: iterm2.App | None = None
        self._connected = False

    async def connect(self) -> bool:
        """Establish connection to iTerm2."""
        try:
            self.connection = await iterm2.Connection.async_create()
            self.app = await iterm2.async_get_app(self.connection)
            self._connected = True
            return True
        except Exception as e:
            self._connected = False
            raise ItermConnectionError(f"Failed to connect: {e}")

    async def disconnect(self):
        """Cleanly disconnect from iTerm2."""
        if self.connection:
            # Connection auto-closes when garbage collected
            self.connection = None
            self.app = None
            self._connected = False

    async def reconnect(self) -> bool:
        """Attempt to reconnect after disconnection."""
        await self.disconnect()
        return await self.connect()

    @property
    def is_connected(self) -> bool:
        return self._connected and self.connection is not None

    async def verify_version(self) -> tuple[bool, str]:
        """Check iTerm2 version meets requirements."""
        if not self.app:
            return (False, "Not connected")
        # iTerm2 API doesn't expose version directly, but connection success
        # implies compatible version
        return (True, "Connected")
```

## Session Spawning

```python
@dataclass
class SpawnResult:
    """Result of spawning a session."""
    session_id: str
    tab_id: str
    success: bool
    error: str | None = None

class SessionSpawner:
    """Spawns and manages terminal sessions."""

    def __init__(self, controller: ItermController):
        self.controller = controller
        self.managed_sessions: dict[str, ManagedSession] = {}

    async def spawn_session(
        self,
        template: SessionTemplate,
        project: Project,
        window: iterm2.Window | None = None
    ) -> SpawnResult:
        """Spawn a new session from template."""
        app = self.controller.app

        # Use current window or create new
        if window is None:
            window = app.current_terminal_window
            if window is None:
                window = await iterm2.Window.async_create(self.controller.connection)

        # Create new tab
        tab = await window.async_create_tab()
        session = tab.current_session

        # Set working directory
        working_dir = template.working_dir or project.path

        # Build command with environment
        env_exports = " ".join(
            f'{k}="{v}"' for k, v in template.env.items()
        )
        full_command = f"cd {working_dir}"
        if env_exports:
            full_command += f" && export {env_exports}"
        if template.command:
            full_command += f" && {template.command}"

        # Send command
        await session.async_send_text(full_command + "\n")

        # Track session
        managed = ManagedSession(
            id=session.session_id,
            template_id=template.id,
            project_id=project.id,
            tab_id=tab.tab_id,
        )
        self.managed_sessions[session.session_id] = managed

        return SpawnResult(
            session_id=session.session_id,
            tab_id=tab.tab_id,
            success=True
        )

    async def spawn_split(
        self,
        template: SessionTemplate,
        project: Project,
        parent_session: iterm2.Session,
        vertical: bool = True,
        size_percent: int = 50
    ) -> SpawnResult:
        """Spawn session as split pane."""
        session = await parent_session.async_split_pane(vertical=vertical)

        # Send command
        working_dir = template.working_dir or project.path
        full_command = f"cd {working_dir} && {template.command}"
        await session.async_send_text(full_command + "\n")

        managed = ManagedSession(
            id=session.session_id,
            template_id=template.id,
            project_id=project.id,
            tab_id=parent_session.tab.tab_id,
        )
        self.managed_sessions[session.session_id] = managed

        return SpawnResult(
            session_id=session.session_id,
            tab_id=parent_session.tab.tab_id,
            success=True
        )
```

## Session Termination

```python
class SessionTerminator:
    """Handles graceful session termination."""

    SIGTERM_TIMEOUT = 5.0  # Seconds to wait for graceful shutdown

    async def close_session(
        self,
        session: iterm2.Session,
        force: bool = False
    ) -> bool:
        """Close a session, optionally with force."""
        try:
            if force:
                await session.async_close(force=True)
            else:
                # Try graceful shutdown first
                await session.async_send_text("\x03")  # Ctrl+C
                await asyncio.sleep(0.5)
                await session.async_send_text("exit\n")

                # Wait for session to close
                try:
                    await asyncio.wait_for(
                        self._wait_for_close(session),
                        timeout=self.SIGTERM_TIMEOUT
                    )
                except asyncio.TimeoutError:
                    # Force close if graceful failed
                    await session.async_close(force=True)

            return True
        except Exception as e:
            return False

    async def _wait_for_close(self, session: iterm2.Session):
        """Wait for session to terminate."""
        while True:
            try:
                # Session properties raise if session is gone
                _ = session.session_id
                await asyncio.sleep(0.1)
            except:
                break

    async def close_tab(self, tab: iterm2.Tab) -> bool:
        """Close a tab and all its sessions."""
        try:
            await tab.async_close(force=False)
            return True
        except:
            return False

    async def close_all_managed(
        self,
        sessions: list[ManagedSession],
        controller: ItermController
    ) -> int:
        """Close all managed sessions, return count closed."""
        closed = 0
        for managed in sessions:
            try:
                session = await controller.app.async_get_session_by_id(managed.id)
                if session:
                    await self.close_session(session)
                    closed += 1
            except:
                pass
        return closed
```

## Window Layout Spawning

```python
class WindowLayoutSpawner:
    """Spawns window layouts with predefined tabs and sessions."""

    def __init__(self, controller: ItermController, spawner: SessionSpawner):
        self.controller = controller
        self.spawner = spawner

    async def spawn_layout(
        self,
        layout: WindowLayout,
        project: Project,
        session_templates: dict[str, SessionTemplate]
    ) -> list[SpawnResult]:
        """Spawn a complete window layout."""
        results = []

        # Create new window
        window = await iterm2.Window.async_create(self.controller.connection)

        for i, tab_layout in enumerate(layout.tabs):
            # First tab uses the window's default tab
            if i == 0:
                tab = window.current_tab
            else:
                tab = await window.async_create_tab()

            # Set tab title
            await tab.async_set_title(tab_layout.name)

            # Spawn sessions in this tab
            current_session = tab.current_session
            for j, session_layout in enumerate(tab_layout.sessions):
                template = session_templates.get(session_layout.template_id)
                if not template:
                    continue

                if j == 0:
                    # First session uses tab's default session
                    result = await self.spawner.spawn_session(
                        template, project, window
                    )
                else:
                    # Subsequent sessions are splits
                    vertical = session_layout.split == "vertical"
                    result = await self.spawner.spawn_split(
                        template, project, current_session, vertical
                    )

                results.append(result)

        return results
```

## Window State Tracking

```python
@dataclass
class WindowState:
    """Tracks iTerm2 window state."""
    window_id: str
    tabs: list[TabState] = field(default_factory=list)
    managed_tab_ids: set[str] = field(default_factory=set)  # Tabs we spawned

@dataclass
class TabState:
    """Tracks iTerm2 tab state."""
    tab_id: str
    title: str
    session_ids: list[str] = field(default_factory=list)
    is_managed: bool = False

class WindowTracker:
    """Tracks window and tab state across the application."""

    def __init__(self, controller: ItermController):
        self.controller = controller
        self.windows: dict[str, WindowState] = {}

    async def refresh(self):
        """Refresh window state from iTerm2."""
        self.windows.clear()

        for window in self.controller.app.terminal_windows:
            state = WindowState(window_id=window.window_id)

            for tab in window.tabs:
                tab_state = TabState(
                    tab_id=tab.tab_id,
                    title=await tab.async_get_variable("title") or "",
                    session_ids=[s.session_id for s in tab.sessions],
                    is_managed=tab.tab_id in state.managed_tab_ids
                )
                state.tabs.append(tab_state)

            self.windows[window.window_id] = state

    def mark_managed(self, tab_id: str, window_id: str):
        """Mark a tab as managed by this application."""
        if window_id in self.windows:
            self.windows[window_id].managed_tab_ids.add(tab_id)
```

## Error Handling

```python
class ItermConnectionError(Exception):
    """Raised when iTerm2 connection fails."""
    pass

class ItermSessionError(Exception):
    """Raised when session operations fail."""
    pass

async def with_reconnect(
    controller: ItermController,
    operation: Callable,
    max_retries: int = 3
):
    """Execute operation with automatic reconnect on failure."""
    for attempt in range(max_retries):
        try:
            return await operation()
        except Exception as e:
            if "connection" in str(e).lower() and attempt < max_retries - 1:
                await controller.reconnect()
            else:
                raise
```
