"""Main AppState class composing focused state managers.

This module provides the unified AppState interface while delegating
to focused state managers for better organization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

from iterm_controller.models import (
    AppConfig,
    HealthStatus,
    ManagedSession,
    Plan,
    Project,
    TestPlan,
)
from iterm_controller.state.events import (
    ConfigChanged,
    StateEvent,
)
from iterm_controller.state.health_manager import HealthStateManager
from iterm_controller.state.plan_manager import PlanStateManager
from iterm_controller.state.project_manager import ProjectStateManager
from iterm_controller.state.session_manager import SessionStateManager
from iterm_controller.state.snapshot import StateSnapshot

if TYPE_CHECKING:
    from textual.app import App


@dataclass
class AppState:
    """Reactive application state with event dispatch.

    This class composes focused state managers for better organization while
    maintaining a unified public API for backwards compatibility.

    The class provides two mechanisms for notifying about state changes:

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

    # Configuration
    config: AppConfig | None = None

    # Internal state managers
    _project_manager: ProjectStateManager = field(
        default_factory=ProjectStateManager, repr=False
    )
    _session_manager: SessionStateManager = field(
        default_factory=SessionStateManager, repr=False
    )
    _plan_manager: PlanStateManager = field(
        default_factory=PlanStateManager, repr=False
    )
    _health_manager: HealthStateManager = field(
        default_factory=HealthStateManager, repr=False
    )

    # Event subscribers (legacy callback mechanism)
    _listeners: dict[StateEvent, list[Callable[..., Any]]] = field(
        default_factory=lambda: {e: [] for e in StateEvent}
    )

    # Textual app reference for posting messages
    _app: App | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Set up manager emit callbacks after initialization."""
        self._project_manager.set_emit_callback(self._emit_from_manager)
        self._session_manager.set_emit_callback(self._emit_from_manager)
        self._plan_manager.set_emit_callback(self._emit_from_manager)
        self._health_manager.set_emit_callback(self._emit_from_manager)

    def _emit_from_manager(self, event: StateEvent, kwargs: dict[str, Any]) -> None:
        """Handle emit calls from state managers."""
        self.emit(event, **kwargs)

    # =========================================================================
    # Properties delegating to state managers (backwards compatibility)
    # =========================================================================

    @property
    def projects(self) -> dict[str, Project]:
        """Get all projects (delegated to ProjectStateManager)."""
        return self._project_manager.projects

    @projects.setter
    def projects(self, value: dict[str, Project]) -> None:
        """Set projects dictionary."""
        self._project_manager.projects = value

    @property
    def active_project_id(self) -> str | None:
        """Get active project ID (delegated to ProjectStateManager)."""
        return self._project_manager.active_project_id

    @active_project_id.setter
    def active_project_id(self, value: str | None) -> None:
        """Set active project ID."""
        self._project_manager.active_project_id = value

    @property
    def active_project(self) -> Project | None:
        """Get currently active project."""
        return self._project_manager.active_project

    @property
    def sessions(self) -> dict[str, ManagedSession]:
        """Get all sessions (delegated to SessionStateManager)."""
        return self._session_manager.sessions

    @sessions.setter
    def sessions(self, value: dict[str, ManagedSession]) -> None:
        """Set sessions dictionary."""
        self._session_manager.sessions = value

    @property
    def has_active_sessions(self) -> bool:
        """Check if any sessions are currently active."""
        return self._session_manager.has_active_sessions

    @property
    def plans(self) -> dict[str, Plan]:
        """Get all plans (delegated to PlanStateManager)."""
        return self._plan_manager.plans

    @plans.setter
    def plans(self, value: dict[str, Plan]) -> None:
        """Set plans dictionary."""
        self._plan_manager.plans = value

    @property
    def test_plans(self) -> dict[str, TestPlan]:
        """Get all test plans (delegated to PlanStateManager)."""
        return self._plan_manager.test_plans

    @test_plans.setter
    def test_plans(self, value: dict[str, TestPlan]) -> None:
        """Set test plans dictionary."""
        self._plan_manager.test_plans = value

    # =========================================================================
    # Connection and Event System
    # =========================================================================

    def connect_app(self, app: App) -> None:
        """Connect to a Textual App for message posting.

        Args:
            app: The Textual App instance to post messages to.
        """
        self._app = app
        # Connect managers to app for message posting
        self._project_manager.connect_app(app)
        self._session_manager.connect_app(app)
        self._plan_manager.connect_app(app)
        self._health_manager.connect_app(app)

    def _post_message(self, message: Any) -> None:
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

    # =========================================================================
    # Config Loading
    # =========================================================================

    async def load_config(self) -> None:
        """Load configuration from disk."""
        from iterm_controller.config import load_global_config

        self.config = load_global_config()

        # Load projects from config into the project manager
        if self.config.projects:
            self._project_manager.load_projects(self.config.projects)

        self.emit(StateEvent.CONFIG_CHANGED, config=self.config)
        self._post_message(ConfigChanged(self.config))

    # =========================================================================
    # Project Operations (delegated to ProjectStateManager)
    # =========================================================================

    async def open_project(self, project_id: str) -> None:
        """Open a project and spawn its sessions.

        Args:
            project_id: The ID of the project to open.
        """
        await self._project_manager.open_project(project_id)

    async def close_project(self, project_id: str) -> None:
        """Close a project and its sessions.

        Args:
            project_id: The ID of the project to close.
        """
        await self._project_manager.close_project(project_id)

    def update_project(self, project: Project, persist: bool = True) -> None:
        """Update a project in the state.

        Args:
            project: The project with updated fields.
            persist: If True, save the updated config to disk.
        """
        from iterm_controller.config import save_global_config

        self._project_manager.update_project(
            project,
            persist=persist,
            config=self.config,
            save_callback=save_global_config if persist else None,
        )

    # =========================================================================
    # Session Operations (delegated to SessionStateManager)
    # =========================================================================

    def add_session(self, session: ManagedSession) -> None:
        """Add a session to the state.

        Args:
            session: The managed session to add.
        """
        self._session_manager.add_session(session)

    def remove_session(self, session_id: str) -> None:
        """Remove a session from the state.

        Args:
            session_id: The ID of the session to remove.
        """
        self._session_manager.remove_session(session_id)

    def update_session_status(self, session_id: str, **kwargs: Any) -> None:
        """Update session status.

        Args:
            session_id: The ID of the session to update.
            **kwargs: Attributes to update on the session.
        """
        self._session_manager.update_session_status(session_id, **kwargs)

    def get_sessions_for_project(self, project_id: str) -> list[ManagedSession]:
        """Get all sessions for a project.

        Args:
            project_id: The project ID to filter by.

        Returns:
            List of managed sessions for the project.
        """
        return self._session_manager.get_sessions_for_project(project_id)

    # =========================================================================
    # Plan Operations (delegated to PlanStateManager)
    # =========================================================================

    def set_plan(self, project_id: str, plan: Plan) -> None:
        """Set or update the plan for a project.

        Args:
            project_id: The project ID.
            plan: The parsed plan.
        """
        self._plan_manager.set_plan(project_id, plan)

    def get_plan(self, project_id: str) -> Plan | None:
        """Get the plan for a project.

        Args:
            project_id: The project ID.

        Returns:
            The plan if one exists, None otherwise.
        """
        return self._plan_manager.get_plan(project_id)

    def notify_plan_conflict(self, project_id: str, new_plan: Plan) -> None:
        """Notify about a PLAN.md conflict.

        Args:
            project_id: The project ID.
            new_plan: The new plan from the external change.
        """
        self._plan_manager.notify_plan_conflict(project_id, new_plan)

    def update_task_status(self, project_id: str, task_id: str) -> None:
        """Notify about a task status change.

        Args:
            project_id: The project ID.
            task_id: The task that changed.
        """
        self._plan_manager.update_task_status(project_id, task_id)

    def update_workflow_stage(self, project_id: str, stage: str) -> None:
        """Notify about a workflow stage change.

        Args:
            project_id: The project ID.
            stage: The new workflow stage.
        """
        self._plan_manager.update_workflow_stage(project_id, stage)

    # =========================================================================
    # Test Plan Operations (delegated to PlanStateManager)
    # =========================================================================

    def set_test_plan(self, project_id: str, test_plan: TestPlan) -> None:
        """Set or update the test plan for a project.

        Args:
            project_id: The project ID.
            test_plan: The parsed test plan.
        """
        self._plan_manager.set_test_plan(project_id, test_plan)

    def get_test_plan(self, project_id: str) -> TestPlan | None:
        """Get the test plan for a project.

        Args:
            project_id: The project ID.

        Returns:
            The test plan if one exists, None otherwise.
        """
        return self._plan_manager.get_test_plan(project_id)

    def clear_test_plan(self, project_id: str) -> None:
        """Clear the test plan for a project (e.g., when file is deleted).

        Args:
            project_id: The project ID.
        """
        self._plan_manager.clear_test_plan(project_id)

    def notify_test_plan_conflict(self, project_id: str, new_plan: TestPlan) -> None:
        """Notify about a TEST_PLAN.md conflict.

        Args:
            project_id: The project ID.
            new_plan: The new plan from the external change.
        """
        self._plan_manager.notify_test_plan_conflict(project_id, new_plan)

    def update_test_step_status(self, project_id: str, step_id: str) -> None:
        """Notify about a test step status change.

        Args:
            project_id: The project ID.
            step_id: The step that changed.
        """
        self._plan_manager.update_test_step_status(project_id, step_id)

    # =========================================================================
    # Health Status Operations (delegated to HealthStateManager)
    # =========================================================================

    def update_health_status(
        self, project_id: str, check_name: str, status: HealthStatus
    ) -> None:
        """Notify about a health check status change.

        Args:
            project_id: The project ID.
            check_name: The name of the health check.
            status: The new health status.
        """
        self._health_manager.update_health_status(project_id, check_name, status)

    def get_health_statuses(self, project_id: str) -> dict[str, HealthStatus]:
        """Get all health check statuses for a project.

        Args:
            project_id: The project ID.

        Returns:
            Dictionary mapping check names to their health status.
        """
        return self._health_manager.get_health_statuses(project_id)

    def clear_health_statuses(self, project_id: str) -> None:
        """Clear all health check statuses for a project.

        Args:
            project_id: The project ID.
        """
        self._health_manager.clear_health_statuses(project_id)

    # =========================================================================
    # State Query (External Observation)
    # =========================================================================

    def to_snapshot(self) -> StateSnapshot:
        """Create an immutable snapshot of the current state.

        Use this method for external observation by agents, CLI tools, or
        other integrations that need to query state without TUI context.

        Returns:
            A StateSnapshot containing a copy of all state data.

        Example:
            state = AppState()
            await state.load_config()
            snapshot = state.to_snapshot()
            for project in snapshot.projects.values():
                print(f"{project.name}: {len(snapshot.get_sessions_for_project(project.id))} sessions")
        """
        return StateSnapshot(
            projects=dict(self.projects),
            active_project_id=self.active_project_id,
            sessions=dict(self.sessions),
            plans=dict(self.plans),
            test_plans=dict(self.test_plans),
            health_statuses=self._health_manager.get_all_statuses(),
            config=self.config,
        )
