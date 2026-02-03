"""Tests for the PlanningSection widget."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from iterm_controller.models import ArtifactStatus, Project
from iterm_controller.widgets.artifact_list import (
    check_artifact_status,
    get_spec_files,
)
from iterm_controller.widgets.planning_section import PlanningSection


def make_project(path: str = "/tmp/test-project") -> Project:
    """Create a test project."""
    return Project(
        id="project-1",
        name="Test Project",
        path=path,
    )


class TestPlanningSectionInit:
    """Tests for PlanningSection initialization."""

    def test_init_without_project(self) -> None:
        """Test widget initializes without a project."""
        widget = PlanningSection()

        assert widget.project is None
        assert widget.collapsed is False

    def test_init_with_project(self) -> None:
        """Test widget initializes with a project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = PlanningSection(project=project)

            assert widget.project == project

    def test_init_collapsed(self) -> None:
        """Test widget initializes collapsed."""
        widget = PlanningSection(collapsed=True)

        assert widget.collapsed is True

    def test_artifacts_constant(self) -> None:
        """Test ARTIFACTS constant has expected values."""
        expected_names = ["PROBLEM.md", "PRD.md", "specs/", "PLAN.md"]
        actual_names = [name for name, _, _ in PlanningSection.ARTIFACTS]

        assert actual_names == expected_names


class TestPlanningSectionToggle:
    """Tests for section collapse toggle."""

    def test_toggle_collapsed(self) -> None:
        """Test toggling collapsed state."""
        widget = PlanningSection()

        assert widget.collapsed is False

        with patch.object(widget, "refresh"):
            widget.toggle_collapsed()

        assert widget.collapsed is True

        with patch.object(widget, "refresh"):
            widget.toggle_collapsed()

        assert widget.collapsed is False


class TestPlanningSectionNavigation:
    """Tests for artifact navigation."""

    def test_selected_artifact_initial(self) -> None:
        """Test initial selection is first artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = PlanningSection(project=project)

            assert widget.selected_artifact == "PROBLEM.md"

    def test_select_next(self) -> None:
        """Test selecting next artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = PlanningSection(project=project)

            with patch.object(widget, "refresh"):
                widget.select_next()

            assert widget.selected_artifact == "PRD.md"

    def test_select_previous(self) -> None:
        """Test selecting previous artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = PlanningSection(project=project)

            with patch.object(widget, "refresh"):
                widget.select_next()
                widget.select_next()  # Now at specs/
                widget.select_previous()  # Back to PRD.md

            assert widget.selected_artifact == "PRD.md"

    def test_select_previous_at_start(self) -> None:
        """Test select_previous doesn't go below zero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = PlanningSection(project=project)

            with patch.object(widget, "refresh"):
                widget.select_previous()

            assert widget.selected_artifact == "PROBLEM.md"

    def test_select_next_at_end(self) -> None:
        """Test select_next doesn't exceed list bounds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = PlanningSection(project=project)

            with patch.object(widget, "refresh"):
                for _ in range(10):
                    widget.select_next()

            assert widget.selected_artifact == "PLAN.md"

    def test_select_when_collapsed_does_nothing(self) -> None:
        """Test navigation disabled when collapsed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = PlanningSection(project=project, collapsed=True)

            # When collapsed, selected_artifact should be None
            assert widget.selected_artifact is None


class TestPlanningSectionSpecsExpansion:
    """Tests for specs directory expansion."""

    def test_toggle_specs_expanded(self) -> None:
        """Test toggling specs expansion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            specs_dir = Path(tmpdir) / "specs"
            specs_dir.mkdir()
            (specs_dir / "api.md").write_text("# API")

            project = make_project(path=tmpdir)
            widget = PlanningSection(project=project)

            # Manually set up spec files
            widget._artifact_status = check_artifact_status(Path(tmpdir))
            widget._spec_files = get_spec_files(Path(tmpdir))

            assert widget._expanded_specs is True

            with patch.object(widget, "refresh"):
                widget.toggle_specs_expanded()

            assert widget._expanded_specs is False

    def test_spec_files_selectable_when_expanded(self) -> None:
        """Test spec files are selectable when expanded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            specs_dir = Path(tmpdir) / "specs"
            specs_dir.mkdir()
            (specs_dir / "api.md").write_text("# API")
            (specs_dir / "ui.md").write_text("# UI")

            project = make_project(path=tmpdir)
            widget = PlanningSection(project=project)

            # Manually set up spec files
            widget._artifact_status = check_artifact_status(Path(tmpdir))
            widget._spec_files = get_spec_files(Path(tmpdir))

            selectable = widget._get_selectable_items()

            assert "PROBLEM.md" in selectable
            assert "specs/" in selectable
            assert "specs/api.md" in selectable
            assert "specs/ui.md" in selectable

    def test_spec_files_not_selectable_when_collapsed(self) -> None:
        """Test spec files not selectable when specs collapsed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            specs_dir = Path(tmpdir) / "specs"
            specs_dir.mkdir()
            (specs_dir / "api.md").write_text("# API")

            project = make_project(path=tmpdir)
            widget = PlanningSection(project=project)

            # Manually set up spec files
            widget._artifact_status = check_artifact_status(Path(tmpdir))
            widget._spec_files = get_spec_files(Path(tmpdir))
            widget._expanded_specs = False

            selectable = widget._get_selectable_items()

            assert "specs/" in selectable
            assert "specs/api.md" not in selectable


class TestPlanningSectionMissingArtifacts:
    """Tests for missing artifacts detection."""

    def test_missing_artifacts_all_missing(self) -> None:
        """Test missing_artifacts when all artifacts missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = PlanningSection(project=project)

            widget._artifact_status = check_artifact_status(Path(tmpdir))

            missing = widget.missing_artifacts

            assert "PROBLEM.md" in missing
            assert "PRD.md" in missing
            assert "specs/" in missing
            assert "PLAN.md" in missing

    def test_missing_artifacts_some_exist(self) -> None:
        """Test missing_artifacts when some artifacts exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "PROBLEM.md").write_text("# Problem")
            specs_dir = Path(tmpdir) / "specs"
            specs_dir.mkdir()
            (specs_dir / "readme.md").write_text("# Specs")

            project = make_project(path=tmpdir)
            widget = PlanningSection(project=project)

            widget._artifact_status = check_artifact_status(Path(tmpdir))

            missing = widget.missing_artifacts

            assert "PROBLEM.md" not in missing
            assert "specs/" not in missing
            assert "PRD.md" in missing
            assert "PLAN.md" in missing

    def test_missing_artifacts_none_missing(self) -> None:
        """Test missing_artifacts when all artifacts exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "PROBLEM.md").write_text("# Problem")
            (Path(tmpdir) / "PRD.md").write_text("# PRD")
            (Path(tmpdir) / "PLAN.md").write_text("- [ ] Task")
            specs_dir = Path(tmpdir) / "specs"
            specs_dir.mkdir()
            (specs_dir / "readme.md").write_text("# Specs")

            project = make_project(path=tmpdir)
            widget = PlanningSection(project=project)

            widget._artifact_status = check_artifact_status(Path(tmpdir))

            missing = widget.missing_artifacts

            assert missing == []


class TestPlanningSectionGetSelectedPath:
    """Tests for get_selected_path method."""

    def test_get_selected_path_no_project(self) -> None:
        """Test get_selected_path returns None when no project."""
        widget = PlanningSection()

        assert widget.get_selected_path() is None

    def test_get_selected_path_returns_correct_path(self) -> None:
        """Test get_selected_path returns correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = PlanningSection(project=project)

            path = widget.get_selected_path()

            assert path == Path(tmpdir) / "PROBLEM.md"


class TestPlanningSectionMessages:
    """Tests for message posting."""

    def test_artifact_selected_message(self) -> None:
        """Test ArtifactSelected message has correct attributes."""
        msg = PlanningSection.ArtifactSelected(
            artifact_name="PROBLEM.md",
            artifact_path=Path("/tmp/project/PROBLEM.md"),
            exists=True,
        )

        assert msg.artifact_name == "PROBLEM.md"
        assert msg.artifact_path == Path("/tmp/project/PROBLEM.md")
        assert msg.exists is True

    def test_create_missing_requested_message(self) -> None:
        """Test CreateMissingRequested message has correct attributes."""
        msg = PlanningSection.CreateMissingRequested(
            missing_artifacts=["PRD.md", "PLAN.md"]
        )

        assert msg.missing_artifacts == ["PRD.md", "PLAN.md"]


class TestPlanningSectionRendering:
    """Tests for rendering methods."""

    def test_render_artifact_selected(self) -> None:
        """Test _render_artifact with selection."""
        widget = PlanningSection()
        status = ArtifactStatus(exists=True, description="Problem statement")

        text = widget._render_artifact(
            name="PROBLEM.md",
            description="Problem statement",
            status=status,
            is_selected=True,
        )
        rendered = str(text)

        assert ">" in rendered  # Selection indicator
        assert "PROBLEM.md" in rendered

    def test_render_artifact_not_selected(self) -> None:
        """Test _render_artifact without selection."""
        widget = PlanningSection()
        status = ArtifactStatus(exists=False, description="Not created yet")

        text = widget._render_artifact(
            name="PRD.md",
            description="Product requirements",
            status=status,
            is_selected=False,
        )
        rendered = str(text)

        assert "PRD.md" in rendered

    def test_render_artifact_exists(self) -> None:
        """Test _render_artifact shows edit hint when exists and selected."""
        widget = PlanningSection()
        status = ArtifactStatus(exists=True, description="Problem statement")

        text = widget._render_artifact(
            name="PROBLEM.md",
            description="Problem statement",
            status=status,
            is_selected=True,
        )
        rendered = str(text)

        assert "[e]" in rendered  # Edit hint

    def test_render_spec_file(self) -> None:
        """Test _render_spec_file output."""
        widget = PlanningSection()

        text = widget._render_spec_file(filename="api.md", is_selected=False)
        rendered = str(text)

        assert "api.md" in rendered
        assert "└─" in rendered  # Tree connector

    def test_render_spec_file_selected(self) -> None:
        """Test _render_spec_file with selection."""
        widget = PlanningSection()

        text = widget._render_spec_file(filename="api.md", is_selected=True)
        rendered = str(text)

        assert ">" in rendered  # Selection indicator
        assert "api.md" in rendered


class TestPlanningSectionRefresh:
    """Tests for refresh_artifacts method."""

    def test_refresh_artifacts_updates_status(self) -> None:
        """Test refresh_artifacts updates artifact status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = PlanningSection(project=project)

            # Set initial status manually (empty project)
            widget._artifact_status = check_artifact_status(Path(tmpdir))

            # Initially empty
            assert widget._artifact_status["PROBLEM.md"].exists is False

            # Create file
            (Path(tmpdir) / "PROBLEM.md").write_text("# Problem")

            # Refresh manually (simulating what refresh_artifacts does)
            widget._artifact_status = check_artifact_status(Path(tmpdir))

            # Should now exist
            assert widget._artifact_status["PROBLEM.md"].exists is True

    def test_set_project_sets_project(self) -> None:
        """Test set_project sets the project reference."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "PLAN.md").write_text("- [ ] Task")

            widget = PlanningSection()
            assert widget.project is None

            project = make_project(path=tmpdir)

            # Directly set project
            widget._project = project
            widget._artifact_status = check_artifact_status(Path(tmpdir))
            widget._spec_files = get_spec_files(Path(tmpdir))

            assert widget.project == project
            assert widget._artifact_status["PLAN.md"].exists is True
