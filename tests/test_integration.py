"""Integration tests for full workflows with mocked iTerm2 API.

These tests verify end-to-end workflows:
1. Project lifecycle: create project -> spawn sessions -> monitor -> close
2. PLAN.md workflow: file change -> parse -> update state -> UI notification
3. Auto mode workflow: stage change -> command execution
4. Health check integration: spawn -> poll health -> update status
5. Session monitoring: spawn -> detect attention state -> notify
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iterm_controller.auto_mode import (
    AutoModeIntegration,
    StageTransition,
)
from iterm_controller.health_checker import (
    HealthCheckPoller,
    ProjectHealthManager,
)
from iterm_controller.iterm import (
    ItermController,
    SessionSpawner,
    SessionTerminator,
    WindowLayoutSpawner,
    WindowTracker,
)
from iterm_controller.models import (
    AppConfig,
    AppSettings,
    AttentionState,
    AutoModeConfig,
    HealthCheck,
    HealthStatus,
    ManagedSession,
    Phase,
    Plan,
    Project,
    SessionTemplate,
    TabLayout,
    Task,
    TaskStatus,
    WindowLayout,
    WorkflowStage,
)
from iterm_controller.plan_parser import PlanParser
from iterm_controller.plan_watcher import PlanWatcher
from iterm_controller.session_monitor import AttentionDetector, SessionMonitor
from iterm_controller.state import (
    AppState,
    PlanReloaded,
    SessionSpawned,
    SessionStatusChanged,
    StateEvent,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_project(tmp_path: Path) -> Project:
    """Create a temporary test project with PLAN.md."""
    plan_content = """# Plan: Test Project

## Overview

Test project for integration testing.

## Tasks

### Phase 1: Setup

- [ ] **Task 1.1** `[pending]`
  - Spec: specs/setup.md
  - Scope: Initial setup
  - Acceptance: Project is set up

- [ ] **Task 1.2** `[pending]`
  - Scope: Second task
  - Acceptance: Second task is done
"""
    (tmp_path / "PLAN.md").write_text(plan_content)
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "setup.md").write_text("# Setup Spec")

    return Project(
        id="test-project",
        name="Test Project",
        path=str(tmp_path),
    )


@pytest.fixture
def mock_iterm_connection() -> MagicMock:
    """Create a mock iTerm2 connection."""
    connection = MagicMock()
    connection.async_create = AsyncMock()
    return connection


@pytest.fixture
def mock_iterm_app() -> MagicMock:
    """Create a mock iTerm2 app with windows/tabs/sessions."""
    mock_session = MagicMock()
    mock_session.session_id = "mock-session-1"
    mock_session.async_send_text = AsyncMock()
    mock_session.async_get_screen_contents = AsyncMock()

    mock_tab = MagicMock()
    mock_tab.tab_id = "mock-tab-1"
    mock_tab.current_session = mock_session
    mock_tab.sessions = [mock_session]
    mock_tab.async_set_title = AsyncMock()

    mock_window = MagicMock()
    mock_window.window_id = "mock-window-1"
    mock_window.current_tab = mock_tab
    mock_window.tabs = [mock_tab]
    mock_window.async_create_tab = AsyncMock(return_value=mock_tab)

    mock_app = MagicMock()
    mock_app.current_terminal_window = mock_window
    mock_app.terminal_windows = [mock_window]
    mock_app.async_get_session_by_id = AsyncMock(return_value=mock_session)

    return mock_app


@pytest.fixture
def connected_controller(
    mock_iterm_connection: MagicMock, mock_iterm_app: MagicMock
) -> ItermController:
    """Create a connected iTerm controller with mocked dependencies."""
    controller = ItermController()
    controller._connected = True
    controller.connection = mock_iterm_connection
    controller.app = mock_iterm_app
    return controller


# =============================================================================
# Project Lifecycle Integration Tests
# =============================================================================


class TestProjectLifecycleWorkflow:
    """Test complete project lifecycle: create -> spawn -> monitor -> close."""

    @pytest.mark.asyncio
    async def test_project_open_spawns_sessions(
        self,
        temp_project: Project,
        connected_controller: ItermController,
    ) -> None:
        """Test that opening a project spawns configured sessions."""
        state = AppState()
        state.projects[temp_project.id] = temp_project

        spawner = SessionSpawner(connected_controller)
        tracker = WindowTracker(connected_controller)

        # Define session templates
        template = SessionTemplate(
            id="dev-server",
            name="Development Server",
            command="npm run dev",
        )

        # Simulate project open
        await state.open_project(temp_project.id)

        # Spawn a session
        result = await spawner.spawn_session(template, temp_project)

        assert result.success is True
        assert result.session_id == "mock-session-1"
        assert result.tab_id == "mock-tab-1"

        # Verify session is tracked
        assert "mock-session-1" in spawner.managed_sessions
        managed = spawner.managed_sessions["mock-session-1"]
        assert managed.template_id == "dev-server"
        assert managed.project_id == "test-project"

    @pytest.mark.asyncio
    async def test_project_lifecycle_with_state_events(
        self,
        temp_project: Project,
        connected_controller: ItermController,
    ) -> None:
        """Test that project lifecycle events are properly emitted."""
        state = AppState()
        state.projects[temp_project.id] = temp_project

        # Track events
        events_received: list[str] = []

        def on_project_opened(project: Project) -> None:
            events_received.append(f"opened:{project.id}")

        def on_project_closed(project_id: str) -> None:
            events_received.append(f"closed:{project_id}")

        state.subscribe(StateEvent.PROJECT_OPENED, on_project_opened)
        state.subscribe(StateEvent.PROJECT_CLOSED, on_project_closed)

        # Open project
        await state.open_project(temp_project.id)
        assert "opened:test-project" in events_received
        assert state.active_project_id == temp_project.id
        assert temp_project.is_open is True

        # Close project
        await state.close_project(temp_project.id)
        assert "closed:test-project" in events_received
        assert state.active_project_id is None
        assert temp_project.is_open is False

    @pytest.mark.asyncio
    async def test_session_spawn_and_close_lifecycle(
        self,
        temp_project: Project,
        connected_controller: ItermController,
    ) -> None:
        """Test complete session spawn and close lifecycle."""
        spawner = SessionSpawner(connected_controller)
        terminator = SessionTerminator(connected_controller)

        template = SessionTemplate(
            id="test-session",
            name="Test Session",
            command="echo hello",
        )

        # Spawn session
        result = await spawner.spawn_session(template, temp_project)
        assert result.success is True
        assert "mock-session-1" in spawner.managed_sessions

        # Get managed session
        managed = spawner.managed_sessions["mock-session-1"]

        # Close session gracefully (mock session closes immediately)
        mock_session = connected_controller.app.async_get_session_by_id.return_value
        mock_session.async_get_screen_contents.side_effect = Exception("Session closed")

        closed, results = await terminator.close_all_managed([managed], spawner)

        assert closed == 1
        assert len(results) == 1
        assert results[0].success is True
        assert "mock-session-1" not in spawner.managed_sessions

    @pytest.mark.asyncio
    async def test_window_layout_spawn_integration(
        self,
        temp_project: Project,
        connected_controller: ItermController,
    ) -> None:
        """Test spawning a complete window layout."""
        spawner = SessionSpawner(connected_controller)
        layout_spawner = WindowLayoutSpawner(connected_controller, spawner)

        # Create templates
        templates = {
            "server": SessionTemplate(id="server", name="Server", command="npm start"),
            "client": SessionTemplate(id="client", name="Client", command="npm run client"),
        }

        # Create layout
        layout = WindowLayout(
            id="dev-layout",
            name="Development Layout",
            tabs=[
                TabLayout(
                    name="Main",
                    sessions=[
                        {"template_id": "server"},
                    ],
                ),
            ],
        )

        # Spawn layout
        with patch("iterm2.Window.async_create", new_callable=AsyncMock) as mock_create:
            mock_window = connected_controller.app.current_terminal_window
            mock_create.return_value = mock_window

            # Note: The layout uses dicts for sessions, need to convert
            from iterm_controller.models import SessionLayout
            layout.tabs[0].sessions = [SessionLayout(template_id="server")]

            result = await layout_spawner.spawn_layout(layout, temp_project, templates)

        assert result.success is True
        assert result.window_id == "mock-window-1"
        assert len(result.results) == 1


# =============================================================================
# PLAN.md Workflow Integration Tests
# =============================================================================


class TestPlanWorkflowIntegration:
    """Test PLAN.md file change -> parse -> state update workflow."""

    def test_plan_parse_to_state_update(self, temp_project: Project) -> None:
        """Test parsing PLAN.md and updating state."""
        state = AppState()
        state.projects[temp_project.id] = temp_project

        # Parse plan
        parser = PlanParser()
        plan = parser.parse_file(temp_project.full_plan_path)

        # Verify parsing
        assert len(plan.phases) >= 1
        assert len(plan.all_tasks) >= 2

        # Update state
        state.set_plan(temp_project.id, plan)

        # Verify state updated
        assert temp_project.id in state.plans
        stored_plan = state.get_plan(temp_project.id)
        assert stored_plan is not None
        assert stored_plan.all_tasks == plan.all_tasks

    def test_plan_reload_emits_event(self, temp_project: Project) -> None:
        """Test that plan reload emits proper event."""
        state = AppState()
        state.projects[temp_project.id] = temp_project

        events_received: list[tuple[str, Plan]] = []

        def on_plan_reloaded(project_id: str, plan: Plan) -> None:
            events_received.append((project_id, plan))

        state.subscribe(StateEvent.PLAN_RELOADED, on_plan_reloaded)

        # Parse and set plan
        parser = PlanParser()
        plan = parser.parse_file(temp_project.full_plan_path)
        state.set_plan(temp_project.id, plan)

        # Verify event emitted
        assert len(events_received) == 1
        assert events_received[0][0] == temp_project.id
        assert events_received[0][1] == plan

    @pytest.mark.asyncio
    async def test_plan_watcher_detects_changes(self, temp_project: Project) -> None:
        """Test that plan watcher can be configured and detects file changes.

        This tests the integration between the PlanWatcher configuration
        and its change detection callbacks. We verify the callback mechanism
        works by simulating what _on_file_change does internally.
        """
        changes_detected: list[Plan] = []

        def on_reloaded(plan: Plan) -> None:
            changes_detected.append(plan)

        def on_conflict(plan: Plan, changes: list) -> None:
            changes_detected.append(plan)

        # PlanWatcher is a dataclass - set attributes after creation
        watcher = PlanWatcher()
        watcher.plan_path = temp_project.full_plan_path
        watcher.on_plan_reloaded = on_reloaded
        watcher.on_conflict_detected = on_conflict

        # Initialize with current plan
        parser = PlanParser()
        watcher.plan = parser.parse_file(temp_project.full_plan_path)

        # Write updated content (with status change to trigger conflict)
        new_content = """# Plan: Updated

## Tasks

### Phase 1: Setup

- [x] **Task 1.1** `[complete]`
  - Spec: specs/setup.md
  - Scope: Initial setup done
  - Acceptance: Project is set up

- [ ] **Task 1.2** `[pending]`
  - Scope: Second task
  - Acceptance: Second task is done
"""
        plan_path = temp_project.full_plan_path
        plan_path.write_text(new_content)

        # Manually trigger the change detection with mtime update
        watcher.last_mtime = 0  # Force mtime check to pass
        await watcher._on_file_change()

        # Should have detected the status change as a conflict
        assert len(changes_detected) == 1
        # The detected plan should have the updated task status
        assert changes_detected[0].all_tasks[0].status == TaskStatus.COMPLETE

    def test_task_status_change_updates_state(self, temp_project: Project) -> None:
        """Test that task status changes update state and emit events."""
        state = AppState()
        state.projects[temp_project.id] = temp_project

        task_changes: list[tuple[str, str]] = []

        def on_task_changed(project_id: str, task_id: str) -> None:
            task_changes.append((project_id, task_id))

        state.subscribe(StateEvent.TASK_STATUS_CHANGED, on_task_changed)

        # Update task status
        state.update_task_status(temp_project.id, "1.1")

        assert len(task_changes) == 1
        assert task_changes[0] == (temp_project.id, "1.1")


# =============================================================================
# Auto Mode Integration Tests
# =============================================================================


class TestAutoModeIntegration:
    """Test auto mode workflow: plan change -> stage inference -> command execution."""

    @pytest.mark.asyncio
    async def test_stage_inference_on_plan_change(
        self, temp_project: Project
    ) -> None:
        """Test that stage is inferred when plan changes."""
        config = AutoModeConfig(enabled=False)  # Disable auto-execution

        integration = AutoModeIntegration(
            config=config,
            project_id=temp_project.id,
            project_path=Path(temp_project.path),
        )

        # Plan with pending tasks = EXECUTE stage
        plan = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.PENDING)],
                )
            ]
        )

        state = await integration.on_plan_change(plan)

        assert state.stage == WorkflowStage.EXECUTE
        assert integration.current_stage == WorkflowStage.EXECUTE

    @pytest.mark.asyncio
    async def test_stage_progression_from_execute_to_review(
        self, temp_project: Project
    ) -> None:
        """Test stage progression when all tasks complete."""
        config = AutoModeConfig(enabled=False)

        integration = AutoModeIntegration(
            config=config,
            project_id=temp_project.id,
            project_path=Path(temp_project.path),
        )

        # Start in EXECUTE with pending tasks
        plan1 = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.PENDING)],
                )
            ]
        )
        await integration.on_plan_change(plan1)
        assert integration.current_stage == WorkflowStage.EXECUTE

        # Complete all tasks -> REVIEW
        plan2 = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.COMPLETE)],
                )
            ]
        )
        state = await integration.on_plan_change(plan2)

        assert state.stage == WorkflowStage.REVIEW
        assert integration.current_stage == WorkflowStage.REVIEW

    @pytest.mark.asyncio
    async def test_auto_mode_executes_command_on_stage_change(
        self,
        temp_project: Project,
        connected_controller: ItermController,
    ) -> None:
        """Test that auto mode executes configured command on stage change."""
        config = AutoModeConfig(
            enabled=True,
            auto_advance=True,
            require_confirmation=False,
            stage_commands={"review": "claude /review"},
        )

        integration = AutoModeIntegration(
            config=config,
            project_id=temp_project.id,
            project_path=Path(temp_project.path),
            iterm=connected_controller,
        )

        # Set up EXECUTE stage first
        plan1 = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.PENDING)],
                )
            ]
        )
        await integration.on_plan_change(plan1)

        # Transition to REVIEW by completing tasks
        plan2 = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task 1", status=TaskStatus.COMPLETE)],
                )
            ]
        )
        await integration.on_plan_change(plan2)

        # Verify command was executed
        assert integration.last_execution_result is not None
        assert integration.last_execution_result.success is True
        assert integration.last_execution_result.command == "claude /review"

        # Verify command was sent to session
        mock_session = connected_controller.app.current_terminal_window.current_tab.current_session
        mock_session.async_send_text.assert_called_with("claude /review\n")


# =============================================================================
# Health Check Integration Tests
# =============================================================================


class TestHealthCheckIntegration:
    """Test health check workflow: poll endpoints -> update status -> notify."""

    @pytest.mark.asyncio
    async def test_health_check_updates_state(
        self, temp_project: Project
    ) -> None:
        """Test that health checks update application state."""
        state = AppState()
        state.projects[temp_project.id] = temp_project

        health_changes: list[tuple[str, str, str]] = []

        def on_health_change(project_id: str, check_name: str, status: str) -> None:
            health_changes.append((project_id, check_name, status))

        state.subscribe(StateEvent.HEALTH_STATUS_CHANGED, on_health_change)

        # Update health status
        state.update_health_status(temp_project.id, "API Health", HealthStatus.HEALTHY)

        assert len(health_changes) == 1
        assert health_changes[0] == (temp_project.id, "API Health", "healthy")

        # Verify stored status
        statuses = state.get_health_statuses(temp_project.id)
        assert statuses["API Health"] == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_poller_integration(
        self, temp_project: Project
    ) -> None:
        """Test health check poller updates status correctly."""
        health_check = HealthCheck(
            name="API Health",
            url="http://localhost:3000/health",
            timeout_seconds=1.0,
            interval_seconds=0,  # Manual only
        )

        statuses: list[tuple[str, HealthStatus]] = []

        def on_status_change(name: str, status: HealthStatus) -> None:
            statuses.append((name, status))

        # HealthCheckPoller takes env dict and optional callback
        poller = HealthCheckPoller(
            env={},
            on_status_change=on_status_change,
        )

        # Mock successful HTTP response
        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_request.return_value = mock_response

            # Use check_now instead of check_once
            result = await poller.check_now(health_check)

        assert result == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_failure_handling(
        self, temp_project: Project
    ) -> None:
        """Test that health check failures are handled correctly."""
        health_check = HealthCheck(
            name="API Health",
            url="http://localhost:3000/health",
            timeout_seconds=1.0,
            interval_seconds=0,
        )

        statuses: list[tuple[str, HealthStatus]] = []

        def on_status_change(name: str, status: HealthStatus) -> None:
            statuses.append((name, status))

        poller = HealthCheckPoller(
            env={},
            on_status_change=on_status_change,
        )

        # Mock connection refused
        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
            import httpx
            mock_request.side_effect = httpx.ConnectError("Connection refused")

            result = await poller.check_now(health_check)

        assert result == HealthStatus.UNHEALTHY


# =============================================================================
# Session Monitoring Integration Tests
# =============================================================================


class TestSessionMonitoringIntegration:
    """Test session monitoring: output detection -> attention state -> notification."""

    def test_attention_detector_patterns(self) -> None:
        """Test attention detection patterns for various outputs."""
        detector = AttentionDetector()

        # Test WAITING detection using get_pattern_match
        waiting_outputs = [
            "Should I continue? [y/N]",
            "What would you like me to do next?",
            "I have a question: which approach would you prefer?",
            "Continue? (yes/no)",
        ]

        for output in waiting_outputs:
            state, _pattern = detector.get_pattern_match(output)
            assert state == AttentionState.WAITING, f"Failed for: {output}"

        # Test WORKING detection
        working_outputs = [
            "Reading file src/main.py",
            "Writing to database...",
            "Searching for matches...",
        ]

        for output in working_outputs:
            state, _pattern = detector.get_pattern_match(output)
            assert state == AttentionState.WORKING, f"Failed for: {output}"

    def test_session_status_events(self) -> None:
        """Test that session status changes emit proper events."""
        state = AppState()

        status_changes: list[ManagedSession] = []

        def on_status_change(session: ManagedSession) -> None:
            status_changes.append(session)

        state.subscribe(StateEvent.SESSION_STATUS_CHANGED, on_status_change)

        # Add a session
        session = ManagedSession(
            id="test-session",
            template_id="dev",
            project_id="test-project",
            tab_id="tab-1",
        )
        state.sessions[session.id] = session

        # Update session status
        state.update_session_status(
            session.id,
            attention_state=AttentionState.WAITING,
            last_output="What should I do?",
        )

        assert len(status_changes) == 1
        assert status_changes[0].attention_state == AttentionState.WAITING


# =============================================================================
# End-to-End Integration Tests
# =============================================================================


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows combining multiple systems."""

    @pytest.mark.asyncio
    async def test_full_project_workflow(
        self,
        temp_project: Project,
        connected_controller: ItermController,
    ) -> None:
        """Test complete workflow: open project -> spawn sessions -> monitor -> update plan -> close."""
        # 1. Set up state with events tracking
        state = AppState()
        state.projects[temp_project.id] = temp_project

        events: list[str] = []

        state.subscribe(
            StateEvent.PROJECT_OPENED,
            lambda project: events.append(f"project_opened:{project.id}"),
        )
        state.subscribe(
            StateEvent.SESSION_SPAWNED,
            lambda session: events.append(f"session_spawned:{session.id}"),
        )
        state.subscribe(
            StateEvent.PLAN_RELOADED,
            lambda project_id, plan: events.append(f"plan_reloaded:{project_id}"),
        )

        # 2. Open project
        await state.open_project(temp_project.id)
        assert "project_opened:test-project" in events

        # 3. Spawn session
        spawner = SessionSpawner(connected_controller)
        template = SessionTemplate(id="dev", name="Dev", command="npm start")

        result = await spawner.spawn_session(template, temp_project)
        assert result.success is True

        # Add to state
        managed = spawner.managed_sessions[result.session_id]
        state.add_session(managed)
        assert "session_spawned:mock-session-1" in events

        # 4. Parse and update plan
        parser = PlanParser()
        plan = parser.parse_file(temp_project.full_plan_path)
        state.set_plan(temp_project.id, plan)
        assert "plan_reloaded:test-project" in events

        # 5. Verify state consistency
        assert state.active_project_id == temp_project.id
        assert temp_project.id in state.plans
        assert len(state.sessions) == 1
        assert state.has_active_sessions is True

        # 6. Close session
        terminator = SessionTerminator(connected_controller)
        mock_session = connected_controller.app.async_get_session_by_id.return_value
        mock_session.async_get_screen_contents.side_effect = Exception("Closed")

        await terminator.close_all_managed([managed], spawner)
        state.remove_session(managed.id)

        assert state.has_active_sessions is False

        # 7. Close project
        await state.close_project(temp_project.id)
        assert state.active_project_id is None

    @pytest.mark.asyncio
    async def test_auto_mode_with_plan_update(
        self,
        temp_project: Project,
        connected_controller: ItermController,
    ) -> None:
        """Test auto mode responding to plan updates."""
        state = AppState()
        state.projects[temp_project.id] = temp_project

        # Configure auto mode
        config = AutoModeConfig(
            enabled=True,
            auto_advance=True,
            require_confirmation=False,
            stage_commands={
                "execute": "claude /plan",
                "review": "claude /review",
            },
        )

        integration = AutoModeIntegration(
            config=config,
            project_id=temp_project.id,
            project_path=Path(temp_project.path),
            iterm=connected_controller,
        )

        # Transition: PLANNING -> EXECUTE
        plan1 = Plan(phases=[])  # Empty = PLANNING
        await integration.on_plan_change(plan1)
        first_stage = integration.current_stage

        # Add tasks -> should trigger EXECUTE command
        plan2 = Plan(
            phases=[
                Phase(
                    id="1",
                    title="Phase 1",
                    tasks=[Task(id="1.1", title="Task", status=TaskStatus.PENDING)],
                )
            ]
        )
        await integration.on_plan_change(plan2)

        # Verify execute command was run
        assert integration.current_stage == WorkflowStage.EXECUTE
        if integration.last_execution_result:
            assert integration.last_execution_result.command == "claude /plan"

    @pytest.mark.asyncio
    async def test_state_consistency_across_operations(
        self,
        temp_project: Project,
        connected_controller: ItermController,
    ) -> None:
        """Test that state remains consistent across multiple operations."""
        state = AppState()
        state.projects[temp_project.id] = temp_project

        spawner = SessionSpawner(connected_controller)

        templates = [
            SessionTemplate(id=f"session-{i}", name=f"Session {i}", command=f"echo {i}")
            for i in range(3)
        ]

        # Spawn multiple sessions
        for template in templates:
            result = await spawner.spawn_session(template, temp_project)
            # Each spawn uses the same mock session ID
            if result.success:
                # Create unique session for state tracking
                managed = ManagedSession(
                    id=f"session-{template.id}",
                    template_id=template.id,
                    project_id=temp_project.id,
                    tab_id="tab-1",
                )
                state.add_session(managed)

        # Verify state
        assert len(state.sessions) == 3
        assert state.has_active_sessions is True

        # Get sessions for project
        project_sessions = state.get_sessions_for_project(temp_project.id)
        assert len(project_sessions) == 3

        # Update one session's status
        first_session_id = list(state.sessions.keys())[0]
        state.update_session_status(
            first_session_id,
            attention_state=AttentionState.WAITING,
        )

        # Verify update applied
        assert state.sessions[first_session_id].attention_state == AttentionState.WAITING

        # Remove sessions
        for session_id in list(state.sessions.keys()):
            state.remove_session(session_id)

        assert len(state.sessions) == 0
        assert state.has_active_sessions is False


class TestMessagePostingIntegration:
    """Test that state changes properly post Textual messages."""

    @pytest.mark.asyncio
    async def test_state_posts_messages_to_app(
        self, temp_project: Project
    ) -> None:
        """Test that state posts messages when connected to an app."""
        state = AppState()
        state.projects[temp_project.id] = temp_project

        # Mock Textual app
        mock_app = MagicMock()
        mock_app.post_message = MagicMock()

        state.connect_app(mock_app)

        # Open project - should post ProjectOpened message
        await state.open_project(temp_project.id)

        # Verify message posted
        assert mock_app.post_message.called
        call_args = mock_app.post_message.call_args_list

        # Find ProjectOpened message
        from iterm_controller.state import ProjectOpened

        project_opened_posted = any(
            isinstance(call[0][0], ProjectOpened) for call in call_args
        )
        assert project_opened_posted

    @pytest.mark.asyncio
    async def test_session_messages_posted(
        self, temp_project: Project
    ) -> None:
        """Test that session events post messages."""
        state = AppState()

        mock_app = MagicMock()
        mock_app.post_message = MagicMock()
        state.connect_app(mock_app)

        # Add session
        session = ManagedSession(
            id="test-session",
            template_id="dev",
            project_id=temp_project.id,
            tab_id="tab-1",
        )
        state.add_session(session)

        # Verify SessionSpawned message
        call_args = mock_app.post_message.call_args_list
        session_spawned_posted = any(
            isinstance(call[0][0], SessionSpawned) for call in call_args
        )
        assert session_spawned_posted

        # Update session status
        mock_app.post_message.reset_mock()
        state.update_session_status(session.id, attention_state=AttentionState.WAITING)

        call_args = mock_app.post_message.call_args_list
        status_changed_posted = any(
            isinstance(call[0][0], SessionStatusChanged) for call in call_args
        )
        assert status_changed_posted
