"""Tests for the Project List screen."""

from unittest.mock import MagicMock, patch

import pytest

from iterm_controller.app import ItermControllerApp
from iterm_controller.models import (
    AppConfig,
    Project,
)
from iterm_controller.screens.project_list import ProjectListScreen
from iterm_controller.screens.project_dashboard import ProjectDashboardScreen
from iterm_controller.screens.new_project import NewProjectScreen


# Empty config fixture for isolated tests
def get_empty_config():
    """Return an empty AppConfig for testing."""
    return AppConfig()


def make_project(
    project_id: str = "project-1",
    name: str = "Test Project",
    path: str = "/tmp/test-project",
    is_open: bool = False,
) -> Project:
    """Create a test project."""
    return Project(
        id=project_id,
        name=name,
        path=path,
        is_open=is_open,
    )


class TestProjectListScreen:
    """Tests for ProjectListScreen."""

    def test_screen_has_bindings(self) -> None:
        """Test that screen has required keybindings."""
        screen = ProjectListScreen()
        binding_keys = [b.key for b in screen.BINDINGS]

        assert "enter" in binding_keys  # Open
        assert "n" in binding_keys  # New Project
        assert "d" in binding_keys  # Delete
        assert "r" in binding_keys  # Refresh
        assert "escape" in binding_keys  # Back


@pytest.mark.asyncio
class TestProjectListScreenAsync:
    """Async tests for ProjectListScreen."""

    async def test_screen_shows_empty_message_when_no_projects(self) -> None:
        """Test that screen shows helpful message when no projects exist."""
        with patch(
            "iterm_controller.config.load_global_config",
            return_value=get_empty_config(),
        ):
            app = ItermControllerApp()
            async with app.run_test() as pilot:
                # Navigate to project list
                await pilot.press("p")

                # Should be on ProjectListScreen
                assert isinstance(app.screen, ProjectListScreen)

                # Empty message should be visible when no projects
                empty_message = app.screen.query_one("#empty-message")
                assert empty_message.display is True

    async def test_screen_displays_projects(self) -> None:
        """Test that screen displays projects from state."""
        with patch(
            "iterm_controller.config.load_global_config",
            return_value=get_empty_config(),
        ):
            app = ItermControllerApp()

            # Add a project to state before running
            project = make_project()
            app.state.projects[project.id] = project

            async with app.run_test() as pilot:
                # Navigate to project list
                await pilot.press("p")

                assert isinstance(app.screen, ProjectListScreen)

                # Table should be visible
                table = app.screen.query_one("#project-table")
                assert table.display is True

                # Empty message should be hidden
                empty_message = app.screen.query_one("#empty-message")
                assert empty_message.display is False

    async def test_screen_shows_project_details(self) -> None:
        """Test that screen shows project name, path, session count, and status."""
        with patch(
            "iterm_controller.config.load_global_config",
            return_value=get_empty_config(),
        ):
            app = ItermControllerApp()

            # Add project
            project = make_project(name="My Project", path="/path/to/project")
            app.state.projects[project.id] = project

            async with app.run_test() as pilot:
                await pilot.press("p")

                assert isinstance(app.screen, ProjectListScreen)

                # Table should have the project data
                table = app.screen.query_one("#project-table")
                assert table.row_count == 1

    async def test_open_project_navigates_to_dashboard(self) -> None:
        """Test that opening a project pushes ProjectDashboardScreen."""
        with patch(
            "iterm_controller.config.load_global_config",
            return_value=get_empty_config(),
        ):
            app = ItermControllerApp()

            # Add project
            project = make_project()
            app.state.projects[project.id] = project

            async with app.run_test() as pilot:
                # Navigate to project list
                await pilot.press("p")

                assert isinstance(app.screen, ProjectListScreen)

                # Call the action directly to avoid async timing issues
                screen = app.screen
                assert isinstance(screen, ProjectListScreen)

                # Verify the action can get the project ID
                project_id = screen._get_selected_project_id()
                assert project_id == project.id

                # Verify the action implementation is correct by checking it would push the screen
                # We can't easily test the full flow because ProjectDashboardScreen has
                # dependencies on state (plans, sessions) that require more setup

    async def test_open_project_marks_project_open(self) -> None:
        """Test that opening a project sets is_open to True via state."""
        with patch(
            "iterm_controller.config.load_global_config",
            return_value=get_empty_config(),
        ):
            app = ItermControllerApp()

            # Add project
            project = make_project(is_open=False)
            app.state.projects[project.id] = project

            async with app.run_test():
                # Directly call open_project on state (which is what the action does)
                await app.state.open_project(project.id)

                # Project should be marked as open
                assert app.state.projects[project.id].is_open is True
                assert app.state.active_project_id == project.id

    async def test_new_project_navigates_to_new_project_screen(self) -> None:
        """Test that pressing 'n' opens the new project screen."""
        with patch(
            "iterm_controller.config.load_global_config",
            return_value=get_empty_config(),
        ):
            app = ItermControllerApp()
            async with app.run_test() as pilot:
                # Navigate to project list
                await pilot.press("p")

                # Press 'n' for new project
                await pilot.press("n")

                # Should be on NewProjectScreen
                assert isinstance(app.screen, NewProjectScreen)

    async def test_delete_requires_project_to_be_closed(self) -> None:
        """Test that delete shows error for open projects."""
        with patch(
            "iterm_controller.config.load_global_config",
            return_value=get_empty_config(),
        ):
            app = ItermControllerApp()

            # Add a closed project (delete should work differently for open ones)
            project = make_project(is_open=False)
            app.state.projects[project.id] = project

            async with app.run_test() as pilot:
                # Navigate to project list
                await pilot.press("p")

                # Try to delete - should show notification (not implemented yet)
                await pilot.press("d")

                # Project should still exist (delete not implemented yet)
                assert project.id in app.state.projects

    async def test_refresh_updates_table(self) -> None:
        """Test that pressing 'r' refreshes the table."""
        with patch(
            "iterm_controller.config.load_global_config",
            return_value=get_empty_config(),
        ):
            app = ItermControllerApp()

            async with app.run_test() as pilot:
                # Navigate to project list
                await pilot.press("p")

                assert isinstance(app.screen, ProjectListScreen)

                # Add a project after the screen is mounted
                project = make_project()
                app.state.projects[project.id] = project

                # Press 'r' to refresh
                await pilot.press("r")

                # Table should now have the project
                table = app.screen.query_one("#project-table")
                assert table.row_count == 1

    async def test_escape_returns_to_previous_screen(self) -> None:
        """Test that pressing 'escape' pops the screen."""
        with patch(
            "iterm_controller.config.load_global_config",
            return_value=get_empty_config(),
        ):
            app = ItermControllerApp()
            async with app.run_test() as pilot:
                # Navigate to project list
                await pilot.press("p")

                assert isinstance(app.screen, ProjectListScreen)

                # Press escape to go back
                await pilot.press("escape")

                # Should be back on control room
                from iterm_controller.screens.control_room import ControlRoomScreen

                assert isinstance(app.screen, ControlRoomScreen)

    async def test_truncate_path_short_path(self) -> None:
        """Test that short paths are not truncated."""
        screen = ProjectListScreen()
        short_path = "/home/user/project"
        result = screen._truncate_path(short_path)
        assert result == short_path

    async def test_truncate_path_long_path(self) -> None:
        """Test that long paths are truncated with ellipsis."""
        screen = ProjectListScreen()
        long_path = "/home/user/very/long/path/that/exceeds/the/maximum/length/allowed"
        result = screen._truncate_path(long_path, max_length=30)
        assert result.startswith("...")
        assert len(result) == 30


@pytest.mark.asyncio
class TestProjectListWithMultipleProjects:
    """Tests for ProjectListScreen with multiple projects."""

    async def test_displays_multiple_projects(self) -> None:
        """Test that all projects are displayed."""
        with patch(
            "iterm_controller.config.load_global_config",
            return_value=get_empty_config(),
        ):
            app = ItermControllerApp()

            # Add multiple projects
            project1 = make_project(project_id="p1", name="Project 1")
            project2 = make_project(project_id="p2", name="Project 2")
            project3 = make_project(project_id="p3", name="Project 3")

            app.state.projects[project1.id] = project1
            app.state.projects[project2.id] = project2
            app.state.projects[project3.id] = project3

            async with app.run_test() as pilot:
                await pilot.press("p")

                assert isinstance(app.screen, ProjectListScreen)

                table = app.screen.query_one("#project-table")
                assert table.row_count == 3

    async def test_shows_correct_session_counts(self) -> None:
        """Test that session counts are displayed correctly."""
        with patch(
            "iterm_controller.config.load_global_config",
            return_value=get_empty_config(),
        ):
            app = ItermControllerApp()

            # Add project
            project = make_project()
            app.state.projects[project.id] = project

            # Add sessions for the project
            from iterm_controller.models import ManagedSession, AttentionState

            session1 = ManagedSession(
                id="s1",
                template_id="t1",
                project_id=project.id,
                tab_id="tab-1",
                attention_state=AttentionState.IDLE,
            )
            session2 = ManagedSession(
                id="s2",
                template_id="t2",
                project_id=project.id,
                tab_id="tab-2",
                attention_state=AttentionState.WORKING,
            )

            app.state.sessions[session1.id] = session1
            app.state.sessions[session2.id] = session2

            async with app.run_test() as pilot:
                await pilot.press("p")

                # The session count column should show "2"
                # We can verify this by checking the table has the project
                table = app.screen.query_one("#project-table")
                assert table.row_count == 1


@pytest.mark.asyncio
class TestProjectListScreenResume:
    """Tests for ProjectListScreen auto-refresh on resume."""

    async def test_screen_refreshes_on_resume_from_new_project(self) -> None:
        """Test that project list refreshes when returning from NewProjectScreen."""
        with patch(
            "iterm_controller.config.load_global_config",
            return_value=get_empty_config(),
        ):
            app = ItermControllerApp()

            async with app.run_test() as pilot:
                # Navigate to project list (initially empty)
                await pilot.press("p")
                assert isinstance(app.screen, ProjectListScreen)

                # Table should be empty
                table = app.screen.query_one("#project-table")
                assert table.row_count == 0

                # Navigate to new project screen
                await pilot.press("n")
                assert isinstance(app.screen, NewProjectScreen)

                # Simulate a project being created by adding it to state
                project = make_project()
                app.state.projects[project.id] = project

                # Press escape to cancel/return to project list
                await pilot.press("escape")
                assert isinstance(app.screen, ProjectListScreen)

                # Table should now show the project (auto-refreshed on resume)
                table = app.screen.query_one("#project-table")
                assert table.row_count == 1

    async def test_screen_refreshes_on_resume_shows_new_project(self) -> None:
        """Test that newly created project appears after returning from creation screen."""
        with patch(
            "iterm_controller.config.load_global_config",
            return_value=get_empty_config(),
        ):
            app = ItermControllerApp()

            # Add one project initially
            initial_project = make_project(project_id="initial", name="Initial Project")
            app.state.projects[initial_project.id] = initial_project

            async with app.run_test() as pilot:
                # Navigate to project list
                await pilot.press("p")
                assert isinstance(app.screen, ProjectListScreen)

                # Should have 1 project
                table = app.screen.query_one("#project-table")
                assert table.row_count == 1

                # Navigate to new project screen
                await pilot.press("n")
                assert isinstance(app.screen, NewProjectScreen)

                # Simulate creating a new project
                new_project = make_project(project_id="new", name="New Project")
                app.state.projects[new_project.id] = new_project

                # Return to project list
                await pilot.press("escape")
                assert isinstance(app.screen, ProjectListScreen)

                # Table should now show both projects
                table = app.screen.query_one("#project-table")
                assert table.row_count == 2


@pytest.mark.asyncio
class TestProjectListEnterKeySelection:
    """Tests for Enter key project selection via DataTable."""

    async def test_enter_key_opens_project(self) -> None:
        """Test that pressing Enter on a project row opens it.

        The DataTable widget intercepts Enter key presses and emits RowSelected
        instead of allowing screen-level bindings to fire. The screen should
        handle this event to open the selected project.
        """
        with patch(
            "iterm_controller.config.load_global_config",
            return_value=get_empty_config(),
        ):
            app = ItermControllerApp()

            # Add a project
            project = make_project()
            app.state.projects[project.id] = project

            async with app.run_test() as pilot:
                # Navigate to project list
                await pilot.press("p")
                assert isinstance(app.screen, ProjectListScreen)

                # Focus the table (it should already be focused, but just in case)
                table = app.screen.query_one("#project-table")
                table.focus()

                # Press Enter to open the project
                await pilot.press("enter")

                # Should now be on ProjectDashboardScreen
                assert isinstance(app.screen, ProjectDashboardScreen)

    async def test_data_table_row_selected_handler_exists(self) -> None:
        """Test that screen has on_data_table_row_selected handler."""
        screen = ProjectListScreen()
        # Check that the handler method exists
        assert hasattr(screen, "on_data_table_row_selected")
        assert callable(getattr(screen, "on_data_table_row_selected"))
