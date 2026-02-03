"""iTerm2 Project Orchestrator.

A TUI application that serves as a "control room" for development projects.
Manages terminal sessions through iTerm2's Python API, monitors session output
for attention-needed states, and provides unified visibility across projects.

Public API Usage:
    # Standalone programmatic access
    from iterm_controller import ItermControllerAPI

    async def main():
        api = ItermControllerAPI()
        await api.initialize()
        projects = await api.list_projects()
        await api.spawn_session("my-project", "dev-server")
        await api.shutdown()

    # Quick operations with convenience functions
    from iterm_controller import spawn_session, claim_task, list_projects

    await spawn_session("my-project", "dev-server")
    await claim_task("my-project", "2.1")

    # Data models for type hints
    from iterm_controller import Project, ManagedSession, Task, Plan

    # Configuration access
    from iterm_controller import load_global_config, save_global_config
"""

__version__ = "0.1.0"
__author__ = "Pete Stewart"

# =============================================================================
# Main API Classes
# =============================================================================

from iterm_controller.api import (
    # Main API classes
    ItermControllerAPI,
    AppAPI,
    # Result types
    APIResult,
    SessionResult,
    TaskResult,
    TestStepResult,
    ProjectResult,
    # Convenience functions
    spawn_session,
    claim_task,
    toggle_test_step,
    list_projects,
    list_sessions,
    # State query functions
    get_state,
    get_plan,
    get_project,
    get_sessions,
    get_task_progress,
    get_test_plan,
)

# =============================================================================
# Core Data Models
# =============================================================================

from iterm_controller.models import (
    # Session models
    AttentionState,
    SessionType,
    SessionTemplate,
    ManagedSession,
    # Task models
    TaskStatus,
    Task,
    Phase,
    Plan,
    # Review models
    ReviewResult,
    TaskReview,
    ReviewConfig,
    ReviewContextConfig,
    # Test models
    TestStatus,
    TestStep,
    TestSection,
    TestPlan,
    # Project models
    Project,
    ProjectTemplate,
    ProjectScript,
    WorkflowMode,
    WorkflowStage,
    WorkflowState,
    # Configuration models
    AppConfig,
    AppSettings,
    HealthCheck,
    HealthStatus,
    WindowLayout,
    TabLayout,
    SessionLayout,
    AutoModeConfig,
    NotificationSettings,
    # Git models
    GitFileStatus,
    GitStatus,
    GitConfig,
    # GitHub models
    GitHubStatus,
    PullRequest,
    WorkflowRun,
    # Artifact tracking
    ArtifactStatus,
)

# =============================================================================
# State Management
# =============================================================================

from iterm_controller.state import (
    AppState,
    StateSnapshot,
    StateEvent,
)

# =============================================================================
# iTerm2 Integration
# =============================================================================

from iterm_controller.iterm import (
    ItermController,
    SessionSpawner,
    SessionTerminator,
    WindowLayoutSpawner,
    WindowLayoutManager,
    SpawnResult,
    CloseResult,
    LayoutSpawnResult,
)

# =============================================================================
# Configuration
# =============================================================================

from iterm_controller.config import (
    load_global_config,
    save_global_config,
    load_project_config,
    save_project_config,
    load_merged_config,
    get_global_config_path,
    get_config_dir,
    get_project_config_path,
)

# =============================================================================
# Plan Parsing
# =============================================================================

from iterm_controller.plan_parser import (
    PlanParser,
    PlanUpdater,
)

from iterm_controller.plan_watcher import (
    PlanWatcher,
    PlanWriteQueue,
)

# =============================================================================
# Test Plan Parsing
# =============================================================================

from iterm_controller.test_plan_parser import (
    TestPlanParser,
    TestPlanUpdater,
)

# =============================================================================
# Public API Exports
# =============================================================================

__all__ = [
    # Version info
    "__version__",
    "__author__",
    # Main API
    "ItermControllerAPI",
    "AppAPI",
    "APIResult",
    "SessionResult",
    "TaskResult",
    "TestStepResult",
    "ProjectResult",
    # Convenience functions
    "spawn_session",
    "claim_task",
    "toggle_test_step",
    "list_projects",
    "list_sessions",
    # State query functions
    "get_state",
    "get_plan",
    "get_project",
    "get_sessions",
    "get_task_progress",
    "get_test_plan",
    # Session models
    "AttentionState",
    "SessionType",
    "SessionTemplate",
    "ManagedSession",
    # Task models
    "TaskStatus",
    "Task",
    "Phase",
    "Plan",
    # Review models
    "ReviewResult",
    "TaskReview",
    "ReviewConfig",
    "ReviewContextConfig",
    # Test models
    "TestStatus",
    "TestStep",
    "TestSection",
    "TestPlan",
    # Project models
    "Project",
    "ProjectTemplate",
    "ProjectScript",
    "WorkflowMode",
    "WorkflowStage",
    "WorkflowState",
    # Configuration models
    "AppConfig",
    "AppSettings",
    "HealthCheck",
    "HealthStatus",
    "WindowLayout",
    "TabLayout",
    "SessionLayout",
    "AutoModeConfig",
    "NotificationSettings",
    # Git models
    "GitFileStatus",
    "GitStatus",
    "GitConfig",
    # GitHub models
    "GitHubStatus",
    "PullRequest",
    "WorkflowRun",
    # Artifact tracking
    "ArtifactStatus",
    # State management
    "AppState",
    "StateSnapshot",
    "StateEvent",
    # iTerm2 integration
    "ItermController",
    "SessionSpawner",
    "SessionTerminator",
    "WindowLayoutSpawner",
    "WindowLayoutManager",
    "SpawnResult",
    "CloseResult",
    "LayoutSpawnResult",
    # Configuration
    "load_global_config",
    "save_global_config",
    "load_project_config",
    "save_project_config",
    "load_merged_config",
    "get_global_config_path",
    "get_config_dir",
    "get_project_config_path",
    # Plan parsing
    "PlanParser",
    "PlanUpdater",
    "PlanWatcher",
    "PlanWriteQueue",
    # Test plan parsing
    "TestPlanParser",
    "TestPlanUpdater",
]
