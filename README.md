# iTerm2 Project Orchestrator

A Python-based TUI application that serves as a "control room" for development projects. Manages terminal sessions through iTerm2's Python API, monitors session output for attention-needed states, and provides unified visibility across multiple projects.

**Core value:** One command to open a project with all dev environment tabs spawned, configured, and monitored.

## Features

- **Session Management** - Spawn, monitor, and kill terminal sessions programmatically
- **Attention Detection** - Real-time monitoring for sessions needing user input (questions, prompts, errors)
- **Task Tracking** - Parse and update PLAN.md task lists, track progress
- **Health Checks** - Poll HTTP endpoints and display service health status
- **GitHub Integration** - Branch sync, PR status via `gh` CLI
- **Workflow Modes** - Plan, Docs, Work, and Test modes for different development phases
- **Auto Mode** - Automatic stage progression with configurable commands
- **Notifications** - macOS notifications when sessions need attention

## Setup

### Prerequisites

- **macOS** (iTerm2 is macOS-specific)
- **iTerm2 3.5+** with Python API enabled
- **Python 3.11+**

### Installation

1. **Enable iTerm2 Python API**:
   - Open iTerm2 Preferences (⌘,)
   - Go to General → Magic
   - Check "Enable Python API"

2. **Install the package**:
   ```bash
   pip install -e .
   ```

   Or install dependencies manually:
   ```bash
   pip install textual iterm2 dacite watchfiles httpx
   ```

## Usage

### TUI Mode (Default)

Launch the interactive terminal UI:

```bash
python -m iterm_controller
```

### CLI Mode (Headless)

Perform operations without launching the TUI:

```bash
# List configured projects
python -m iterm_controller list-projects

# List active sessions
python -m iterm_controller list-sessions --project myproj

# Spawn a session
python -m iterm_controller spawn --project myproj --template dev-server

# Kill a session
python -m iterm_controller kill --session SESSION_ID

# Task operations
python -m iterm_controller task list --project myproj
python -m iterm_controller task claim --project myproj --task 2.1
python -m iterm_controller task done --project myproj --task 2.1
python -m iterm_controller task skip --project myproj --task 2.1
```

All CLI commands support `--json` for machine-readable output:

```bash
python -m iterm_controller list-projects --json
```

## Agent Integration (Programmatic API)

The package provides a complete programmatic API for integration with AI agents, automation scripts, or custom tooling. This enables agents to perform all TUI actions without a graphical interface.

### Quick Start

```python
import asyncio
from iterm_controller import ItermControllerAPI

async def main():
    # Initialize the API
    api = ItermControllerAPI()
    await api.initialize()

    # List projects
    projects = await api.list_projects()
    print(f"Found {len(projects)} projects")

    # Open a project and work with tasks
    await api.open_project("my-project")
    tasks = await api.list_tasks("my-project")

    # Claim and complete a task
    await api.claim_task("my-project", "2.1")
    # ... do work ...
    await api.complete_task("my-project", "2.1")

    # Spawn a terminal session
    result = await api.spawn_session("my-project", "dev-server")
    if result.success:
        print(f"Spawned session: {result.session.id}")

    # Clean up
    await api.shutdown()

asyncio.run(main())
```

### Convenience Functions

For one-off operations, use the convenience functions that handle API lifecycle automatically:

```python
from iterm_controller import (
    spawn_session,
    claim_task,
    list_projects,
    list_sessions,
    get_state,
    get_plan,
    get_task_progress,
)

# Spawn a session (creates temporary API, spawns, cleans up)
result = await spawn_session("my-project", "dev-server")

# Claim a task (no iTerm2 connection needed)
result = await claim_task("my-project", "2.1")

# Query state
projects = await list_projects()
sessions = await list_sessions("my-project")
progress = await get_task_progress("my-project")
```

### Session Management

```python
from iterm_controller import ItermControllerAPI

api = ItermControllerAPI()
await api.initialize()

# Spawn a session linked to a task
result = await api.spawn_session(
    project_id="my-project",
    template_id="dev-server",
    task_id="2.1"  # Optional: link session to task
)

if result.success:
    session = result.session
    print(f"Session ID: {session.id}")
    print(f"Attention state: {session.attention_state.value}")

# List sessions
sessions = await api.list_sessions("my-project")
for s in sessions:
    print(f"{s.template_id}: {s.attention_state.value}")

# Get sessions needing attention
waiting = await api.get_sessions_waiting("my-project")
for s in waiting:
    print(f"Session {s.id} needs input!")

# Send text to a session
await api.send_to_session(session.id, "echo hello")

# Focus a session in iTerm2
await api.focus_session(session.id)

# Kill a session
await api.kill_session(session.id)
```

### Task Operations (PLAN.md)

```python
# Open project to load PLAN.md
await api.open_project("my-project")

# Get the parsed plan
plan = await api.get_plan("my-project")
if plan:
    print(f"Total tasks: {len(plan.all_tasks)}")
    print(f"Summary: {plan.completion_summary}")

# List tasks (optionally filter by status)
from iterm_controller import TaskStatus

all_tasks = await api.list_tasks("my-project")
pending = await api.list_tasks("my-project", status=TaskStatus.PENDING)

# Get a specific task
task = await api.get_task("my-project", "2.1")
if task:
    print(f"Task: {task.title}")
    print(f"Status: {task.status.value}")
    print(f"Blocked: {task.is_blocked}")
    print(f"Depends on: {task.depends}")

# Update task status
await api.claim_task("my-project", "2.1")      # Set to IN_PROGRESS
await api.complete_task("my-project", "2.1")   # Set to COMPLETE
await api.unclaim_task("my-project", "2.1")    # Set back to PENDING
await api.skip_task("my-project", "2.1")       # Set to SKIPPED

# Or use generic update
await api.update_task_status("my-project", "2.1", TaskStatus.IN_PROGRESS)

# Get progress summary
progress = await api.get_task_progress("my-project")
# Returns: {"pending": 3, "in_progress": 1, "complete": 5, "skipped": 1}
```

### Test Plan Operations (TEST_PLAN.md)

```python
# Get test plan
test_plan = await api.get_test_plan("my-project")
if test_plan:
    print(f"Total steps: {len(test_plan.all_steps)}")
    print(f"Summary: {test_plan.summary}")

# List test steps
from iterm_controller import TestStatus

steps = await api.list_test_steps("my-project")
pending = await api.list_test_steps("my-project", status=TestStatus.PENDING)

# Toggle test step status (cycles through states)
await api.toggle_test_step("my-project", "section-0-1")

# Or set specific status with notes
await api.toggle_test_step(
    "my-project",
    "section-0-1",
    new_status=TestStatus.FAILED,
    notes="Button not visible on mobile"
)
```

### Project Operations

```python
# List all projects
projects = await api.list_projects()
for p in projects:
    print(f"{p.id}: {p.name} at {p.path}")

# Get specific project
project = await api.get_project("my-project")

# Open/close projects
await api.open_project("my-project")
await api.close_project("my-project")

# Create a new project
result = await api.create_project(
    project_id="new-project",
    name="New Project",
    path="/path/to/project",
    template_id="rails-app",  # Optional
    jira_ticket="PROJ-123",   # Optional
)

# Delete a project (from config, not disk)
await api.delete_project("old-project")

# Update workflow mode
from iterm_controller import WorkflowMode
await api.update_project_mode("my-project", WorkflowMode.WORK)
```

### State Observation

For monitoring tools that need to observe state without taking actions:

```python
from iterm_controller import get_state

# Get complete state snapshot
state = await get_state()
if state:
    print(f"Projects: {len(state.projects)}")
    print(f"Active project: {state.active_project_id}")
    print(f"Sessions: {len(state.sessions)}")

    for session in state.sessions.values():
        print(f"  {session.name}: {session.attention_state.value}")
```

### Window Layouts

```python
# List available layouts
layouts = await api.list_layouts()
for layout in layouts:
    print(f"{layout.id}: {layout.name}")

# Spawn a predefined layout
result = await api.spawn_layout("my-project", "full-stack")
if result and result.success:
    print(f"Spawned {len(result.results)} sessions")
```

### Result Types

All API methods return typed result objects:

```python
from iterm_controller import (
    APIResult,       # Base: success, error
    SessionResult,   # + session, spawn_result
    TaskResult,      # + task
    TestStepResult,  # + step
    ProjectResult,   # + project
)

result = await api.spawn_session("my-project", "dev-server")
if result.success:
    print(f"Session: {result.session.name}")
else:
    print(f"Error: {result.error}")
```

### Data Models

Import data models for type hints:

```python
from iterm_controller import (
    # Projects
    Project,
    WorkflowMode,
    WorkflowStage,

    # Sessions
    ManagedSession,
    SessionTemplate,
    AttentionState,

    # Tasks
    Task,
    TaskStatus,
    Phase,
    Plan,

    # Tests
    TestStep,
    TestStatus,
    TestPlan,

    # Configuration
    AppConfig,
    WindowLayout,
    HealthCheck,
)
```

### Agent Loop Example

A complete example of an agent monitoring sessions and handling attention states:

```python
import asyncio
from iterm_controller import ItermControllerAPI, AttentionState

async def agent_loop():
    api = ItermControllerAPI()
    await api.initialize()

    try:
        await api.open_project("my-project")

        # Spawn dev environment
        await api.spawn_session("my-project", "dev-server")
        await api.spawn_session("my-project", "test-watcher")

        # Claim first pending task
        tasks = await api.list_tasks("my-project")
        pending = [t for t in tasks if t.status.value == "pending" and not t.is_blocked]
        if pending:
            await api.claim_task("my-project", pending[0].id)

        # Monitor loop
        while True:
            sessions = await api.list_sessions("my-project")

            for session in sessions:
                if session.attention_state == AttentionState.WAITING:
                    print(f"Session {session.name} needs attention!")
                    # Agent could read output, make decision, send response
                    # await api.send_to_session(session.id, "y\n")

            # Check task progress
            progress = await api.get_task_progress("my-project")
            total = sum(progress.values())
            done = progress.get("complete", 0) + progress.get("skipped", 0)
            print(f"Progress: {done}/{total} tasks complete")

            await asyncio.sleep(5)

    finally:
        await api.shutdown()

asyncio.run(agent_loop())
```

## Configuration

Configuration is stored in JSON files:

- **Global**: `~/.config/iterm-controller/config.json`
- **Project**: `{project}/.iterm-controller.json` (optional overrides)

### Example Configuration

```json
{
  "settings": {
    "default_ide": "cursor",
    "default_shell": "zsh",
    "polling_interval_ms": 500,
    "notification_enabled": true
  },
  "projects": [
    {
      "id": "my-project",
      "name": "My Project",
      "path": "/path/to/project",
      "template_id": "rails-app"
    }
  ],
  "session_templates": [
    {
      "id": "dev-server",
      "name": "Dev Server",
      "command": "bin/dev",
      "env": {"RAILS_ENV": "development"}
    },
    {
      "id": "claude",
      "name": "Claude Code",
      "command": "claude"
    }
  ],
  "window_layouts": [
    {
      "id": "full-stack",
      "name": "Full Stack",
      "tabs": [
        {"name": "Server", "sessions": [{"template_id": "dev-server"}]},
        {"name": "Claude", "sessions": [{"template_id": "claude"}]}
      ]
    }
  ]
}
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1-4` | Switch workflow modes (Plan/Docs/Work/Test) |
| `s` | Open Sessions/Control Room |
| `,` | Open Settings |
| `p` | Open Project List |
| `n` | New session (spawn) |
| `k` | Kill selected session |
| `f` | Focus selected session in iTerm2 |
| `?` | Show help |
| `q` | Quit |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Textual TUI App                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Control Room│  │  Project    │  │  Settings   │              │
│  │   Screen    │  │  Dashboard  │  │   Screen    │              │
│  └──────┬──────┘  └──────┬──────┘  └─────────────┘              │
│         │                │                                       │
│         │         ┌──────┴──────────────────────────┐           │
│         │         │      Workflow Modes             │           │
│         │         │  ┌────┐┌────┐┌────┐┌────┐      │           │
│         │         │  │Plan││Docs││Work││Test│      │           │
│         │         │  └────┘└────┘└────┘└────┘      │           │
│         │         └─────────────────────────────────┘           │
│         │                │                                       │
│         └────────┬───────┘                                       │
│                  ▼                                               │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                     App State Manager                        ││
│  │  - Projects, Sessions, Settings                              ││
│  │  - Event dispatch                                            ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  iTerm2     │  │  Plan       │  │  GitHub     │  │  Notifier   │
│  Controller │  │  Parser     │  │  (gh CLI)   │  │  (macOS)    │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     iTerm2 Python API                           │
│  - Session creation (tabs/panes)                                │
│  - Output polling                                               │
│  - Notifications (terminate, prompt, layout)                    │
└─────────────────────────────────────────────────────────────────┘
```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `textual` | ~2.x | TUI framework |
| `iterm2` | ~2.x | iTerm2 Python API |
| `dacite` | ~1.8 | JSON to dataclass conversion |
| `watchfiles` | ~0.21 | File watching for PLAN.md changes |
| `httpx` | ~0.27 | Health check HTTP requests |

### Optional

| Package | Purpose | Fallback |
|---------|---------|----------|
| `terminal-notifier` (CLI) | macOS notifications | Silent degradation |
| `gh` (CLI) | GitHub integration | GitHub panel hidden |

## License

MIT
