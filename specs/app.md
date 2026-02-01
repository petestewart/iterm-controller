# App Entry & State

## Overview

The main Textual application class and reactive state management system that coordinates all UI components and backend services.

## Entry Point

```python
# __main__.py
import asyncio
from iterm_controller.app import ItermControllerApp

def main():
    app = ItermControllerApp()
    app.run()

if __name__ == "__main__":
    main()
```

## Main Application Class

```python
from textual.app import App
from textual.screen import Screen

class ItermControllerApp(App):
    """Main iTerm2 Controller TUI application."""

    CSS_PATH = "styles.tcss"
    TITLE = "iTerm Controller"

    SCREENS = {
        "control_room": ControlRoomScreen,
        "project_list": ProjectListScreen,
        "project_dashboard": ProjectDashboardScreen,
        "new_project": NewProjectScreen,
        "settings": SettingsScreen,
    }

    BINDINGS = [
        ("q", "request_quit", "Quit"),
        ("ctrl+c", "request_quit", "Quit"),
        ("?", "show_help", "Help"),
        ("p", "push_screen('project_list')", "Projects"),
        ("s", "push_screen('settings')", "Settings"),
    ]

    def __init__(self):
        super().__init__()
        self.state = AppState()
        self.iterm = ItermController()
        self.github = GitHubIntegration()
        self.notifier = Notifier()

    async def on_mount(self):
        """Initialize services when app starts."""
        await self.iterm.connect()
        await self.github.initialize()
        await self.state.load_config()
        self.push_screen("control_room")

    async def action_request_quit(self):
        """Handle quit with confirmation if sessions active."""
        if self.state.has_active_sessions:
            await self.push_screen(QuitConfirmModal())
        else:
            self.exit()
```

## App State Manager

Centralized reactive state with event dispatch for coordinating UI updates.

```python
from dataclasses import dataclass, field
from typing import Callable
from enum import Enum

class StateEvent(Enum):
    PROJECT_OPENED = "project_opened"
    PROJECT_CLOSED = "project_closed"
    SESSION_SPAWNED = "session_spawned"
    SESSION_CLOSED = "session_closed"
    SESSION_STATUS_CHANGED = "session_status_changed"
    TASK_STATUS_CHANGED = "task_status_changed"
    PLAN_RELOADED = "plan_reloaded"
    PLAN_CONFLICT = "plan_conflict"
    CONFIG_CHANGED = "config_changed"
    HEALTH_STATUS_CHANGED = "health_status_changed"
    WORKFLOW_STAGE_CHANGED = "workflow_stage_changed"

@dataclass
class AppState:
    """Reactive application state with event dispatch."""

    # Core state
    projects: dict[str, Project] = field(default_factory=dict)
    active_project_id: str | None = None
    sessions: dict[str, ManagedSession] = field(default_factory=dict)
    config: AppConfig | None = None

    # Event subscribers
    _listeners: dict[StateEvent, list[Callable]] = field(default_factory=dict)

    def subscribe(self, event: StateEvent, callback: Callable):
        """Register callback for state event."""
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)

    def unsubscribe(self, event: StateEvent, callback: Callable):
        """Remove callback from event."""
        if event in self._listeners:
            self._listeners[event].remove(callback)

    def emit(self, event: StateEvent, **kwargs):
        """Dispatch event to all subscribers."""
        for callback in self._listeners.get(event, []):
            callback(**kwargs)

    @property
    def has_active_sessions(self) -> bool:
        """Check if any sessions are currently active."""
        return any(s.is_active for s in self.sessions.values())

    @property
    def active_project(self) -> Project | None:
        """Get currently active project."""
        if self.active_project_id:
            return self.projects.get(self.active_project_id)
        return None

    async def load_config(self):
        """Load configuration from disk."""
        self.config = await load_app_config()
        self.emit(StateEvent.CONFIG_CHANGED, config=self.config)

    async def open_project(self, project_id: str):
        """Open a project and spawn its sessions."""
        project = self.projects[project_id]
        self.active_project_id = project_id
        self.emit(StateEvent.PROJECT_OPENED, project=project)

    async def close_project(self, project_id: str):
        """Close a project and its sessions."""
        self.emit(StateEvent.PROJECT_CLOSED, project_id=project_id)
        if self.active_project_id == project_id:
            self.active_project_id = None
```

## Screen Navigation

```python
class ScreenNavigator:
    """Manages screen stack and navigation."""

    def __init__(self, app: ItermControllerApp):
        self.app = app
        self._history: list[str] = []

    def push(self, screen_name: str, **kwargs):
        """Push screen onto navigation stack."""
        self._history.append(self.app.screen.name)
        self.app.push_screen(screen_name, **kwargs)

    def pop(self):
        """Return to previous screen."""
        if self._history:
            self.app.pop_screen()
            self._history.pop()

    def replace(self, screen_name: str, **kwargs):
        """Replace current screen without adding to history."""
        self.app.switch_screen(screen_name, **kwargs)
```

## Lifecycle Management

### Application Startup Sequence

1. Load global configuration from `~/.config/iterm-controller/config.json`
2. Connect to iTerm2 Python API
3. Check GitHub CLI availability
4. Initialize notification system
5. Load project list from config
6. Display Control Room screen

### Application Shutdown Sequence

1. Show quit confirmation if sessions active
2. Based on user choice:
   - **Close All**: SIGTERM all sessions, wait 5s, SIGKILL if needed
   - **Close Managed**: Close only spawned sessions
   - **Leave Running**: Disconnect cleanly, sessions continue
3. Save any pending configuration changes
4. Disconnect from iTerm2 API
5. Exit application

## Error Handling

```python
class AppErrorHandler:
    """Centralized error handling for the application."""

    def __init__(self, app: ItermControllerApp):
        self.app = app

    async def handle_error(self, error: Exception, context: str = ""):
        """Handle errors with appropriate UI feedback."""
        if isinstance(error, ItermConnectionError):
            await self.show_iterm_reconnect_dialog()
        elif isinstance(error, ConfigLoadError):
            await self.show_config_error_toast(error)
        else:
            await self.log_and_toast(error, context)

    async def show_iterm_reconnect_dialog(self):
        """Prompt user to reconnect to iTerm2."""
        modal = ReconnectModal()
        if await self.app.push_screen_wait(modal):
            await self.app.iterm.reconnect()
```

## CSS Styling

The app uses Textual CSS for styling. Base styles are in `styles.tcss`:

```css
/* styles.tcss */
Screen {
    background: $surface;
}

.session-waiting {
    color: $warning;
}

.session-working {
    color: $success;
}

.session-idle {
    color: $text-muted;
}

.task-blocked {
    color: $text-disabled;
}

.health-healthy {
    color: $success;
}

.health-unhealthy {
    color: $error;
}
```
