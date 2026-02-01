# Data Models

## Overview

Core dataclasses representing all domain entities. All models are designed for JSON serialization using `dacite`.

## Project Models

```python
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

@dataclass
class Project:
    """A development project managed by the controller."""
    id: str                              # Unique identifier
    name: str                            # Display name
    path: str                            # Absolute path to project root
    plan_path: str = "PLAN.md"           # Relative path to plan file
    config_path: str | None = None       # Project-local config override
    template_id: str | None = None       # Template used to create project

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
class AttentionState(Enum):
    """Session attention state for user notification."""
    WAITING = "waiting"   # Needs user input (highest priority)
    WORKING = "working"   # Actively producing output
    IDLE = "idle"         # At prompt, not doing anything

@dataclass
class SessionTemplate:
    """Template for spawning terminal sessions."""
    id: str                              # Unique identifier
    name: str                            # Display name
    command: str                         # Initial command to run
    working_dir: str | None = None       # Working directory (default: project root)
    env: dict[str, str] = field(default_factory=dict)  # Additional env vars
    health_check: str | None = None      # Associated health check ID

@dataclass
class ManagedSession:
    """A terminal session managed by the controller."""
    id: str                              # iTerm2 session ID
    template_id: str                     # Which template spawned this
    project_id: str                      # Parent project
    tab_id: str                          # iTerm2 tab ID

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
    COMPLETE = "complete"
    SKIPPED = "skipped"
    BLOCKED = "blocked"

@dataclass
class Task:
    """A task parsed from PLAN.md."""
    id: str                              # Task identifier (e.g., "2.1")
    title: str                           # Task title
    status: TaskStatus = TaskStatus.PENDING

    # Metadata
    spec_ref: str | None = None          # Reference to spec file/section
    session_id: str | None = None        # Assigned session
    depends: list[str] = field(default_factory=list)  # Task IDs this blocks on

    # Content
    scope: str = ""                      # What's in scope
    acceptance: str = ""                 # Acceptance criteria
    notes: list[str] = field(default_factory=list)    # Additional notes

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
    service: str | None = None           # Links to script name for context

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
class AppSettings:
    """Global application settings."""
    default_ide: str = "vscode"
    default_shell: str = "zsh"
    polling_interval_ms: int = 500
    notification_enabled: bool = True
    github_refresh_seconds: int = 60
    health_check_interval_seconds: float = 10.0

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
