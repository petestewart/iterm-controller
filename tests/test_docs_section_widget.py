"""Tests for the DocsSection widget."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from iterm_controller.models import DocReference, Project
from iterm_controller.widgets.docs_section import DocsSection


def make_project(path: str = "/tmp/test-project") -> Project:
    """Create a test project."""
    return Project(
        id="project-1",
        name="Test Project",
        path=path,
    )


def make_doc_reference(
    id: str = "ref-1",
    title: str = "API Docs",
    url: str = "https://example.com/docs",
    category: str = "",
) -> DocReference:
    """Create a test doc reference."""
    return DocReference(
        id=id,
        title=title,
        url=url,
        category=category,
    )


class TestDocsSectionInit:
    """Tests for DocsSection initialization."""

    def test_init_without_project(self) -> None:
        """Test widget initializes without a project."""
        widget = DocsSection()

        assert widget.project is None
        assert widget.collapsed is False

    def test_init_with_project(self) -> None:
        """Test widget initializes with a project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = DocsSection(project=project)

            assert widget.project == project

    def test_init_collapsed(self) -> None:
        """Test widget initializes collapsed."""
        widget = DocsSection(collapsed=True)

        assert widget.collapsed is True


class TestDocsSectionToggle:
    """Tests for section collapse toggle."""

    def test_toggle_collapsed(self) -> None:
        """Test toggling collapsed state."""
        widget = DocsSection()

        assert widget.collapsed is False

        with patch.object(widget, "refresh"):
            widget.toggle_collapsed()

        assert widget.collapsed is True

        with patch.object(widget, "refresh"):
            widget.toggle_collapsed()

        assert widget.collapsed is False


class TestDocsSectionNavigation:
    """Tests for document navigation."""

    def test_selected_item_initial(self) -> None:
        """Test initial selection is first item."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "README.md").write_text("# Test")
            project = make_project(path=tmpdir)
            widget = DocsSection(project=project)
            widget.refresh_docs()

            assert widget.selected_item is not None
            assert widget.selected_item[0] == "README.md"

    def test_select_next(self) -> None:
        """Test selecting next item."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "README.md").write_text("# Test")
            (Path(tmpdir) / "CHANGELOG.md").write_text("# Changes")
            project = make_project(path=tmpdir)
            widget = DocsSection(project=project)
            widget.refresh_docs()

            with patch.object(widget, "refresh"):
                widget.select_next()

            assert widget.selected_item is not None
            assert widget.selected_item[0] == "CHANGELOG.md"

    def test_select_previous(self) -> None:
        """Test selecting previous item."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "README.md").write_text("# Test")
            (Path(tmpdir) / "CHANGELOG.md").write_text("# Changes")
            project = make_project(path=tmpdir)
            widget = DocsSection(project=project)
            widget.refresh_docs()

            with patch.object(widget, "refresh"):
                widget.select_next()  # Now at CHANGELOG.md
                widget.select_previous()  # Back to README.md

            assert widget.selected_item is not None
            assert widget.selected_item[0] == "README.md"

    def test_select_previous_at_start(self) -> None:
        """Test select_previous doesn't go below zero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "README.md").write_text("# Test")
            project = make_project(path=tmpdir)
            widget = DocsSection(project=project)
            widget.refresh_docs()

            with patch.object(widget, "refresh"):
                widget.select_previous()

            assert widget.selected_item is not None
            assert widget.selected_item[0] == "README.md"

    def test_select_next_at_end(self) -> None:
        """Test select_next doesn't exceed list bounds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "README.md").write_text("# Test")
            project = make_project(path=tmpdir)
            widget = DocsSection(project=project)
            widget.refresh_docs()

            with patch.object(widget, "refresh"):
                for _ in range(10):
                    widget.select_next()

            assert widget.selected_item is not None
            assert widget.selected_item[0] == "README.md"

    def test_select_when_collapsed_returns_none(self) -> None:
        """Test selected_item is None when collapsed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "README.md").write_text("# Test")
            project = make_project(path=tmpdir)
            widget = DocsSection(project=project, collapsed=True)
            widget.refresh_docs()

            assert widget.selected_item is None


class TestDocsSectionFileScanning:
    """Tests for document file scanning."""

    def test_scans_docs_directory(self) -> None:
        """Test scanning docs/ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            (docs_dir / "architecture.md").write_text("# Architecture")
            (docs_dir / "api-design.md").write_text("# API")

            project = make_project(path=tmpdir)
            widget = DocsSection(project=project)
            widget.refresh_docs()

            items = widget._get_all_items()
            names = [item[0] for item in items]

            assert "docs/architecture.md" in names
            assert "docs/api-design.md" in names

    def test_scans_specs_directory(self) -> None:
        """Test scanning specs/ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            specs_dir = Path(tmpdir) / "specs"
            specs_dir.mkdir()
            (specs_dir / "models.md").write_text("# Models")

            project = make_project(path=tmpdir)
            widget = DocsSection(project=project)
            widget.refresh_docs()

            items = widget._get_all_items()
            names = [item[0] for item in items]

            assert "specs/models.md" in names

    def test_scans_root_level_files(self) -> None:
        """Test scanning root-level documentation files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "README.md").write_text("# Test")
            (Path(tmpdir) / "CHANGELOG.md").write_text("# Changes")
            (Path(tmpdir) / "CONTRIBUTING.md").write_text("# Contributing")

            project = make_project(path=tmpdir)
            widget = DocsSection(project=project)
            widget.refresh_docs()

            items = widget._get_all_items()
            names = [item[0] for item in items]

            assert "README.md" in names
            assert "CHANGELOG.md" in names
            assert "CONTRIBUTING.md" in names

    def test_scans_nested_directories(self) -> None:
        """Test scanning nested directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = Path(tmpdir) / "docs" / "api"
            nested_dir.mkdir(parents=True)
            (nested_dir / "endpoints.md").write_text("# Endpoints")

            project = make_project(path=tmpdir)
            widget = DocsSection(project=project)
            widget.refresh_docs()

            items = widget._get_all_items()
            names = [item[0] for item in items]

            assert "docs/api/endpoints.md" in names

    def test_ignores_hidden_files(self) -> None:
        """Test hidden files are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            (docs_dir / ".hidden.md").write_text("# Hidden")
            (docs_dir / "visible.md").write_text("# Visible")

            project = make_project(path=tmpdir)
            widget = DocsSection(project=project)
            widget.refresh_docs()

            items = widget._get_all_items()
            names = [item[0] for item in items]

            assert "docs/.hidden.md" not in names
            assert "docs/visible.md" in names

    def test_ignores_non_doc_files(self) -> None:
        """Test non-documentation files are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            (docs_dir / "readme.md").write_text("# Readme")
            (docs_dir / "script.py").write_text("# Python")
            (docs_dir / "data.json").write_text("{}")

            project = make_project(path=tmpdir)
            widget = DocsSection(project=project)
            widget.refresh_docs()

            items = widget._get_all_items()
            names = [item[0] for item in items]

            assert "docs/readme.md" in names
            assert "docs/script.py" not in names
            assert "docs/data.json" not in names


class TestDocsSectionUrlReferences:
    """Tests for URL reference handling."""

    def test_includes_url_references(self) -> None:
        """Test URL references are included in items."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ref = make_doc_reference(
                id="ref-1",
                title="API Documentation",
                url="https://example.com/api",
            )
            project = make_project(path=tmpdir)
            project.doc_references = [ref]

            widget = DocsSection(project=project)
            widget.refresh_docs()

            items = widget._get_all_items()
            names = [item[0] for item in items]
            is_urls = [item[2] for item in items]

            assert "API Documentation" in names
            idx = names.index("API Documentation")
            assert is_urls[idx] is True

    def test_url_references_have_correct_data(self) -> None:
        """Test URL references have correct URL data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ref = make_doc_reference(
                id="ref-1",
                title="API Documentation",
                url="https://example.com/api",
            )
            project = make_project(path=tmpdir)
            project.doc_references = [ref]

            widget = DocsSection(project=project)
            widget.refresh_docs()

            items = widget._get_all_items()
            api_item = next(item for item in items if item[0] == "API Documentation")

            # (name, path, is_url, url)
            assert api_item[1] is None  # No path for URLs
            assert api_item[2] is True  # is_url
            assert api_item[3] == "https://example.com/api"  # url


class TestDocsSectionMessages:
    """Tests for message posting."""

    def test_doc_selected_message_file(self) -> None:
        """Test DocSelected message for file selection."""
        msg = DocsSection.DocSelected(
            doc_path=Path("/tmp/project/docs/readme.md"),
            doc_name="docs/readme.md",
            is_url=False,
            url="",
        )

        assert msg.doc_path == Path("/tmp/project/docs/readme.md")
        assert msg.doc_name == "docs/readme.md"
        assert msg.is_url is False
        assert msg.url == ""

    def test_doc_selected_message_url(self) -> None:
        """Test DocSelected message for URL selection."""
        msg = DocsSection.DocSelected(
            doc_path=None,
            doc_name="API Docs",
            is_url=True,
            url="https://example.com/api",
        )

        assert msg.doc_path is None
        assert msg.doc_name == "API Docs"
        assert msg.is_url is True
        assert msg.url == "https://example.com/api"

    def test_add_doc_requested_message(self) -> None:
        """Test AddDocRequested message."""
        msg = DocsSection.AddDocRequested()

        # Just verify it's a valid message instance
        assert isinstance(msg, DocsSection.AddDocRequested)


class TestDocsSectionRendering:
    """Tests for rendering methods."""

    def test_render_doc_item_file(self) -> None:
        """Test _render_doc_item for file."""
        widget = DocsSection()

        text = widget._render_doc_item(
            name="docs/readme.md",
            is_url=False,
            is_selected=False,
        )
        rendered = str(text)

        assert "docs/readme.md" in rendered
        assert "•" in rendered  # File icon

    def test_render_doc_item_url(self) -> None:
        """Test _render_doc_item for URL."""
        widget = DocsSection()

        text = widget._render_doc_item(
            name="API Documentation",
            is_url=True,
            is_selected=False,
        )
        rendered = str(text)

        assert "API Documentation" in rendered
        assert "🌐" in rendered  # URL icon

    def test_render_doc_item_selected(self) -> None:
        """Test _render_doc_item shows selection indicator."""
        widget = DocsSection()

        text = widget._render_doc_item(
            name="docs/readme.md",
            is_url=False,
            is_selected=True,
        )
        rendered = str(text)

        assert ">" in rendered  # Selection indicator
        assert "[e]" in rendered  # Edit hint

    def test_render_doc_item_not_selected(self) -> None:
        """Test _render_doc_item without selection."""
        widget = DocsSection()

        text = widget._render_doc_item(
            name="docs/readme.md",
            is_url=False,
            is_selected=False,
        )
        rendered = str(text)

        assert "[e]" not in rendered  # No edit hint when not selected


class TestDocsSectionRefresh:
    """Tests for refresh methods."""

    def test_refresh_docs_updates_file_list(self) -> None:
        """Test refresh_docs updates the file list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = DocsSection(project=project)
            widget.refresh_docs()

            # Initially empty
            assert widget.get_doc_count() == 0

            # Create file
            (Path(tmpdir) / "README.md").write_text("# Test")

            # Refresh
            widget.refresh_docs()

            # Should now have one file
            assert widget.get_doc_count() == 1

    def test_set_project_sets_project(self) -> None:
        """Test set_project sets the project reference."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "README.md").write_text("# Test")

            widget = DocsSection()
            assert widget.project is None

            project = make_project(path=tmpdir)
            widget._project = project
            widget.refresh_docs()

            assert widget.project == project
            assert widget.get_doc_count() == 1


class TestDocsSectionGetDocCount:
    """Tests for get_doc_count method."""

    def test_get_doc_count_empty(self) -> None:
        """Test get_doc_count with no documents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = DocsSection(project=project)
            widget.refresh_docs()

            assert widget.get_doc_count() == 0

    def test_get_doc_count_files_only(self) -> None:
        """Test get_doc_count with files only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "README.md").write_text("# Test")
            (Path(tmpdir) / "CHANGELOG.md").write_text("# Changes")

            project = make_project(path=tmpdir)
            widget = DocsSection(project=project)
            widget.refresh_docs()

            assert widget.get_doc_count() == 2

    def test_get_doc_count_urls_only(self) -> None:
        """Test get_doc_count with URLs only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ref1 = make_doc_reference(id="ref-1", title="API Docs")
            ref2 = make_doc_reference(id="ref-2", title="Wiki")

            project = make_project(path=tmpdir)
            project.doc_references = [ref1, ref2]

            widget = DocsSection(project=project)
            widget.refresh_docs()

            assert widget.get_doc_count() == 2

    def test_get_doc_count_mixed(self) -> None:
        """Test get_doc_count with files and URLs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "README.md").write_text("# Test")

            ref = make_doc_reference(id="ref-1", title="API Docs")
            project = make_project(path=tmpdir)
            project.doc_references = [ref]

            widget = DocsSection(project=project)
            widget.refresh_docs()

            assert widget.get_doc_count() == 2


class TestDocsSectionIsDocFile:
    """Tests for _is_doc_file method."""

    def test_is_doc_file_markdown(self) -> None:
        """Test markdown files are recognized."""
        widget = DocsSection()

        assert widget._is_doc_file(Path("readme.md")) is True
        assert widget._is_doc_file(Path("README.MD")) is True

    def test_is_doc_file_text(self) -> None:
        """Test text files are recognized."""
        widget = DocsSection()

        assert widget._is_doc_file(Path("notes.txt")) is True

    def test_is_doc_file_rst(self) -> None:
        """Test RST files are recognized."""
        widget = DocsSection()

        assert widget._is_doc_file(Path("docs.rst")) is True

    def test_is_doc_file_adoc(self) -> None:
        """Test AsciiDoc files are recognized."""
        widget = DocsSection()

        assert widget._is_doc_file(Path("manual.adoc")) is True

    def test_is_doc_file_python_not_doc(self) -> None:
        """Test Python files are not documentation."""
        widget = DocsSection()

        assert widget._is_doc_file(Path("script.py")) is False

    def test_is_doc_file_hidden_not_doc(self) -> None:
        """Test hidden files are not documentation."""
        widget = DocsSection()

        assert widget._is_doc_file(Path(".hidden.md")) is False
