# TUI Screens

## Overview

Textual-based screens that form the user interface. Each screen is a self-contained view with its own widgets and keybindings.

## Screen Hierarchy

```
ControlRoomScreen (main)
├── ProjectListScreen
│   └── ProjectDashboardScreen
│       ├── PlanModeScreen          # Workflow mode
│       │   └── ArtifactPreviewModal
│       ├── DocsModeScreen          # Workflow mode
│       │   ├── AddDocumentModal
│       │   └── DocPreviewModal
│       ├── WorkModeScreen          # Workflow mode
│       │   └── DependencyChainModal
│       ├── TestModeScreen          # Workflow mode
│       │   └── TestStepDetailModal
│       ├── ScriptPickerModal
│       ├── DocsPickerModal
│       └── PlanConflictModal
├── NewProjectScreen
└── SettingsScreen

Modals (can appear from any screen):
├── QuitConfirmModal
└── GitHubActionsModal
```

## Workflow Modes

From Project Dashboard, users can enter focused workflow modes:

| Key | Mode | Spec |
|-----|------|------|
| `1` | Plan Mode | [plan-mode.md](./plan-mode.md) |
| `2` | Docs Mode | [docs-mode.md](./docs-mode.md) |
| `3` | Work Mode | [work-mode.md](./work-mode.md) |
| `4` | Test Mode | [test-mode.md](./test-mode.md) |

See [workflow-modes.md](./workflow-modes.md) for mode system overview.

## Control Room Screen

The main dashboard showing all sessions across all projects.

```python
from textual.screen import Screen
from textual.widgets import Header, Footer, Static
from textual.containers import Container, Vertical, Horizontal

class ControlRoomScreen(Screen):
    """Main control room showing all active sessions."""

    BINDINGS = [
        ("n", "new_session", "New Session"),
        ("k", "kill_session", "Kill Session"),
        ("enter", "focus_session", "Focus"),
        ("p", "app.push_screen('project_list')", "Projects"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            SessionListWidget(id="sessions"),
            Horizontal(
                WorkflowBarWidget(id="workflow"),
                HealthStatusWidget(id="health"),
                id="status-bar"
            ),
            id="main"
        )
        yield Footer()

    async def on_mount(self):
        """Load sessions when screen mounts."""
        await self.refresh_sessions()

    async def refresh_sessions(self):
        """Refresh session list from state."""
        widget = self.query_one("#sessions", SessionListWidget)
        await widget.refresh(self.app.state.sessions.values())
```

### Control Room Layout

```
┌────────────────────────────────────────────────────────────────┐
│ iTerm Controller                                    [?] Help   │
├────────────────────────────────────────────────────────────────┤
│ Sessions                                                       │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ ● my-project/API Server         Working   [a]             │ │
│ │ ⧖ my-project/Claude             Waiting   [c]             │ │
│ │ ○ my-project/Tests              Idle      [t]             │ │
│ │ ● other-project/Dev Server      Working   [d]             │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                │
│ ┌─────────────────────────────┬──────────────────────────────┐ │
│ │ Planning → Execute → Review │  API ● Web ● DB ○            │ │
│ └─────────────────────────────┴──────────────────────────────┘ │
├────────────────────────────────────────────────────────────────┤
│ n New  k Kill  Enter Focus  p Projects  q Quit                 │
└────────────────────────────────────────────────────────────────┘
```

## Project Dashboard Screen

Single project view with tasks, sessions, and GitHub panel.

```python
class ProjectDashboardScreen(Screen):
    """Dashboard for a single project."""

    BINDINGS = [
        ("t", "toggle_task", "Toggle Task"),
        ("s", "spawn_session", "Spawn"),
        ("r", "run_script", "Run Script"),
        ("d", "open_docs", "Docs"),
        ("g", "github_actions", "GitHub"),
        ("1", "enter_mode('plan')", "Plan Mode"),
        ("2", "enter_mode('docs')", "Docs Mode"),
        ("3", "enter_mode('work')", "Work Mode"),
        ("4", "enter_mode('test')", "Test Mode"),
        ("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, project_id: str):
        super().__init__()
        self.project_id = project_id

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(
                Vertical(
                    TaskListWidget(id="tasks"),
                    SessionListWidget(id="sessions"),
                    id="left-panel"
                ),
                Vertical(
                    GitHubPanelWidget(id="github"),
                    HealthStatusWidget(id="health"),
                    id="right-panel"
                ),
            ),
            WorkflowBarWidget(id="workflow"),
            id="main"
        )
        yield Footer()
```

### Project Dashboard Layout

```
┌────────────────────────────────────────────────────────────────┐
│ my-project                                         [?] Help    │
├────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────┬──────────────────────────────┐ │
│ │ Tasks              Progress │ GitHub                       │ │
│ │ ▼ Phase 1           3/4     │ Branch: feature/auth         │ │
│ │   ✓ 1.1 Setup          Done │ ↑2 ↓0 from main              │ │
│ │   ✓ 1.2 Models         Done │                              │ │
│ │   ● 1.3 API      In Progress│ PR #42: Add auth             │ │
│ │   ○ 1.4 Tests       Pending │ ● Checks passing             │ │
│ │ ▼ Phase 2           0/3     │ 2 reviews pending            │ │
│ │   ⊘ 2.1 Auth      blocked   │                              │ │
│ │   ⊘ 2.2 Login     blocked   │                              │ │
│ ├─────────────────────────────┼──────────────────────────────┤ │
│ │ Sessions                    │ Health                       │ │
│ │ ● API Server       Working  │ API ● Web ● DB ○             │ │
│ │ ⧖ Claude           Waiting  │                              │ │
│ │ ○ Tests            Idle     │                              │ │
│ └─────────────────────────────┴──────────────────────────────┘ │
│                                                                │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ Planning ✓ → [Execute] → Review → PR → Done                │ │
│ └────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────┤
│ t Toggle  s Spawn  r Script  d Docs  g GitHub  1-4 Modes  Esc  │
└────────────────────────────────────────────────────────────────┘
```

## Project List Screen

Browse and select projects.

```python
class ProjectListScreen(Screen):
    """Browse and select projects."""

    BINDINGS = [
        ("enter", "open_project", "Open"),
        ("n", "new_project", "New Project"),
        ("d", "delete_project", "Delete"),
        ("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            DataTable(id="project-table"),
            id="main"
        )
        yield Footer()

    async def on_mount(self):
        table = self.query_one("#project-table", DataTable)
        table.add_columns("Name", "Path", "Sessions", "Status")

        for project in self.app.state.projects.values():
            table.add_row(
                project.name,
                project.path,
                str(len(project.sessions)),
                "Open" if project.is_open else "Closed"
            )
```

## New Project Screen

Create project from template.

```python
class NewProjectScreen(Screen):
    """Create a new project from template."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Cancel"),
        ("ctrl+s", "save", "Create"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Vertical(
                Label("Select Template"),
                Select(id="template-select", options=[]),
                Label("Project Name"),
                Input(id="name-input", placeholder="my-project"),
                Label("Path"),
                Input(id="path-input", placeholder="/path/to/project"),
                Label("Git Branch"),
                Input(id="branch-input", placeholder="feature/new-thing"),
                Horizontal(
                    Button("Cancel", variant="default", id="cancel"),
                    Button("Create Project", variant="primary", id="create"),
                ),
                id="form"
            ),
            id="main"
        )
        yield Footer()

    async def action_save(self):
        """Create the project."""
        template_id = self.query_one("#template-select", Select).value
        name = self.query_one("#name-input", Input).value
        path = self.query_one("#path-input", Input).value
        branch = self.query_one("#branch-input", Input).value

        # Validate
        if not name or not path:
            self.notify("Name and path are required", severity="error")
            return

        # Create project
        template = self.app.state.config.templates.get(template_id)
        if template and template.setup_script:
            # Run setup script
            await self.run_setup_script(template, path)

        # Spawn initial sessions
        if template and template.initial_sessions:
            for session_id in template.initial_sessions:
                await self.app.spawn_session(session_id)

        self.app.pop_screen()
```

## Settings Screen

Configure application defaults.

```python
class SettingsScreen(Screen):
    """Application settings."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("ctrl+s", "save", "Save"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Vertical(
                Label("Default IDE"),
                Select(
                    id="ide-select",
                    options=[("vscode", "VS Code"), ("cursor", "Cursor"), ("vim", "Vim")]
                ),
                Label("Default Shell"),
                Select(
                    id="shell-select",
                    options=[("zsh", "zsh"), ("bash", "bash"), ("fish", "fish")]
                ),
                Label("Polling Interval (ms)"),
                Input(id="polling-input", value="500"),
                Checkbox("Enable Notifications", id="notify-checkbox"),
                Checkbox("Auto-advance Workflow", id="auto-advance-checkbox"),
                Horizontal(
                    Button("Cancel", variant="default", id="cancel"),
                    Button("Save Settings", variant="primary", id="save"),
                ),
                id="form"
            ),
            id="main"
        )
        yield Footer()
```

## Widgets

### Session List Widget

```python
class SessionListWidget(Static):
    """Displays list of sessions with status indicators."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sessions: list[ManagedSession] = []

    async def refresh(self, sessions: Iterable[ManagedSession]):
        """Update displayed sessions."""
        self.sessions = list(sessions)
        self.update(self.render_sessions())

    def render_sessions(self) -> str:
        lines = []
        for session in self.sessions:
            icon = self.get_status_icon(session.attention_state)
            status = session.attention_state.value.title()
            lines.append(f"{icon} {session.template_id:<20} {status}")
        return "\n".join(lines) or "No active sessions"

    def get_status_icon(self, state: AttentionState) -> str:
        return {
            AttentionState.WAITING: "⧖",
            AttentionState.WORKING: "●",
            AttentionState.IDLE: "○",
        }[state]
```

### Task List Widget

```python
class TaskListWidget(Static):
    """Displays tasks with phases and dependencies."""

    def render_task(self, task: Task) -> str:
        icon = self.get_status_icon(task.status)

        if task.is_blocked:
            blockers = ", ".join(task.depends)
            return f"  [dim]⊘ {task.id} {task.title}  blocked by {blockers}[/dim]"

        return f"  {icon} {task.id} {task.title}"

    def get_status_icon(self, status: TaskStatus) -> str:
        return {
            TaskStatus.PENDING: "○",
            TaskStatus.IN_PROGRESS: "●",
            TaskStatus.COMPLETE: "✓",
            TaskStatus.SKIPPED: "⊖",
            TaskStatus.BLOCKED: "⊘",
        }[status]
```

### Workflow Bar Widget

```python
class WorkflowBarWidget(Static):
    """Displays workflow stage progression."""

    STAGES = ["Planning", "Execute", "Review", "PR", "Done"]

    def render_bar(self, current: WorkflowStage) -> str:
        parts = []
        for stage_name in self.STAGES:
            stage = WorkflowStage[stage_name.upper()]
            if stage == current:
                parts.append(f"[bold][{stage_name}][/bold]")
            elif stage.value < current.value:
                parts.append(f"[green]{stage_name} ✓[/green]")
            else:
                parts.append(f"[dim]{stage_name}[/dim]")
        return " → ".join(parts)
```

### Health Status Widget

```python
class HealthStatusWidget(Static):
    """Displays health check status indicators."""

    def render_health(self, checks: list[tuple[str, HealthStatus]]) -> str:
        parts = []
        for name, status in checks:
            icon = "●" if status == HealthStatus.HEALTHY else "✗"
            color = "green" if status == HealthStatus.HEALTHY else "red"
            parts.append(f"[{color}]{name} {icon}[/{color}]")
        return " ".join(parts)
```

### GitHub Panel Widget

```python
class GitHubPanelWidget(Static):
    """Displays GitHub status and PR information."""

    def render(self) -> str:
        status = self.app.state.github_status

        if not status or not status.available:
            if status and status.error_message:
                return f"[dim]GitHub: {status.error_message}[/dim]"
            return ""

        lines = [
            f"Branch: {status.current_branch}",
            f"↑{status.ahead} ↓{status.behind} from {status.default_branch}"
        ]

        if status.pr:
            lines.append("")
            lines.append(f"PR #{status.pr.number}: {status.pr.title}")

            if status.pr.checks_passing:
                lines.append("[green]● Checks passing[/green]")
            elif status.pr.checks_passing is False:
                lines.append("[red]✗ Checks failing[/red]")

            if status.pr.reviews_pending:
                lines.append(f"{status.pr.reviews_pending} reviews pending")

        return "\n".join(lines)
```
