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

    # === Runtime state (not persisted) ===

    # Workflow tracking
    workflow_state: WorkflowState = field(default_factory=WorkflowState)

    # Parsed plan from PLAN.md
    plan: Plan | None = None

    # GitHub integration status
    github_status: GitHubStatus | None = None
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

    # Attention tracking (for Control Room)
    attention_state: AttentionState = AttentionState.IDLE
    attention_state_since: datetime | None = None  # When entered current state
    waiting_prompt: str | None = None              # The prompt/question if WAITING
    last_activity: datetime | None = None          # Last output timestamp

    # Current task (if linked to PLAN.md)
    current_task_id: str | None = None             # e.g., "2.1"

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

class AttentionState(Enum):
    """Session state from Control Room perspective (needs user attention?)."""
    WAITING = "waiting"      # Needs user input (highest priority)
    WORKING = "working"      # Actively producing output
    IDLE = "idle"            # At prompt, not doing anything

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

Project-level settings and context.

```python
@dataclass
class ProjectConfig:
    # === Documentation ===
    docs: ProjectDocs = field(default_factory=ProjectDocs)

    # === Scripts (named commands for dev workflows) ===
    scripts: dict[str, Script] = field(default_factory=dict)

    # === Environment ===
    env: EnvConfig = field(default_factory=EnvConfig)

    # === Version Control ===
    git: GitConfig | None = None

    # === References (additional docs, links, resources) ===
    references: list[Reference] = field(default_factory=list)

    # === External Tracking ===
    external_ticket: ExternalTicket | None = None

    # === Classification ===
    project_type: ProjectType = ProjectType.MISC

    # === IDE ===
    ide: IDE = IDE.VSCODE              # Default editor for opening files

    # === Ports ===
    ports: list[PortConfig] = field(default_factory=list)

    # === Health Checks ===
    health_checks: list[HealthCheck] = field(default_factory=list)

    # === Behavior ===
    close_sessions_on_project_close: bool = True
    confirm_before_close: bool = True

    # === Display ===
    tab_prefix: str = ""       # Prefix for tab names (e.g., "[proj] ")

    # === Orchestration ===
    startup_sequence: list[str] = field(default_factory=list)  # Template IDs in order
    shutdown_sequence: list[str] = field(default_factory=list)
```

### ProjectDocs

Paths to key project documentation files with state tracking.

```python
@dataclass
class ProjectDocs:
    prd: DocRef | None = None              # Product requirements doc
    problem_statement: DocRef | None = None # Problem definition
    plan: DocRef | None = None             # Implementation plan (PLAN.md)
    specs_dir: str | None = None           # Directory containing spec files
    specs: list[str] = field(default_factory=list)  # Individual spec file paths
    qa_test_plan: DocRef | None = None     # QA/test plan document

    # Auto-discovery settings
    auto_discover_specs: bool = True          # Scan specs_dir for spec files
    spec_patterns: list[str] = field(        # Glob patterns for spec discovery
        default_factory=lambda: ["*.spec.md", "*.spec.txt", "SPEC_*.md"]
    )

    def get_all_specs(self, project_path: str) -> list[str]:
        """Returns specs list + auto-discovered specs from specs_dir."""
        all_specs = list(self.specs)
        if self.auto_discover_specs and self.specs_dir:
            # Implementation would glob for spec_patterns in specs_dir
            pass
        return all_specs

@dataclass
class DocRef:
    """Reference to a document with state tracking."""
    path: str                            # File path (relative to project root)
    state: DocState = DocState.EXISTS    # Current state

class DocState(Enum):
    MISSING = "missing"       # File doesn't exist yet
    EXISTS = "exists"         # File is present
    COMPLETE = "complete"     # Manually marked as finished
    UNNEEDED = "unneeded"     # Explicitly skipped for this project
```

### WorkflowStage

Tracks the current stage in the project development lifecycle.

```python
class WorkflowStage(Enum):
    PLANNING = "planning"     # Defining problem, PRD, specs, plan
    EXECUTE = "execute"       # Working on tasks from the plan
    REVIEW = "review"         # Code review phase
    PR = "pr"                 # Pull request created/in progress
    DONE = "done"             # PR merged, work complete

@dataclass
class WorkflowState:
    """Runtime state for workflow progression (not persisted)."""
    current_stage: WorkflowStage = WorkflowStage.PLANNING

    # Inferred from project state
    planning_complete: bool = False
    all_tasks_complete: bool = False
    pr_exists: bool = False
    pr_merged: bool = False

    def infer_stage(self) -> WorkflowStage:
        """Determine current stage based on project state."""
        if self.pr_merged:
            return WorkflowStage.DONE
        if self.pr_exists:
            return WorkflowStage.PR
        if self.all_tasks_complete:
            return WorkflowStage.REVIEW
        if self.planning_complete:
            return WorkflowStage.EXECUTE
        return WorkflowStage.PLANNING
```

### Plan and Tasks

Structures for parsing and tracking PLAN.md content.

```python
class TaskStatus(Enum):
    NOT_IMPLEMENTED = "Not Yet Implemented"
    IN_PROGRESS = "In Progress"
    COMPLETE = "Complete"
    BLOCKED = "Blocked"
    SKIPPED = "Skipped"

@dataclass
class Task:
    """A single task from PLAN.md."""
    id: str                          # Task ID (e.g., "1.1", "2.3")
    title: str                       # Task title
    description: str                 # Full task description (markdown)
    status: TaskStatus = TaskStatus.NOT_IMPLEMENTED

    # Metadata from PLAN.md
    spec_ref: str | None = None      # Reference to spec file (e.g., "specs/auth.md#login")
    depends: list[str] = field(default_factory=list)  # Task IDs this depends on
    session_name: str | None = None  # Which session is working on this (if in progress)

    # Runtime (not in PLAN.md)
    phase_id: str | None = None      # Which phase this belongs to
    is_blocked: bool = False         # Computed from dependencies

@dataclass
class Phase:
    """A phase/section from PLAN.md containing tasks."""
    id: str                          # Phase ID (e.g., "1", "2")
    title: str                       # Phase title (e.g., "Setup", "Core Features")
    tasks: list[Task] = field(default_factory=list)

    # UI state (not persisted)
    is_collapsed: bool = False

    @property
    def progress(self) -> tuple[int, int]:
        """Returns (completed, total) task count."""
        completed = sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETE)
        return (completed, len(self.tasks))

    @property
    def is_complete(self) -> bool:
        """True if all tasks in phase are complete."""
        return all(t.status == TaskStatus.COMPLETE for t in self.tasks)

@dataclass
class Plan:
    """Parsed representation of PLAN.md."""
    phases: list[Phase] = field(default_factory=list)
    flat_tasks: list[Task] = field(default_factory=list)  # Tasks without phases

    # Source tracking
    file_path: str | None = None
    last_parsed: datetime | None = None

    @property
    def has_phases(self) -> bool:
        """True if plan uses phase structure."""
        return len(self.phases) > 0

    @property
    def all_tasks(self) -> list[Task]:
        """All tasks, whether in phases or flat."""
        if self.has_phases:
            return [t for p in self.phases for t in p.tasks]
        return self.flat_tasks

    @property
    def progress(self) -> tuple[int, int]:
        """Returns (completed, total) across all tasks."""
        tasks = self.all_tasks
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETE)
        return (completed, len(tasks))
```

### GitHubStatus

Runtime state for GitHub integration.

```python
class PRState(Enum):
    NONE = "none"             # No PR exists
    DRAFT = "draft"           # PR is in draft
    OPEN = "open"             # PR is open for review
    MERGED = "merged"         # PR has been merged
    CLOSED = "closed"         # PR was closed without merging

class ReviewState(Enum):
    NONE = "none"             # No reviews yet
    PENDING = "pending"       # Reviews requested but not complete
    APPROVED = "approved"     # All reviewers approved
    CHANGES_REQUESTED = "changes_requested"  # Changes requested

@dataclass
class GitHubStatus:
    """Runtime state for GitHub PR/branch status (not persisted)."""
    # Branch sync
    is_synced: bool = True
    commits_ahead: int = 0
    commits_behind: int = 0

    # PR info
    pr_state: PRState = PRState.NONE
    pr_number: int | None = None
    pr_url: str | None = None
    pr_title: str | None = None

    # Review status
    review_state: ReviewState = ReviewState.NONE
    unresolved_comments: int = 0

    # Timestamps
    last_checked: datetime | None = None
```

### Script

A named command with optional context for monorepo support.

```python
@dataclass
class Script:
    command: str                         # The command to run
    working_dir: str | None = None       # Relative path from project root (for monorepos)
    description: str | None = None       # Human-readable description for UI
    env: dict[str, str] = field(default_factory=dict)  # Script-specific env overrides
    category: ScriptCategory = ScriptCategory.OTHER

class ScriptCategory(Enum):
    DEV = "dev"              # Development servers, watchers
    TEST = "test"            # Test runners
    BUILD = "build"          # Build/compile commands
    LINT = "lint"            # Linting, formatting
    DEPLOY = "deploy"        # Deployment scripts
    OTHER = "other"
```

**Monorepo example:**
```python
scripts = {
    "start_api": Script(
        command="npm run dev",
        working_dir="packages/api",
        description="Start API server",
        category=ScriptCategory.DEV
    ),
    "start_web": Script(
        command="npm run dev",
        working_dir="packages/web",
        description="Start web client",
        category=ScriptCategory.DEV
    ),
    "test_all": Script(
        command="npm test",
        working_dir=None,  # Run from project root
        category=ScriptCategory.TEST
    )
}
```

### EnvConfig

Environment variable configuration with parsing and display settings.

```python
@dataclass
class EnvConfig:
    # Files to parse
    files: list[str] = field(default_factory=list)  # e.g., [".env", ".env.local"]

    # Inline overrides (take precedence over file values)
    overrides: dict[str, str] = field(default_factory=dict)

    # UI Display settings
    show_in_ui: list[str] = field(default_factory=list)  # Var names to display (empty = show all)
    hide_in_ui: list[str] = field(default_factory=list)  # Var names to hide (takes precedence)
    sensitive_patterns: list[str] = field(              # Patterns to mask values (e.g., "*_KEY", "*_SECRET")
        default_factory=lambda: ["*_KEY", "*_SECRET", "*_TOKEN", "*_PASSWORD", "*API*"]
    )

    # Runtime (not persisted) - populated by parsing files
    _parsed_vars: dict[str, EnvVar] = field(default_factory=dict, repr=False)

@dataclass
class EnvVar:
    name: str
    value: str
    source: str                      # Which file it came from (or "override")
    is_sensitive: bool = False       # Matched a sensitive_pattern

    def display_value(self) -> str:
        """Returns masked value if sensitive, otherwise actual value."""
        if self.is_sensitive:
            return "••••••••"
        return self.value
```

**Usage:**
- `files` lists .env files to parse (in order, later files override earlier)
- `show_in_ui` filters which vars appear in the dashboard (empty means all)
- `hide_in_ui` excludes vars even if in show_in_ui
- `sensitive_patterns` uses glob-style matching to auto-mask values like API keys

### GitConfig

Version control context for the project.

```python
@dataclass
class GitConfig:
    branch: str | None = None        # Working branch (e.g., "feature/user-auth")
    remote: str = "origin"           # Remote name
    repo_url: str | None = None      # Repository URL (for reference/linking)
    base_branch: str = "main"        # Branch to compare against / PR target
```

### Reference

Links to external resources or local files.

```python
@dataclass
class Reference:
    name: str                        # Display name
    location: str                    # URL or file path
    ref_type: ReferenceType = ReferenceType.LINK

class ReferenceType(Enum):
    LINK = "link"                    # External URL
    FILE = "file"                    # Local file path
    DIRECTORY = "directory"          # Local directory
```

### ExternalTicket

Link to external issue tracking.

```python
@dataclass
class ExternalTicket:
    ticket_id: str                   # e.g., "PROJ-123"
    url: str | None = None           # Full URL to ticket
    system: TicketSystem = TicketSystem.OTHER

class TicketSystem(Enum):
    JIRA = "jira"
    LINEAR = "linear"
    GITHUB = "github"
    ASANA = "asana"
    OTHER = "other"
```

### ProjectType

Classification of the work being done.

```python
class ProjectType(Enum):
    FEATURE = "feature"              # New feature development
    BUG = "bug"                      # Bug fix
    REFACTOR = "refactor"            # Code refactoring
    SPIKE = "spike"                  # Research/exploration
    CHORE = "chore"                  # Maintenance tasks
    MISC = "misc"                    # Other/unclassified
```

### IDE

Supported editors/IDEs for opening files.

```python
class IDE(Enum):
    VSCODE = "vscode"                # code {path}
    CURSOR = "cursor"                # cursor {path}
    ZED = "zed"                      # zed {path}
    SUBLIME = "sublime"              # subl {path}
    WEBSTORM = "webstorm"            # webstorm {path}
    VIM = "vim"                      # vim {path}
    NEOVIM = "neovim"                # nvim {path}
    EMACS = "emacs"                  # emacs {path}
    OTHER = "other"                  # Custom command

    def open_command(self, path: str) -> str:
        """Returns the shell command to open a file/directory."""
        commands = {
            IDE.VSCODE: f"code {path}",
            IDE.CURSOR: f"cursor {path}",
            IDE.ZED: f"zed {path}",
            IDE.SUBLIME: f"subl {path}",
            IDE.WEBSTORM: f"webstorm {path}",
            IDE.VIM: f"vim {path}",
            IDE.NEOVIM: f"nvim {path}",
            IDE.EMACS: f"emacs {path}",
        }
        return commands.get(self, f"open {path}")
```

### PortConfig

Port configuration with optional env variable linking.

```python
@dataclass
class PortConfig:
    port: int | None = None          # Static port number
    env_var: str | None = None       # Or read from env variable (e.g., "API_PORT")
    name: str | None = None          # Display name (e.g., "API Server")
    service: str | None = None       # Which script/service uses this port

    def resolve(self, env_vars: dict[str, str]) -> int | None:
        """Resolve the port number, using env_var if port is not set."""
        if self.port is not None:
            return self.port
        if self.env_var and self.env_var in env_vars:
            try:
                return int(env_vars[self.env_var])
            except ValueError:
                return None
        return None
```

**Example:**
```python
ports = [
    PortConfig(port=3000, name="Web Client", service="start_web"),
    PortConfig(env_var="API_PORT", name="API Server", service="start_api"),
    PortConfig(env_var="DATABASE_PORT", name="PostgreSQL"),
]
```

### HealthCheck

Health check endpoints to verify services are running.

```python
@dataclass
class HealthCheck:
    name: str                        # Display name
    url: str                         # URL to check (can include {env.VAR} placeholders)
    method: str = "GET"              # HTTP method
    expected_status: int = 200       # Expected HTTP status code
    timeout_seconds: float = 5.0     # Request timeout
    interval_seconds: float = 10.0   # How often to check (0 = manual only)
    service: str | None = None       # Which script/service this checks

    # Runtime state (not persisted)
    _last_check: datetime | None = None
    _last_status: HealthStatus = HealthStatus.UNKNOWN

class HealthStatus(Enum):
    UNKNOWN = "unknown"              # Not yet checked
    HEALTHY = "healthy"              # Check passed
    UNHEALTHY = "unhealthy"          # Check failed
    CHECKING = "checking"            # Check in progress
```

**Example:**
```python
health_checks = [
    HealthCheck(
        name="API Health",
        url="http://localhost:{env.API_PORT}/health",
        service="start_api"
    ),
    HealthCheck(
        name="Web App",
        url="http://localhost:3000",
        expected_status=200,
        service="start_web"
    ),
]
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
          "command": "{scripts.start}",
          "layout": "tab",
          "restart_on_exit": true
        },
        {
          "id": "tests",
          "name": "Tests",
          "command": "{scripts.test_watch}",
          "layout": "pane_vertical",
          "parent_template_id": "server"
        }
      ],
      "config": {
        "docs": {
          "prd": {
            "path": "docs/PRD.md",
            "state": "exists"
          },
          "problem_statement": {
            "path": "docs/PROBLEM.md",
            "state": "missing"
          },
          "plan": {
            "path": "docs/PLAN.md",
            "state": "exists"
          },
          "specs_dir": "docs/specs",
          "specs": [],
          "qa_test_plan": {
            "path": "docs/QA_TEST_PLAN.md",
            "state": "unneeded"
          },
          "auto_discover_specs": true,
          "spec_patterns": ["*.spec.md", "*.spec.txt", "SPEC_*.md"]
        },
        "scripts": {
          "start_api": {
            "command": "npm run dev",
            "working_dir": "packages/api",
            "description": "Start API server",
            "category": "dev"
          },
          "start_web": {
            "command": "npm run dev",
            "working_dir": "packages/web",
            "description": "Start web client",
            "category": "dev"
          },
          "test": {
            "command": "npm test",
            "description": "Run all tests",
            "category": "test"
          },
          "test_watch": {
            "command": "npm run test:watch",
            "category": "test"
          },
          "lint": {
            "command": "npm run lint",
            "category": "lint"
          },
          "build": {
            "command": "npm run build",
            "category": "build"
          },
          "typecheck": {
            "command": "npm run typecheck",
            "category": "lint"
          }
        },
        "env": {
          "files": [".env", ".env.local"],
          "overrides": {},
          "show_in_ui": ["DATABASE_URL", "API_URL", "NODE_ENV"],
          "hide_in_ui": [],
          "sensitive_patterns": ["*_KEY", "*_SECRET", "*_TOKEN", "*_PASSWORD"]
        },
        "git": {
          "branch": "feature/user-auth",
          "remote": "origin",
          "repo_url": "https://github.com/me/webapp",
          "base_branch": "main"
        },
        "references": [
          {
            "name": "Design Figma",
            "location": "https://figma.com/file/abc123",
            "ref_type": "link"
          },
          {
            "name": "API Docs",
            "location": "docs/api/README.md",
            "ref_type": "file"
          }
        ],
        "external_ticket": {
          "ticket_id": "WEBAPP-456",
          "url": "https://mycompany.atlassian.net/browse/WEBAPP-456",
          "system": "jira"
        },
        "project_type": "feature",
        "ide": "cursor",
        "ports": [
          {
            "port": 3000,
            "name": "Web Client",
            "service": "start_web"
          },
          {
            "env_var": "API_PORT",
            "name": "API Server",
            "service": "start_api"
          },
          {
            "env_var": "DATABASE_PORT",
            "name": "PostgreSQL"
          }
        ],
        "health_checks": [
          {
            "name": "API Health",
            "url": "http://localhost:{env.API_PORT}/health",
            "service": "start_api",
            "interval_seconds": 10
          },
          {
            "name": "Web App",
            "url": "http://localhost:3000",
            "service": "start_web"
          }
        ],
        "tab_prefix": "[webapp] ",
        "startup_sequence": ["server", "tests", "plan"],
        "close_sessions_on_project_close": true
      }
    }
  ],
  "settings": {
    "default_shell": "/bin/zsh",
    "default_ide": "cursor",
    "default_project_dir": "~/Projects/",
    "confirm_on_quit": true,
    "notifications": {
      "enabled": true,
      "sound_enabled": true,
      "cooldown_seconds": 30,
      "monitor_session_types": ["all"]
    },
    "control_room": {
      "default_sort": "status",
      "polling_interval_ms": 500
    },
    "github": {
      "auth_method": "gh_cli",
      "refresh_interval_seconds": 60
    }
  }
}
```

**Note**: Session template commands can reference scripts using `{scripts.NAME}` syntax, allowing you to define commands once and reuse them.

### SQLite Schema (Alternative)

```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    project_type TEXT DEFAULT 'misc',
    config_json TEXT,                    -- Full ProjectConfig as JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Normalized scripts table (alternative to storing in config_json)
CREATE TABLE project_scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,                  -- e.g., "start", "test", "lint"
    command TEXT NOT NULL,
    UNIQUE(project_id, name)
);

-- Normalized references table
CREATE TABLE project_references (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    ref_type TEXT DEFAULT 'link'         -- 'link', 'file', 'directory'
);

-- Git context (one per project)
CREATE TABLE project_git (
    project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    branch TEXT,
    remote TEXT DEFAULT 'origin',
    repo_url TEXT,
    base_branch TEXT DEFAULT 'main'
);

-- External ticket tracking
CREATE TABLE project_tickets (
    project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    ticket_id TEXT NOT NULL,
    url TEXT,
    system TEXT DEFAULT 'other'          -- 'jira', 'linear', 'github', etc.
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

### AppSettings

Application-level settings (persisted).

```python
@dataclass
class NotificationSettings:
    enabled: bool = True                           # Enable system notifications
    sound_enabled: bool = True                     # Play sound on notification
    cooldown_seconds: int = 30                     # Min time between notifications for same session
    monitor_session_types: list[str] = field(     # Which session types to monitor
        default_factory=lambda: ["all"]            # "all", "claude", or specific template IDs
    )

@dataclass
class ControlRoomSettings:
    default_sort: str = "status"                   # "status", "project", "activity"
    polling_interval_ms: int = 500                 # How often to check session output

@dataclass
class GitHubSettings:
    auth_method: str = "gh_cli"                    # "gh_cli", "token", "oauth"
    refresh_interval_seconds: int = 60             # How often to refresh PR status
    # Token stored separately in keychain/secure storage, not in config

@dataclass
class AppSettings:
    # General
    default_shell: str = "/bin/zsh"
    default_ide: IDE = IDE.VSCODE
    default_project_dir: str = "~/Projects/"
    confirm_on_quit: bool = True

    # Feature settings
    notifications: NotificationSettings = field(default_factory=NotificationSettings)
    control_room: ControlRoomSettings = field(default_factory=ControlRoomSettings)
    github: GitHubSettings = field(default_factory=GitHubSettings)
```

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

    # Control Room state
    current_view: str = "control_room"             # "control_room", "project_list", "project_dashboard"
    control_room_sort: str = "status"              # Current sort mode

    # UI State
    selected_session_id: str | None = None

    def get_active_project(self) -> Project | None:
        if self.active_project_id:
            return self.projects.get(self.active_project_id)
        return None

    def get_all_sessions(self) -> list[ManagedSession]:
        """Get all active sessions across all projects (for Control Room)."""
        sessions = []
        for project in self.projects.values():
            sessions.extend(project.active_sessions.values())
        return sessions

    def get_sessions_needing_attention(self) -> list[ManagedSession]:
        """Get sessions in WAITING state."""
        return [s for s in self.get_all_sessions()
                if s.attention_state == AttentionState.WAITING]
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

## Project Templates

Templates provide reusable setup scripts and default configurations for new projects.

### ProjectTemplate

```python
@dataclass
class ProjectTemplate:
    id: str                          # Unique identifier
    name: str                        # Display name (e.g., "Trunk Tools Feature")
    description: str | None = None   # Optional description

    # Setup script configuration
    setup_script: str                # Path to script or inline command
    setup_params: list[SetupParam] = field(default_factory=list)

    # Project config defaults (applied to new projects)
    default_config: ProjectConfigDefaults = field(default_factory=ProjectConfigDefaults)

@dataclass
class SetupParam:
    name: str                        # Parameter name (e.g., "branch_name")
    description: str | None = None   # Help text
    required: bool = True
    default: str | None = None       # Default value (can use {variables})

@dataclass
class ProjectConfigDefaults:
    """Partial ProjectConfig - all fields optional, applied as defaults."""
    docs: ProjectDocs | None = None
    scripts: dict[str, Script] | None = None
    env: EnvConfig | None = None
    git: GitConfig | None = None
    ports: list[PortConfig] | None = None
    health_checks: list[HealthCheck] | None = None
    ide: IDE | None = None
    session_templates: list[SessionTemplate] | None = None
    startup_sequence: list[str] | None = None
```

### Template Storage

Templates are stored globally in the app config:

```json
{
  "templates": [
    {
      "id": "trunk-tools-feature",
      "name": "Trunk Tools Feature",
      "description": "Create a new feature branch with worktree and database",
      "setup_script": "~/scripts/create-trunk-worktree.sh",
      "setup_params": [
        {
          "name": "branch_name",
          "description": "Git branch name",
          "required": true
        },
        {
          "name": "project_path",
          "description": "Where to create the worktree",
          "required": true,
          "default": "~/Projects/trunk-tools/{branch_name}"
        }
      ],
      "default_config": {
        "scripts": {
          "start": {
            "command": "bin/dev",
            "description": "Start dev server",
            "category": "dev"
          },
          "test": {
            "command": "bin/rails test",
            "category": "test"
          },
          "lint": {
            "command": "bin/rubocop",
            "category": "lint"
          }
        },
        "env": {
          "files": [".env", ".env.development.local"]
        },
        "docs": {
          "specs_dir": "docs/specs",
          "auto_discover_specs": true
        },
        "ports": [
          {
            "env_var": "PORT",
            "name": "Rails Server",
            "service": "start"
          }
        ],
        "health_checks": [
          {
            "name": "App Health",
            "url": "http://localhost:{env.PORT}/health"
          }
        ],
        "session_templates": [
          {
            "id": "server",
            "name": "Dev Server",
            "command": "{scripts.start}",
            "auto_start": true
          },
          {
            "id": "claude",
            "name": "Claude",
            "command": "claude",
            "layout": "tab"
          }
        ],
        "startup_sequence": ["server", "claude"]
      }
    }
  ]
}
```

### Template Execution

When a project is created from a template:

```python
async def create_project_from_template(
    template: ProjectTemplate,
    user_input: dict,  # name, type, jira_ticket, branch, etc.
) -> Project:
    # 1. Resolve setup params
    params = resolve_params(template.setup_params, user_input)

    # 2. Run setup script
    await run_setup_script(template.setup_script, params)

    # 3. Create project with merged config
    project = Project(
        id=generate_id(),
        name=user_input["name"],
        path=params["project_path"],
        config=merge_configs(
            template.default_config,  # Base from template
            user_input_to_config(user_input),  # User overrides
        ),
    )

    # 4. Save project
    await save_project(project)

    return project
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
