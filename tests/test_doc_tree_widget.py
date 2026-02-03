"""Tests for the DocTreeWidget."""

import tempfile
from pathlib import Path

import pytest

from iterm_controller.models import DocReference
from iterm_controller.widgets.doc_tree import (
    DOC_DIRECTORIES,
    DOC_EXTENSIONS,
    DOC_FILES,
    DocNode,
    DocTreeWidget,
)


class TestDocTreeWidgetConstants:
    """Tests for DocTreeWidget constants."""

    def test_doc_directories_includes_standard_dirs(self) -> None:
        """Test that DOC_DIRECTORIES includes standard documentation directories."""
        assert "docs/" in DOC_DIRECTORIES
        assert "specs/" in DOC_DIRECTORIES
        assert "documentation/" in DOC_DIRECTORIES

    def test_doc_files_includes_standard_files(self) -> None:
        """Test that DOC_FILES includes standard documentation files."""
        assert "README.md" in DOC_FILES
        assert "CHANGELOG.md" in DOC_FILES
        assert "CONTRIBUTING.md" in DOC_FILES
        assert "LICENSE" in DOC_FILES

    def test_doc_extensions_includes_common_formats(self) -> None:
        """Test that DOC_EXTENSIONS includes common documentation formats."""
        assert ".md" in DOC_EXTENSIONS
        assert ".txt" in DOC_EXTENSIONS
        assert ".rst" in DOC_EXTENSIONS


class TestDocNodeDataclass:
    """Tests for the DocNode dataclass."""

    def test_doc_node_creation(self) -> None:
        """Test creating a DocNode."""
        node = DocNode(
            path=Path("/test/docs/file.md"),
            is_directory=False,
            name="file.md",
        )

        assert node.path == Path("/test/docs/file.md")
        assert node.is_directory is False
        assert node.name == "file.md"

    def test_doc_node_directory(self) -> None:
        """Test creating a DocNode for a directory."""
        node = DocNode(
            path=Path("/test/docs"),
            is_directory=True,
            name="docs",
        )

        assert node.is_directory is True


class TestDocTreeWidgetBasic:
    """Basic tests for DocTreeWidget."""

    def test_widget_creation(self) -> None:
        """Test that DocTreeWidget can be created."""
        widget = DocTreeWidget()
        assert widget is not None

    def test_widget_creation_with_project_path(self) -> None:
        """Test that DocTreeWidget can be created with a project path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            widget = DocTreeWidget(project_path=tmpdir)
            assert widget._project_path == Path(tmpdir)

    def test_set_project(self) -> None:
        """Test setting the project path after creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            widget = DocTreeWidget()
            widget.set_project(tmpdir)
            assert widget._project_path == Path(tmpdir)

    def test_selected_path_initially_none(self) -> None:
        """Test that selected_path is None initially."""
        widget = DocTreeWidget()
        assert widget.selected_path is None

    def test_selected_is_file_initially_false(self) -> None:
        """Test that selected_is_file is False initially."""
        widget = DocTreeWidget()
        assert widget.selected_is_file is False

    def test_selected_is_directory_initially_false(self) -> None:
        """Test that selected_is_directory is False initially."""
        widget = DocTreeWidget()
        assert widget.selected_is_directory is False


class TestDocTreeWidgetBuildTree:
    """Tests for DocTreeWidget.build_tree()."""

    def test_build_tree_empty_project(self) -> None:
        """Test building tree for a project with no docs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            widget = DocTreeWidget(project_path=tmpdir)
            widget.build_tree()

            # Should have root but no children
            assert widget.root is not None
            assert len(list(widget.root.children)) == 0

    def test_build_tree_with_readme(self) -> None:
        """Test building tree with README.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create README.md
            (Path(tmpdir) / "README.md").write_text("# Test")

            widget = DocTreeWidget(project_path=tmpdir)
            widget.build_tree()

            # Should have README.md as a child
            children = list(widget.root.children)
            assert len(children) == 1
            assert children[0].data.name == "README.md"
            assert children[0].data.is_directory is False

    def test_build_tree_with_docs_directory(self) -> None:
        """Test building tree with docs/ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create docs/ with a file
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            (docs_dir / "guide.md").write_text("# Guide")

            widget = DocTreeWidget(project_path=tmpdir)
            widget.build_tree()

            # Should have docs/ as a child
            children = list(widget.root.children)
            assert len(children) == 1
            assert children[0].data.name == "docs"
            assert children[0].data.is_directory is True

            # docs/ should have guide.md
            docs_children = list(children[0].children)
            assert len(docs_children) == 1
            assert docs_children[0].data.name == "guide.md"

    def test_build_tree_with_specs_directory(self) -> None:
        """Test building tree with specs/ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create specs/ with files
            specs_dir = Path(tmpdir) / "specs"
            specs_dir.mkdir()
            (specs_dir / "models.md").write_text("# Models")
            (specs_dir / "api.md").write_text("# API")

            widget = DocTreeWidget(project_path=tmpdir)
            widget.build_tree()

            # Should have specs/ as a child
            children = list(widget.root.children)
            assert len(children) == 1
            assert children[0].data.name == "specs"

            # specs/ should have 2 files
            specs_children = list(children[0].children)
            assert len(specs_children) == 2

    def test_build_tree_ignores_hidden_files(self) -> None:
        """Test that build_tree ignores hidden files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create docs/ with hidden and normal files
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            (docs_dir / ".hidden.md").write_text("# Hidden")
            (docs_dir / "visible.md").write_text("# Visible")

            widget = DocTreeWidget(project_path=tmpdir)
            widget.build_tree()

            # Should have docs/ as a child
            docs_node = list(widget.root.children)[0]
            docs_children = list(docs_node.children)

            # Should only have visible.md
            assert len(docs_children) == 1
            assert docs_children[0].data.name == "visible.md"

    def test_build_tree_ignores_hidden_directories(self) -> None:
        """Test that build_tree ignores hidden directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create docs/ with hidden subdirectory
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            hidden_dir = docs_dir / ".hidden"
            hidden_dir.mkdir()
            (hidden_dir / "file.md").write_text("# Hidden File")
            (docs_dir / "visible.md").write_text("# Visible")

            widget = DocTreeWidget(project_path=tmpdir)
            widget.build_tree()

            # Should only have visible.md
            docs_node = list(widget.root.children)[0]
            docs_children = list(docs_node.children)
            assert len(docs_children) == 1
            assert docs_children[0].data.name == "visible.md"

    def test_build_tree_nested_directories(self) -> None:
        """Test building tree with nested directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested structure
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            arch_dir = docs_dir / "architecture"
            arch_dir.mkdir()
            (arch_dir / "overview.md").write_text("# Overview")

            widget = DocTreeWidget(project_path=tmpdir)
            widget.build_tree()

            # Navigate to nested file
            docs_node = list(widget.root.children)[0]
            arch_node = list(docs_node.children)[0]
            overview_node = list(arch_node.children)[0]

            assert docs_node.data.name == "docs"
            assert arch_node.data.name == "architecture"
            assert overview_node.data.name == "overview.md"

    def test_build_tree_sorts_directories_first(self) -> None:
        """Test that directories come before files in the tree."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create docs/ with mixed files and directories
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            (docs_dir / "z-file.md").write_text("# Z File")
            (docs_dir / "a-file.md").write_text("# A File")
            subdir = docs_dir / "b-subdir"
            subdir.mkdir()
            (subdir / "nested.md").write_text("# Nested")

            widget = DocTreeWidget(project_path=tmpdir)
            widget.build_tree()

            # Get docs children
            docs_node = list(widget.root.children)[0]
            docs_children = list(docs_node.children)

            # First should be b-subdir (directory), then a-file.md, then z-file.md
            assert docs_children[0].data.name == "b-subdir"
            assert docs_children[0].data.is_directory is True
            assert docs_children[1].data.name == "a-file.md"
            assert docs_children[2].data.name == "z-file.md"

    def test_build_tree_only_includes_doc_extensions(self) -> None:
        """Test that only documentation files are included."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create docs/ with various file types
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            (docs_dir / "guide.md").write_text("# Guide")
            (docs_dir / "notes.txt").write_text("Notes")
            (docs_dir / "script.py").write_text("# Python file")
            (docs_dir / "data.json").write_text("{}")

            widget = DocTreeWidget(project_path=tmpdir)
            widget.build_tree()

            # Get docs children
            docs_node = list(widget.root.children)[0]
            docs_children = list(docs_node.children)

            # Should only have .md and .txt files
            names = [c.data.name for c in docs_children]
            assert "guide.md" in names
            assert "notes.txt" in names
            assert "script.py" not in names
            assert "data.json" not in names


class TestDocTreeWidgetRefresh:
    """Tests for DocTreeWidget.refresh_tree()."""

    def test_refresh_tree_adds_new_files(self) -> None:
        """Test that refresh_tree picks up new files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            widget = DocTreeWidget(project_path=tmpdir)
            widget.build_tree()

            # Initially empty
            assert len(list(widget.root.children)) == 0

            # Create a file
            (Path(tmpdir) / "README.md").write_text("# Test")

            # Refresh
            widget.refresh_tree()

            # Now should have the file
            assert len(list(widget.root.children)) == 1

    def test_refresh_tree_removes_deleted_files(self) -> None:
        """Test that refresh_tree removes deleted files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial file
            readme_path = Path(tmpdir) / "README.md"
            readme_path.write_text("# Test")

            widget = DocTreeWidget(project_path=tmpdir)
            widget.build_tree()

            # Initially has file
            assert len(list(widget.root.children)) == 1

            # Delete the file
            readme_path.unlink()

            # Refresh
            widget.refresh_tree()

            # Now should be empty
            assert len(list(widget.root.children)) == 0


class TestDocTreeWidgetIsDocFile:
    """Tests for DocTreeWidget._is_doc_file()."""

    def test_is_doc_file_markdown(self) -> None:
        """Test that .md files are recognized as docs."""
        widget = DocTreeWidget()
        assert widget._is_doc_file(Path("test.md")) is True

    def test_is_doc_file_text(self) -> None:
        """Test that .txt files are recognized as docs."""
        widget = DocTreeWidget()
        assert widget._is_doc_file(Path("test.txt")) is True

    def test_is_doc_file_rst(self) -> None:
        """Test that .rst files are recognized as docs."""
        widget = DocTreeWidget()
        assert widget._is_doc_file(Path("test.rst")) is True

    def test_is_doc_file_python_not_doc(self) -> None:
        """Test that .py files are not recognized as docs."""
        widget = DocTreeWidget()
        assert widget._is_doc_file(Path("test.py")) is False

    def test_is_doc_file_hidden_not_doc(self) -> None:
        """Test that hidden files are not recognized as docs."""
        widget = DocTreeWidget()
        assert widget._is_doc_file(Path(".hidden.md")) is False


# TestDocTreeWidgetAsync was removed in task 27.9.3
# as it depended on DocsModeScreen which has been deprecated


class TestDocNodeUrlSupport:
    """Tests for URL support in DocNode dataclass."""

    def test_doc_node_with_url_defaults(self) -> None:
        """Test creating a DocNode with URL default values."""
        node = DocNode(
            path=Path("/test/file.md"),
            is_directory=False,
            name="file.md",
        )

        assert node.is_url is False
        assert node.url == ""
        assert node.reference_id == ""
        assert node.category == ""

    def test_doc_node_url_reference(self) -> None:
        """Test creating a DocNode for a URL reference."""
        node = DocNode(
            path=None,
            is_directory=False,
            name="Textual Docs",
            is_url=True,
            url="https://textual.textualize.io/",
            reference_id="ref-123",
            category="API Docs",
        )

        assert node.path is None
        assert node.is_directory is False
        assert node.is_url is True
        assert node.url == "https://textual.textualize.io/"
        assert node.reference_id == "ref-123"
        assert node.category == "API Docs"


class TestDocTreeWidgetUrlReferences:
    """Tests for URL reference support in DocTreeWidget."""

    def test_selected_is_url_initially_false(self) -> None:
        """Test that selected_is_url is False initially."""
        widget = DocTreeWidget()
        assert widget.selected_is_url is False

    def test_selected_url_initially_none(self) -> None:
        """Test that selected_url is None initially."""
        widget = DocTreeWidget()
        assert widget.selected_url is None

    def test_selected_reference_id_initially_none(self) -> None:
        """Test that selected_reference_id is None initially."""
        widget = DocTreeWidget()
        assert widget.selected_reference_id is None

    def test_set_project_with_references(self) -> None:
        """Test setting project with doc references."""
        with tempfile.TemporaryDirectory() as tmpdir:
            references = [
                DocReference(
                    id="ref1",
                    title="Textual Docs",
                    url="https://textual.textualize.io/",
                    category="API Docs",
                ),
                DocReference(
                    id="ref2",
                    title="iTerm2 API",
                    url="https://iterm2.com/python-api/",
                    category="API Docs",
                ),
                DocReference(
                    id="ref3",
                    title="Design Spec",
                    url="https://figma.com/example",
                ),
            ]

            widget = DocTreeWidget()
            widget.set_project(tmpdir, references)

            # Should have doc references stored
            assert widget._doc_references == references

    def test_build_tree_includes_references_section(self) -> None:
        """Test that build_tree adds External References section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            references = [
                DocReference(
                    id="ref1",
                    title="Textual Docs",
                    url="https://textual.textualize.io/",
                ),
            ]

            widget = DocTreeWidget(project_path=tmpdir)
            widget._doc_references = references
            widget.build_tree()

            # Should have External References section
            children = list(widget.root.children)
            assert len(children) == 1
            assert "External References" in children[0].label

    def test_build_tree_categorizes_references(self) -> None:
        """Test that references are grouped by category."""
        with tempfile.TemporaryDirectory() as tmpdir:
            references = [
                DocReference(
                    id="ref1",
                    title="Textual Docs",
                    url="https://textual.textualize.io/",
                    category="API Docs",
                ),
                DocReference(
                    id="ref2",
                    title="iTerm2 API",
                    url="https://iterm2.com/python-api/",
                    category="API Docs",
                ),
                DocReference(
                    id="ref3",
                    title="Design Spec",
                    url="https://figma.com/example",
                ),
            ]

            widget = DocTreeWidget(project_path=tmpdir)
            widget._doc_references = references
            widget.build_tree()

            # Find External References section
            refs_section = list(widget.root.children)[0]

            # Should have "API Docs" category and one uncategorized reference
            refs_children = list(refs_section.children)
            assert len(refs_children) == 2  # API Docs category + Design Spec

            # First should be the category
            api_category = refs_children[0]
            assert "API Docs" in str(api_category.label)
            assert len(list(api_category.children)) == 2

            # Second should be the uncategorized reference
            design_ref = refs_children[1]
            assert design_ref.data.is_url is True
            assert design_ref.data.name == "Design Spec"

    def test_update_references(self) -> None:
        """Test update_references method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            widget = DocTreeWidget(project_path=tmpdir)
            widget.build_tree()

            # Initially no references
            assert widget._doc_references == []

            # Add references
            new_refs = [
                DocReference(
                    id="ref1",
                    title="New Doc",
                    url="https://example.com/",
                ),
            ]
            widget.update_references(new_refs)

            # Should have the new references
            assert widget._doc_references == new_refs

            # Tree should be rebuilt with references
            children = list(widget.root.children)
            assert len(children) == 1
            assert "External References" in children[0].label

    def test_no_references_section_when_empty(self) -> None:
        """Test that External References section is not added when empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            widget = DocTreeWidget(project_path=tmpdir)
            widget.build_tree()

            # Should have no children (no docs, no references)
            assert len(list(widget.root.children)) == 0


class TestDocReferenceModel:
    """Tests for DocReference model."""

    def test_doc_reference_creation(self) -> None:
        """Test creating a DocReference."""
        ref = DocReference(
            id="ref-123",
            title="Textual Documentation",
            url="https://textual.textualize.io/",
            category="API Docs",
            notes="Primary framework documentation",
        )

        assert ref.id == "ref-123"
        assert ref.title == "Textual Documentation"
        assert ref.url == "https://textual.textualize.io/"
        assert ref.category == "API Docs"
        assert ref.notes == "Primary framework documentation"

    def test_doc_reference_defaults(self) -> None:
        """Test DocReference default values."""
        ref = DocReference(
            id="ref-123",
            title="Test",
            url="https://example.com/",
        )

        assert ref.category == ""
        assert ref.notes == ""

    def test_doc_reference_serialization(self) -> None:
        """Test DocReference serializes to JSON-compatible dict."""
        from dataclasses import asdict

        ref = DocReference(
            id="ref-123",
            title="Test",
            url="https://example.com/",
            category="Test Cat",
        )

        data = asdict(ref)
        assert data == {
            "id": "ref-123",
            "title": "Test",
            "url": "https://example.com/",
            "category": "Test Cat",
            "notes": "",
        }

    def test_doc_reference_in_project(self) -> None:
        """Test that Project model includes doc_references field."""
        from iterm_controller.models import Project

        project = Project(
            id="test",
            name="Test Project",
            path="/tmp/test",
        )

        # Should have empty list by default
        assert project.doc_references == []

        # Can add references
        ref = DocReference(
            id="ref1",
            title="Test Doc",
            url="https://example.com/",
        )
        project.doc_references.append(ref)

        assert len(project.doc_references) == 1
        assert project.doc_references[0].title == "Test Doc"
