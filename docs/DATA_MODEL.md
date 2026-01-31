# Data Model for Project Orchestrator

This document outlines data structures for a project manager/orchestrator application built on the iTerm2 controller POC.

## Core Entities

### Project

A project represents a workspace with associated terminal sessions.

```python
@dataclass
class Project:
    id: str                      # Unique identifier (uuid)
    name: str                    # Display name
    path: str                    # Working directory
    created_at: datetime
    updated_at: datetime

    # Session templates - what tabs this project needs
    session_templates: list[SessionTemplate]

    # Active sessions (runtime, not persisted)
    active_sessions: dict[str, ManagedSession] = field(default_factory=dict)

    # Project-level configuration
    config: ProjectConfig = field(default_factory=ProjectConfig)
```

### SessionTemplate

Defines a type of session that can be spawned for a project.

```python
@dataclass
class SessionTemplate:
    id: str                      # Template identifier
    name: str                    # Display name (e.g., "Plan", "Work", "Test")
    command: str                 # Command to run (can include {variables})

    # Layout configuration
    layout: SessionLayout = SessionLayout.TAB  # TAB, PANE_HORIZONTAL, PANE_VERTICAL
    parent_template_id: str | None = None      # For panes: which session to split from

    # Behavior
    auto_start: bool = False     # Start when project opens
    restart_on_exit: bool = False
    working_directory: str | None = None  # Override project path

    # Monitoring
    monitor_output: bool = True
    success_pattern: str | None = None   # Regex to detect success
    error_pattern: str | None = None     # Regex to detect errors

class SessionLayout(Enum):
    TAB = "tab"
    PANE_HORIZONTAL = "pane_horizontal"  # Split top/bottom
    PANE_VERTICAL = "pane_vertical"      # Split left/right
```

### ManagedSession

Runtime state for an active session.

```python
@dataclass
class ManagedSession:
    id: str                      # Our internal ID
    iterm_session_id: str        # iTerm2's session ID
    template_id: str             # Which template spawned this
    project_id: str

    # State
    status: SessionStatus
    started_at: datetime
    ended_at: datetime | None = None
    exit_code: int | None = None

    # Output tracking
    last_output: str = ""
    output_history: list[OutputEntry] = field(default_factory=list)

    # Error tracking
    errors: list[SessionError] = field(default_factory=list)

class SessionStatus(Enum):
    STARTING = "starting"
    RUNNING = "running"
    WAITING = "waiting"      # Waiting for input / at prompt
    SUCCEEDED = "succeeded"  # Detected success pattern
    FAILED = "failed"        # Detected error pattern
    EXITED = "exited"        # Process exited

@dataclass
class OutputEntry:
    timestamp: datetime
    content: str
    entry_type: str = "output"  # "output", "error", "prompt"

@dataclass
class SessionError:
    timestamp: datetime
    message: str
    output_context: str        # Surrounding output for debugging
```

### ProjectConfig

Project-level settings.

```python
@dataclass
class ProjectConfig:
    # Environment
    environment_variables: dict[str, str] = field(default_factory=dict)

    # Behavior
    close_sessions_on_project_close: bool = True
    confirm_before_close: bool = True

    # Display
    tab_prefix: str = ""       # Prefix for tab names (e.g., "[proj] ")

    # Orchestration
    startup_sequence: list[str] = field(default_factory=list)  # Template IDs in order
    shutdown_sequence: list[str] = field(default_factory=list)
```

## Window/Tab Awareness

For tracking all tabs in the window, not just managed ones:

```python
@dataclass
class WindowState:
    window_id: str

    # All tabs in the window
    tabs: list[TabInfo]

    # Which tabs we manage
    managed_tab_ids: set[str]

    # Which tabs existed before we started (external)
    external_tab_ids: set[str]

@dataclass
class TabInfo:
    tab_id: str
    title: str
    session_ids: list[str]     # Panes within the tab
    is_managed: bool           # Did we create this?
    project_id: str | None     # If managed, which project
```

## Persistence Schema

### JSON File Structure

```json
{
  "version": "1.0",
  "projects": [
    {
      "id": "proj-abc123",
      "name": "My Web App",
      "path": "/Users/me/projects/webapp",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-20T14:22:00Z",
      "session_templates": [
        {
          "id": "plan",
          "name": "Plan",
          "command": "claude /plan",
          "layout": "tab",
          "auto_start": true
        },
        {
          "id": "work",
          "name": "Work",
          "command": "claude",
          "layout": "tab"
        },
        {
          "id": "server",
          "name": "Dev Server",
          "command": "npm run dev",
          "layout": "tab",
          "restart_on_exit": true
        },
        {
          "id": "tests",
          "name": "Tests",
          "command": "npm run test:watch",
          "layout": "pane_vertical",
          "parent_template_id": "server"
        }
      ],
      "config": {
        "tab_prefix": "[webapp] ",
        "startup_sequence": ["server", "tests", "plan"],
        "close_sessions_on_project_close": true
      }
    }
  ],
  "settings": {
    "default_shell": "/bin/zsh",
    "confirm_on_quit": true
  }
}
```

### SQLite Schema (Alternative)

```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    config_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE session_templates (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    command TEXT NOT NULL,
    layout TEXT DEFAULT 'tab',
    parent_template_id TEXT,
    auto_start BOOLEAN DEFAULT FALSE,
    restart_on_exit BOOLEAN DEFAULT FALSE,
    config_json TEXT
);

CREATE TABLE session_history (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    template_id TEXT,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    exit_code INTEGER,
    status TEXT
);
```

## State Management

### Application State

```python
@dataclass
class AppState:
    # Persistence
    projects: dict[str, Project]
    settings: AppSettings

    # Runtime
    active_project_id: str | None = None
    iterm_connection: Connection | None = None
    window_state: WindowState | None = None

    # UI State
    selected_session_id: str | None = None

    def get_active_project(self) -> Project | None:
        if self.active_project_id:
            return self.projects.get(self.active_project_id)
        return None
```

### Event System

For coordinating between components:

```python
class EventType(Enum):
    # Session events
    SESSION_STARTED = "session_started"
    SESSION_OUTPUT = "session_output"
    SESSION_STATUS_CHANGED = "session_status_changed"
    SESSION_ENDED = "session_ended"

    # Project events
    PROJECT_OPENED = "project_opened"
    PROJECT_CLOSED = "project_closed"

    # Window events
    TAB_CREATED = "tab_created"
    TAB_CLOSED = "tab_closed"
    WINDOW_TABS_CHANGED = "window_tabs_changed"

    # App events
    APP_QUIT_REQUESTED = "app_quit_requested"

@dataclass
class Event:
    type: EventType
    data: dict
    timestamp: datetime = field(default_factory=datetime.now)
```

## Orchestration Workflows

### Project Startup

```python
async def open_project(project_id: str):
    project = state.projects[project_id]

    # 1. Switch to project directory
    # 2. Spawn sessions in startup_sequence order
    for template_id in project.config.startup_sequence:
        template = get_template(project, template_id)
        await spawn_session_from_template(project, template)

        # Wait for session to be ready if needed
        if template.wait_for_ready:
            await wait_for_prompt(session)

    state.active_project_id = project_id
```

### Project Shutdown

```python
async def close_project(project_id: str, force: bool = False):
    project = state.projects[project_id]

    if not force and project.config.confirm_before_close:
        if not await confirm_close():
            return

    # Close sessions in reverse order
    for template_id in reversed(project.config.shutdown_sequence):
        session = get_session_for_template(project, template_id)
        if session:
            await close_session(session)

    state.active_project_id = None
```

### Quit with Tab Cleanup

```python
async def quit_app():
    # Get all tabs in window
    window_state = await get_window_state()

    if window_state.tabs:
        # Show confirmation with tab list
        action = await show_quit_dialog(window_state.tabs)

        if action == QuitAction.CANCEL:
            return
        elif action == QuitAction.CLOSE_ALL:
            for tab in window_state.tabs:
                await close_tab(tab.tab_id)
        elif action == QuitAction.CLOSE_MANAGED:
            for tab in window_state.tabs:
                if tab.is_managed:
                    await close_tab(tab.tab_id)
        # QuitAction.KEEP_ALL - just quit, leave tabs

    app.exit()
```

## Future Considerations

### Inter-Session Communication

```python
@dataclass
class SessionMessage:
    from_session_id: str
    to_session_id: str
    message_type: str   # "command", "data", "signal"
    payload: Any

# Example: Tell test session to run after build completes
async def on_build_complete(build_session: ManagedSession):
    test_session = get_session("tests")
    await send_message(SessionMessage(
        from_session_id=build_session.id,
        to_session_id=test_session.id,
        message_type="command",
        payload="npm test"
    ))
```

### Task Dependencies

```python
@dataclass
class TaskDependency:
    task_id: str
    depends_on: list[str]      # Task IDs that must complete first
    condition: str = "success"  # "success", "any", "failure"
```

### Output Parsing

```python
@dataclass
class OutputParser:
    name: str
    patterns: list[OutputPattern]

@dataclass
class OutputPattern:
    regex: str
    event_type: str            # "error", "warning", "success", "progress"
    extract_groups: list[str]  # Named groups to extract
```
