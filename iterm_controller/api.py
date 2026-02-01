"""Public API for programmatic access to iterm-controller.

This module exposes core operations as async functions, enabling agents and
external tools to perform all actions available in the TUI without requiring
a graphical interface.

Usage:
    from iterm_controller.api import ItermControllerAPI

    async def main():
        api = ItermControllerAPI()
        await api.initialize()

        # List projects
        projects = await api.list_projects()

        # Open a project
        await api.open_project("my-project")

        # Spawn a session
        result = await api.spawn_session("my-project", "dev-server")

        # Claim a task
        await api.claim_task("my-project", "2.1")

        # Clean up
        await api.shutdown()
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import (
    load_global_config,
    save_global_config,
)
from .exceptions import (
    ConfigLoadError,
    ItermConnectionError,
    ItermNotConnectedError,
    PlanParseError,
    PlanWriteError,
    TestPlanParseError,
    TestPlanWriteError,
)
from .iterm_api import (
    CloseResult,
    ItermController,
    LayoutSpawnResult,
    SessionSpawner,
    SessionTerminator,
    SpawnResult,
    WindowLayoutManager,
    WindowLayoutSpawner,
)
from .models import (
    AppConfig,
    AttentionState,
    ManagedSession,
    Plan,
    Project,
    SessionTemplate,
    Task,
    TaskStatus,
    TestPlan,
    TestStatus,
    TestStep,
    WindowLayout,
    WorkflowMode,
)
from .plan_parser import PlanParser, PlanUpdater
from .plan_watcher import PlanWatcher, PlanWriteQueue
from .state import AppState, StateSnapshot
from .test_plan_parser import TestPlanParser, TestPlanUpdater

logger = logging.getLogger(__name__)


# =============================================================================
# Result Types
# =============================================================================


@dataclass
class APIResult:
    """Base result type for API operations."""

    success: bool
    error: str | None = None

    @classmethod
    def ok(cls) -> "APIResult":
        return cls(success=True)

    @classmethod
    def fail(cls, error: str) -> "APIResult":
        return cls(success=False, error=error)


@dataclass
class SessionResult(APIResult):
    """Result of a session operation."""

    session: ManagedSession | None = None
    spawn_result: SpawnResult | None = None


@dataclass
class TaskResult(APIResult):
    """Result of a task operation."""

    task: Task | None = None


@dataclass
class TestStepResult(APIResult):
    """Result of a test step operation."""

    step: TestStep | None = None


@dataclass
class ProjectResult(APIResult):
    """Result of a project operation."""

    project: Project | None = None


# =============================================================================
# Main API Class
# =============================================================================


class ItermControllerAPI:
    """Programmatic API for iterm-controller operations.

    This class provides async methods for all core operations that can be
    performed in the TUI, enabling agents and external tools to interact
    with iterm-controller without a graphical interface.

    Example:
        api = ItermControllerAPI()
        await api.initialize()
        await api.spawn_session("my-project", "dev-server")
        await api.shutdown()
    """

    def __init__(self) -> None:
        """Initialize the API (not yet connected)."""
        self._initialized = False
        self._state: AppState = AppState()
        self._iterm: ItermController = ItermController()
        self._spawner: SessionSpawner | None = None
        self._terminator: SessionTerminator | None = None
        self._layout_manager: WindowLayoutManager | None = None
        self._layout_spawner: WindowLayoutSpawner | None = None
        self._plan_watchers: dict[str, PlanWatcher] = {}
        self._write_queues: dict[str, PlanWriteQueue] = {}

    @property
    def is_initialized(self) -> bool:
        """Check if the API has been initialized."""
        return self._initialized

    @property
    def is_connected(self) -> bool:
        """Check if connected to iTerm2."""
        return self._iterm.is_connected

    @property
    def state(self) -> AppState:
        """Get the current application state."""
        return self._state

    async def initialize(self, connect_iterm: bool = True) -> APIResult:
        """Initialize the API.

        Loads configuration and optionally connects to iTerm2.

        Args:
            connect_iterm: If True, establish iTerm2 connection.

        Returns:
            APIResult indicating success or failure.
        """
        try:
            # Load configuration
            await self._state.load_config()

            # Initialize iTerm2 components
            self._spawner = SessionSpawner(self._iterm)
            self._terminator = SessionTerminator(self._iterm)
            self._layout_manager = WindowLayoutManager(self._iterm)
            self._layout_spawner = WindowLayoutSpawner(self._iterm, self._spawner)

            # Load layouts from config
            if self._state.config and self._state.config.window_layouts:
                self._layout_manager.load_from_config(self._state.config.window_layouts)

            # Connect to iTerm2
            if connect_iterm:
                try:
                    await self._iterm.connect()
                except ItermConnectionError as e:
                    logger.warning("Could not connect to iTerm2: %s", e)
                    # Continue without iTerm2 connection

            self._initialized = True
            logger.info("ItermControllerAPI initialized")
            return APIResult.ok()

        except ConfigLoadError as e:
            logger.error("Failed to load config: %s", e)
            return APIResult.fail(str(e))
        except Exception as e:
            logger.error("Failed to initialize API: %s", e)
            return APIResult.fail(str(e))

    async def shutdown(self, close_sessions: bool = False) -> APIResult:
        """Shutdown the API.

        Args:
            close_sessions: If True, close all managed sessions.

        Returns:
            APIResult indicating success or failure.
        """
        try:
            # Stop all plan watchers
            for watcher in self._plan_watchers.values():
                await watcher.stop_watching()
            self._plan_watchers.clear()
            self._write_queues.clear()

            # Close sessions if requested
            if close_sessions and self._terminator and self._spawner:
                sessions = list(self._spawner.managed_sessions.values())
                await self._terminator.close_all_managed(
                    sessions, self._spawner, force=False
                )

            # Disconnect from iTerm2
            await self._iterm.disconnect()

            self._initialized = False
            logger.info("ItermControllerAPI shutdown complete")
            return APIResult.ok()

        except Exception as e:
            logger.error("Error during shutdown: %s", e)
            return APIResult.fail(str(e))

    # =========================================================================
    # Configuration Operations
    # =========================================================================

    def get_config(self) -> AppConfig | None:
        """Get the current application configuration.

        Returns:
            The AppConfig if loaded, None otherwise.
        """
        return self._state.config

    async def save_config(self) -> APIResult:
        """Save the current configuration to disk.

        Returns:
            APIResult indicating success or failure.
        """
        try:
            if self._state.config:
                save_global_config(self._state.config)
                return APIResult.ok()
            return APIResult.fail("No configuration loaded")
        except Exception as e:
            return APIResult.fail(str(e))

    # =========================================================================
    # Project Operations
    # =========================================================================

    async def list_projects(self) -> list[Project]:
        """List all configured projects.

        Returns:
            List of all projects in the configuration.
        """
        return list(self._state.projects.values())

    async def get_project(self, project_id: str) -> Project | None:
        """Get a project by ID.

        Args:
            project_id: The project's unique identifier.

        Returns:
            The Project if found, None otherwise.
        """
        return self._state.projects.get(project_id)

    async def open_project(self, project_id: str) -> ProjectResult:
        """Open a project.

        Loads the project's PLAN.md and starts file watching.

        Args:
            project_id: The project's unique identifier.

        Returns:
            ProjectResult with the opened project.
        """
        project = self._state.projects.get(project_id)
        if not project:
            return ProjectResult(success=False, error=f"Project not found: {project_id}")

        try:
            await self._state.open_project(project_id)

            # Load and watch PLAN.md
            await self._load_plan_for_project(project)

            return ProjectResult(success=True, project=project)

        except Exception as e:
            logger.error("Failed to open project %s: %s", project_id, e)
            return ProjectResult(success=False, error=str(e))

    async def close_project(self, project_id: str) -> APIResult:
        """Close a project.

        Stops file watching and optionally closes sessions.

        Args:
            project_id: The project's unique identifier.

        Returns:
            APIResult indicating success or failure.
        """
        try:
            # Stop plan watcher
            if project_id in self._plan_watchers:
                await self._plan_watchers[project_id].stop_watching()
                del self._plan_watchers[project_id]

            if project_id in self._write_queues:
                self._write_queues[project_id].cancel()
                del self._write_queues[project_id]

            await self._state.close_project(project_id)
            return APIResult.ok()

        except Exception as e:
            logger.error("Failed to close project %s: %s", project_id, e)
            return APIResult.fail(str(e))

    async def create_project(
        self,
        project_id: str,
        name: str,
        path: str,
        template_id: str | None = None,
        jira_ticket: str | None = None,
    ) -> ProjectResult:
        """Create a new project.

        Args:
            project_id: Unique identifier for the project.
            name: Display name.
            path: Absolute path to project root.
            template_id: Optional template ID to use.
            jira_ticket: Optional Jira ticket number.

        Returns:
            ProjectResult with the created project.
        """
        if project_id in self._state.projects:
            return ProjectResult(
                success=False, error=f"Project already exists: {project_id}"
            )

        try:
            project = Project(
                id=project_id,
                name=name,
                path=path,
                template_id=template_id,
                jira_ticket=jira_ticket,
            )

            self._state.projects[project_id] = project

            # Add to config and save
            if self._state.config:
                self._state.config.projects.append(project)
                save_global_config(self._state.config)

            return ProjectResult(success=True, project=project)

        except Exception as e:
            logger.error("Failed to create project: %s", e)
            return ProjectResult(success=False, error=str(e))

    async def delete_project(self, project_id: str) -> APIResult:
        """Delete a project from the configuration.

        Does not delete files on disk.

        Args:
            project_id: The project's unique identifier.

        Returns:
            APIResult indicating success or failure.
        """
        if project_id not in self._state.projects:
            return APIResult.fail(f"Project not found: {project_id}")

        project = self._state.projects[project_id]
        if project.is_open:
            return APIResult.fail("Cannot delete an open project")

        try:
            del self._state.projects[project_id]

            # Remove from config and save
            if self._state.config:
                self._state.config.projects = [
                    p for p in self._state.config.projects if p.id != project_id
                ]
                save_global_config(self._state.config)

            return APIResult.ok()

        except Exception as e:
            logger.error("Failed to delete project: %s", e)
            return APIResult.fail(str(e))

    async def update_project_mode(
        self, project_id: str, mode: WorkflowMode
    ) -> APIResult:
        """Update a project's workflow mode.

        Args:
            project_id: The project's unique identifier.
            mode: The new workflow mode.

        Returns:
            APIResult indicating success or failure.
        """
        project = self._state.projects.get(project_id)
        if not project:
            return APIResult.fail(f"Project not found: {project_id}")

        try:
            project.last_mode = mode
            self._state.update_project(project, persist=True)
            return APIResult.ok()
        except Exception as e:
            return APIResult.fail(str(e))

    # =========================================================================
    # Session Operations
    # =========================================================================

    async def list_sessions(
        self, project_id: str | None = None
    ) -> list[ManagedSession]:
        """List managed sessions.

        Args:
            project_id: If provided, filter to sessions for this project.

        Returns:
            List of managed sessions.
        """
        if project_id:
            return self._state.get_sessions_for_project(project_id)
        return list(self._state.sessions.values())

    async def get_session(self, session_id: str) -> ManagedSession | None:
        """Get a session by ID.

        Args:
            session_id: The session's unique identifier.

        Returns:
            The ManagedSession if found, None otherwise.
        """
        return self._state.sessions.get(session_id)

    async def spawn_session(
        self,
        project_id: str,
        template_id: str,
        task_id: str | None = None,
    ) -> SessionResult:
        """Spawn a new terminal session.

        Args:
            project_id: The project to spawn the session for.
            template_id: The session template to use.
            task_id: Optional task ID to link to this session.

        Returns:
            SessionResult with the spawned session.
        """
        if not self._iterm.is_connected:
            return SessionResult(success=False, error="Not connected to iTerm2")

        project = self._state.projects.get(project_id)
        if not project:
            return SessionResult(success=False, error=f"Project not found: {project_id}")

        # Find template
        template = self._get_session_template(template_id)
        if not template:
            return SessionResult(
                success=False, error=f"Template not found: {template_id}"
            )

        if not self._spawner:
            return SessionResult(success=False, error="Spawner not initialized")

        try:
            result = await self._spawner.spawn_session(template, project)

            if result.success:
                session = self._spawner.get_session(result.session_id)
                if session:
                    # Link task if provided
                    if task_id:
                        session.metadata["task_id"] = task_id

                    # Add to state
                    self._state.add_session(session)

                    return SessionResult(
                        success=True, session=session, spawn_result=result
                    )

            return SessionResult(
                success=False, error=result.error or "Unknown spawn error"
            )

        except Exception as e:
            logger.error("Failed to spawn session: %s", e)
            return SessionResult(success=False, error=str(e))

    async def kill_session(self, session_id: str, force: bool = False) -> APIResult:
        """Kill a terminal session.

        Args:
            session_id: The session to terminate.
            force: If True, force-close without graceful shutdown.

        Returns:
            APIResult indicating success or failure.
        """
        if not self._iterm.is_connected:
            return APIResult.fail("Not connected to iTerm2")

        session = self._state.sessions.get(session_id)
        if not session:
            return APIResult.fail(f"Session not found: {session_id}")

        if not self._terminator or not self._spawner:
            return APIResult.fail("Terminator not initialized")

        try:
            if not self._iterm.app:
                return APIResult.fail("iTerm app not available")

            iterm_session = await self._iterm.app.async_get_session_by_id(session_id)
            if not iterm_session:
                # Session already gone, just clean up tracking
                self._spawner.untrack_session(session_id)
                self._state.remove_session(session_id)
                return APIResult.ok()

            result = await self._terminator.close_session(iterm_session, force=force)

            if result.success:
                self._spawner.untrack_session(session_id)
                self._state.remove_session(session_id)
                return APIResult.ok()

            return APIResult.fail(result.error or "Failed to close session")

        except Exception as e:
            logger.error("Failed to kill session: %s", e)
            return APIResult.fail(str(e))

    async def focus_session(self, session_id: str) -> APIResult:
        """Focus a terminal session in iTerm2.

        Args:
            session_id: The session to focus.

        Returns:
            APIResult indicating success or failure.
        """
        if not self._iterm.is_connected:
            return APIResult.fail("Not connected to iTerm2")

        session = self._state.sessions.get(session_id)
        if not session:
            return APIResult.fail(f"Session not found: {session_id}")

        try:
            if not self._iterm.app:
                return APIResult.fail("iTerm app not available")

            iterm_session = await self._iterm.app.async_get_session_by_id(session_id)
            if not iterm_session:
                return APIResult.fail("Session no longer exists in iTerm2")

            await iterm_session.async_activate()
            return APIResult.ok()

        except Exception as e:
            logger.error("Failed to focus session: %s", e)
            return APIResult.fail(str(e))

    async def get_session_status(self, session_id: str) -> AttentionState | None:
        """Get a session's attention state.

        Args:
            session_id: The session to check.

        Returns:
            The session's AttentionState, or None if not found.
        """
        session = self._state.sessions.get(session_id)
        return session.attention_state if session else None

    async def send_to_session(self, session_id: str, text: str) -> APIResult:
        """Send text to a terminal session.

        Args:
            session_id: The session to send to.
            text: The text to send (newline appended if not present).

        Returns:
            APIResult indicating success or failure.
        """
        if not self._iterm.is_connected:
            return APIResult.fail("Not connected to iTerm2")

        session = self._state.sessions.get(session_id)
        if not session:
            return APIResult.fail(f"Session not found: {session_id}")

        try:
            if not self._iterm.app:
                return APIResult.fail("iTerm app not available")

            iterm_session = await self._iterm.app.async_get_session_by_id(session_id)
            if not iterm_session:
                return APIResult.fail("Session no longer exists in iTerm2")

            if not text.endswith("\n"):
                text = text + "\n"
            await iterm_session.async_send_text(text)
            return APIResult.ok()

        except Exception as e:
            logger.error("Failed to send to session: %s", e)
            return APIResult.fail(str(e))

    # =========================================================================
    # Task Operations (PLAN.md)
    # =========================================================================

    async def get_plan(self, project_id: str) -> Plan | None:
        """Get the parsed PLAN.md for a project.

        Args:
            project_id: The project's unique identifier.

        Returns:
            The Plan if available, None otherwise.
        """
        return self._state.get_plan(project_id)

    async def list_tasks(
        self, project_id: str, status: TaskStatus | None = None
    ) -> list[Task]:
        """List tasks from a project's PLAN.md.

        Args:
            project_id: The project's unique identifier.
            status: If provided, filter to tasks with this status.

        Returns:
            List of tasks.
        """
        plan = self._state.get_plan(project_id)
        if not plan:
            return []

        tasks = plan.all_tasks
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    async def get_task(self, project_id: str, task_id: str) -> Task | None:
        """Get a specific task by ID.

        Args:
            project_id: The project's unique identifier.
            task_id: The task's identifier (e.g., "2.1").

        Returns:
            The Task if found, None otherwise.
        """
        plan = self._state.get_plan(project_id)
        if not plan:
            return None

        return next((t for t in plan.all_tasks if t.id == task_id), None)

    async def update_task_status(
        self, project_id: str, task_id: str, new_status: TaskStatus
    ) -> TaskResult:
        """Update a task's status in PLAN.md.

        Args:
            project_id: The project's unique identifier.
            task_id: The task's identifier (e.g., "2.1").
            new_status: The new status to set.

        Returns:
            TaskResult with the updated task.
        """
        project = self._state.projects.get(project_id)
        if not project:
            return TaskResult(success=False, error=f"Project not found: {project_id}")

        plan = self._state.get_plan(project_id)
        if not plan:
            return TaskResult(success=False, error="PLAN.md not loaded for project")

        task = next((t for t in plan.all_tasks if t.id == task_id), None)
        if not task:
            return TaskResult(success=False, error=f"Task not found: {task_id}")

        try:
            # Get or create write queue
            write_queue = self._get_or_create_write_queue(project)
            await write_queue.enqueue(task_id, new_status)

            # Update in-memory task
            task.status = new_status
            self._state.update_task_status(project_id, task_id)

            return TaskResult(success=True, task=task)

        except PlanWriteError as e:
            logger.error("Failed to update task: %s", e)
            return TaskResult(success=False, error=str(e))
        except Exception as e:
            logger.error("Unexpected error updating task: %s", e)
            return TaskResult(success=False, error=str(e))

    async def claim_task(self, project_id: str, task_id: str) -> TaskResult:
        """Claim a task (set to IN_PROGRESS).

        Args:
            project_id: The project's unique identifier.
            task_id: The task's identifier (e.g., "2.1").

        Returns:
            TaskResult with the claimed task.
        """
        return await self.update_task_status(project_id, task_id, TaskStatus.IN_PROGRESS)

    async def unclaim_task(self, project_id: str, task_id: str) -> TaskResult:
        """Unclaim a task (set back to PENDING).

        Args:
            project_id: The project's unique identifier.
            task_id: The task's identifier (e.g., "2.1").

        Returns:
            TaskResult with the unclaimed task.
        """
        return await self.update_task_status(project_id, task_id, TaskStatus.PENDING)

    async def complete_task(self, project_id: str, task_id: str) -> TaskResult:
        """Complete a task (set to COMPLETE).

        Args:
            project_id: The project's unique identifier.
            task_id: The task's identifier (e.g., "2.1").

        Returns:
            TaskResult with the completed task.
        """
        return await self.update_task_status(project_id, task_id, TaskStatus.COMPLETE)

    async def skip_task(self, project_id: str, task_id: str) -> TaskResult:
        """Skip a task (set to SKIPPED).

        Args:
            project_id: The project's unique identifier.
            task_id: The task's identifier (e.g., "2.1").

        Returns:
            TaskResult with the skipped task.
        """
        return await self.update_task_status(project_id, task_id, TaskStatus.SKIPPED)

    async def reload_plan(self, project_id: str) -> APIResult:
        """Force reload a project's PLAN.md from disk.

        Args:
            project_id: The project's unique identifier.

        Returns:
            APIResult indicating success or failure.
        """
        project = self._state.projects.get(project_id)
        if not project:
            return APIResult.fail(f"Project not found: {project_id}")

        try:
            await self._load_plan_for_project(project)
            return APIResult.ok()
        except Exception as e:
            return APIResult.fail(str(e))

    # =========================================================================
    # Test Plan Operations (TEST_PLAN.md)
    # =========================================================================

    async def get_test_plan(self, project_id: str) -> TestPlan | None:
        """Get the parsed TEST_PLAN.md for a project.

        Args:
            project_id: The project's unique identifier.

        Returns:
            The TestPlan if available, None otherwise.
        """
        return self._state.get_test_plan(project_id)

    async def list_test_steps(
        self, project_id: str, status: TestStatus | None = None
    ) -> list[TestStep]:
        """List test steps from a project's TEST_PLAN.md.

        Args:
            project_id: The project's unique identifier.
            status: If provided, filter to steps with this status.

        Returns:
            List of test steps.
        """
        test_plan = self._state.get_test_plan(project_id)
        if not test_plan:
            return []

        steps = test_plan.all_steps
        if status:
            steps = [s for s in steps if s.status == status]
        return steps

    async def get_test_step(self, project_id: str, step_id: str) -> TestStep | None:
        """Get a specific test step by ID.

        Args:
            project_id: The project's unique identifier.
            step_id: The step's identifier (e.g., "section-0-1").

        Returns:
            The TestStep if found, None otherwise.
        """
        test_plan = self._state.get_test_plan(project_id)
        if not test_plan:
            return None

        return next((s for s in test_plan.all_steps if s.id == step_id), None)

    async def toggle_test_step(
        self,
        project_id: str,
        step_id: str,
        new_status: TestStatus | None = None,
        notes: str | None = None,
    ) -> TestStepResult:
        """Toggle or set a test step's status.

        If new_status is not provided, cycles through:
        PENDING -> IN_PROGRESS -> PASSED -> FAILED -> PENDING

        Args:
            project_id: The project's unique identifier.
            step_id: The step's identifier (e.g., "section-0-1").
            new_status: Optional explicit status to set.
            notes: Optional notes (typically for failed steps).

        Returns:
            TestStepResult with the updated step.
        """
        project = self._state.projects.get(project_id)
        if not project:
            return TestStepResult(success=False, error=f"Project not found: {project_id}")

        test_plan = self._state.get_test_plan(project_id)
        if not test_plan:
            return TestStepResult(
                success=False, error="TEST_PLAN.md not loaded for project"
            )

        step = next((s for s in test_plan.all_steps if s.id == step_id), None)
        if not step:
            return TestStepResult(success=False, error=f"Step not found: {step_id}")

        # Determine new status
        if new_status is None:
            status_cycle = [
                TestStatus.PENDING,
                TestStatus.IN_PROGRESS,
                TestStatus.PASSED,
                TestStatus.FAILED,
            ]
            try:
                current_idx = status_cycle.index(step.status)
                new_status = status_cycle[(current_idx + 1) % len(status_cycle)]
            except ValueError:
                new_status = TestStatus.PENDING

        try:
            # Update the file
            test_plan_path = project.full_test_plan_path
            updater = TestPlanUpdater()
            updater.update_step_status_in_file(
                test_plan_path, step_id, new_status, notes
            )

            # Update in-memory
            step.status = new_status
            step.notes = notes
            self._state.update_test_step_status(project_id, step_id)

            return TestStepResult(success=True, step=step)

        except (TestPlanParseError, TestPlanWriteError) as e:
            logger.error("Failed to toggle test step: %s", e)
            return TestStepResult(success=False, error=str(e))
        except Exception as e:
            logger.error("Unexpected error toggling test step: %s", e)
            return TestStepResult(success=False, error=str(e))

    async def reload_test_plan(self, project_id: str) -> APIResult:
        """Force reload a project's TEST_PLAN.md from disk.

        Args:
            project_id: The project's unique identifier.

        Returns:
            APIResult indicating success or failure.
        """
        project = self._state.projects.get(project_id)
        if not project:
            return APIResult.fail(f"Project not found: {project_id}")

        try:
            parser = TestPlanParser()
            test_plan = parser.parse_file(project.full_test_plan_path)
            self._state.set_test_plan(project_id, test_plan)
            return APIResult.ok()
        except Exception as e:
            return APIResult.fail(str(e))

    # =========================================================================
    # Window Layout Operations
    # =========================================================================

    async def list_layouts(self) -> list[WindowLayout]:
        """List available window layouts.

        Returns:
            List of WindowLayout configurations.
        """
        if not self._layout_manager:
            return []
        return self._layout_manager.list_layouts()

    async def spawn_layout(
        self, project_id: str, layout_id: str
    ) -> LayoutSpawnResult | None:
        """Spawn a predefined window layout.

        Args:
            project_id: The project to spawn the layout for.
            layout_id: The layout to spawn.

        Returns:
            LayoutSpawnResult, or None if layout not found.
        """
        if not self._iterm.is_connected:
            return None

        project = self._state.projects.get(project_id)
        if not project:
            return None

        if not self._layout_manager or not self._layout_spawner:
            return None

        layout = self._layout_manager.get_layout(layout_id)
        if not layout:
            return None

        # Build template map
        templates = self._get_session_templates_dict()

        try:
            result = await self._layout_spawner.spawn_layout(layout, project, templates)

            # Track spawned sessions
            if result.success and self._spawner:
                for spawn_result in result.results:
                    if spawn_result.success:
                        session = self._spawner.get_session(spawn_result.session_id)
                        if session:
                            self._state.add_session(session)

            return result

        except Exception as e:
            logger.error("Failed to spawn layout: %s", e)
            return None

    # =========================================================================
    # State Query Methods
    # =========================================================================

    async def get_active_project(self) -> Project | None:
        """Get the currently active project.

        Returns:
            The active Project, or None if no project is active.
        """
        return self._state.active_project

    async def get_sessions_waiting(
        self, project_id: str | None = None
    ) -> list[ManagedSession]:
        """Get sessions in WAITING state.

        Args:
            project_id: If provided, filter to this project.

        Returns:
            List of sessions needing attention.
        """
        sessions = await self.list_sessions(project_id)
        return [s for s in sessions if s.attention_state == AttentionState.WAITING]

    async def get_task_progress(self, project_id: str) -> dict[str, int]:
        """Get task completion summary for a project.

        Args:
            project_id: The project's unique identifier.

        Returns:
            Dictionary with status counts (e.g., {"pending": 3, "complete": 5}).
        """
        plan = self._state.get_plan(project_id)
        if not plan:
            return {}
        return plan.completion_summary

    async def get_test_progress(self, project_id: str) -> dict[str, int]:
        """Get test step completion summary for a project.

        Args:
            project_id: The project's unique identifier.

        Returns:
            Dictionary with status counts (e.g., {"pending": 3, "passed": 5}).
        """
        test_plan = self._state.get_test_plan(project_id)
        if not test_plan:
            return {}
        return test_plan.summary

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_session_template(self, template_id: str) -> SessionTemplate | None:
        """Get a session template by ID."""
        if not self._state.config:
            return None
        return next(
            (t for t in self._state.config.session_templates if t.id == template_id),
            None,
        )

    def _get_session_templates_dict(self) -> dict[str, SessionTemplate]:
        """Get all session templates as a dictionary."""
        if not self._state.config:
            return {}
        return {t.id: t for t in self._state.config.session_templates}

    async def _load_plan_for_project(self, project: Project) -> None:
        """Load PLAN.md for a project and set up watching."""
        plan_path = project.full_plan_path

        if plan_path.exists():
            parser = PlanParser()
            try:
                plan = parser.parse_file(plan_path)
                self._state.set_plan(project.id, plan)

                # Set up watcher
                watcher = PlanWatcher()
                watcher.on_plan_reloaded = lambda p: self._state.set_plan(
                    project.id, p
                )
                watcher.on_conflict_detected = lambda p, c: self._state.notify_plan_conflict(
                    project.id, p
                )
                await watcher.start_watching(plan_path, initial_plan=plan)
                self._plan_watchers[project.id] = watcher

            except PlanParseError as e:
                logger.warning("Failed to parse PLAN.md for %s: %s", project.id, e)

        # Load TEST_PLAN.md if it exists
        test_plan_path = project.full_test_plan_path
        if test_plan_path.exists():
            parser = TestPlanParser()
            try:
                test_plan = parser.parse_file(test_plan_path)
                self._state.set_test_plan(project.id, test_plan)
            except TestPlanParseError as e:
                logger.warning(
                    "Failed to parse TEST_PLAN.md for %s: %s", project.id, e
                )

    def _get_or_create_write_queue(self, project: Project) -> PlanWriteQueue:
        """Get or create a write queue for a project."""
        if project.id not in self._write_queues:
            watcher = self._plan_watchers.get(project.id, PlanWatcher())
            self._write_queues[project.id] = PlanWriteQueue(watcher, project)
        return self._write_queues[project.id]


# =============================================================================
# Convenience Functions (Stateless)
# =============================================================================


async def spawn_session(
    project_id: str, template_id: str, task_id: str | None = None
) -> SessionResult:
    """Convenience function to spawn a session.

    Creates a temporary API instance, spawns the session, and returns.
    For multiple operations, use ItermControllerAPI directly.

    Args:
        project_id: The project to spawn for.
        template_id: The session template to use.
        task_id: Optional task to link.

    Returns:
        SessionResult with the spawned session.
    """
    api = ItermControllerAPI()
    result = await api.initialize()
    if not result.success:
        return SessionResult(success=False, error=result.error)

    try:
        return await api.spawn_session(project_id, template_id, task_id)
    finally:
        await api.shutdown()


async def claim_task(project_id: str, task_id: str) -> TaskResult:
    """Convenience function to claim a task.

    Creates a temporary API instance, claims the task, and returns.

    Args:
        project_id: The project's unique identifier.
        task_id: The task's identifier.

    Returns:
        TaskResult with the claimed task.
    """
    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=False)
    if not result.success:
        return TaskResult(success=False, error=result.error)

    try:
        return await api.claim_task(project_id, task_id)
    finally:
        await api.shutdown()


async def toggle_test_step(
    project_id: str,
    step_id: str,
    new_status: TestStatus | None = None,
) -> TestStepResult:
    """Convenience function to toggle a test step.

    Creates a temporary API instance, toggles the step, and returns.

    Args:
        project_id: The project's unique identifier.
        step_id: The step's identifier.
        new_status: Optional explicit status to set.

    Returns:
        TestStepResult with the updated step.
    """
    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=False)
    if not result.success:
        return TestStepResult(success=False, error=result.error)

    try:
        return await api.toggle_test_step(project_id, step_id, new_status)
    finally:
        await api.shutdown()


async def list_projects() -> list[Project]:
    """Convenience function to list all projects.

    Creates a temporary API instance and returns the project list.

    Returns:
        List of configured projects.
    """
    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=False)
    if not result.success:
        return []

    try:
        return await api.list_projects()
    finally:
        await api.shutdown()


async def list_sessions(project_id: str | None = None) -> list[ManagedSession]:
    """Convenience function to list sessions.

    Creates a temporary API instance and returns the session list.

    Args:
        project_id: Optional project to filter by.

    Returns:
        List of managed sessions.
    """
    api = ItermControllerAPI()
    result = await api.initialize()
    if not result.success:
        return []

    try:
        return await api.list_sessions(project_id)
    finally:
        await api.shutdown()


# =============================================================================
# State Query Functions (External Observation)
# =============================================================================


async def get_state() -> StateSnapshot | None:
    """Get a snapshot of the current application state.

    Creates a temporary API instance and returns a read-only snapshot
    of all state data. Useful for external tools that need to query
    sessions, tasks, projects, and plans without interacting with the TUI.

    Returns:
        StateSnapshot containing all current state, or None on error.

    Example:
        from iterm_controller.api import get_state

        state = await get_state()
        if state:
            print(f"Projects: {len(state.projects)}")
            print(f"Active: {state.active_project_id}")
            for session in state.sessions.values():
                print(f"  Session {session.name}: {session.attention_state}")
    """
    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=False)
    if not result.success:
        return None

    try:
        return api.state.to_snapshot()
    finally:
        await api.shutdown()


async def get_plan(project_id: str) -> Plan | None:
    """Get the parsed PLAN.md for a project.

    Creates a temporary API instance and returns the plan.

    Args:
        project_id: The project's unique identifier.

    Returns:
        The Plan if available, None otherwise.

    Example:
        from iterm_controller.api import get_plan

        plan = await get_plan("my-project")
        if plan:
            for task in plan.all_tasks:
                print(f"{task.id}: {task.title} [{task.status.value}]")
    """
    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=False)
    if not result.success:
        return None

    try:
        await api.open_project(project_id)
        return await api.get_plan(project_id)
    finally:
        await api.shutdown()


async def get_project(project_id: str) -> Project | None:
    """Get a project by ID.

    Creates a temporary API instance and returns the project.

    Args:
        project_id: The project's unique identifier.

    Returns:
        The Project if found, None otherwise.

    Example:
        from iterm_controller.api import get_project

        project = await get_project("my-project")
        if project:
            print(f"Path: {project.path}")
            print(f"Template: {project.template_id}")
    """
    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=False)
    if not result.success:
        return None

    try:
        return await api.get_project(project_id)
    finally:
        await api.shutdown()


async def get_sessions(project_id: str | None = None) -> list[ManagedSession]:
    """Get managed sessions (alias for list_sessions).

    Creates a temporary API instance and returns the session list.
    This function connects to iTerm2 to get live session data.

    Args:
        project_id: Optional project to filter by.

    Returns:
        List of managed sessions.

    Example:
        from iterm_controller.api import get_sessions

        sessions = await get_sessions("my-project")
        for s in sessions:
            print(f"{s.name}: {s.attention_state.value}")
    """
    return await list_sessions(project_id)


async def get_task_progress(project_id: str) -> dict[str, int]:
    """Get task completion summary for a project.

    Creates a temporary API instance and returns task counts by status.

    Args:
        project_id: The project's unique identifier.

    Returns:
        Dictionary with status counts (e.g., {"pending": 3, "complete": 5}).

    Example:
        from iterm_controller.api import get_task_progress

        progress = await get_task_progress("my-project")
        print(f"Completed: {progress.get('complete', 0)}/{sum(progress.values())}")
    """
    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=False)
    if not result.success:
        return {}

    try:
        await api.open_project(project_id)
        return await api.get_task_progress(project_id)
    finally:
        await api.shutdown()


async def get_test_plan(project_id: str) -> TestPlan | None:
    """Get the parsed TEST_PLAN.md for a project.

    Creates a temporary API instance and returns the test plan.

    Args:
        project_id: The project's unique identifier.

    Returns:
        The TestPlan if available, None otherwise.

    Example:
        from iterm_controller.api import get_test_plan

        test_plan = await get_test_plan("my-project")
        if test_plan:
            for step in test_plan.all_steps:
                print(f"{step.id}: {step.description} [{step.status.value}]")
    """
    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=False)
    if not result.success:
        return None

    try:
        await api.open_project(project_id)
        return await api.get_test_plan(project_id)
    finally:
        await api.shutdown()
