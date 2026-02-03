"""Main AppState class composing focused state managers.

This module provides the unified AppState interface while delegating
to focused state managers for better organization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from iterm_controller.models import (
    AppConfig,
    GitStatus,
    HealthStatus,
    ManagedSession,
    Plan,
    Project,
    TestPlan,
)
from iterm_controller.state.events import ConfigChanged
from iterm_controller.state.git_manager import GitStateManager
from iterm_controller.state.health_manager import HealthStateManager
from iterm_controller.state.plan_manager import PlanStateManager
from iterm_controller.state.project_manager import ProjectStateManager
from iterm_controller.state.review_manager import ReviewStateManager
from iterm_controller.state.session_manager import SessionStateManager
from iterm_controller.state.snapshot import StateSnapshot

if TYPE_CHECKING:
    from textual.app import App


@dataclass
class AppState:
    """Reactive application state with event dispatch.

    This class composes focused state managers for better organization while
    maintaining a unified public API for backwards compatibility.

    When connected to a Textual App via `connect_app()`, state changes
    automatically post Messages that widgets can handle with `on_*` methods.

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
    _git_manager: GitStateManager = field(
        default_factory=GitStateManager, repr=False
    )
    _review_manager: ReviewStateManager = field(
        default_factory=ReviewStateManager, repr=False
    )

    # Textual app reference for posting messages
    _app: App | None = field(default=None, repr=False)

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
        self._git_manager.connect_app(app)
        self._review_manager.connect_app(app)

    def _post_message(self, message: Any) -> None:
        """Post a message to the connected Textual app.

        Args:
            message: The message to post.
        """
        if self._app is not None:
            self._app.post_message(message)

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

    def remove_project(self, project_id: str) -> bool:
        """Remove a project from the state.

        Args:
            project_id: The ID of the project to remove.

        Returns:
            True if project was removed, False if not found.
        """
        from iterm_controller.config import save_global_config

        return self._project_manager.remove_project(
            project_id,
            config=self.config,
            save_callback=save_global_config,
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
    # Git Operations (delegated to GitStateManager)
    # =========================================================================

    @property
    def git(self) -> GitStateManager:
        """Get the git state manager.

        Returns:
            The GitStateManager instance.
        """
        return self._git_manager

    async def refresh_git_status(
        self, project_id: str, use_cache: bool = True
    ) -> GitStatus | None:
        """Refresh git status for a project.

        Args:
            project_id: The project ID.
            use_cache: Whether to use cached status if available.

        Returns:
            The refreshed GitStatus, or None if project not found.
        """
        return await self._git_manager.refresh(project_id, use_cache=use_cache)

    async def stage_git_files(
        self, project_id: str, files: list[str] | None = None
    ) -> bool:
        """Stage files for a project.

        Args:
            project_id: The project ID.
            files: List of files to stage, or None to stage all.

        Returns:
            True if successful, False otherwise.
        """
        return await self._git_manager.stage_files(project_id, files)

    async def unstage_git_files(
        self, project_id: str, files: list[str] | None = None
    ) -> bool:
        """Unstage files for a project.

        Args:
            project_id: The project ID.
            files: List of files to unstage, or None to unstage all.

        Returns:
            True if successful, False otherwise.
        """
        return await self._git_manager.unstage_files(project_id, files)

    async def git_commit(self, project_id: str, message: str) -> str | None:
        """Create a git commit for a project.

        Args:
            project_id: The project ID.
            message: The commit message.

        Returns:
            The SHA of the created commit, or None on failure.
        """
        return await self._git_manager.commit(project_id, message)

    async def git_push(
        self,
        project_id: str,
        remote: str = "origin",
        branch: str | None = None,
        force: bool = False,
        set_upstream: bool = False,
    ) -> bool:
        """Push to remote for a project.

        Args:
            project_id: The project ID.
            remote: The remote name.
            branch: The branch to push, or None for current branch.
            force: Whether to force push.
            set_upstream: Whether to set upstream tracking.

        Returns:
            True if successful, False otherwise.
        """
        return await self._git_manager.push(
            project_id,
            remote=remote,
            branch=branch,
            force=force,
            set_upstream=set_upstream,
        )

    async def git_pull(
        self,
        project_id: str,
        remote: str = "origin",
        branch: str | None = None,
    ) -> bool:
        """Pull from remote for a project.

        Args:
            project_id: The project ID.
            remote: The remote name.
            branch: The branch to pull, or None for current branch.

        Returns:
            True if successful, False otherwise.
        """
        return await self._git_manager.pull(project_id, remote=remote, branch=branch)

    def get_git_status(self, project_id: str) -> GitStatus | None:
        """Get cached git status for a project.

        Args:
            project_id: The project ID.

        Returns:
            The cached GitStatus, or None if not cached.
        """
        return self._git_manager.get(project_id)

    def clear_git_status(self, project_id: str) -> None:
        """Clear cached git status for a project.

        Args:
            project_id: The project ID.
        """
        self._git_manager.clear(project_id)

    # =========================================================================
    # Review Operations (delegated to ReviewStateManager)
    # =========================================================================

    @property
    def reviews(self) -> ReviewStateManager:
        """Get the review state manager.

        Returns:
            The ReviewStateManager instance.
        """
        return self._review_manager

    async def start_review(
        self, project_id: str, task_id: str
    ) -> "TaskReview | None":
        """Start a review for a task.

        Args:
            project_id: The project ID.
            task_id: The task ID to review.

        Returns:
            The TaskReview result, or None if the review couldn't be started.
        """
        from iterm_controller.models import TaskReview

        return await self._review_manager.start_review(project_id, task_id)

    def get_active_review(self, task_id: str) -> "TaskReview | None":
        """Get the active review for a task.

        Args:
            task_id: The task ID.

        Returns:
            The active TaskReview if one exists, None otherwise.
        """
        return self._review_manager.get_active_review(task_id)

    def is_reviewing(self, task_id: str) -> bool:
        """Check if a task is currently being reviewed.

        Args:
            task_id: The task ID.

        Returns:
            True if a review is in progress.
        """
        return self._review_manager.is_reviewing(task_id)

    def get_all_active_reviews(self) -> "list[TaskReview]":
        """Get all currently active reviews.

        Returns:
            List of all active TaskReview objects.
        """
        from iterm_controller.models import TaskReview

        return self._review_manager.get_all_active_reviews()

    def clear_reviews(self) -> None:
        """Clear all active reviews."""
        self._review_manager.clear()

    def clear_reviews_for_project(self, project_id: str) -> None:
        """Clear active reviews for a specific project.

        Args:
            project_id: The project ID.
        """
        self._review_manager.clear_for_project(project_id)

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
            git_statuses=self._git_manager.get_all_statuses(),
            config=self.config,
        )
