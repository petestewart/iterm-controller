# Data Models

## Overview

Core dataclasses representing all domain entities. All models are designed for JSON serialization using `dacite`.

## Project Models

```python
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
from typing import Callable

@dataclass
class Project:
    """A development project managed by the controller."""
    id: str                              # Unique identifier
    name: str                            # Display name
    path: str                            # Absolute path to project root
    plan_path: str = "PLAN.md"           # Relative path to plan file
    test_plan_path: str = "TEST_PLAN.md" # Relative path to test plan file
    config_path: str | None = None       # Project-local config override
    template_id: str | None = None       # Template used to create project

    # Project configuration
    scripts: list["ProjectScript"] | None = None      # Named scripts for toolbar/hotkeys
    review_config: "ReviewConfig" | None = None       # Auto-review settings
    git_config: "GitConfig" | None = None             # Git integration settings

    # Runtime state (not persisted)
    is_open: bool = field(default=False, repr=False)
    sessions: list[str] = field(default_factory=list, repr=False)  # Session IDs

    @property
    def full_plan_path(self) -> Path:
        return Path(self.path) / self.plan_path

@dataclass
class ProjectTemplate:
    """Template for creating new projects."""
    id: str                              # Unique template identifier
    name: str                            # Display name
    description: str = ""                # Template description
    setup_script: str | None = None      # Script to run after creation
    initial_sessions: list[str] = field(default_factory=list)  # SessionTemplate IDs
    default_plan: str | None = None      # Initial PLAN.md content
    files: dict[str, str] = field(default_factory=dict)  # Additional files to create

    # Validation
    required_fields: list[str] = field(default_factory=list)  # Form fields needed
```

## Session Models

```python
class SessionType(Enum):
    """What kind of work this session is doing."""
    CLAUDE_TASK = "claude_task"          # Working on specific task
    ORCHESTRATOR = "orchestrator"        # Running task loop script
    REVIEW = "review"                    # Running review command
    TEST_RUNNER = "test_runner"          # Running tests
    SCRIPT = "script"                    # Custom project script
    SERVER = "server"                    # Dev server
    SHELL = "shell"                      # Interactive shell

class AttentionState(Enum):
    """Session attention state for user notification."""
    WAITING = "waiting"   # Needs user input (highest priority)
    WORKING = "working"   # Actively producing output
    IDLE = "idle"         # At prompt, not doing anything

@dataclass
class SessionProgress:
    """Progress tracking for orchestrator sessions."""
    total_tasks: int
    completed_tasks: int
    current_task_id: str | None
    current_task_title: str | None
    phase_id: str | None

@dataclass
class SessionTemplate:
    """Template for spawning terminal sessions."""
    id: str                              # Unique identifier
    name: str                            # Display name
    command: str                         # Initial command to run
    working_dir: str | None = None       # Working directory (default: project root)
    env: dict[str, str] = field(default_factory=dict)  # Additional env vars

@dataclass
class ManagedSession:
    """A terminal session managed by the controller."""
    id: str                              # iTerm2 session ID
    template_id: str                     # Which template spawned this
    project_id: str                      # Parent project
    tab_id: str                          # iTerm2 tab ID

    # Session type and context
    session_type: SessionType = SessionType.SHELL
    task_id: str | None = None           # If working on a specific task
    display_name: str | None = None      # Custom display name override
    progress: SessionProgress | None = None  # For orchestrator sessions

    # Runtime state
    attention_state: AttentionState = AttentionState.IDLE
    last_output: str = ""                # Last captured output chunk
    last_activity: datetime | None = None
    is_active: bool = True

    # Tracking
    spawned_at: datetime = field(default_factory=datetime.now)
    is_managed: bool = True              # True if we spawned it
```

## Task Models

```python
class TaskStatus(Enum):
    """Status of a task in PLAN.md."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETE = "complete"
    SKIPPED = "skipped"
    BLOCKED = "blocked"

@dataclass
class Task:
    """A task parsed from PLAN.md."""
    id: str                              # Task identifier (e.g., "2.1")
    title: str                           # Task title

    # Status
    status: TaskStatus = TaskStatus.PENDING
    revision_count: int = 0              # Number of review revisions

    # Metadata
    spec_ref: str | None = None          # Reference to spec file/section
    session_id: str | None = None        # Assigned session
    assigned_session_id: str | None = None  # Session actively working on this
    depends: list[str] = field(default_factory=list)  # Task IDs this blocks on

    # Content
    scope: str = ""                      # What's in scope
    acceptance: str = ""                 # Acceptance criteria
    notes: list[str] = field(default_factory=list)    # Additional notes

    # Review state
    current_review: "TaskReview | None" = None
    review_history: list["TaskReview"] | None = None

    @property
    def is_blocked(self) -> bool:
        """Check if any dependencies are incomplete."""
        # Note: Actual blocking check needs access to other tasks
        return self.status == TaskStatus.BLOCKED

@dataclass
class Phase:
    """A phase/section in PLAN.md containing tasks."""
    id: str                              # Phase identifier (e.g., "2")
    title: str                           # Phase title
    tasks: list[Task] = field(default_factory=list)

    @property
    def completion_count(self) -> tuple[int, int]:
        """Return (completed, total) task counts."""
        completed = sum(1 for t in self.tasks
                       if t.status in (TaskStatus.COMPLETE, TaskStatus.SKIPPED))
        return (completed, len(self.tasks))

    @property
    def completion_percent(self) -> float:
        """Return completion percentage."""
        completed, total = self.completion_count
        return (completed / total * 100) if total > 0 else 0.0

@dataclass
class Plan:
    """Parsed PLAN.md document."""
    phases: list[Phase] = field(default_factory=list)
    overview: str = ""
    success_criteria: list[str] = field(default_factory=list)

    @property
    def all_tasks(self) -> list[Task]:
        """Flatten all tasks from all phases."""
        return [task for phase in self.phases for task in phase.tasks]

    @property
    def completion_summary(self) -> dict[str, int]:
        """Return summary of task statuses."""
        summary = {status.value: 0 for status in TaskStatus}
        for task in self.all_tasks:
            summary[task.status.value] += 1
        return summary

    @property
    def overall_progress(self) -> float:
        """Return overall completion percentage."""
        tasks = self.all_tasks
        if not tasks:
            return 0.0
        completed = sum(1 for t in tasks
                       if t.status in (TaskStatus.COMPLETE, TaskStatus.SKIPPED))
        return completed / len(tasks) * 100
```

## Review Models

```python
class ReviewResult(Enum):
    """Result of a task review."""
    PENDING = "pending"
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"                # Blocking, needs human

@dataclass
class TaskReview:
    """A single review attempt for a task."""
    id: str
    task_id: str
    attempt: int
    result: ReviewResult
    issues: list[str]
    summary: str
    blocking: bool
    reviewed_at: datetime
    reviewer_command: str
    raw_output: str | None = None

@dataclass
class ReviewContextConfig:
    """What context to provide to the reviewer."""
    include_task_definition: bool = True
    include_git_diff: bool = True
    include_test_results: bool = True
    include_lint_results: bool = False
    include_session_log: bool = False

@dataclass
class ReviewConfig:
    """Review settings for a project."""
    enabled: bool = True
    command: str = "/review-task"
    model: str | None = None
    max_revisions: int = 3
    trigger: str = "script_completion"
    context: ReviewContextConfig | None = None
```

## Git Models

```python
@dataclass
class GitFileStatus:
    """Status of a single file in git."""
    path: str
    status: str                          # "M", "A", "D", "?", etc.
    staged: bool

@dataclass
class GitStatus:
    """Current git status for a project."""
    branch: str
    ahead: int = 0
    behind: int = 0
    staged: list[GitFileStatus] | None = None
    unstaged: list[GitFileStatus] | None = None
    untracked: list[GitFileStatus] | None = None
    has_conflicts: bool = False
    last_commit_sha: str | None = None
    last_commit_message: str | None = None
    fetched_at: datetime | None = None

@dataclass
class GitCommit:
    """A git commit."""
    sha: str
    short_sha: str
    message: str
    author: str
    date: datetime

@dataclass
class GitConfig:
    """Git settings for a project."""
    auto_stage: bool = False
    default_branch: str = "main"
    remote: str = "origin"
```

## Script Models

```python
@dataclass
class ProjectScript:
    """A named script that can be run from the project screen."""
    id: str
    name: str
    command: str
    keybinding: str | None = None
    working_dir: str | None = None
    env: dict[str, str] | None = None
    session_type: SessionType = SessionType.SCRIPT
    show_in_toolbar: bool = True

@dataclass
class RunningScript:
    """A script currently executing in a session."""
    script: ProjectScript
    session_id: str
    started_at: datetime
    on_complete: Callable[[int], None] | None = None
```

## Test Plan Models

```python
class TestStatus(Enum):
    """Status of a test step."""
    PENDING = "pending"         # [ ]
    IN_PROGRESS = "in_progress" # [~]
    PASSED = "passed"           # [x]
    FAILED = "failed"           # [!]

@dataclass
class TestStep:
    """A single verification step from TEST_PLAN.md."""
    id: str                          # Generated ID (e.g., "func-1")
    section: str                     # Parent section name
    description: str                 # Step description
    status: TestStatus = TestStatus.PENDING
    notes: str | None = None         # Failure notes or details
    line_number: int = 0             # Line in file (for updates)

@dataclass
class TestSection:
    """A section in TEST_PLAN.md containing test steps."""
    id: str                          # Section identifier
    title: str                       # Section title
    steps: list[TestStep] = field(default_factory=list)

    @property
    def completion_count(self) -> tuple[int, int]:
        """Return (passed, total) step counts."""
        passed = sum(1 for s in self.steps if s.status == TestStatus.PASSED)
        return (passed, len(self.steps))

@dataclass
class TestPlan:
    """Parsed TEST_PLAN.md document."""
    sections: list[TestSection] = field(default_factory=list)
    title: str = "Test Plan"
    path: str = ""

    @property
    def all_steps(self) -> list[TestStep]:
        return [step for section in self.sections for step in section.steps]

    @property
    def completion_percentage(self) -> float:
        steps = self.all_steps
        if not steps:
            return 0.0
        passed = sum(1 for s in steps if s.status == TestStatus.PASSED)
        return passed / len(steps) * 100
```

## Documentation Reference Models

```python
@dataclass
class DocReference:
    """External documentation reference/bookmark."""
    id: str                          # Unique identifier
    title: str                       # Display title
    url: str                         # URL to external doc
    category: str = ""               # Category/grouping
    notes: str = ""                  # User notes
    added_at: datetime = field(default_factory=datetime.now)
```

## Workflow Models

```python
class WorkflowStage(Enum):
    """Project workflow stages."""
    PLANNING = "planning"
    EXECUTE = "execute"
    REVIEW = "review"
    PR = "pr"
    DONE = "done"

@dataclass
class WorkflowState:
    """Current workflow state for a project."""
    stage: WorkflowStage = WorkflowStage.PLANNING
    prd_exists: bool = False
    prd_unneeded: bool = False
    pr_url: str | None = None
    pr_merged: bool = False

    @classmethod
    def infer_stage(cls, plan: Plan, github_status: "GitHubStatus | None") -> "WorkflowState":
        """Infer workflow stage from plan and GitHub state."""
        state = cls()

        # Check PR status
        if github_status and github_status.pr:
            state.pr_url = github_status.pr.url
            state.pr_merged = github_status.pr.merged
            if state.pr_merged:
                state.stage = WorkflowStage.DONE
                return state
            state.stage = WorkflowStage.PR
            return state

        # Check task completion
        all_done = all(
            t.status in (TaskStatus.COMPLETE, TaskStatus.SKIPPED)
            for t in plan.all_tasks
        )
        if all_done and plan.all_tasks:
            state.stage = WorkflowStage.REVIEW
            return state

        # Check planning completion
        if plan.all_tasks:
            state.stage = WorkflowStage.EXECUTE
            return state

        return state
```

## Configuration Models

```python
@dataclass
class HealthCheck:
    """HTTP health check configuration."""
    name: str                            # Display name
    url: str                             # URL with optional {env.VAR} placeholders
    method: str = "GET"                  # HTTP method
    expected_status: int = 200           # Expected response code
    timeout_seconds: float = 5.0         # Request timeout
    interval_seconds: float = 10.0       # Polling interval (0 = manual only)

class HealthStatus(Enum):
    """Health check result status."""
    UNKNOWN = "unknown"
    CHECKING = "checking"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"

@dataclass
class AutoModeConfig:
    """Auto mode workflow configuration."""
    enabled: bool = False
    stage_commands: dict[str, str] = field(default_factory=dict)
    auto_advance: bool = True
    require_confirmation: bool = True

@dataclass
class NotificationSettings:
    """Notification settings for the application."""
    enabled: bool = True
    sound_enabled: bool = True
    sound_name: str = "default"
    on_session_waiting: bool = True
    on_session_idle: bool = False
    on_review_failed: bool = True
    on_task_complete: bool = False
    on_phase_complete: bool = True
    on_orchestrator_done: bool = True

@dataclass
class AppSettings:
    """Global application settings."""
    default_ide: str = "vscode"
    default_shell: str = "zsh"
    polling_interval_ms: int = 500
    notification_enabled: bool = True
    github_refresh_seconds: int = 60
    health_check_interval_seconds: float = 10.0
    notifications: NotificationSettings = field(default_factory=NotificationSettings)

@dataclass
class AppConfig:
    """Complete application configuration."""
    settings: AppSettings = field(default_factory=AppSettings)
    projects: list[Project] = field(default_factory=list)
    templates: list[ProjectTemplate] = field(default_factory=list)
    session_templates: list[SessionTemplate] = field(default_factory=list)
    window_layouts: list["WindowLayout"] = field(default_factory=list)
```

## Window Layout Models

```python
@dataclass
class SessionLayout:
    """Layout specification for a session within a tab."""
    template_id: str                     # Which SessionTemplate to use
    split: str = "none"                  # "none", "horizontal", "vertical"
    size_percent: int = 50               # Split size percentage

@dataclass
class TabLayout:
    """Layout specification for a tab within a window."""
    name: str                            # Tab title
    sessions: list[SessionLayout] = field(default_factory=list)

@dataclass
class WindowLayout:
    """Predefined window layout with tabs and sessions."""
    id: str                              # Layout identifier
    name: str                            # Display name
    tabs: list[TabLayout] = field(default_factory=list)
```

## GitHub Models

```python
@dataclass
class PullRequest:
    """GitHub pull request information."""
    number: int
    title: str
    url: str
    state: str                           # "open", "closed", "merged"
    merged: bool = False
    draft: bool = False
    comments: int = 0
    reviews_pending: int = 0
    checks_passing: bool | None = None

@dataclass
class GitHubStatus:
    """Current GitHub state for a project."""
    available: bool = True
    error_message: str | None = None

    # Branch info
    current_branch: str | None = None
    default_branch: str = "main"
    ahead: int = 0
    behind: int = 0

    # PR info
    pr: PullRequest | None = None

    # Cached state
    last_updated: datetime | None = None
```

## Serialization

All models use `dacite` for JSON serialization:

```python
import json
from dacite import from_dict, Config as DaciteConfig

def load_config(path: Path) -> AppConfig:
    """Load configuration from JSON file."""
    with open(path) as f:
        data = json.load(f)
    return from_dict(
        data_class=AppConfig,
        data=data,
        config=DaciteConfig(cast=[Enum])
    )

def save_config(config: AppConfig, path: Path):
    """Save configuration to JSON file."""
    data = asdict(config)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
```
