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
        "project_list": ProjectListScreen,
        "project_screen": ProjectScreen,
        "new_project": NewProjectScreen,
        "settings": SettingsScreen,
    }

    # Mode screens require a Project argument and are accessed via ProjectScreen.
    # Plan, Docs, and Work modes were removed in task 27.9.3.
    # TestModeScreen is retained for test plan management.
    MODE_SCREENS = {
        "test": TestModeScreen,
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
        # MissionControlScreen is pushed as an instance, not via SCREENS dict
        self.push_screen(MissionControlScreen())

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
6. Display Mission Control screen (main dashboard with live session output)

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

## New State Managers

### GitStateManager

```python
class GitStateManager:
    """Manages git status for all open projects"""

    def __init__(self, git_service: GitService):
        self.git_service = git_service
        self.statuses: dict[str, GitStatus] = {}  # project_id -> GitStatus

    async def refresh(self, project_id: str) -> GitStatus:
        """Refresh git status for a project"""
        project = self.app.state.projects.get(project_id)
        status = await self.git_service.get_status(Path(project.path))
        self.statuses[project_id] = status
        self.post_message(GitStatusChanged(project_id, status))
        return status

    async def stage_files(self, project_id: str, files: list[str]) -> None:
        """Stage files and refresh status"""
        project = self.app.state.projects.get(project_id)
        await self.git_service.stage_files(Path(project.path), files)
        await self.refresh(project_id)

    async def commit(self, project_id: str, message: str) -> str:
        """Create commit and refresh status"""
        project = self.app.state.projects.get(project_id)
        sha = await self.git_service.commit(Path(project.path), message)
        await self.refresh(project_id)
        return sha

    async def push(self, project_id: str) -> None:
        """Push to remote and refresh status"""
        project = self.app.state.projects.get(project_id)
        await self.git_service.push(Path(project.path))
        await self.refresh(project_id)

    async def pull(self, project_id: str) -> None:
        """Pull from remote and refresh status"""
        project = self.app.state.projects.get(project_id)
        await self.git_service.pull(Path(project.path))
        await self.refresh(project_id)

    def get(self, project_id: str) -> GitStatus | None:
        """Get cached status for a project"""
        return self.statuses.get(project_id)
```

### ReviewStateManager

```python
class ReviewStateManager:
    """Manages review state for tasks"""

    def __init__(self, review_service: ReviewService):
        self.review_service = review_service
        self.active_reviews: dict[str, TaskReview] = {}  # task_id -> current review

    async def start_review(
        self,
        project_id: str,
        task_id: str
    ) -> TaskReview:
        """Start a review for a task"""
        project = self.app.state.projects.get(project_id)
        task = self.app.state.plans.get_task(project_id, task_id)

        context = await self.review_service.build_review_context(project, task)
        review = await self.review_service.run_review(project, task, context)

        self.active_reviews[task_id] = review
        self.post_message(ReviewCompleted(task_id, review.result, review))

        return review

    def get_active_review(self, task_id: str) -> TaskReview | None:
        """Get active review for a task"""
        return self.active_reviews.get(task_id)
```

## Updated AppState

```python
@dataclass
class AppState:
    """Master application state"""

    # Existing managers
    projects: ProjectStateManager
    sessions: SessionStateManager
    plans: PlanStateManager
    health: HealthStateManager

    # NEW managers
    git: GitStateManager
    reviews: ReviewStateManager
```

## New Services

### Service Registration

```python
class ServiceContainer:
    """Dependency injection container for services"""

    def __init__(self):
        # Existing services
        self.iterm_controller: ItermController
        self.session_spawner: SessionSpawner
        self.session_terminator: SessionTerminator
        self.session_monitor: SessionMonitor
        self.window_layout_manager: WindowLayoutManager
        self.github_integration: GitHubIntegration
        self.notifier: Notifier

        # NEW services
        self.git_service: GitService
        self.review_service: ReviewService
        self.script_service: ScriptService
```

### Service Initialization

```python
async def initialize_services(self):
    """Initialize all services"""
    # Existing...

    # NEW
    self.git_service = GitService(notifier=self.notifier)

    self.review_service = ReviewService(
        session_spawner=self.session_spawner,
        git_service=self.git_service,
        plan_manager=self.state.plans,
        notifier=self.notifier
    )

    self.script_service = ScriptService(
        session_spawner=self.session_spawner,
        session_monitor=self.session_monitor
    )

    # Initialize state managers with services
    self.state.git = GitStateManager(self.git_service)
    self.state.reviews = ReviewStateManager(self.review_service)
```

## New Events/Messages

```python
class GitStatusChanged(Message):
    """Posted when git status changes for a project"""
    project_id: str
    status: GitStatus

class ReviewStarted(Message):
    """Posted when a review begins"""
    task_id: str
    project_id: str

class ReviewCompleted(Message):
    """Posted when a review finishes"""
    task_id: str
    result: ReviewResult
    review: TaskReview

class ReviewFailed(Message):
    """Posted when review fails max times and needs human"""
    task_id: str
    review: TaskReview

class ScriptStarted(Message):
    """Posted when a script starts running"""
    project_id: str
    script_id: str
    session_id: str

class ScriptCompleted(Message):
    """Posted when a script finishes"""
    project_id: str
    script_id: str
    exit_code: int

class SessionOutputUpdated(Message):
    """Posted when new output is available for a session"""
    session_id: str
    output: str

class OrchestratorProgress(Message):
    """Posted when orchestrator makes progress"""
    project_id: str
    session_id: str
    progress: SessionProgress
```
