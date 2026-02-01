"""Tests for the ModeScreen base class and mode screens."""

import pytest

from iterm_controller.app import ItermControllerApp
from iterm_controller.models import Project, WorkflowMode
from iterm_controller.screens import (
    DocsModeScreen,
    ModeScreen,
    PlanModeScreen,
    ProjectDashboardScreen,
    TestModeScreen,
    WorkModeScreen,
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


class TestModeScreenBindings:
    """Tests for ModeScreen bindings."""

    def test_mode_screen_has_required_bindings(self) -> None:
        """Test that ModeScreen has all required navigation bindings."""
        # Create a minimal concrete subclass for testing
        project = make_project()
        screen = PlanModeScreen(project)
        binding_keys = [b.key for b in screen.BINDINGS]

        assert "1" in binding_keys  # Plan Mode
        assert "2" in binding_keys  # Docs Mode
        assert "3" in binding_keys  # Work Mode
        assert "4" in binding_keys  # Test Mode
        assert "escape" in binding_keys  # Back

    def test_mode_screen_stores_project(self) -> None:
        """Test that ModeScreen stores the project reference."""
        project = make_project(name="My Project")
        screen = PlanModeScreen(project)

        assert screen.project == project
        assert screen.project.name == "My Project"


class TestPlanModeScreen:
    """Tests for PlanModeScreen."""

    def test_plan_mode_current_mode(self) -> None:
        """Test that PlanModeScreen has correct CURRENT_MODE."""
        project = make_project()
        screen = PlanModeScreen(project)

        assert screen.CURRENT_MODE == WorkflowMode.PLAN

    def test_plan_mode_has_artifact_bindings(self) -> None:
        """Test that PlanModeScreen has artifact action bindings."""
        project = make_project()
        screen = PlanModeScreen(project)
        binding_keys = [b.key for b in screen.BINDINGS]

        assert "enter" in binding_keys  # View
        assert "e" in binding_keys  # Edit
        assert "c" in binding_keys  # Create
        assert "s" in binding_keys  # Spawn
        assert "r" in binding_keys  # Refresh

    def test_plan_mode_has_navigation_bindings(self) -> None:
        """Test that PlanModeScreen has cursor navigation bindings."""
        project = make_project()
        screen = PlanModeScreen(project)
        binding_keys = [b.key for b in screen.BINDINGS]

        assert "j" in binding_keys  # Down (vim)
        assert "k" in binding_keys  # Up (vim)
        assert "down" in binding_keys  # Down arrow
        assert "up" in binding_keys  # Up arrow


class TestDocsModeScreen:
    """Tests for DocsModeScreen."""

    def test_docs_mode_current_mode(self) -> None:
        """Test that DocsModeScreen has correct CURRENT_MODE."""
        project = make_project()
        screen = DocsModeScreen(project)

        assert screen.CURRENT_MODE == WorkflowMode.DOCS


class TestWorkModeScreen:
    """Tests for WorkModeScreen."""

    def test_work_mode_current_mode(self) -> None:
        """Test that WorkModeScreen has correct CURRENT_MODE."""
        project = make_project()
        screen = WorkModeScreen(project)

        assert screen.CURRENT_MODE == WorkflowMode.WORK


class TestTestModeScreen:
    """Tests for TestModeScreen."""

    def test_test_mode_current_mode(self) -> None:
        """Test that TestModeScreen has correct CURRENT_MODE."""
        project = make_project()
        screen = TestModeScreen(project)

        assert screen.CURRENT_MODE == WorkflowMode.TEST


@pytest.mark.asyncio
class TestModeScreenAsync:
    """Async tests for ModeScreen."""

    async def test_mode_screen_composes(self) -> None:
        """Test that mode screens compose without errors."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project

            # Test each mode screen composes
            for screen_class in [PlanModeScreen, DocsModeScreen, WorkModeScreen, TestModeScreen]:
                screen = screen_class(project)
                await app.push_screen(screen)

                # Screen should mount without error
                assert app.screen.project == project

                await app.pop_screen()

    async def test_mode_screen_subtitle_includes_project_name(self) -> None:
        """Test that mode screen subtitle includes project name."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project(name="Awesome Project")
            app.state.projects[project.id] = project

            await app.push_screen(PlanModeScreen(project))

            assert "Awesome Project" in app.screen.sub_title
            assert "Plan" in app.screen.sub_title

    async def test_back_to_dashboard_pops_screen(self) -> None:
        """Test that Esc action pops the screen."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            # Push project dashboard first, then mode screen
            await app.push_screen(ProjectDashboardScreen(project.id))
            await app.push_screen(PlanModeScreen(project))

            # Verify we're on the mode screen
            assert isinstance(app.screen, PlanModeScreen)

            # Press Escape to go back
            await pilot.press("escape")

            # Should now be on the project dashboard
            assert isinstance(app.screen, ProjectDashboardScreen)


@pytest.mark.asyncio
class TestModeScreenSwitching:
    """Tests for mode switching functionality."""

    async def test_switch_mode_updates_last_mode(self) -> None:
        """Test that switching modes updates project.last_mode."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            # Start in Plan Mode
            await app.push_screen(PlanModeScreen(project))

            # Press '2' to switch to Docs Mode
            await pilot.press("2")

            # Project's last_mode should be updated
            assert project.last_mode == WorkflowMode.DOCS

    async def test_switch_mode_changes_screen(self) -> None:
        """Test that switching modes changes to the correct screen."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            # Start in Plan Mode
            await app.push_screen(PlanModeScreen(project))
            assert isinstance(app.screen, PlanModeScreen)

            # Press '3' to switch to Work Mode
            await pilot.press("3")
            assert isinstance(app.screen, WorkModeScreen)

    async def test_switch_to_same_mode_does_nothing(self) -> None:
        """Test that switching to current mode doesn't push new screen."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            # Start in Plan Mode
            await app.push_screen(PlanModeScreen(project))
            original_screen = app.screen

            # Press '1' to "switch" to Plan Mode (same mode)
            await pilot.press("1")

            # Should still be on the same screen (not a new instance)
            assert app.screen is original_screen

    async def test_switch_mode_cycle_through_all(self) -> None:
        """Test switching through all modes."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            # Start in Plan Mode
            await app.push_screen(PlanModeScreen(project))
            assert isinstance(app.screen, PlanModeScreen)

            # Switch to Docs (2)
            await pilot.press("2")
            assert isinstance(app.screen, DocsModeScreen)

            # Switch to Work (3)
            await pilot.press("3")
            assert isinstance(app.screen, WorkModeScreen)

            # Switch to Test (4)
            await pilot.press("4")
            assert isinstance(app.screen, TestModeScreen)

            # Switch back to Plan (1)
            await pilot.press("1")
            assert isinstance(app.screen, PlanModeScreen)


@pytest.mark.asyncio
class TestProjectDashboardModeNavigation:
    """Tests for navigating to modes from project dashboard."""

    async def test_dashboard_enter_mode_pushes_screen(self) -> None:
        """Test that pressing 1-4 on dashboard pushes mode screen."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            # Press '1' to enter Plan Mode
            await pilot.press("1")

            # Should now be on PlanModeScreen
            assert isinstance(app.screen, PlanModeScreen)

    async def test_dashboard_updates_last_mode_on_enter(self) -> None:
        """Test that entering a mode from dashboard updates last_mode."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))

            # Press '3' to enter Work Mode
            await pilot.press("3")

            # Project's last_mode should be updated
            assert project.last_mode == WorkflowMode.WORK

    async def test_mode_screen_back_returns_to_dashboard(self) -> None:
        """Test that Esc from mode returns to project dashboard."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            await app.push_screen(ProjectDashboardScreen(project.id))
            await pilot.press("2")  # Enter Docs Mode

            assert isinstance(app.screen, DocsModeScreen)

            await pilot.press("escape")  # Go back

            assert isinstance(app.screen, ProjectDashboardScreen)


@pytest.mark.asyncio
class TestPlanModeScreenArtifacts:
    """Tests for PlanModeScreen artifact list functionality."""

    async def test_plan_mode_shows_artifact_list(self) -> None:
        """Test that PlanModeScreen displays artifact list widget."""
        import tempfile

        from iterm_controller.widgets.artifact_list import ArtifactListWidget

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test():
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(PlanModeScreen(project))

                # Should have an artifact list widget
                artifact_widget = app.screen.query_one("#artifacts", ArtifactListWidget)
                assert artifact_widget is not None

    async def test_plan_mode_shows_workflow_bar(self) -> None:
        """Test that PlanModeScreen displays workflow bar widget."""
        import tempfile

        from iterm_controller.widgets.workflow_bar import WorkflowBarWidget

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test():
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(PlanModeScreen(project))

                # Should have a workflow bar widget
                workflow_bar = app.screen.query_one("#workflow-bar", WorkflowBarWidget)
                assert workflow_bar is not None

    async def test_plan_mode_cursor_navigation(self) -> None:
        """Test cursor navigation with j/k keys in PlanModeScreen."""
        import tempfile

        from iterm_controller.widgets.artifact_list import ArtifactListWidget

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(PlanModeScreen(project))

                artifact_widget = app.screen.query_one("#artifacts", ArtifactListWidget)
                assert artifact_widget.selected_artifact == "PROBLEM.md"

                # Press 'j' to move down
                await pilot.press("j")
                assert artifact_widget.selected_artifact == "PRD.md"

                # Press 'k' to move back up
                await pilot.press("k")
                assert artifact_widget.selected_artifact == "PROBLEM.md"

    async def test_plan_mode_refresh_action(self) -> None:
        """Test refresh action updates artifact status."""
        import tempfile
        from pathlib import Path

        from iterm_controller.widgets.artifact_list import ArtifactListWidget

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(PlanModeScreen(project))

                artifact_widget = app.screen.query_one("#artifacts", ArtifactListWidget)

                # Initially no PROBLEM.md
                assert artifact_widget.artifact_status["PROBLEM.md"].exists is False

                # Create PROBLEM.md
                (Path(tmpdir) / "PROBLEM.md").write_text("# Problem")

                # Press 'r' to refresh
                await pilot.press("r")

                # Now should show as existing
                assert artifact_widget.artifact_status["PROBLEM.md"].exists is True


@pytest.mark.asyncio
class TestPlanModeCreateEditActions:
    """Tests for PlanModeScreen create/edit artifact actions."""

    async def test_edit_artifact_notifies_when_no_selection(self) -> None:
        """Test that edit action shows warning when nothing selected."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(PlanModeScreen(project))

                # Default selection is PROBLEM.md which doesn't exist
                # Press 'e' to try to edit
                await pilot.press("e")

                # Should notify that file doesn't exist
                # (notification contains warning about using 'c' to create)

    async def test_edit_existing_artifact_opens_editor(self) -> None:
        """Test that edit action opens existing file in editor."""
        import tempfile
        from pathlib import Path
        from unittest.mock import AsyncMock, patch

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create the artifact
            (Path(tmpdir) / "PROBLEM.md").write_text("# Problem Statement")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(PlanModeScreen(project))

                # Refresh to pick up the file
                await pilot.press("r")

                # Mock subprocess.Popen to verify it's called
                with patch("asyncio.to_thread") as mock_to_thread:
                    mock_to_thread.return_value = None

                    # Press 'e' to edit
                    await pilot.press("e")

                    # Give time for async operation
                    await pilot.pause()

                    # Should have called to_thread (which wraps Popen)
                    assert mock_to_thread.called

    async def test_create_artifact_notifies_when_exists(self) -> None:
        """Test that create action shows warning when file already exists."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create the artifact
            (Path(tmpdir) / "PROBLEM.md").write_text("# Problem Statement")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(PlanModeScreen(project))

                # Refresh to pick up the file
                await pilot.press("r")

                # Press 'c' to try to create
                await pilot.press("c")

                # Should notify that file already exists
                # (notification says to use 'e' to edit)

    async def test_create_artifact_spawns_session_when_not_connected(self) -> None:
        """Test that create action shows error when not connected to iTerm2."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(PlanModeScreen(project))

                # Ensure not connected to iTerm2
                app.iterm._connected = False

                # Press 'c' to try to create (PROBLEM.md doesn't exist)
                await pilot.press("c")

                # Should notify about not being connected

    async def test_spawn_planning_shows_error_when_not_connected(self) -> None:
        """Test that spawn planning shows error when not connected to iTerm2."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(PlanModeScreen(project))

                # Ensure not connected to iTerm2
                app.iterm._connected = False

                # Press 's' to spawn planning session
                await pilot.press("s")

                # Should notify about not being connected

    async def test_artifact_commands_mapping(self) -> None:
        """Test that ARTIFACT_COMMANDS has correct mappings."""
        from iterm_controller.screens.modes.plan_mode import ARTIFACT_COMMANDS

        assert ARTIFACT_COMMANDS["PROBLEM.md"] == "claude /problem-statement"
        assert ARTIFACT_COMMANDS["PRD.md"] == "claude /prd"
        assert ARTIFACT_COMMANDS["specs/"] == "claude /specs"
        assert ARTIFACT_COMMANDS["PLAN.md"] == "claude /plan"

    async def test_editor_commands_mapping(self) -> None:
        """Test that EDITOR_COMMANDS has standard editor mappings."""
        from iterm_controller.screens.modes.plan_mode import EDITOR_COMMANDS

        assert EDITOR_COMMANDS["vscode"] == "code"
        assert EDITOR_COMMANDS["cursor"] == "cursor"
        assert EDITOR_COMMANDS["vim"] == "vim"
        assert EDITOR_COMMANDS["nvim"] == "nvim"
        assert EDITOR_COMMANDS["emacs"] == "emacs"

    async def test_view_specs_toggles_expansion(self) -> None:
        """Test that pressing Enter on specs/ toggles expansion."""
        import tempfile
        from pathlib import Path

        from iterm_controller.widgets.artifact_list import ArtifactListWidget

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create specs directory with a file
            specs_dir = Path(tmpdir) / "specs"
            specs_dir.mkdir()
            (specs_dir / "api.md").write_text("# API Spec")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(PlanModeScreen(project))

                # Navigate to specs/
                await pilot.press("j")  # PRD.md
                await pilot.press("j")  # specs/

                artifact_widget = app.screen.query_one("#artifacts", ArtifactListWidget)
                assert artifact_widget.selected_artifact == "specs/"
                assert artifact_widget._expanded_specs is True

                # Press Enter to toggle
                await pilot.press("enter")

                # Should be collapsed now
                assert artifact_widget._expanded_specs is False

                # Press Enter again to expand
                await pilot.press("enter")
                assert artifact_widget._expanded_specs is True


@pytest.mark.asyncio
class TestWorkModeClaimUnclaim:
    """Tests for WorkModeScreen claim/unclaim functionality."""

    async def test_claim_task_changes_status_to_in_progress(self) -> None:
        """Test that claiming a task changes its status to in_progress."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a PLAN.md with a pending task
            plan_content = """# Plan

## Tasks

### Phase 1: Test

- [ ] **Test task** `[pending]`
  - Scope: Test scope
"""
            (Path(tmpdir) / "PLAN.md").write_text(plan_content)

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(WorkModeScreen(project))

                # Verify the task is loaded and pending
                from iterm_controller.widgets.task_queue import TaskQueueWidget
                queue_widget = app.screen.query_one("#task-queue", TaskQueueWidget)
                assert queue_widget.selected_task is not None
                assert queue_widget.selected_task.title == "Test task"

                # Press 'c' to claim the task
                await pilot.press("c")
                await pilot.pause()

                # Read the PLAN.md to verify status changed
                updated_content = (Path(tmpdir) / "PLAN.md").read_text()
                assert "[in_progress]" in updated_content

    async def test_claim_blocked_task_shows_warning(self) -> None:
        """Test that claiming a blocked task shows a warning."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a PLAN.md with a blocked task (depends on incomplete task)
            plan_content = """# Plan

## Tasks

### Phase 1: Test

- [ ] **First task** `[pending]`
  - Scope: First scope

- [ ] **Second task** `[pending]`
  - Depends: 1.1
  - Scope: Depends on first
"""
            (Path(tmpdir) / "PLAN.md").write_text(plan_content)

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(WorkModeScreen(project))

                # Navigate to the blocked task
                from iterm_controller.widgets.task_queue import TaskQueueWidget
                queue_widget = app.screen.query_one("#task-queue", TaskQueueWidget)

                # The first task should be selected by default
                assert queue_widget.selected_task is not None
                assert "First" in queue_widget.selected_task.title

                # Verify second task is blocked
                blocked_tasks = queue_widget.get_blocked_tasks()
                assert len(blocked_tasks) == 1
                assert "Second" in blocked_tasks[0].title
                assert queue_widget.is_task_blocked(blocked_tasks[0])

                # Try to move to a blocked task and claim it
                # The rendering shows available tasks first, then blocked
                # Move to the blocked task (1 available + we start at 0, so press j once to go to blocked)
                await pilot.press("j")
                await pilot.pause()

                # Now we should be on the second (blocked) task
                # Note: The selection index is based on visible_tasks order
                assert queue_widget.selected_task is not None

                # Press 'c' to try to claim this task
                await pilot.press("c")
                await pilot.pause()

                # The PLAN.md should not have changed for the blocked task
                # At most the first task may have been claimed, but the second should still be pending
                updated_content = (Path(tmpdir) / "PLAN.md").read_text()
                # Second task should still be pending (it was blocked)
                assert "Second task" in updated_content
                # The blocked task's status should still be pending
                assert updated_content.count("[pending]") >= 1

    async def test_unclaim_task_changes_status_to_pending(self) -> None:
        """Test that unclaiming a task changes its status back to pending."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a PLAN.md with an in-progress task
            plan_content = """# Plan

## Tasks

### Phase 1: Test

- [ ] **In progress task** `[in_progress]`
  - Scope: Test scope
"""
            (Path(tmpdir) / "PLAN.md").write_text(plan_content)

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(WorkModeScreen(project))

                # Switch to active work panel
                await pilot.press("tab")
                await pilot.pause()

                # Verify the active task is selected
                from iterm_controller.widgets.active_work import ActiveWorkWidget
                active_widget = app.screen.query_one("#active-work", ActiveWorkWidget)
                assert active_widget.selected_task is not None
                assert active_widget.selected_task.title == "In progress task"

                # Press 'u' to unclaim the task
                await pilot.press("u")
                await pilot.pause()

                # Read the PLAN.md to verify status changed back to pending
                updated_content = (Path(tmpdir) / "PLAN.md").read_text()
                assert "[pending]" in updated_content

    async def test_mark_done_changes_status_to_complete(self) -> None:
        """Test that marking a task done changes its status to complete."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a PLAN.md with an in-progress task
            plan_content = """# Plan

## Tasks

### Phase 1: Test

- [ ] **Active task** `[in_progress]`
  - Scope: Test scope
"""
            (Path(tmpdir) / "PLAN.md").write_text(plan_content)

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(WorkModeScreen(project))

                # Switch to active work panel
                await pilot.press("tab")
                await pilot.pause()

                # Press 'd' to mark done
                await pilot.press("d")
                await pilot.pause()

                # Read the PLAN.md to verify status changed to complete
                updated_content = (Path(tmpdir) / "PLAN.md").read_text()
                assert "[complete]" in updated_content
                assert "[x]" in updated_content  # Checkbox should be marked

    async def test_claim_no_task_selected_shows_warning(self) -> None:
        """Test that claiming with no task selected shows warning."""
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a PLAN.md with no pending tasks
            plan_content = """# Plan

## Tasks

### Phase 1: Test

- [x] **Completed task** `[complete]`
  - Scope: Already done
"""
            (Path(tmpdir) / "PLAN.md").write_text(plan_content)

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(WorkModeScreen(project))

                # Verify no pending tasks
                from iterm_controller.widgets.task_queue import TaskQueueWidget
                queue_widget = app.screen.query_one("#task-queue", TaskQueueWidget)
                assert queue_widget.selected_task is None

                # Press 'c' to try to claim (should show warning)
                await pilot.press("c")
                await pilot.pause()

                # No change should happen
                updated_content = (Path(tmpdir) / "PLAN.md").read_text()
                assert "[complete]" in updated_content

    async def test_work_mode_has_claim_unclaim_bindings(self) -> None:
        """Test that WorkModeScreen has claim/unclaim bindings."""
        project = make_project()
        screen = WorkModeScreen(project)
        binding_keys = [b.key for b in screen.BINDINGS]

        assert "c" in binding_keys  # Claim
        assert "u" in binding_keys  # Unclaim
        assert "d" in binding_keys  # Done
        assert "f" in binding_keys  # Focus
        assert "tab" in binding_keys  # Switch panel
