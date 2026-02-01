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
    StateEvent,
    StateMessage,
    ProjectOpened,
    ProjectClosed,
    SessionSpawned,
    SessionClosed,
    SessionStatusChanged,
    TaskStatusChanged,
    PlanReloaded,
    PlanConflict,
    ConfigChanged,
    HealthStatusChanged,
    WorkflowStageChanged,
    TestPlanReloaded,
    TestPlanDeleted,
    TestPlanConflict,
    TestStepUpdated,
)
from iterm_controller.state.snapshot import StateSnapshot

__all__ = [
    # Main state class
    "AppState",
    # Snapshot for external observation
    "StateSnapshot",
    # Events
    "StateEvent",
    "StateMessage",
    "ProjectOpened",
    "ProjectClosed",
    "SessionSpawned",
    "SessionClosed",
    "SessionStatusChanged",
    "TaskStatusChanged",
    "PlanReloaded",
    "PlanConflict",
    "ConfigChanged",
    "HealthStatusChanged",
    "WorkflowStageChanged",
    "TestPlanReloaded",
    "TestPlanDeleted",
    "TestPlanConflict",
    "TestStepUpdated",
]
