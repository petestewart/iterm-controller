# TUI Screens

## Overview

Textual-based screens that form the user interface. Each screen is a self-contained view with its own widgets and keybindings.

## Screen Hierarchy

```
MissionControlScreen (main)
├── ProjectListScreen
│   └── ProjectScreen (unified)
│       ├── CommitModal
│       ├── ReviewDetailModal
│       ├── TaskDetailModal
│       ├── EnvEditModal
│       └── ... other modals
├── NewProjectScreen
└── SettingsScreen

Modals (can appear from any screen):
├── QuitConfirmModal
└── GitHubActionsModal
```

## Mission Control Screen

The main dashboard showing live output from all active sessions across ALL projects.

```python
from textual.screen import Screen
from textual.widgets import Header, Footer, Static
from textual.containers import Container, Vertical, Horizontal

class MissionControlScreen(Screen):
    """Main mission control showing all active sessions across projects."""

    BINDINGS = [
        ("n", "new_session", "New Session"),
        ("k", "kill_session", "Kill Session"),
        ("enter", "open_project", "Open Project"),
        ("1", "focus_session_1", "Focus 1"),
        ("2", "focus_session_2", "Focus 2"),
        ("3", "focus_session_3", "Focus 3"),
        ("4", "focus_session_4", "Focus 4"),
        ("5", "focus_session_5", "Focus 5"),
        ("6", "focus_session_6", "Focus 6"),
        ("7", "focus_session_7", "Focus 7"),
        ("8", "focus_session_8", "Focus 8"),
        ("9", "focus_session_9", "Focus 9"),
        ("x", "expand_collapse", "Expand/Collapse"),
        ("p", "app.push_screen('project_list')", "Projects"),
        ("?", "show_help", "Help"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("MISSION CONTROL", id="title"),
            Static(id="session-count"),
            Vertical(id="session-cards"),
            id="main"
        )
        yield Footer()

    async def on_mount(self):
        """Load sessions when screen mounts."""
        await self.refresh_sessions()

    async def refresh_sessions(self):
        """Refresh session cards from state."""
        container = self.query_one("#session-cards", Vertical)
        container.remove_children()

        active_sessions = [s for s in self.app.state.sessions.values() if s.is_active]
        self.query_one("#session-count").update(f"{len(active_sessions)} active sessions")

        for i, session in enumerate(active_sessions, 1):
            card = SessionCard(session=session, index=i)
            container.mount(card)
```

### Mission Control Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  MISSION CONTROL                                           4 active sessions│
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─ 1. Project A ─────────────────────────────────────────────── WORKING ──┐│
│  │  Claude: Creating PLAN.md                                    00:03:42   ││
│  │  ───────────────────────────────────────────────────────────────────────││
│  │  > Analyzing the PRD structure...                                       ││
│  │  > Creating Phase 1: Project Setup                                      ││
│  │  > Adding task 1.1: Initialize repository█                              ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│  ┌─ 2. Project B ─────────────────────────────────────────────── WORKING ──┐│
│  │  Orchestrator: Phase 2 (Task 2.3 of 6)                       00:12:07   ││
│  │  Progress: ████████░░░░░░░░ 3/6 tasks                                   ││
│  │  ───────────────────────────────────────────────────────────────────────││
│  │  [2.3] Adding user authentication                                       ││
│  │  > Creating app/models/user.rb                                          ││
│  │  > Running rails db:migrate█                                            ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│  [1-9] Focus  [Enter] Open project  [n] New session  [?] Help  [p] Projects │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Project Screen

Unified view with all sections visible. Replaces the old Project Dashboard + Mode Screens.

```python
class ProjectScreen(Screen):
    """Unified project view with collapsible sections."""

    BINDINGS = [
        ("e", "edit_artifact", "Edit"),
        ("c", "commit", "Commit"),
        ("p", "push", "Push"),
        ("s", "run_server", "Server"),
        ("t", "run_tests", "Tests"),
        ("l", "run_lint", "Lint"),
        ("b", "run_build", "Build"),
        ("o", "run_orchestrator", "Orchestrator"),
        ("r", "review_task", "Review"),
        ("tab", "next_section", "Next Section"),
        ("shift+tab", "prev_section", "Prev Section"),
        ("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, project_id: str):
        super().__init__()
        self.project_id = project_id

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            # Project header with name and branch
            Horizontal(
                Static(id="project-name"),
                Static(id="branch-info"),
                id="project-header"
            ),
            # Main content grid
            Horizontal(
                # Left column
                Vertical(
                    PlanningSection(id="planning"),
                    TasksSection(id="tasks"),
                    id="left-column"
                ),
                # Right column
                Vertical(
                    DocsSection(id="docs"),
                    GitSection(id="git"),
                    EnvSection(id="env"),
                    id="right-column"
                ),
                id="content-grid"
            ),
            # Scripts toolbar
            ScriptToolbar(id="scripts"),
            # Active sessions panel
            SessionsPanel(id="sessions"),
            id="main"
        )
        yield Footer()

    async def on_mount(self):
        """Load project data when screen mounts."""
        project = self.app.state.projects.get(self.project_id)
        if project:
            self.query_one("#project-name").update(f"PROJECT: {project.name}")
            self.query_one("#branch-info").update(f"[branch: {project.branch}]")
```

### Project Screen Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  PROJECT: My App                                              [branch: main]│
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─ Planning ────────────┐  ┌─ Docs ─────────────────┐                      │
│  │ ○ PROBLEM.md          │  │ • docs/architecture.md │                      │
│  │ ● PRD.md        [e]   │  │ • docs/api-design.md   │                      │
│  │ ○ specs/              │  │ + Add doc...           │                      │
│  │ ● PLAN.md       [e]   │  └────────────────────────┘                      │
│  │ [c] Create missing    │                                                  │
│  └───────────────────────┘  ┌─ Git Status ───────────┐                      │
│                             │ M  src/auth.py         │                      │
│  ┌─ Tasks ──────────────────│ A  src/users.py        │                      │
│  │ ▼ Phase 1: Setup [2/3] │  │ [c] Commit  [p] Push   │                      │
│  │   ✓ 1.1 Create project │  └────────────────────────┘                      │
│  │   ✓ 1.2 Setup deps     │                                                  │
│  │   ○ 1.3 Configure DB   │  ┌─ Env Variables ───────┐                      │
│  │ ▼ Phase 2: Core [0/4]  │  │ DATABASE_URL: ...      │                      │
│  │   ⏳ 2.1 User model ←REVIEW│ API_KEY: ****          │                      │
│  │   ○ 2.2 Auth service   │  │ [e] Edit               │                      │
│  └────────────────────────┘  └────────────────────────┘                      │
│  ┌─ Scripts ────────────────────────────────────────────────────────────────┐│
│  │ [s] Server  [t] Tests  [l] Lint  [b] Build  [o] Orchestrator            ││
│  └──────────────────────────────────────────────────────────────────────────┘│
│  ┌─ Active Sessions ────────────────────────────────────────────────────────┐│
│  │ 1. Claude: Task 2.1    │ > Creating User model...                        ││
│  │ 2. Tests: pytest       │ > test_auth.py::test_login PASSED               ││
│  └──────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
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

### SessionCard

Shows a single session with header and live output log.

```python
class SessionCard(Static):
    """Card displaying a session with header and live output."""

    def __init__(self, session: ManagedSession, index: int, **kwargs):
        super().__init__(**kwargs)
        self.session = session
        self.index = index

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Static(f"{self.index}. {self.session.project_name}", classes="card-title"),
            Static(self.session.attention_state.value.upper(), classes="card-status"),
            classes="card-header"
        )
        yield Static(self.get_session_info(), classes="card-info")
        if self.is_orchestrator:
            yield OrchestratorProgress(session=self.session)
        yield Static("─" * 70, classes="card-separator")
        yield OutputLog(session=self.session, lines=3)

    def get_session_info(self) -> str:
        """Get session type and current activity."""
        elapsed = format_duration(self.session.elapsed_time)
        return f"{self.session.template_id}: {self.session.current_activity}  {elapsed}"

    @property
    def is_orchestrator(self) -> bool:
        return self.session.template_id == "orchestrator"
```

### OutputLog

Scrollable output display showing last N lines with ANSI color support.

```python
class OutputLog(Static):
    """Displays scrollable output with ANSI color support."""

    def __init__(self, session: ManagedSession, lines: int = 5, **kwargs):
        super().__init__(**kwargs)
        self.session = session
        self.max_lines = lines

    def render(self) -> str:
        """Render the last N lines of output."""
        output_lines = self.session.output_buffer.get_last_lines(self.max_lines)
        return "\n".join(f"> {line}" for line in output_lines)

    async def on_mount(self):
        """Subscribe to output updates."""
        self.session.on_output += self.refresh
```

### OrchestratorProgress

Progress bar for orchestrator sessions showing completed/total tasks.

```python
class OrchestratorProgress(Static):
    """Progress bar for orchestrator sessions."""

    def __init__(self, session: ManagedSession, **kwargs):
        super().__init__(**kwargs)
        self.session = session

    def render(self) -> str:
        """Render progress bar with task counts."""
        completed = self.session.orchestrator_state.completed_tasks
        total = self.session.orchestrator_state.total_tasks
        phase = self.session.orchestrator_state.current_phase

        # Calculate progress bar
        if total > 0:
            filled = int((completed / total) * 16)
            bar = "█" * filled + "░" * (16 - filled)
        else:
            bar = "░" * 16

        return f"Progress: {bar} {completed}/{total} tasks"
```

### GitSection

Git status display with staged/unstaged/untracked files and action buttons.

```python
class GitSection(Static):
    """Git status section with file list and actions."""

    def __init__(self, project: Project, **kwargs):
        super().__init__(**kwargs)
        self.project = project

    def compose(self) -> ComposeResult:
        yield Static("─ Git Status ─", classes="section-header")
        yield Vertical(id="git-files")
        yield Horizontal(
            Button("[c] Commit", id="commit-btn"),
            Button("[p] Push", id="push-btn"),
            classes="git-actions"
        )

    async def refresh_status(self):
        """Refresh git status from project."""
        container = self.query_one("#git-files", Vertical)
        container.remove_children()

        status = await self.project.get_git_status()
        for file_status in status.files:
            indicator = self.get_status_indicator(file_status.status)
            container.mount(Static(f"{indicator}  {file_status.path}"))

    def get_status_indicator(self, status: str) -> str:
        """Get status indicator character."""
        return {
            "modified": "M",
            "added": "A",
            "deleted": "D",
            "untracked": "?",
            "renamed": "R",
        }.get(status, " ")
```

### ScriptToolbar

Row of script buttons with keybindings from project config.

```python
class ScriptToolbar(Static):
    """Toolbar with script buttons from project config."""

    DEFAULT_SCRIPTS = [
        ("s", "server", "Server"),
        ("t", "tests", "Tests"),
        ("l", "lint", "Lint"),
        ("b", "build", "Build"),
        ("o", "orchestrator", "Orchestrator"),
    ]

    def __init__(self, project: Project = None, **kwargs):
        super().__init__(**kwargs)
        self.project = project

    def compose(self) -> ComposeResult:
        yield Static("─ Scripts ─", classes="section-header")
        yield Horizontal(
            *[
                Button(f"[{key}] {label}", id=f"script-{script_id}")
                for key, script_id, label in self.get_scripts()
            ],
            classes="script-buttons"
        )

    def get_scripts(self) -> list[tuple[str, str, str]]:
        """Get scripts from project config or use defaults."""
        if self.project and self.project.config.scripts:
            return [
                (s.keybinding, s.id, s.label)
                for s in self.project.config.scripts
            ]
        return self.DEFAULT_SCRIPTS
```

### TaskRow

Task display with review status indicator.

```python
class TaskRow(Static):
    """Single task row with status and review indicators."""

    def __init__(self, task: Task, **kwargs):
        super().__init__(**kwargs)
        self.task = task

    def render(self) -> str:
        """Render task with appropriate status icon."""
        icon = self.get_status_icon()
        review_indicator = self.get_review_indicator()

        if self.task.is_blocked:
            blockers = ", ".join(self.task.depends)
            return f"  [dim]⊘ {self.task.id} {self.task.title}  blocked by {blockers}[/dim]"

        return f"  {icon} {self.task.id} {self.task.title}{review_indicator}"

    def get_status_icon(self) -> str:
        """Get status icon based on task state."""
        if self.task.status == TaskStatus.AWAITING_REVIEW:
            return "⏳"
        return {
            TaskStatus.PENDING: "○",
            TaskStatus.IN_PROGRESS: "●",
            TaskStatus.COMPLETE: "✓",
            TaskStatus.SKIPPED: "⊖",
            TaskStatus.BLOCKED: "⊘",
        }.get(self.task.status, "○")

    def get_review_indicator(self) -> str:
        """Get review indicator if task is awaiting review."""
        if self.task.status == TaskStatus.AWAITING_REVIEW:
            return " ←REVIEW"
        return ""
```

### MiniSessionCard

Compact session display for the Sessions Panel in Project Screen.

```python
class MiniSessionCard(Static):
    """Compact session card for project screen sessions panel."""

    def __init__(self, session: ManagedSession, index: int, **kwargs):
        super().__init__(**kwargs)
        self.session = session
        self.index = index

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Static(f"{self.index}. {self.session.template_id}: {self.session.current_activity}"),
            Static("│", classes="divider"),
            Static(self.get_last_output(), classes="mini-output"),
            classes="mini-session"
        )

    def get_last_output(self) -> str:
        """Get last line of output."""
        lines = self.session.output_buffer.get_last_lines(1)
        if lines:
            return f"> {lines[0][:50]}..."
        return ""
```

### PlanningSection

Section showing planning artifacts with existence status.

```python
class PlanningSection(Static):
    """Planning artifacts section with existence indicators."""

    ARTIFACTS = [
        ("PROBLEM.md", "problem"),
        ("PRD.md", "prd"),
        ("specs/", "specs"),
        ("PLAN.md", "plan"),
    ]

    def __init__(self, project: Project, **kwargs):
        super().__init__(**kwargs)
        self.project = project

    def compose(self) -> ComposeResult:
        yield Static("─ Planning ─", classes="section-header")
        yield Vertical(id="artifacts")
        yield Button("[c] Create missing", id="create-missing-btn")

    async def refresh_artifacts(self):
        """Refresh artifact list with existence status."""
        container = self.query_one("#artifacts", Vertical)
        container.remove_children()

        for name, artifact_id in self.ARTIFACTS:
            exists = await self.project.artifact_exists(artifact_id)
            icon = "●" if exists else "○"
            edit_btn = " [e]" if exists else ""
            container.mount(Static(f"{icon} {name}{edit_btn}"))
```

### DocsSection

Section for project documentation files.

```python
class DocsSection(Static):
    """Documentation section with file list."""

    def __init__(self, project: Project, **kwargs):
        super().__init__(**kwargs)
        self.project = project

    def compose(self) -> ComposeResult:
        yield Static("─ Docs ─", classes="section-header")
        yield Vertical(id="doc-list")
        yield Button("+ Add doc...", id="add-doc-btn")

    async def refresh_docs(self):
        """Refresh documentation file list."""
        container = self.query_one("#doc-list", Vertical)
        container.remove_children()

        for doc in self.project.docs:
            container.mount(Static(f"• {doc.path}"))
```

### EnvSection

Environment variables section with masked values.

```python
class EnvSection(Static):
    """Environment variables section with edit button."""

    def __init__(self, project: Project, **kwargs):
        super().__init__(**kwargs)
        self.project = project

    def compose(self) -> ComposeResult:
        yield Static("─ Env Variables ─", classes="section-header")
        yield Vertical(id="env-list")
        yield Button("[e] Edit", id="edit-env-btn")

    async def refresh_env(self):
        """Refresh environment variable list."""
        container = self.query_one("#env-list", Vertical)
        container.remove_children()

        for key, value in self.project.env_vars.items():
            # Mask sensitive values
            display_value = "****" if self.is_sensitive(key) else value[:20] + "..."
            container.mount(Static(f"{key}: {display_value}"))

    def is_sensitive(self, key: str) -> bool:
        """Check if key is sensitive and should be masked."""
        sensitive_patterns = ["KEY", "SECRET", "PASSWORD", "TOKEN"]
        return any(pattern in key.upper() for pattern in sensitive_patterns)
```

### TasksSection

Collapsible task list organized by phases.

```python
class TasksSection(Static):
    """Tasks section with collapsible phases."""

    def __init__(self, project: Project, **kwargs):
        super().__init__(**kwargs)
        self.project = project
        self.collapsed_phases: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Static("─ Tasks ─", classes="section-header")
        yield Vertical(id="task-list")

    async def refresh_tasks(self):
        """Refresh task list organized by phases."""
        container = self.query_one("#task-list", Vertical)
        container.remove_children()

        plan = self.project.plan
        if not plan:
            container.mount(Static("[dim]No plan loaded[/dim]"))
            return

        for phase in plan.phases:
            completed = sum(1 for t in phase.tasks if t.status == TaskStatus.COMPLETE)
            total = len(phase.tasks)

            # Phase header with collapse indicator
            collapse_icon = "▶" if phase.id in self.collapsed_phases else "▼"
            container.mount(
                Static(f"{collapse_icon} {phase.name} [{completed}/{total}]",
                       classes="phase-header",
                       id=f"phase-{phase.id}")
            )

            # Tasks (if not collapsed)
            if phase.id not in self.collapsed_phases:
                for task in phase.tasks:
                    container.mount(TaskRow(task=task))

    def toggle_phase(self, phase_id: str):
        """Toggle phase collapse state."""
        if phase_id in self.collapsed_phases:
            self.collapsed_phases.remove(phase_id)
        else:
            self.collapsed_phases.add(phase_id)
        self.refresh_tasks()
```

### SessionsPanel

Panel showing active sessions for the current project.

```python
class SessionsPanel(Static):
    """Active sessions panel for project screen."""

    def __init__(self, project: Project, **kwargs):
        super().__init__(**kwargs)
        self.project = project

    def compose(self) -> ComposeResult:
        yield Static("─ Active Sessions ─", classes="section-header")
        yield Vertical(id="session-list")

    async def refresh_sessions(self):
        """Refresh session list for this project."""
        container = self.query_one("#session-list", Vertical)
        container.remove_children()

        sessions = [s for s in self.project.sessions if s.is_active]
        if not sessions:
            container.mount(Static("[dim]No active sessions[/dim]"))
            return

        for i, session in enumerate(sessions, 1):
            container.mount(MiniSessionCard(session=session, index=i))
```

## Modals

### CommitModal

Modal for staging and committing changes.

```python
class CommitModal(ModalScreen):
    """Modal for committing git changes."""

    BINDINGS = [
        ("escape", "dismiss", "Cancel"),
        ("ctrl+enter", "commit", "Commit"),
    ]

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Commit Changes", classes="modal-title"),
            Vertical(id="staged-files"),
            Input(id="commit-message", placeholder="Commit message..."),
            Horizontal(
                Button("Cancel", variant="default", id="cancel"),
                Button("Commit", variant="primary", id="commit"),
            ),
            classes="modal-content"
        )
```

### ReviewDetailModal

Modal for reviewing task completion.

```python
class ReviewDetailModal(ModalScreen):
    """Modal for reviewing completed task."""

    def __init__(self, task: Task, **kwargs):
        super().__init__(**kwargs)
        self.task = task

    def compose(self) -> ComposeResult:
        yield Container(
            Static(f"Review: {self.task.id} {self.task.title}", classes="modal-title"),
            Static(self.task.description, classes="task-description"),
            Vertical(id="changes-list"),
            Horizontal(
                Button("Reject", variant="error", id="reject"),
                Button("Request Changes", variant="warning", id="request-changes"),
                Button("Approve", variant="success", id="approve"),
            ),
            classes="modal-content"
        )
```

### TaskDetailModal

Modal showing full task details.

```python
class TaskDetailModal(ModalScreen):
    """Modal showing task details."""

    def __init__(self, task: Task, **kwargs):
        super().__init__(**kwargs)
        self.task = task

    def compose(self) -> ComposeResult:
        yield Container(
            Static(f"Task: {self.task.id}", classes="modal-title"),
            Static(self.task.title, classes="task-title"),
            Static(self.task.description, classes="task-description"),
            Static(f"Status: {self.task.status.value}", classes="task-status"),
            Static(f"Dependencies: {', '.join(self.task.depends) or 'None'}", classes="task-deps"),
            Button("Close", variant="default", id="close"),
            classes="modal-content"
        )
```

### EnvEditModal

Modal for editing environment variables.

```python
class EnvEditModal(ModalScreen):
    """Modal for editing environment variables."""

    def __init__(self, project: Project, **kwargs):
        super().__init__(**kwargs)
        self.project = project

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Edit Environment Variables", classes="modal-title"),
            TextArea(id="env-editor"),
            Horizontal(
                Button("Cancel", variant="default", id="cancel"),
                Button("Save", variant="primary", id="save"),
            ),
            classes="modal-content"
        )

    async def on_mount(self):
        """Load current env vars into editor."""
        editor = self.query_one("#env-editor", TextArea)
        env_content = "\n".join(
            f"{key}={value}"
            for key, value in self.project.env_vars.items()
        )
        editor.load_text(env_content)
```
