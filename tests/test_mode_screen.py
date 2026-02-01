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
