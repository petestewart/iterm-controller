"""State management package.

This package provides reactive application state with event dispatch.
The main AppState class composes focused state managers for better
organization while maintaining a unified public API.

For external observation (agents, CLI tools), use `AppState.to_snapshot()`
or the convenience functions in `iterm_controller.api`.
"""

# Re-export everything from the main state module for backwards compatibility
from iterm_controller.state.app_state import AppState
from iterm_controller.state.events import (
    ConfigChanged,
    GitStatusChanged,
    HealthStatusChanged,
    PlanConflict,
    PlanReloaded,
    ProjectClosed,
    ProjectOpened,
    ReviewCompleted,
    ReviewFailed,
    ReviewStarted,
    SessionClosed,
    SessionSpawned,
    SessionStatusChanged,
    StateEvent,
    StateMessage,
    TaskStatusChanged,
    TestPlanConflict,
    TestPlanDeleted,
    TestPlanReloaded,
    TestStepUpdated,
    WorkflowStageChanged,
)
from iterm_controller.state.git_manager import GitStateManager
from iterm_controller.state.review_manager import ReviewStateManager
from iterm_controller.state.snapshot import StateSnapshot

__all__ = [
    # Main state class
    "AppState",
    # State managers
    "GitStateManager",
    "ReviewStateManager",
    # Snapshot for external observation
    "StateSnapshot",
    # Events
    "ConfigChanged",
    "GitStatusChanged",
    "HealthStatusChanged",
    "PlanConflict",
    "PlanReloaded",
    "ProjectClosed",
    "ProjectOpened",
    "ReviewCompleted",
    "ReviewFailed",
    "ReviewStarted",
    "SessionClosed",
    "SessionSpawned",
    "SessionStatusChanged",
    "StateEvent",
    "StateMessage",
    "TaskStatusChanged",
    "TestPlanConflict",
    "TestPlanDeleted",
    "TestPlanReloaded",
    "TestStepUpdated",
    "WorkflowStageChanged",
]
