"""Tests for ModeIndicatorWidget."""

import pytest

from iterm_controller.models import WorkflowMode
from iterm_controller.widgets.mode_indicator import ModeIndicatorWidget


class TestModeIndicatorWidget:
    """Tests for ModeIndicatorWidget."""

    def test_mode_indicator_renders_plan_mode(self) -> None:
        """Test that mode indicator renders correctly for Plan mode."""
        widget = ModeIndicatorWidget(current_mode=WorkflowMode.PLAN)
        rendered = str(widget.render())

        # Should contain the mode name
        assert "Plan" in rendered
        # Should contain all mode numbers
        assert "1" in rendered
        assert "2" in rendered
        assert "3" in rendered
        assert "4" in rendered

    def test_mode_indicator_renders_docs_mode(self) -> None:
        """Test that mode indicator renders correctly for Docs mode."""
        widget = ModeIndicatorWidget(current_mode=WorkflowMode.DOCS)
        rendered = str(widget.render())

        assert "Docs" in rendered
        assert "1" in rendered
        assert "2" in rendered
        assert "3" in rendered
        assert "4" in rendered

    def test_mode_indicator_renders_work_mode(self) -> None:
        """Test that mode indicator renders correctly for Work mode."""
        widget = ModeIndicatorWidget(current_mode=WorkflowMode.WORK)
        rendered = str(widget.render())

        assert "Work" in rendered
        assert "1" in rendered
        assert "2" in rendered
        assert "3" in rendered
        assert "4" in rendered

    def test_mode_indicator_renders_test_mode(self) -> None:
        """Test that mode indicator renders correctly for Test mode."""
        widget = ModeIndicatorWidget(current_mode=WorkflowMode.TEST)
        rendered = str(widget.render())

        assert "Test" in rendered
        assert "1" in rendered
        assert "2" in rendered
        assert "3" in rendered
        assert "4" in rendered

    def test_mode_indicator_renders_empty_when_no_mode(self) -> None:
        """Test that mode indicator renders empty when no mode is set."""
        widget = ModeIndicatorWidget(current_mode=None)
        rendered = str(widget.render())

        assert rendered == ""

    def test_mode_indicator_set_mode(self) -> None:
        """Test that set_mode updates the current mode."""
        widget = ModeIndicatorWidget(current_mode=WorkflowMode.PLAN)
        assert widget.current_mode == WorkflowMode.PLAN

        widget.set_mode(WorkflowMode.DOCS)
        assert widget.current_mode == WorkflowMode.DOCS

    def test_mode_indicator_mode_info_mapping(self) -> None:
        """Test that MODE_INFO has correct mappings."""
        mode_info = ModeIndicatorWidget.MODE_INFO
        assert mode_info[0] == (WorkflowMode.PLAN, "1", "Plan")
        assert mode_info[1] == (WorkflowMode.DOCS, "2", "Docs")
        assert mode_info[2] == (WorkflowMode.WORK, "3", "Work")
        assert mode_info[3] == (WorkflowMode.TEST, "4", "Test")

    def test_mode_indicator_renders_all_labels(self) -> None:
        """Test that mode indicator shows labels for all modes."""
        widget = ModeIndicatorWidget(current_mode=WorkflowMode.PLAN)
        rendered = str(widget.render())

        # Should contain all mode labels
        assert "Plan" in rendered
        assert "Docs" in rendered
        assert "Work" in rendered
        assert "Test" in rendered


@pytest.mark.asyncio
class TestModeIndicatorIntegration:
    """Integration tests for ModeIndicatorWidget with mode screens."""

    async def test_plan_mode_screen_has_mode_indicator(self) -> None:
        """Test that PlanModeScreen includes the mode indicator."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes import PlanModeScreen

        app = ItermControllerApp()
        async with app.run_test():
            project = Project(id="test", name="Test", path="/tmp/test")
            app.state.projects[project.id] = project

            await app.push_screen(PlanModeScreen(project))

            # Should have a mode indicator widget
            indicator = app.screen.query_one("#mode-indicator", ModeIndicatorWidget)
            assert indicator is not None
            assert indicator.current_mode == WorkflowMode.PLAN

    async def test_docs_mode_screen_has_mode_indicator(self) -> None:
        """Test that DocsModeScreen includes the mode indicator."""
        import tempfile

        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes import DocsModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test():
                project = Project(id="test", name="Test", path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))

                # Should have a mode indicator widget
                indicator = app.screen.query_one("#mode-indicator", ModeIndicatorWidget)
                assert indicator is not None
                assert indicator.current_mode == WorkflowMode.DOCS

    async def test_work_mode_screen_has_mode_indicator(self) -> None:
        """Test that WorkModeScreen includes the mode indicator."""
        import tempfile

        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes import WorkModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test():
                project = Project(id="test", name="Test", path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(WorkModeScreen(project))

                # Should have a mode indicator widget
                indicator = app.screen.query_one("#mode-indicator", ModeIndicatorWidget)
                assert indicator is not None
                assert indicator.current_mode == WorkflowMode.WORK

    async def test_test_mode_screen_has_mode_indicator(self) -> None:
        """Test that TestModeScreen includes the mode indicator."""
        import tempfile

        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes import TestModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test():
                project = Project(id="test", name="Test", path=tmpdir)
                app.state.projects[project.id] = project

                await app.push_screen(TestModeScreen(project))

                # Should have a mode indicator widget
                indicator = app.screen.query_one("#mode-indicator", ModeIndicatorWidget)
                assert indicator is not None
                assert indicator.current_mode == WorkflowMode.TEST

    async def test_mode_indicator_changes_on_mode_switch(self) -> None:
        """Test that mode indicator updates when switching modes."""
        import tempfile

        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes import DocsModeScreen, PlanModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(id="test", name="Test", path=tmpdir)
                app.state.projects[project.id] = project

                # Start in Plan Mode
                await app.push_screen(PlanModeScreen(project))
                indicator = app.screen.query_one("#mode-indicator", ModeIndicatorWidget)
                assert indicator.current_mode == WorkflowMode.PLAN

                # Switch to Docs Mode (press 2)
                await pilot.press("2")

                # Should now be on Docs Mode with updated indicator
                assert isinstance(app.screen, DocsModeScreen)
                indicator = app.screen.query_one("#mode-indicator", ModeIndicatorWidget)
                assert indicator.current_mode == WorkflowMode.DOCS
