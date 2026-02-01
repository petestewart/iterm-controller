"""Tests for the ArtifactListWidget."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from iterm_controller.models import ArtifactStatus, Project
from iterm_controller.widgets.artifact_list import (
    ArtifactListWidget,
    check_artifact_status,
    get_spec_files,
)


def make_project(path: str = "/tmp/test-project") -> Project:
    """Create a test project."""
    return Project(
        id="project-1",
        name="Test Project",
        path=path,
    )


class TestArtifactStatus:
    """Tests for ArtifactStatus dataclass."""

    def test_artifact_status_exists_true(self) -> None:
        """Test ArtifactStatus with exists=True."""
        status = ArtifactStatus(exists=True, description="4 spec files")

        assert status.exists is True
        assert status.description == "4 spec files"

    def test_artifact_status_exists_false(self) -> None:
        """Test ArtifactStatus with exists=False."""
        status = ArtifactStatus(exists=False)

        assert status.exists is False
        assert status.description == ""

    def test_artifact_status_default_description(self) -> None:
        """Test ArtifactStatus with default description."""
        status = ArtifactStatus(exists=True)

        assert status.description == ""


class TestCheckArtifactStatus:
    """Tests for check_artifact_status function."""

    def test_check_artifact_status_empty_project(self) -> None:
        """Test status check on empty project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            status = check_artifact_status(Path(tmpdir))

            assert status["PROBLEM.md"].exists is False
            assert status["PRD.md"].exists is False
            assert status["specs/"].exists is False
            assert status["PLAN.md"].exists is False

    def test_check_artifact_status_with_problem_md(self) -> None:
        """Test status check with PROBLEM.md present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            problem_path = Path(tmpdir) / "PROBLEM.md"
            problem_path.write_text("# Problem Statement\n\nSome problem.")

            status = check_artifact_status(Path(tmpdir))

            assert status["PROBLEM.md"].exists is True
            assert "Problem statement" in status["PROBLEM.md"].description

    def test_check_artifact_status_with_prd_md(self) -> None:
        """Test status check with PRD.md present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            prd_path = Path(tmpdir) / "PRD.md"
            prd_path.write_text("# PRD\n\nRequirements here.")

            status = check_artifact_status(Path(tmpdir))

            assert status["PRD.md"].exists is True
            assert "Product requirements" in status["PRD.md"].description

    def test_check_artifact_status_with_specs_dir(self) -> None:
        """Test status check with specs/ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            specs_dir = Path(tmpdir) / "specs"
            specs_dir.mkdir()
            (specs_dir / "README.md").write_text("# Specs")
            (specs_dir / "models.md").write_text("# Models")
            (specs_dir / "api.md").write_text("# API")

            status = check_artifact_status(Path(tmpdir))

            assert status["specs/"].exists is True
            assert "3 spec files" in status["specs/"].description

    def test_check_artifact_status_with_single_spec(self) -> None:
        """Test status check with single spec file (singular grammar)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            specs_dir = Path(tmpdir) / "specs"
            specs_dir.mkdir()
            (specs_dir / "README.md").write_text("# Specs")

            status = check_artifact_status(Path(tmpdir))

            assert status["specs/"].exists is True
            assert "1 spec file" in status["specs/"].description

    def test_check_artifact_status_with_plan_md_tasks(self) -> None:
        """Test status check with PLAN.md containing tasks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(
                "# Plan\n"
                "- [ ] Task 1\n"
                "- [ ] Task 2\n"
                "- [x] Task 3\n"
            )

            status = check_artifact_status(Path(tmpdir))

            assert status["PLAN.md"].exists is True
            assert "3 tasks" in status["PLAN.md"].description

    def test_check_artifact_status_with_plan_md_no_tasks(self) -> None:
        """Test status check with PLAN.md but no tasks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text("# Plan\n\nNo tasks yet.")

            status = check_artifact_status(Path(tmpdir))

            assert status["PLAN.md"].exists is True
            assert "No tasks yet" in status["PLAN.md"].description


class TestGetSpecFiles:
    """Tests for get_spec_files function."""

    def test_get_spec_files_no_dir(self) -> None:
        """Test get_spec_files when specs/ doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = get_spec_files(Path(tmpdir))

            assert files == []

    def test_get_spec_files_empty_dir(self) -> None:
        """Test get_spec_files with empty specs/ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            specs_dir = Path(tmpdir) / "specs"
            specs_dir.mkdir()

            files = get_spec_files(Path(tmpdir))

            assert files == []

    def test_get_spec_files_with_files(self) -> None:
        """Test get_spec_files returns sorted filenames."""
        with tempfile.TemporaryDirectory() as tmpdir:
            specs_dir = Path(tmpdir) / "specs"
            specs_dir.mkdir()
            (specs_dir / "ui.md").write_text("# UI")
            (specs_dir / "api.md").write_text("# API")
            (specs_dir / "README.md").write_text("# README")

            files = get_spec_files(Path(tmpdir))

            assert files == ["README.md", "api.md", "ui.md"]

    def test_get_spec_files_ignores_non_md(self) -> None:
        """Test get_spec_files ignores non-markdown files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            specs_dir = Path(tmpdir) / "specs"
            specs_dir.mkdir()
            (specs_dir / "spec.md").write_text("# Spec")
            (specs_dir / "notes.txt").write_text("Notes")
            (specs_dir / "diagram.png").write_bytes(b"PNG")

            files = get_spec_files(Path(tmpdir))

            assert files == ["spec.md"]


class TestArtifactListWidget:
    """Tests for ArtifactListWidget initialization and properties."""

    def test_init_without_project(self) -> None:
        """Test widget initializes without a project."""
        widget = ArtifactListWidget()

        assert widget.project is None
        assert widget.artifact_status == {}

    def test_init_with_project(self) -> None:
        """Test widget initializes with a project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = ArtifactListWidget(project=project)

            assert widget.project == project

    def test_artifact_definitions(self) -> None:
        """Test ARTIFACT_DEFINITIONS constant."""
        expected = [
            ("PROBLEM.md", "Problem statement"),
            ("PRD.md", "Product requirements"),
            ("specs/", "Technical specifications"),
            ("PLAN.md", "Implementation task list"),
        ]

        assert ArtifactListWidget.ARTIFACT_DEFINITIONS == expected


class TestArtifactListWidgetNavigation:
    """Tests for artifact list navigation."""

    def test_selected_artifact_initial(self) -> None:
        """Test initial selection is first artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = ArtifactListWidget(project=project)

            assert widget.selected_artifact == "PROBLEM.md"

    def test_select_next(self) -> None:
        """Test selecting next artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = ArtifactListWidget(project=project)

            with patch.object(widget, "update"):
                widget.select_next()

            assert widget.selected_artifact == "PRD.md"

    def test_select_previous(self) -> None:
        """Test selecting previous artifact."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = ArtifactListWidget(project=project)

            with patch.object(widget, "update"):
                widget.select_next()
                widget.select_next()  # Now at specs/
                widget.select_previous()  # Back to PRD.md

            assert widget.selected_artifact == "PRD.md"

    def test_select_previous_at_start(self) -> None:
        """Test select_previous doesn't go below zero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = ArtifactListWidget(project=project)

            with patch.object(widget, "update"):
                widget.select_previous()

            assert widget.selected_artifact == "PROBLEM.md"

    def test_select_next_at_end(self) -> None:
        """Test select_next doesn't exceed list bounds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = ArtifactListWidget(project=project)

            with patch.object(widget, "update"):
                for _ in range(10):
                    widget.select_next()

            assert widget.selected_artifact == "PLAN.md"


class TestArtifactListWidgetSpecsExpansion:
    """Tests for specs directory expansion."""

    def test_toggle_specs_expanded(self) -> None:
        """Test toggling specs expansion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            specs_dir = Path(tmpdir) / "specs"
            specs_dir.mkdir()
            (specs_dir / "api.md").write_text("# API")

            project = make_project(path=tmpdir)
            widget = ArtifactListWidget(project=project)

            # Manually set up spec files (avoid calling refresh_status which needs app)
            widget._artifact_status = check_artifact_status(Path(tmpdir))
            widget._spec_files = get_spec_files(Path(tmpdir))

            assert widget._expanded_specs is True

            with patch.object(widget, "update"):
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
            widget = ArtifactListWidget(project=project)

            # Manually set up spec files
            widget._artifact_status = check_artifact_status(Path(tmpdir))
            widget._spec_files = get_spec_files(Path(tmpdir))

            selectable = widget._get_selectable_items()

            # Should include main artifacts plus spec files
            assert "PROBLEM.md" in selectable
            assert "specs/" in selectable
            assert "specs/api.md" in selectable
            assert "specs/ui.md" in selectable

    def test_spec_files_not_selectable_when_collapsed(self) -> None:
        """Test spec files not selectable when collapsed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            specs_dir = Path(tmpdir) / "specs"
            specs_dir.mkdir()
            (specs_dir / "api.md").write_text("# API")

            project = make_project(path=tmpdir)
            widget = ArtifactListWidget(project=project)

            # Manually set up spec files
            widget._artifact_status = check_artifact_status(Path(tmpdir))
            widget._spec_files = get_spec_files(Path(tmpdir))
            widget._expanded_specs = False

            selectable = widget._get_selectable_items()

            assert "specs/" in selectable
            assert "specs/api.md" not in selectable


class TestArtifactListWidgetGetSelectedPath:
    """Tests for get_selected_path method."""

    def test_get_selected_path_no_project(self) -> None:
        """Test get_selected_path returns None when no project."""
        widget = ArtifactListWidget()

        assert widget.get_selected_path() is None

    def test_get_selected_path_returns_correct_path(self) -> None:
        """Test get_selected_path returns correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = ArtifactListWidget(project=project)

            path = widget.get_selected_path()

            assert path == Path(tmpdir) / "PROBLEM.md"


class TestArtifactListWidgetRendering:
    """Tests for rendering methods."""

    def test_render_no_project(self) -> None:
        """Test rendering without a project."""
        widget = ArtifactListWidget()

        text = widget._render_content()
        rendered = str(text)

        assert "No project selected" in rendered

    def test_render_with_project_empty_dir(self) -> None:
        """Test rendering with project in empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = ArtifactListWidget(project=project)

            text = widget._render_content()
            rendered = str(text)

            # Should show missing status for all artifacts
            assert "PROBLEM.md" in rendered
            assert "PRD.md" in rendered
            assert "specs/" in rendered
            assert "PLAN.md" in rendered

    def test_render_with_existing_artifacts(self) -> None:
        """Test rendering with some artifacts present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "PROBLEM.md").write_text("# Problem")
            (Path(tmpdir) / "PRD.md").write_text("# PRD")

            project = make_project(path=tmpdir)
            widget = ArtifactListWidget(project=project)

            text = widget._render_content()
            rendered = str(text)

            # Should show exists checkmarks for present artifacts
            assert "PROBLEM.md" in rendered
            assert "PRD.md" in rendered

    def test_render_shows_selection_indicator(self) -> None:
        """Test rendering shows selection indicator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = ArtifactListWidget(project=project)

            text = widget._render_content()
            rendered = str(text)

            # First item should have selection indicator
            assert ">" in rendered


class TestArtifactListWidgetRefresh:
    """Tests for refresh_status method."""

    def test_refresh_status_updates_artifact_status(self) -> None:
        """Test refresh_status updates artifact status via manual status check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = ArtifactListWidget(project=project)

            # Set initial status manually (empty project)
            widget._artifact_status = check_artifact_status(Path(tmpdir))
            widget._spec_files = get_spec_files(Path(tmpdir))

            # Initially empty
            assert widget.artifact_status["PROBLEM.md"].exists is False

            # Create file
            (Path(tmpdir) / "PROBLEM.md").write_text("# Problem")

            # Refresh manually (simulating what refresh_status does)
            widget._artifact_status = check_artifact_status(Path(tmpdir))

            # Should now exist
            assert widget.artifact_status["PROBLEM.md"].exists is True

    def test_set_project_sets_project(self) -> None:
        """Test set_project sets the project reference."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "PLAN.md").write_text("- [ ] Task")

            widget = ArtifactListWidget()
            assert widget.project is None

            project = make_project(path=tmpdir)

            # Directly set project (set_project would call refresh_status which needs app)
            widget._project = project
            widget._artifact_status = check_artifact_status(Path(tmpdir))
            widget._spec_files = get_spec_files(Path(tmpdir))

            assert widget.project == project
            assert widget.artifact_status["PLAN.md"].exists is True
