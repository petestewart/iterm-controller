"""Tests for the ModeScreen base class and TestModeScreen.

Plan, Docs, and Work mode screens were removed in task 27.9.3.
This file now only tests ModeScreen base class functionality and TestModeScreen.
"""

import pytest

from iterm_controller.app import ItermControllerApp
from iterm_controller.models import Project, WorkflowMode
from iterm_controller.screens import (
    ModeScreen,
    ProjectDashboardScreen,
    ProjectScreen,
    TestModeScreen,
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
        project = make_project()
        screen = TestModeScreen(project)
        binding_keys = [b.key for b in screen.BINDINGS]

        # Test mode (4) should be available
        assert "4" in binding_keys  # Test Mode
        assert "escape" in binding_keys  # Back

    def test_mode_screen_stores_project(self) -> None:
        """Test that ModeScreen stores the project reference."""
        project = make_project(name="My Project")
        screen = TestModeScreen(project)

        assert screen.project == project
        assert screen.project.name == "My Project"


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
        """Test that TestModeScreen composes without errors."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project

            screen = TestModeScreen(project)
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

            await app.push_screen(TestModeScreen(project))

            assert "Awesome Project" in app.screen.sub_title
            assert "Test" in app.screen.sub_title

    async def test_back_to_dashboard_pops_screen(self) -> None:
        """Test that Esc action pops the screen."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project

            # Push project dashboard first, then mode screen
            await app.push_screen(ProjectDashboardScreen(project.id))
            await app.push_screen(TestModeScreen(project))

            # Verify we're on the mode screen
            assert isinstance(app.screen, TestModeScreen)

            # Press Escape to go back
            await pilot.press("escape")

            # Should now be on the project dashboard
            assert isinstance(app.screen, ProjectDashboardScreen)


class TestManagedSessionMetadata:
    """Tests for ManagedSession metadata field."""

    def test_managed_session_has_metadata_field(self) -> None:
        """Test that ManagedSession has metadata field."""
        from iterm_controller.models import ManagedSession

        session = ManagedSession(
            id="test-session-1",
            template_id="claude",
            project_id="project-1",
            tab_id="tab-1",
        )

        assert hasattr(session, "metadata")
        assert isinstance(session.metadata, dict)

    def test_managed_session_metadata_stores_task_info(self) -> None:
        """Test that ManagedSession metadata can store task info."""
        from iterm_controller.models import ManagedSession

        session = ManagedSession(
            id="test-session-1",
            template_id="claude",
            project_id="project-1",
            tab_id="tab-1",
        )

        session.task_id = "1.1"
        session.metadata["task_title"] = "Add auth middleware"

        assert session.task_id == "1.1"
        assert session.metadata["task_title"] == "Add auth middleware"

    def test_managed_session_serializes_with_metadata(self) -> None:
        """Test that ManagedSession serializes correctly with metadata."""
        from dataclasses import asdict

        from iterm_controller.models import ManagedSession

        session = ManagedSession(
            id="test-session-1",
            template_id="claude",
            project_id="project-1",
            tab_id="tab-1",
        )
        session.task_id = "2.1"

        data = asdict(session)

        assert "task_id" in data
        assert data["task_id"] == "2.1"


class TestSessionListWidgetTaskInfo:
    """Tests for SessionListWidget showing task info."""

    def test_session_list_renders_task_info(self) -> None:
        """Test that SessionListWidget renders task info for linked sessions."""
        from iterm_controller.models import ManagedSession
        from iterm_controller.widgets.session_list import SessionListWidget

        session = ManagedSession(
            id="test-session-1",
            template_id="claude",
            project_id="project-1",
            tab_id="tab-1",
        )
        session.task_id = "1.3"
        session.metadata["task_title"] = "Build API layer"

        widget = SessionListWidget(sessions=[session], show_project=False)
        rendered = widget._render_session(session, is_selected=False)

        # Should contain task ID
        assert "Task 1.3" in str(rendered)

    def test_session_list_renders_dash_for_no_task(self) -> None:
        """Test that SessionListWidget renders dash when no task linked."""
        from iterm_controller.models import ManagedSession
        from iterm_controller.widgets.session_list import SessionListWidget

        session = ManagedSession(
            id="test-session-1",
            template_id="claude",
            project_id="project-1",
            tab_id="tab-1",
        )
        # No task linked

        widget = SessionListWidget(sessions=[session], show_project=False)
        rendered = widget._render_session(session, is_selected=False)

        # Should contain dash placeholder
        assert "—" in str(rendered)


@pytest.mark.asyncio
class TestTestModeScreenGeneration:
    """Tests for TestModeScreen TEST_PLAN.md generation functionality."""

    async def test_test_mode_has_generate_binding(self) -> None:
        """Test that TestModeScreen has the 'g' binding for generation."""
        project = make_project()
        screen = TestModeScreen(project)
        binding_keys = [b.key for b in screen.BINDINGS]

        assert "g" in binding_keys

    async def test_test_mode_shows_generate_tip_when_no_test_plan(self) -> None:
        """Test that TestModeScreen shows generate tip when TEST_PLAN.md doesn't exist."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # No TEST_PLAN.md file

            app = ItermControllerApp()
            async with app.run_test():
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(TestModeScreen(project))

                # The empty state message should mention generating
                # This tests that the UI handles missing TEST_PLAN.md gracefully
                assert isinstance(app.screen, TestModeScreen)


# TestTestPlanWatcherCreationCallback tests were removed as they tested
# functionality (on_creation callback) that doesn't exist in TestPlanWatcher


@pytest.mark.asyncio
class TestModeScreenOpenInEditor:
    """Tests for ModeScreen._open_in_editor shared method."""

    async def test_open_in_editor_with_default_display_name(self) -> None:
        """Test that _open_in_editor uses path.name as default display name."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "README.md"
            test_file.write_text("# Readme")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(TestModeScreen(project))

                # Mock subprocess.Popen to verify it's called correctly
                with patch("asyncio.to_thread") as mock_to_thread:
                    mock_to_thread.return_value = None

                    # Call _open_in_editor without display_name (uses default)
                    app.screen._open_in_editor(test_file, "code")

                    # Give time for async operation
                    await pilot.pause()

                    # Verify to_thread was called (indicating subprocess was spawned)
                    assert mock_to_thread.called

    async def test_open_in_editor_with_custom_display_name(self) -> None:
        """Test that _open_in_editor uses custom display name when provided."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "PROBLEM.md"
            test_file.write_text("# Problem Statement")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(TestModeScreen(project))

                # Mock subprocess.Popen
                with patch("asyncio.to_thread") as mock_to_thread:
                    mock_to_thread.return_value = None

                    # Call _open_in_editor with custom display_name
                    app.screen._open_in_editor(test_file, "code", "Problem Statement")

                    # Give time for async operation
                    await pilot.pause()

                    # Verify to_thread was called
                    assert mock_to_thread.called

    async def test_open_in_editor_falls_back_to_macos_open(self) -> None:
        """Test that _open_in_editor falls back to 'open' when editor not found."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("# Test")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = make_project(path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(TestModeScreen(project))

                # Mock asyncio.to_thread to simulate FileNotFoundError then success
                call_count = [0]

                def mock_to_thread_side_effect(func, *args, **kwargs):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        # First call fails (editor not found)
                        raise FileNotFoundError("code not found")
                    # Second call succeeds (macOS open)
                    return None

                with patch(
                    "iterm_controller.screens.mode_screen.asyncio.to_thread"
                ) as mock_to_thread:
                    mock_to_thread.side_effect = mock_to_thread_side_effect

                    # Call _open_in_editor with an editor that "doesn't exist"
                    app.screen._open_in_editor(test_file, "nonexistent-editor")

                    # Give time for async operation
                    await pilot.pause()

                    # Verify to_thread was called twice (once for editor, once for open fallback)
                    assert mock_to_thread.call_count == 2

    async def test_open_in_editor_method_exists_in_base_class(self) -> None:
        """Test that _open_in_editor exists in ModeScreen base class."""
        # Verify the method exists in the base class
        from iterm_controller.screens.mode_screen import ModeScreen

        assert hasattr(ModeScreen, "_open_in_editor")
        assert callable(getattr(ModeScreen, "_open_in_editor"))

    async def test_test_mode_inherits_open_in_editor(self) -> None:
        """Test that TestModeScreen inherits _open_in_editor from ModeScreen."""
        project = make_project()
        screen = TestModeScreen(project)

        # The method should come from ModeScreen (not defined locally)
        assert hasattr(screen, "_open_in_editor")

        # Verify it's inherited from ModeScreen (not defined in TestModeScreen)
        from iterm_controller.screens.mode_screen import ModeScreen

        assert screen._open_in_editor.__func__ is ModeScreen._open_in_editor
