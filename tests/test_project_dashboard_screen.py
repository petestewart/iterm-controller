"""Tests for the Project Dashboard screen."""

from unittest.mock import MagicMock

import pytest

from iterm_controller.app import ItermControllerApp
from iterm_controller.models import (
    AttentionState,
    ManagedSession,
    Phase,
    Plan,
    Project,
    Task,
    TaskStatus,
    WorkflowMode,
    WorkflowStage,
    WorkflowState,
)
from iterm_controller.screens.project_dashboard import ProjectDashboardScreen
from iterm_controller.widgets import (
    SessionListWidget,
    TaskListWidget,
    TaskProgressWidget,
    WorkflowBarWidget,
)


def make_session(
    session_id: str = "session-1",
    template_id: str = "test-template",
    project_id: str = "project-1",
    attention_state: AttentionState = AttentionState.IDLE,
) -> ManagedSession:
    """Create a test session."""
    return ManagedSession(
        id=session_id,
        template_id=template_id,
        project_id=project_id,
        tab_id="tab-1",
        attention_state=attention_state,
    )


def make_project(
    project_id: str = "project-1",
    name: str = "Test Project",
    path: str = "/tmp/test-project",
) -> Project:
    """Create a test project."""
    return Project(
        id=project_id,
        name=name,
        path=path,
    )


def make_task(
    task_id: str = "1.1",
    title: str = "Test Task",
    status: TaskStatus = TaskStatus.PENDING,
    depends: list[str] | None = None,
) -> Task:
    """Create a test task."""
    return Task(
        id=task_id,
        title=title,
        status=status,
        depends=depends or [],
    )


def make_phase(
    phase_id: str = "1",
    title: str = "Phase 1",
    tasks: list[Task] | None = None,
) -> Phase:
    """Create a test phase."""
    return Phase(
        id=phase_id,
        title=title,
        tasks=tasks or [],
    )


def make_plan(phases: list[Phase] | None = None) -> Plan:
    """Create a test plan."""
    return Plan(phases=phases or [])


class TestProjectDashboardScreen:
    """Tests for ProjectDashboardScreen."""

    def test_screen_has_bindings(self) -> None:
        """Test that screen has required keybindings."""
        screen = ProjectDashboardScreen(project_id="project-1")
        binding_keys = [b.key for b in screen.BINDINGS]

        assert "t" in binding_keys  # Toggle Task
        assert "s" in binding_keys  # Spawn Session
        assert "r" in binding_keys  # Run Script
        assert "d" in binding_keys  # Docs
        assert "g" in binding_keys  # GitHub
        assert "f" in binding_keys  # Focus Session
        assert "k" in binding_keys  # Kill Session
        assert "escape" in binding_keys  # Back

    def test_screen_stores_project_id(self) -> None:
        """Test that screen stores the project ID."""
        screen = ProjectDashboardScreen(project_id="my-project")
        assert screen.project_id == "my-project"


@pytest.mark.asyncio
class TestProjectDashboardScreenAsync:
    """Async tests for ProjectDashboardScreen."""

    async def test_screen_composes_widgets(self) -> None:
        """Test that screen composes required widgets."""
        app = ItermControllerApp()
        async with app.run_test():
            # Add a project to state
            project = make_project()
            app.state.projects[project.id] = project

            # Push the project dashboard
            await app.push_screen(ProjectDashboardScreen(project.id))

            # Check for TaskListWidget
            task_widget = app.screen.query_one("#tasks", TaskListWidget)
            assert task_widget is not None

            # Check for TaskProgressWidget
            progress_widget = app.screen.query_one("#task-progress", TaskProgressWidget)
            assert progress_widget is not None

            # Check for SessionListWidget
            session_widget = app.screen.query_one("#sessions", SessionListWidget)
            assert session_widget is not None

            # Check for WorkflowBarWidget
            workflow_widget = app.screen.query_one("#workflow-bar", WorkflowBarWidget)
            assert workflow_widget is not None

    async def test_screen_shows_project_name_in_subtitle(self) -> None:
        """Test that screen shows project name in subtitle."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project(name="My Awesome Project")
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            assert app.screen.sub_title == "My Awesome Project"

    async def test_screen_shows_error_for_missing_project(self) -> None:
        """Test that screen shows error when project not found."""
        app = ItermControllerApp()
        async with app.run_test():
            # Push dashboard for non-existent project
            await app.push_screen(ProjectDashboardScreen("nonexistent"))
            # Should not crash, just show error notification

    async def test_screen_displays_tasks(self) -> None:
        """Test that screen displays tasks from plan."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project

            # Create a plan with tasks
            plan = make_plan([
                make_phase("1", "Phase 1", [
                    make_task("1.1", "First Task", TaskStatus.COMPLETE),
                    make_task("1.2", "Second Task", TaskStatus.IN_PROGRESS),
                ]),
            ])
            app.state.set_plan(project.id, plan)

            await app.push_screen(ProjectDashboardScreen(project.id))

            task_widget = app.screen.query_one("#tasks", TaskListWidget)
            assert len(task_widget.plan.all_tasks) == 2

    async def test_screen_displays_sessions(self) -> None:
        """Test that screen displays project-specific sessions."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project

            # Add sessions for this project
            session1 = make_session(session_id="s1", project_id=project.id)
            session2 = make_session(session_id="s2", project_id=project.id)
            session_other = make_session(session_id="s3", project_id="other-project")

            app.state.sessions[session1.id] = session1
            app.state.sessions[session2.id] = session2
            app.state.sessions[session_other.id] = session_other

            await app.push_screen(ProjectDashboardScreen(project.id))
            await app.screen._refresh_sessions()

            session_widget = app.screen.query_one("#sessions", SessionListWidget)
            # Should only show sessions for this project
            assert len(session_widget.sessions) == 2

    async def test_screen_updates_workflow_bar(self) -> None:
        """Test that screen updates workflow bar with project state."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            project.workflow_state = WorkflowState(stage=WorkflowStage.EXECUTE)
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))
            await app.screen._refresh_workflow()

            workflow_widget = app.screen.query_one("#workflow-bar", WorkflowBarWidget)
            assert workflow_widget.current_stage == WorkflowStage.EXECUTE


@pytest.mark.asyncio
class TestProjectDashboardActions:
    """Tests for screen actions."""

    async def test_toggle_task_with_in_progress(self) -> None:
        """Test toggle task action with in-progress tasks."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            plan = make_plan([
                make_phase("1", "Phase 1", [
                    make_task("1.1", "First Task", TaskStatus.IN_PROGRESS),
                ]),
            ])
            app.state.set_plan(project.id, plan)

            await app.push_screen(ProjectDashboardScreen(project.id))

            # Press 't' to toggle
            await pilot.press("t")
            # Should show notification (action works but toggle not fully implemented)

    async def test_toggle_task_with_pending(self) -> None:
        """Test toggle task action with only pending tasks."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            plan = make_plan([
                make_phase("1", "Phase 1", [
                    make_task("1.1", "First Task", TaskStatus.PENDING),
                ]),
            ])
            app.state.set_plan(project.id, plan)

            await app.push_screen(ProjectDashboardScreen(project.id))

            # Press 't' to toggle
            await pilot.press("t")

    async def test_toggle_task_with_no_tasks(self) -> None:
        """Test toggle task action with no tasks."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            # Press 't' to toggle - should show warning
            await pilot.press("t")

    async def test_spawn_session_requires_connection(self) -> None:
        """Test spawn session requires iTerm2 connection."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            # iTerm not connected by default
            assert not app.iterm.is_connected

            await pilot.press("s")
            # Should show error notification

    async def test_focus_session_no_sessions(self) -> None:
        """Test focus session with no sessions shows warning."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            # No sessions
            await pilot.press("f")
            # Should show warning

    async def test_kill_session_no_sessions(self) -> None:
        """Test kill session with no sessions shows warning."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            # No sessions
            await pilot.press("k")
            # Should show warning

    async def test_escape_pops_screen(self) -> None:
        """Test escape returns to previous screen."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))
            assert isinstance(app.screen, ProjectDashboardScreen)

            await pilot.press("escape")
            # Should return to control room
            assert not isinstance(app.screen, ProjectDashboardScreen)


@pytest.mark.asyncio
class TestProjectDashboardEventHandlers:
    """Tests for event handler methods."""

    async def test_session_spawned_event_refreshes_list(self) -> None:
        """Test that SessionSpawned event refreshes the session list."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            session = make_session(project_id=project.id)
            app.state.add_session(session)

            # Refresh manually to simulate event processing
            await app.screen._refresh_sessions()

            session_widget = app.screen.query_one("#sessions", SessionListWidget)
            assert len(session_widget.sessions) == 1

    async def test_session_spawned_ignores_other_projects(self) -> None:
        """Test that SessionSpawned for other projects is ignored."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            # Add session for different project
            other_session = make_session(project_id="other-project")
            app.state.add_session(other_session)

            await app.screen._refresh_sessions()

            session_widget = app.screen.query_one("#sessions", SessionListWidget)
            # Should not show session for other project
            assert len(session_widget.sessions) == 0

    async def test_plan_reloaded_event_updates_tasks(self) -> None:
        """Test that PlanReloaded event updates task list."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            # Initially no tasks
            task_widget = app.screen.query_one("#tasks", TaskListWidget)
            assert len(task_widget.plan.all_tasks) == 0

            # Set a plan
            plan = make_plan([
                make_phase("1", "Phase 1", [
                    make_task("1.1", "New Task"),
                ]),
            ])
            app.state.set_plan(project.id, plan)

            await app.screen._refresh_tasks()

            assert len(task_widget.plan.all_tasks) == 1

    async def test_workflow_stage_changed_updates_bar(self) -> None:
        """Test that WorkflowStageChanged event updates workflow bar."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            # Change workflow stage
            app.state.update_workflow_stage(project.id, WorkflowStage.REVIEW.value)

            workflow_widget = app.screen.query_one("#workflow-bar", WorkflowBarWidget)
            # Manually trigger the event handler path
            from iterm_controller.state import WorkflowStageChanged
            event = WorkflowStageChanged(project.id, WorkflowStage.REVIEW.value)
            app.screen.on_workflow_stage_changed(event)

            assert workflow_widget.current_stage == WorkflowStage.REVIEW


@pytest.mark.asyncio
class TestGetSelectedSession:
    """Tests for _get_selected_session method."""

    async def test_returns_waiting_session_first(self) -> None:
        """Test that WAITING sessions are prioritized."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            idle = make_session(
                session_id="idle",
                project_id=project.id,
                attention_state=AttentionState.IDLE,
            )
            waiting = make_session(
                session_id="waiting",
                project_id=project.id,
                attention_state=AttentionState.WAITING,
            )
            app.state.sessions[idle.id] = idle
            app.state.sessions[waiting.id] = waiting

            await app.screen._refresh_sessions()

            screen = app.screen
            assert isinstance(screen, ProjectDashboardScreen)
            selected = screen._get_selected_session()
            assert selected is not None
            assert selected.attention_state == AttentionState.WAITING

    async def test_returns_first_session_when_no_waiting(self) -> None:
        """Test returns first session when none are waiting."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            session = make_session(
                project_id=project.id,
                attention_state=AttentionState.IDLE,
            )
            app.state.sessions[session.id] = session

            await app.screen._refresh_sessions()

            screen = app.screen
            assert isinstance(screen, ProjectDashboardScreen)
            selected = screen._get_selected_session()
            assert selected is not None
            assert selected.id == session.id

    async def test_returns_none_when_no_sessions(self) -> None:
        """Test returns None when no sessions exist."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            screen = app.screen
            assert isinstance(screen, ProjectDashboardScreen)
            assert screen._get_selected_session() is None


class TestModeNavigationBindings:
    """Tests for mode navigation keybindings (1-4)."""

    def test_screen_has_mode_bindings(self) -> None:
        """Test that screen has keybindings for mode navigation."""
        screen = ProjectDashboardScreen(project_id="project-1")
        binding_keys = [b.key for b in screen.BINDINGS]

        assert "1" in binding_keys  # Plan Mode
        assert "2" in binding_keys  # Docs Mode
        assert "3" in binding_keys  # Work Mode
        assert "4" in binding_keys  # Test Mode

    def test_bindings_have_correct_actions(self) -> None:
        """Test that mode bindings are mapped to correct actions."""
        screen = ProjectDashboardScreen(project_id="project-1")
        binding_map = {b.key: b.action for b in screen.BINDINGS}

        assert binding_map["1"] == "enter_mode('plan')"
        assert binding_map["2"] == "enter_mode('docs')"
        assert binding_map["3"] == "enter_mode('work')"
        assert binding_map["4"] == "enter_mode('test')"


@pytest.mark.asyncio
class TestModeNavigationActions:
    """Tests for action_enter_mode method."""

    async def test_enter_plan_mode_updates_last_mode(self) -> None:
        """Test that pressing 1 updates project's last_mode to PLAN."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            # Initially no last_mode
            assert project.last_mode is None

            # Press 1 to enter Plan Mode
            await pilot.press("1")

            # last_mode should be updated
            assert project.last_mode == WorkflowMode.PLAN

    async def test_enter_docs_mode_updates_last_mode(self) -> None:
        """Test that pressing 2 updates project's last_mode to DOCS."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            await pilot.press("2")

            assert project.last_mode == WorkflowMode.DOCS

    async def test_enter_work_mode_updates_last_mode(self) -> None:
        """Test that pressing 3 updates project's last_mode to WORK."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            await pilot.press("3")

            assert project.last_mode == WorkflowMode.WORK

    async def test_enter_test_mode_updates_last_mode(self) -> None:
        """Test that pressing 4 updates project's last_mode to TEST."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            await pilot.press("4")

            assert project.last_mode == WorkflowMode.TEST

    async def test_enter_mode_with_invalid_mode_shows_error(self) -> None:
        """Test that invalid mode shows error notification."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            screen = app.screen
            assert isinstance(screen, ProjectDashboardScreen)

            # Call action directly with invalid mode
            screen.action_enter_mode("invalid")

            # last_mode should remain unchanged
            assert project.last_mode is None

    async def test_enter_mode_with_missing_project_shows_error(self) -> None:
        """Test that missing project shows error notification."""
        app = ItermControllerApp()
        async with app.run_test():
            # Create screen with non-existent project
            await app.push_screen(ProjectDashboardScreen("nonexistent"))

            screen = app.screen
            assert isinstance(screen, ProjectDashboardScreen)

            # Call action - should not crash
            screen.action_enter_mode("plan")

    async def test_mode_switch_preserves_project_id(self) -> None:
        """Test that mode switching doesn't lose project context."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project(project_id="my-project-123")
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            screen = app.screen
            assert isinstance(screen, ProjectDashboardScreen)
            original_project_id = screen.project_id

            # Press mode keys in sequence
            for key in ["1", "2", "3", "4"]:
                await pilot.press(key)

            # Project ID should remain the same
            assert screen.project_id == original_project_id
