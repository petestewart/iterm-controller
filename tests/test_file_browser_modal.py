"""Tests for FileBrowserModal."""

import tempfile
from pathlib import Path

import pytest

from iterm_controller.screens.modals.file_browser import (
    FileBrowserModal,
    FileBrowserTree,
    FileNode,
)


class TestFileNode:
    """Tests for FileNode dataclass."""

    def test_file_node_creation(self) -> None:
        """Test creating a FileNode."""
        node = FileNode(
            path=Path("/test/file.md"),
            is_directory=False,
            name="file.md",
        )
        assert node.path == Path("/test/file.md")
        assert node.is_directory is False
        assert node.name == "file.md"

    def test_directory_node_creation(self) -> None:
        """Test creating a directory FileNode."""
        node = FileNode(
            path=Path("/test/dir"),
            is_directory=True,
            name="dir",
        )
        assert node.path == Path("/test/dir")
        assert node.is_directory is True
        assert node.name == "dir"


class TestFileBrowserTree:
    """Tests for FileBrowserTree widget."""

    def test_tree_creation(self) -> None:
        """Test creating a FileBrowserTree."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tree = FileBrowserTree(tmpdir)
            assert tree._project_path == Path(tmpdir)

    def test_selected_path_none_initially(self) -> None:
        """Test that selected_path is None before any selection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tree = FileBrowserTree(tmpdir)
            assert tree.selected_path is None

    def test_selected_is_file_false_initially(self) -> None:
        """Test that selected_is_file is False before any selection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tree = FileBrowserTree(tmpdir)
            assert tree.selected_is_file is False

    def test_selected_is_directory_false_initially(self) -> None:
        """Test that selected_is_directory is False before any selection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tree = FileBrowserTree(tmpdir)
            assert tree.selected_is_directory is False

    def test_allowed_extensions(self) -> None:
        """Test that allowed extensions include common doc types."""
        assert ".md" in FileBrowserTree.ALLOWED_EXTENSIONS
        assert ".txt" in FileBrowserTree.ALLOWED_EXTENSIONS
        assert ".rst" in FileBrowserTree.ALLOWED_EXTENSIONS
        assert ".json" in FileBrowserTree.ALLOWED_EXTENSIONS
        assert ".yaml" in FileBrowserTree.ALLOWED_EXTENSIONS
        assert ".yml" in FileBrowserTree.ALLOWED_EXTENSIONS


class TestFileBrowserModal:
    """Tests for FileBrowserModal."""

    def test_modal_creation(self) -> None:
        """Test creating a FileBrowserModal."""
        with tempfile.TemporaryDirectory() as tmpdir:
            modal = FileBrowserModal(tmpdir)
            assert modal._project_path == Path(tmpdir)
            assert modal._title == "Select File"
            assert modal._description == "Browse and select a file to add"

    def test_modal_creation_with_custom_title(self) -> None:
        """Test creating modal with custom title and description."""
        with tempfile.TemporaryDirectory() as tmpdir:
            modal = FileBrowserModal(
                tmpdir,
                title="Custom Title",
                description="Custom description",
            )
            assert modal._title == "Custom Title"
            assert modal._description == "Custom description"


@pytest.mark.asyncio
class TestFileBrowserModalAsync:
    """Async tests for FileBrowserModal."""

    async def test_modal_renders(self) -> None:
        """Test that the modal renders correctly."""
        from iterm_controller.app import ItermControllerApp

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("# Test")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                modal = FileBrowserModal(tmpdir)
                app.push_screen(modal)
                await pilot.pause()

                # Should have file tree
                tree = app.screen.query_one("#file-tree", FileBrowserTree)
                assert tree is not None

                # Should have cancel and select buttons
                cancel_btn = app.screen.query_one("#cancel")
                select_btn = app.screen.query_one("#select")
                assert cancel_btn is not None
                assert select_btn is not None

    async def test_cancel_dismisses_with_none(self) -> None:
        """Test that cancel button dismisses with None."""
        from iterm_controller.app import ItermControllerApp

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test() as pilot:
                results: list[Path | None] = []

                def callback(result: Path | None) -> None:
                    results.append(result)

                modal = FileBrowserModal(tmpdir)
                app.push_screen(modal, callback)
                await pilot.pause()

                # Press escape to cancel
                await pilot.press("escape")
                await pilot.pause()

                assert len(results) == 1
                assert results[0] is None

    async def test_tree_builds_on_mount(self) -> None:
        """Test that tree builds when modal is mounted."""
        from iterm_controller.app import ItermControllerApp

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some test files
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            (docs_dir / "readme.md").write_text("# Readme")
            (Path(tmpdir) / "config.yaml").write_text("key: value")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                modal = FileBrowserModal(tmpdir)
                app.push_screen(modal)
                await pilot.pause()

                tree = app.screen.query_one("#file-tree", FileBrowserTree)
                # Tree should have root expanded
                assert tree.root.is_expanded

    async def test_shows_selected_path(self) -> None:
        """Test that selected path is displayed."""
        from textual.widgets import Static

        from iterm_controller.app import ItermControllerApp

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("# Test")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                modal = FileBrowserModal(tmpdir)
                app.push_screen(modal)
                await pilot.pause()

                # Should have path display area
                path_label = app.screen.query_one("#selected-path", Static)
                assert path_label is not None

    async def test_vim_navigation_keys(self) -> None:
        """Test that vim navigation keys work."""
        from iterm_controller.app import ItermControllerApp

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            (Path(tmpdir) / "a.md").write_text("a")
            (Path(tmpdir) / "b.md").write_text("b")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                modal = FileBrowserModal(tmpdir)
                app.push_screen(modal)
                await pilot.pause()

                # Press j to move down
                await pilot.press("j")
                await pilot.pause()

                # Press k to move up
                await pilot.press("k")
                await pilot.pause()

                # Should not crash
                assert app.screen is modal

    async def test_skips_hidden_files(self) -> None:
        """Test that hidden files and directories are skipped."""
        from iterm_controller.app import ItermControllerApp

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create hidden file
            (Path(tmpdir) / ".hidden.md").write_text("hidden")
            # Create visible file
            (Path(tmpdir) / "visible.md").write_text("visible")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                modal = FileBrowserModal(tmpdir)
                app.push_screen(modal)
                await pilot.pause()

                tree = app.screen.query_one("#file-tree", FileBrowserTree)

                # Hidden file should not be in tree
                def find_hidden(node):
                    if node.data and node.data.name == ".hidden.md":
                        return True
                    for child in node.children:
                        if find_hidden(child):
                            return True
                    return False

                assert not find_hidden(tree.root)

    async def test_skips_node_modules(self) -> None:
        """Test that node_modules directory is skipped."""
        from iterm_controller.app import ItermControllerApp

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create node_modules with a file
            nm_dir = Path(tmpdir) / "node_modules"
            nm_dir.mkdir()
            (nm_dir / "package.json").write_text("{}")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                modal = FileBrowserModal(tmpdir)
                app.push_screen(modal)
                await pilot.pause()

                tree = app.screen.query_one("#file-tree", FileBrowserTree)

                # node_modules should not be in tree
                def find_node_modules(node):
                    if node.data and node.data.name == "node_modules":
                        return True
                    for child in node.children:
                        if find_node_modules(child):
                            return True
                    return False

                assert not find_node_modules(tree.root)


class TestAddContentTypeModalIntegration:
    """Tests for updated AddContentTypeModal with Browse option."""

    def test_content_type_enum_has_browse(self) -> None:
        """Test that ContentType enum includes BROWSE."""
        from iterm_controller.screens.modals.add_content_type import ContentType

        assert hasattr(ContentType, "BROWSE")
        assert ContentType.BROWSE.value == "browse"


@pytest.mark.asyncio
class TestAddContentTypeModalAsync:
    """Async tests for AddContentTypeModal with Browse option."""

    async def test_browse_button_exists(self) -> None:
        """Test that the browse button exists."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.screens.modals.add_content_type import AddContentTypeModal

        app = ItermControllerApp()
        async with app.run_test() as pilot:
            modal = AddContentTypeModal()
            app.push_screen(modal)
            await pilot.pause()

            # Should have browse button
            browse_btn = app.screen.query_one("#browse")
            assert browse_btn is not None

    async def test_browse_key_shortcut(self) -> None:
        """Test that 'b' key selects browse option."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.screens.modals.add_content_type import (
            AddContentTypeModal,
            ContentType,
        )

        app = ItermControllerApp()
        async with app.run_test() as pilot:
            results: list[ContentType | None] = []

            def callback(result: ContentType | None) -> None:
                results.append(result)

            modal = AddContentTypeModal()
            app.push_screen(modal, callback)
            await pilot.pause()

            # Press 'b' to select browse
            await pilot.press("b")
            await pilot.pause()

            assert len(results) == 1
            assert results[0] == ContentType.BROWSE

    async def test_new_file_key_is_n(self) -> None:
        """Test that 'n' key selects new file option."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.screens.modals.add_content_type import (
            AddContentTypeModal,
            ContentType,
        )

        app = ItermControllerApp()
        async with app.run_test() as pilot:
            results: list[ContentType | None] = []

            def callback(result: ContentType | None) -> None:
                results.append(result)

            modal = AddContentTypeModal()
            app.push_screen(modal, callback)
            await pilot.pause()

            # Press 'n' to select new file
            await pilot.press("n")
            await pilot.pause()

            assert len(results) == 1
            assert results[0] == ContentType.FILE
