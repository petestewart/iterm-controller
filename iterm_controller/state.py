"""AppState and event system.

This module provides the reactive application state with event dispatch
for coordinating UI updates. Uses Textual Messages for automatic UI updates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

from textual.message import Message

from iterm_controller.models import (
    AppConfig,
    HealthStatus,
    ManagedSession,
    Plan,
    Project,
    TestPlan,
)

if TYPE_CHECKING:
    from textual.app import App


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


@dataclass
class AppState:
    """Reactive application state with event dispatch.

    This class manages application state and provides two mechanisms for
    notifying about state changes:

    1. **Callback-based subscriptions**: Use `subscribe()` and `unsubscribe()`
       for components that need to react to specific events without being
       part of the Textual widget tree.

    2. **Textual Message posting**: When connected to a Textual App via
       `connect_app()`, state changes automatically post Messages that
       widgets can handle with `on_*` methods.

    Example:
        # In a Screen or Widget
        def on_session_status_changed(self, event: SessionStatusChanged) -> None:
            self.refresh_session_display(event.session)
    """

    # Core state
    projects: dict[str, Project] = field(default_factory=dict)
    active_project_id: str | None = None
    sessions: dict[str, ManagedSession] = field(default_factory=dict)
    config: AppConfig | None = None
    plans: dict[str, Plan] = field(default_factory=dict)  # project_id -> Plan
    test_plans: dict[str, TestPlan] = field(default_factory=dict)  # project_id -> TestPlan
    # Health statuses: project_id -> {check_name -> HealthStatus}
    _health_statuses: dict[str, dict[str, HealthStatus]] = field(default_factory=dict)

    # Event subscribers
    _listeners: dict[StateEvent, list[Callable[..., Any]]] = field(
        default_factory=lambda: {e: [] for e in StateEvent}
    )

    # Textual app reference for posting messages
    _app: App | None = field(default=None, repr=False)

    def connect_app(self, app: App) -> None:
        """Connect to a Textual App for message posting.

        Args:
            app: The Textual App instance to post messages to.
        """
        self._app = app

    def _post_message(self, message: StateMessage) -> None:
        """Post a message to the connected Textual app.

        Args:
            message: The message to post.
        """
        if self._app is not None:
            self._app.post_message(message)

    def subscribe(self, event: StateEvent, callback: Callable[..., Any]) -> None:
        """Register callback for state event.

        Args:
            event: The event type to subscribe to.
            callback: Function to call when event occurs.
        """
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(callback)

    def unsubscribe(self, event: StateEvent, callback: Callable[..., Any]) -> None:
        """Remove callback from event.

        Args:
            event: The event type to unsubscribe from.
            callback: The callback function to remove.
        """
        if event in self._listeners:
            try:
                self._listeners[event].remove(callback)
            except ValueError:
                pass

    def emit(self, event: StateEvent, **kwargs: Any) -> None:
        """Dispatch event to all subscribers.

        Args:
            event: The event type to dispatch.
            **kwargs: Additional arguments to pass to callbacks.
        """
        for callback in self._listeners.get(event, []):
            try:
                callback(**kwargs)
            except Exception:
                # Log but don't crash on subscriber errors
                pass

    @property
    def has_active_sessions(self) -> bool:
        """Check if any sessions are currently active."""
        return any(s.is_active for s in self.sessions.values())

    @property
    def active_project(self) -> Project | None:
        """Get currently active project."""
        if self.active_project_id:
            return self.projects.get(self.active_project_id)
        return None

    async def load_config(self) -> None:
        """Load configuration from disk."""
        from iterm_controller.config import load_global_config

        self.config = load_global_config()

        # Load projects from config
        if self.config.projects:
            self.projects = {p.id: p for p in self.config.projects}

        self.emit(StateEvent.CONFIG_CHANGED, config=self.config)
        self._post_message(ConfigChanged(self.config))

    async def open_project(self, project_id: str) -> None:
        """Open a project and spawn its sessions.

        Args:
            project_id: The ID of the project to open.
        """
        if project_id not in self.projects:
            return

        project = self.projects[project_id]
        project.is_open = True
        self.active_project_id = project_id
        self.emit(StateEvent.PROJECT_OPENED, project=project)
        self._post_message(ProjectOpened(project))

    async def close_project(self, project_id: str) -> None:
        """Close a project and its sessions.

        Args:
            project_id: The ID of the project to close.
        """
        if project_id in self.projects:
            self.projects[project_id].is_open = False

        self.emit(StateEvent.PROJECT_CLOSED, project_id=project_id)
        self._post_message(ProjectClosed(project_id))

        if self.active_project_id == project_id:
            self.active_project_id = None

    def update_project(self, project: Project, persist: bool = True) -> None:
        """Update a project in the state.

        This updates the project in the in-memory state and optionally
        persists to the config file. Use this for incremental updates
        like last_mode changes that should survive app restarts.

        Args:
            project: The project with updated fields.
            persist: If True, save the updated config to disk.
        """
        self.projects[project.id] = project

        # Also update the project in the config and persist
        if persist and self.config:
            # Find and update the project in config.projects
            for i, config_project in enumerate(self.config.projects):
                if config_project.id == project.id:
                    self.config.projects[i] = project
                    break
            else:
                # Project not found in config, add it
                self.config.projects.append(project)

            # Save to disk
            from iterm_controller.config import save_global_config

            try:
                save_global_config(self.config)
            except Exception:
                # Log but don't crash on save errors
                pass

    def add_session(self, session: ManagedSession) -> None:
        """Add a session to the state.

        Args:
            session: The managed session to add.
        """
        self.sessions[session.id] = session
        self.emit(StateEvent.SESSION_SPAWNED, session=session)
        self._post_message(SessionSpawned(session))

    def remove_session(self, session_id: str) -> None:
        """Remove a session from the state.

        Args:
            session_id: The ID of the session to remove.
        """
        if session_id in self.sessions:
            session = self.sessions.pop(session_id)
            self.emit(StateEvent.SESSION_CLOSED, session=session)
            self._post_message(SessionClosed(session))

    def update_session_status(self, session_id: str, **kwargs: Any) -> None:
        """Update session status.

        Args:
            session_id: The ID of the session to update.
            **kwargs: Attributes to update on the session.
        """
        if session_id in self.sessions:
            session = self.sessions[session_id]
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)
            self.emit(StateEvent.SESSION_STATUS_CHANGED, session=session)
            self._post_message(SessionStatusChanged(session))

    def get_sessions_for_project(self, project_id: str) -> list[ManagedSession]:
        """Get all sessions for a project.

        Args:
            project_id: The project ID to filter by.

        Returns:
            List of managed sessions for the project.
        """
        return [s for s in self.sessions.values() if s.project_id == project_id]

    def set_plan(self, project_id: str, plan: Plan) -> None:
        """Set or update the plan for a project.

        Args:
            project_id: The project ID.
            plan: The parsed plan.
        """
        self.plans[project_id] = plan
        self.emit(StateEvent.PLAN_RELOADED, project_id=project_id, plan=plan)
        self._post_message(PlanReloaded(project_id, plan))

    def get_plan(self, project_id: str) -> Plan | None:
        """Get the plan for a project.

        Args:
            project_id: The project ID.

        Returns:
            The plan if one exists, None otherwise.
        """
        return self.plans.get(project_id)

    def notify_plan_conflict(self, project_id: str, new_plan: Plan) -> None:
        """Notify about a PLAN.md conflict.

        Args:
            project_id: The project ID.
            new_plan: The new plan from the external change.
        """
        self.emit(StateEvent.PLAN_CONFLICT, project_id=project_id, new_plan=new_plan)
        self._post_message(PlanConflict(project_id, new_plan))

    def update_task_status(self, project_id: str, task_id: str) -> None:
        """Notify about a task status change.

        Args:
            project_id: The project ID.
            task_id: The task that changed.
        """
        self.emit(StateEvent.TASK_STATUS_CHANGED, project_id=project_id, task_id=task_id)
        self._post_message(TaskStatusChanged(task_id, project_id))

    def update_health_status(
        self, project_id: str, check_name: str, status: HealthStatus
    ) -> None:
        """Notify about a health check status change.

        Args:
            project_id: The project ID.
            check_name: The name of the health check.
            status: The new health status.
        """
        # Store the status
        if project_id not in self._health_statuses:
            self._health_statuses[project_id] = {}
        self._health_statuses[project_id][check_name] = status

        self.emit(
            StateEvent.HEALTH_STATUS_CHANGED,
            project_id=project_id,
            check_name=check_name,
            status=status.value,
        )
        self._post_message(HealthStatusChanged(project_id, check_name, status.value))

    def get_health_statuses(self, project_id: str) -> dict[str, HealthStatus]:
        """Get all health check statuses for a project.

        Args:
            project_id: The project ID.

        Returns:
            Dictionary mapping check names to their health status.
        """
        return self._health_statuses.get(project_id, {}).copy()

    def clear_health_statuses(self, project_id: str) -> None:
        """Clear all health check statuses for a project.

        Args:
            project_id: The project ID.
        """
        self._health_statuses.pop(project_id, None)

    def update_workflow_stage(self, project_id: str, stage: str) -> None:
        """Notify about a workflow stage change.

        Args:
            project_id: The project ID.
            stage: The new workflow stage.
        """
        self.emit(
            StateEvent.WORKFLOW_STAGE_CHANGED,
            project_id=project_id,
            stage=stage,
        )
        self._post_message(WorkflowStageChanged(project_id, stage))

    # =========================================================================
    # TEST_PLAN.md Management
    # =========================================================================

    def set_test_plan(self, project_id: str, test_plan: TestPlan) -> None:
        """Set or update the test plan for a project.

        Args:
            project_id: The project ID.
            test_plan: The parsed test plan.
        """
        self.test_plans[project_id] = test_plan
        self.emit(StateEvent.TEST_PLAN_RELOADED, project_id=project_id, test_plan=test_plan)
        self._post_message(TestPlanReloaded(project_id, test_plan))

    def get_test_plan(self, project_id: str) -> TestPlan | None:
        """Get the test plan for a project.

        Args:
            project_id: The project ID.

        Returns:
            The test plan if one exists, None otherwise.
        """
        return self.test_plans.get(project_id)

    def clear_test_plan(self, project_id: str) -> None:
        """Clear the test plan for a project (e.g., when file is deleted).

        Args:
            project_id: The project ID.
        """
        self.test_plans.pop(project_id, None)
        self.emit(StateEvent.TEST_PLAN_DELETED, project_id=project_id)
        self._post_message(TestPlanDeleted(project_id))

    def notify_test_plan_conflict(self, project_id: str, new_plan: TestPlan) -> None:
        """Notify about a TEST_PLAN.md conflict.

        Args:
            project_id: The project ID.
            new_plan: The new plan from the external change.
        """
        self.emit(StateEvent.TEST_PLAN_CONFLICT, project_id=project_id, new_plan=new_plan)
        self._post_message(TestPlanConflict(project_id, new_plan))

    def update_test_step_status(self, project_id: str, step_id: str) -> None:
        """Notify about a test step status change.

        Args:
            project_id: The project ID.
            step_id: The step that changed.
        """
        self.emit(StateEvent.TEST_STEP_UPDATED, project_id=project_id, step_id=step_id)
        self._post_message(TestStepUpdated(project_id, step_id))
