"""Core dataclasses for Project, Session, Task, Config, and related entities.

All models are designed for JSON serialization using dacite.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import dacite


# =============================================================================
# Session Models
# =============================================================================


class AttentionState(Enum):
    """Session attention state for user notification."""

    WAITING = "waiting"  # Needs user input (highest priority)
    WORKING = "working"  # Actively producing output
    IDLE = "idle"  # At prompt, not doing anything


@dataclass
class SessionTemplate:
    """Template for spawning terminal sessions."""

    id: str  # Unique identifier
    name: str  # Display name
    command: str  # Initial command to run
    working_dir: str | None = None  # Working directory (default: project root)
    env: dict[str, str] = field(default_factory=dict)  # Additional env vars
    health_check: str | None = None  # Associated health check ID


@dataclass
class ManagedSession:
    """A terminal session managed by the controller."""

    id: str  # iTerm2 session ID
    template_id: str  # Which template spawned this
    project_id: str  # Parent project
    tab_id: str  # iTerm2 tab ID

    # Runtime state
    attention_state: AttentionState = AttentionState.IDLE
    last_output: str = ""  # Last captured output chunk
    last_activity: datetime | None = None
    is_active: bool = True

    # Tracking
    spawned_at: datetime = field(default_factory=datetime.now)
    is_managed: bool = True  # True if we spawned it

    # Task linking metadata
    metadata: dict[str, str] = field(default_factory=dict)
    # Common metadata keys: task_id, task_title


# =============================================================================
# Task Models
# =============================================================================


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

    id: str  # Task identifier (e.g., "2.1")
    title: str  # Task title
    status: TaskStatus = TaskStatus.PENDING

    # Metadata
    spec_ref: str | None = None  # Reference to spec file/section
    session_id: str | None = None  # Assigned session
    depends: list[str] = field(default_factory=list)  # Task IDs this blocks on

    # Content
    scope: str = ""  # What's in scope
    acceptance: str = ""  # Acceptance criteria
    notes: list[str] = field(default_factory=list)  # Additional notes

    @property
    def is_blocked(self) -> bool:
        """Check if task status indicates blocked state."""
        return self.status == TaskStatus.BLOCKED


@dataclass
class Phase:
    """A phase/section in PLAN.md containing tasks."""

    id: str  # Phase identifier (e.g., "2")
    title: str  # Phase title
    tasks: list[Task] = field(default_factory=list)

    @property
    def completion_count(self) -> tuple[int, int]:
        """Return (completed, total) task counts."""
        completed = sum(
            1 for t in self.tasks if t.status in (TaskStatus.COMPLETE, TaskStatus.SKIPPED)
        )
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

    # Note: _task_map_cache is NOT a dataclass field (not serialized)
    # It's initialized in __post_init__ and stored as an instance attribute

    def __post_init__(self) -> None:
        """Initialize non-serialized cache attribute."""
        # Use object.__setattr__ to bypass frozen if ever needed
        object.__setattr__(self, "_task_map_cache", None)

    @property
    def all_tasks(self) -> list[Task]:
        """Flatten all tasks from all phases."""
        return [task for phase in self.phases for task in phase.tasks]

    @property
    def _task_map(self) -> dict[str, Task]:
        """Get cached task lookup dictionary for O(1) access by ID.

        The cache is automatically invalidated when phases change.
        """
        cache = getattr(self, "_task_map_cache", None)
        if cache is None:
            cache = {task.id: task for task in self.all_tasks}
            object.__setattr__(self, "_task_map_cache", cache)
        return cache

    def get_task_by_id(self, task_id: str) -> Task | None:
        """Get a task by its ID using O(1) lookup.

        Args:
            task_id: The task ID to look up.

        Returns:
            The task if found, None otherwise.
        """
        return self._task_map.get(task_id)

    def invalidate_task_cache(self) -> None:
        """Invalidate the task lookup cache.

        Call this when modifying tasks directly (adding/removing tasks)
        to ensure the cache is rebuilt on next access.
        """
        object.__setattr__(self, "_task_map_cache", None)

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
        completed = sum(
            1 for t in tasks if t.status in (TaskStatus.COMPLETE, TaskStatus.SKIPPED)
        )
        return completed / len(tasks) * 100


# =============================================================================
# Test Plan Models
# =============================================================================


class TestStatus(Enum):
    """Status of a test step in TEST_PLAN.md."""

    PENDING = "pending"  # [ ]
    IN_PROGRESS = "in_progress"  # [~]
    PASSED = "passed"  # [x]
    FAILED = "failed"  # [!]


@dataclass
class TestStep:
    """A single verification step from TEST_PLAN.md."""

    id: str  # Generated ID (e.g., "section-0-1")
    section: str  # Parent section name
    description: str  # Step description
    status: TestStatus = TestStatus.PENDING
    notes: str | None = None  # Failure notes or details
    line_number: int = 0  # Line in file (for updates)


@dataclass
class TestSection:
    """A section in TEST_PLAN.md containing test steps."""

    id: str  # Section identifier
    title: str  # Section title
    steps: list[TestStep] = field(default_factory=list)

    @property
    def completion_count(self) -> tuple[int, int]:
        """Return (passed, total) step counts."""
        passed = sum(1 for s in self.steps if s.status == TestStatus.PASSED)
        return (passed, len(self.steps))

    @property
    def has_failures(self) -> bool:
        """Check if section has any failed steps."""
        return any(s.status == TestStatus.FAILED for s in self.steps)


@dataclass
class TestPlan:
    """Parsed TEST_PLAN.md document."""

    sections: list[TestSection] = field(default_factory=list)
    title: str = "Test Plan"
    path: str = ""  # File path

    @property
    def all_steps(self) -> list[TestStep]:
        """Flatten all steps from all sections."""
        return [step for section in self.sections for step in section.steps]

    @property
    def completion_percentage(self) -> float:
        """Return overall completion percentage."""
        steps = self.all_steps
        if not steps:
            return 0.0
        passed = sum(1 for s in steps if s.status == TestStatus.PASSED)
        return passed / len(steps) * 100

    @property
    def summary(self) -> dict[str, int]:
        """Return summary of step statuses."""
        result: dict[str, int] = {status.value: 0 for status in TestStatus}
        for step in self.all_steps:
            result[step.status.value] += 1
        return result


# =============================================================================
# Workflow Models
# =============================================================================


class WorkflowMode(Enum):
    """Project workflow modes for focused views."""

    PLAN = "plan"  # Planning artifacts
    DOCS = "docs"  # Documentation management
    WORK = "work"  # Task execution
    TEST = "test"  # QA and unit testing


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
    def infer_stage(
        cls,
        plan: Plan,
        github_status: GitHubStatus | None,
        prd_exists: bool = False,
        prd_unneeded: bool = False,
    ) -> WorkflowState:
        """Infer workflow stage from plan and GitHub state.

        Stage progression:
        1. PLANNING: Default stage, waiting for PRD and tasks
        2. EXECUTE: PRD exists (or unneeded) AND plan has tasks
        3. REVIEW: All tasks complete/skipped
        4. PR: Pull request exists on GitHub
        5. DONE: PR merged

        Args:
            plan: The parsed PLAN.md document.
            github_status: Current GitHub status, if available.
            prd_exists: Whether a PRD.md file exists.
            prd_unneeded: Whether PRD has been marked as unnecessary.

        Returns:
            WorkflowState with inferred stage and metadata.
        """
        state = cls()
        state.prd_exists = prd_exists
        state.prd_unneeded = prd_unneeded

        # Check PR status first (highest priority)
        if github_status and github_status.pr:
            state.pr_url = github_status.pr.url
            state.pr_merged = github_status.pr.merged

            if state.pr_merged:
                state.stage = WorkflowStage.DONE
                return state

            state.stage = WorkflowStage.PR
            return state

        # Check task completion
        all_tasks = plan.all_tasks
        if all_tasks:
            all_done = all(
                t.status in (TaskStatus.COMPLETE, TaskStatus.SKIPPED)
                for t in all_tasks
            )
            if all_done:
                state.stage = WorkflowStage.REVIEW
                return state

            # Has tasks = executing
            state.stage = WorkflowStage.EXECUTE
            return state

        # Check planning completion - PRD exists/unneeded AND has tasks
        # Note: This condition is only reached if all_tasks is empty,
        # so we stay in PLANNING if no tasks exist yet
        if prd_exists or prd_unneeded:
            # Still need tasks to advance to EXECUTE
            state.stage = WorkflowStage.PLANNING
            return state

        return state


# =============================================================================
# Planning Artifact Models
# =============================================================================


@dataclass
class ArtifactStatus:
    """Status of a planning artifact (file or directory).

    Used by Plan Mode to track existence and provide descriptions
    of planning artifacts like PROBLEM.md, PRD.md, specs/, and PLAN.md.
    """

    exists: bool
    description: str = ""  # e.g., "4 spec files" or "12 tasks"


# =============================================================================
# Configuration Models
# =============================================================================


@dataclass
class HealthCheck:
    """HTTP health check configuration."""

    name: str  # Display name
    url: str  # URL with optional {env.VAR} placeholders
    method: str = "GET"  # HTTP method
    expected_status: int = 200  # Expected response code
    timeout_seconds: float = 5.0  # Request timeout
    interval_seconds: float = 10.0  # Polling interval (0 = manual only)
    service: str | None = None  # Links to script name for context


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
    # e.g., {"planning": "claude /prd", "execute": "claude /plan"}
    auto_advance: bool = True
    require_confirmation: bool = True
    designated_session: str | None = None  # Session to run commands in
    mode_commands: dict[str, str] = field(default_factory=dict)
    # e.g., {"plan": "claude /prd", "test": "claude /qa", "work": "claude /plan"}
    allowed_commands: list[str] = field(default_factory=lambda: [
        # Claude command patterns - only allow specific Claude slash commands
        r"^claude\s+/prd$",
        r"^claude\s+/plan$",
        r"^claude\s+/review$",
        r"^claude\s+/qa$",
        r"^claude\s+/commit$",
        # Common development commands
        r"^npm\s+(run\s+)?(test|lint|build|start|dev)$",
        r"^yarn\s+(test|lint|build|start|dev)$",
        r"^pnpm\s+(run\s+)?(test|lint|build|start|dev)$",
        r"^pytest(\s+-[vxs]+)?$",
        r"^make\s+(test|lint|build|check)$",
    ])
    # Regex patterns for allowed commands. Commands must match one pattern.


@dataclass
class AppSettings:
    """Global application settings."""

    default_ide: str = "vscode"
    default_shell: str = "zsh"
    polling_interval_ms: int = 500
    notification_enabled: bool = True
    github_refresh_seconds: int = 60
    health_check_interval_seconds: float = 10.0


# =============================================================================
# Window Layout Models
# =============================================================================


@dataclass
class SessionLayout:
    """Layout specification for a session within a tab."""

    template_id: str  # Which SessionTemplate to use
    split: str = "none"  # "none", "horizontal", "vertical"
    size_percent: int = 50  # Split size percentage


@dataclass
class TabLayout:
    """Layout specification for a tab within a window."""

    name: str  # Tab title
    sessions: list[SessionLayout] = field(default_factory=list)


@dataclass
class WindowLayout:
    """Predefined window layout with tabs and sessions."""

    id: str  # Layout identifier
    name: str  # Display name
    tabs: list[TabLayout] = field(default_factory=list)


# =============================================================================
# GitHub Models
# =============================================================================


@dataclass
class PullRequest:
    """GitHub pull request information."""

    number: int
    title: str
    url: str
    state: str  # "open", "closed", "merged"
    merged: bool = False
    draft: bool = False
    comments: int = 0
    reviews_pending: int = 0
    checks_passing: bool | None = None


@dataclass
class WorkflowRun:
    """GitHub Actions workflow run."""

    id: int
    name: str
    status: str  # "queued", "in_progress", "completed"
    conclusion: str | None  # "success", "failure", "cancelled", etc.
    created_at: str
    branch: str


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
    rate_limited: bool = False
    offline: bool = False


# =============================================================================
# Project Models
# =============================================================================


@dataclass
class Project:
    """A development project managed by the controller."""

    id: str  # Unique identifier
    name: str  # Display name
    path: str  # Absolute path to project root
    plan_path: str = "PLAN.md"  # Relative path to plan file
    test_plan_path: str = "TEST_PLAN.md"  # Relative path to test plan file
    config_path: str | None = None  # Project-local config override
    template_id: str | None = None  # Template used to create project
    jira_ticket: str | None = None  # Optional Jira ticket number (e.g., "PROJ-123")
    last_mode: WorkflowMode | None = None  # Last active workflow mode (persisted)

    # Runtime state (not persisted)
    is_open: bool = field(default=False, repr=False)
    sessions: list[str] = field(default_factory=list, repr=False)  # Session IDs
    workflow_state: WorkflowState = field(default_factory=WorkflowState, repr=False)

    @property
    def full_plan_path(self) -> Path:
        """Return full path to the plan file."""
        return Path(self.path) / self.plan_path

    @property
    def full_test_plan_path(self) -> Path:
        """Return full path to the test plan file."""
        return Path(self.path) / self.test_plan_path


@dataclass
class ProjectTemplate:
    """Template for creating new projects."""

    id: str  # Unique template identifier
    name: str  # Display name
    description: str = ""  # Template description
    setup_script: str | None = None  # Script to run after creation
    initial_sessions: list[str] = field(default_factory=list)  # SessionTemplate IDs
    default_plan: str | None = None  # Initial PLAN.md content
    files: dict[str, str] = field(default_factory=dict)  # Additional files to create

    # Validation
    required_fields: list[str] = field(default_factory=list)  # Form fields needed


# =============================================================================
# App Configuration (top-level)
# =============================================================================


@dataclass
class AppConfig:
    """Complete application configuration."""

    settings: AppSettings = field(default_factory=AppSettings)
    auto_mode: AutoModeConfig = field(default_factory=AutoModeConfig)
    projects: list[Project] = field(default_factory=list)
    templates: list[ProjectTemplate] = field(default_factory=list)
    session_templates: list[SessionTemplate] = field(default_factory=list)
    window_layouts: list[WindowLayout] = field(default_factory=list)


# =============================================================================
# Serialization Helpers
# =============================================================================


def _custom_encoder(obj: object) -> str | None:
    """JSON encoder for datetime and Enum objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def load_config_from_dict(data: dict) -> AppConfig:
    """Load AppConfig from a dictionary (parsed JSON)."""
    return dacite.from_dict(
        data_class=AppConfig,
        data=data,
        config=dacite.Config(cast=[Enum]),
    )


def load_config(path: Path) -> AppConfig:
    """Load configuration from JSON file."""
    with open(path) as f:
        data = json.load(f)
    return load_config_from_dict(data)


def save_config(config: AppConfig, path: Path) -> None:
    """Save configuration to JSON file."""
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    data = asdict(config)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=_custom_encoder)


def _convert_enums(obj: object) -> object:
    """Recursively convert Enum values to their string values."""
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _convert_enums(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_enums(item) for item in obj]
    return obj


def model_to_dict(obj: object) -> dict:
    """Convert a dataclass model to a dictionary for JSON serialization."""
    data = asdict(obj)  # type: ignore[arg-type]
    return _convert_enums(data)  # type: ignore[return-value]


def model_from_dict(data_class: type, data: dict) -> object:
    """Load a dataclass model from a dictionary."""
    return dacite.from_dict(
        data_class=data_class,
        data=data,
        config=dacite.Config(cast=[Enum]),
    )
