"""State events and Textual message classes.

This module defines the events that can be dispatched from state changes
and the corresponding Textual Message classes for UI updates.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from textual.message import Message

if TYPE_CHECKING:
    from iterm_controller.models import ManagedSession, Plan, Project, TestPlan, AppConfig


class StateEvent(Enum):
    """Events that can be dispatched from state changes."""

    PROJECT_OPENED = "project_opened"
    PROJECT_CLOSED = "project_closed"
    SESSION_SPAWNED = "session_spawned"
    SESSION_CLOSED = "session_closed"
    SESSION_STATUS_CHANGED = "session_status_changed"
    TASK_STATUS_CHANGED = "task_status_changed"
    PLAN_RELOADED = "plan_reloaded"
    PLAN_CONFLICT = "plan_conflict"
    CONFIG_CHANGED = "config_changed"
    HEALTH_STATUS_CHANGED = "health_status_changed"
    WORKFLOW_STAGE_CHANGED = "workflow_stage_changed"
    # TEST_PLAN.md events
    TEST_PLAN_RELOADED = "test_plan_reloaded"
    TEST_PLAN_DELETED = "test_plan_deleted"
    TEST_PLAN_CONFLICT = "test_plan_conflict"
    TEST_STEP_UPDATED = "test_step_updated"


# =============================================================================
# Textual Messages for State Events
# =============================================================================


class StateMessage(Message):
    """Base class for state change messages."""

    pass


class ProjectOpened(StateMessage):
    """Posted when a project is opened."""

    def __init__(self, project: Project) -> None:
        super().__init__()
        self.project = project


class ProjectClosed(StateMessage):
    """Posted when a project is closed."""

    def __init__(self, project_id: str) -> None:
        super().__init__()
        self.project_id = project_id


class SessionSpawned(StateMessage):
    """Posted when a session is spawned."""

    def __init__(self, session: ManagedSession) -> None:
        super().__init__()
        self.session = session


class SessionClosed(StateMessage):
    """Posted when a session is closed."""

    def __init__(self, session: ManagedSession) -> None:
        super().__init__()
        self.session = session


class SessionStatusChanged(StateMessage):
    """Posted when a session's status changes."""

    def __init__(self, session: ManagedSession) -> None:
        super().__init__()
        self.session = session


class TaskStatusChanged(StateMessage):
    """Posted when a task's status changes."""

    def __init__(self, task_id: str, project_id: str) -> None:
        super().__init__()
        self.task_id = task_id
        self.project_id = project_id


class PlanReloaded(StateMessage):
    """Posted when a PLAN.md file is reloaded."""

    def __init__(self, project_id: str, plan: Plan) -> None:
        super().__init__()
        self.project_id = project_id
        self.plan = plan


class PlanConflict(StateMessage):
    """Posted when an external change to PLAN.md is detected."""

    def __init__(self, project_id: str, new_plan: Plan) -> None:
        super().__init__()
        self.project_id = project_id
        self.new_plan = new_plan


class ConfigChanged(StateMessage):
    """Posted when the configuration changes."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config


class HealthStatusChanged(StateMessage):
    """Posted when health check status changes."""

    def __init__(self, project_id: str, check_name: str, status: str) -> None:
        super().__init__()
        self.project_id = project_id
        self.check_name = check_name
        self.status = status


class WorkflowStageChanged(StateMessage):
    """Posted when workflow stage changes."""

    def __init__(self, project_id: str, stage: str) -> None:
        super().__init__()
        self.project_id = project_id
        self.stage = stage


class TestPlanReloaded(StateMessage):
    """Posted when a TEST_PLAN.md file is reloaded."""

    def __init__(self, project_id: str, test_plan: TestPlan) -> None:
        super().__init__()
        self.project_id = project_id
        self.test_plan = test_plan


class TestPlanDeleted(StateMessage):
    """Posted when a TEST_PLAN.md file is deleted."""

    def __init__(self, project_id: str) -> None:
        super().__init__()
        self.project_id = project_id


class TestPlanConflict(StateMessage):
    """Posted when an external change to TEST_PLAN.md is detected."""

    def __init__(self, project_id: str, new_plan: TestPlan) -> None:
        super().__init__()
        self.project_id = project_id
        self.new_plan = new_plan


class TestStepUpdated(StateMessage):
    """Posted when a test step's status changes."""

    def __init__(self, project_id: str, step_id: str) -> None:
        super().__init__()
        self.project_id = project_id
        self.step_id = step_id
