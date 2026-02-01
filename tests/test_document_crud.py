"""Tests for document CRUD operations in Docs Mode.

Tests for AddDocumentModal, DeleteConfirmModal, RenameDocumentModal,
and the integration with DocsModeScreen.
"""

import tempfile
from pathlib import Path

import pytest

from iterm_controller.screens.modals.add_document import AddDocumentModal
from iterm_controller.screens.modals.delete_confirm import DeleteConfirmModal
from iterm_controller.screens.modals.rename_document import RenameDocumentModal


class TestAddDocumentModal:
    """Tests for AddDocumentModal."""

    def test_modal_creation(self) -> None:
        """Test that AddDocumentModal can be created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            modal = AddDocumentModal(project_path=tmpdir)
            assert modal is not None

    def test_modal_creation_with_default_directory(self) -> None:
        """Test creating modal with a default directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            modal = AddDocumentModal(
                project_path=tmpdir,
                default_directory=str(docs_dir),
            )
            assert modal._default_directory == str(docs_dir)

    def test_get_directories_empty_project(self) -> None:
        """Test getting directories from an empty project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            modal = AddDocumentModal(project_path=tmpdir)
            dirs = modal._get_directories()
            # Should only have root directory
            assert dirs == ["."]

    def test_get_directories_with_docs(self) -> None:
        """Test getting directories with docs/ present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            modal = AddDocumentModal(project_path=tmpdir)
            dirs = modal._get_directories()
            assert "." in dirs
            assert "docs" in dirs

    def test_get_directories_with_nested_subdirs(self) -> None:
        """Test getting directories with nested subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            arch_dir = docs_dir / "architecture"
            arch_dir.mkdir()
            modal = AddDocumentModal(project_path=tmpdir)
            dirs = modal._get_directories()
            assert "docs" in dirs
            assert "docs/architecture" in dirs

    def test_get_relative_default_root(self) -> None:
        """Test getting relative default for root directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            modal = AddDocumentModal(project_path=tmpdir)
            assert modal._get_relative_default() == "."

    def test_get_relative_default_subdirectory(self) -> None:
        """Test getting relative default for a subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()
            modal = AddDocumentModal(
                project_path=tmpdir,
                default_directory=str(docs_dir),
            )
            assert modal._get_relative_default() == "docs"


class TestDeleteConfirmModal:
    """Tests for DeleteConfirmModal."""

    def test_modal_creation(self) -> None:
        """Test that DeleteConfirmModal can be created."""
        modal = DeleteConfirmModal(item_name="test.md")
        assert modal is not None
        assert modal._item_name == "test.md"

    def test_modal_creation_with_type(self) -> None:
        """Test creating modal with custom item type."""
        modal = DeleteConfirmModal(item_name="test.md", item_type="document")
        assert modal._item_type == "document"

    def test_default_item_type(self) -> None:
        """Test default item type is 'file'."""
        modal = DeleteConfirmModal(item_name="test.md")
        assert modal._item_type == "file"


class TestRenameDocumentModal:
    """Tests for RenameDocumentModal."""

    def test_modal_creation(self) -> None:
        """Test that RenameDocumentModal can be created."""
        modal = RenameDocumentModal(current_name="old.md")
        assert modal is not None
        assert modal._current_name == "old.md"


@pytest.mark.asyncio
class TestAddDocumentModalAsync:
    """Async tests for AddDocumentModal."""

    async def test_modal_compose(self) -> None:
        """Test that modal composes correctly."""
        from textual.app import App

        with tempfile.TemporaryDirectory() as tmpdir:

            class TestApp(App):
                async def on_mount(self):
                    modal = AddDocumentModal(project_path=tmpdir)
                    await self.push_screen(modal)

            app = TestApp()
            async with app.run_test():
                # Check that the modal has expected widgets
                assert app.screen.query_one("#filename") is not None
                assert app.screen.query_one("#location") is not None
                assert app.screen.query_one("#create") is not None
                assert app.screen.query_one("#cancel") is not None

    async def test_modal_cancel(self) -> None:
        """Test that cancel button dismisses with None."""
        from textual.app import App
        from textual.widgets import Button

        result = None

        with tempfile.TemporaryDirectory() as tmpdir:

            class TestApp(App):
                async def on_mount(self):
                    nonlocal result

                    def callback(r):
                        nonlocal result
                        result = r

                    modal = AddDocumentModal(project_path=tmpdir)
                    await self.push_screen(modal, callback)

            app = TestApp()
            async with app.run_test() as pilot:
                # Press the cancel button
                app.screen.query_one("#cancel", Button).press()
                await pilot.pause()
                assert result is None

    async def test_modal_create_empty_filename(self) -> None:
        """Test that empty filename shows warning."""
        from textual.app import App
        from textual.widgets import Button

        with tempfile.TemporaryDirectory() as tmpdir:

            class TestApp(App):
                async def on_mount(self):
                    modal = AddDocumentModal(project_path=tmpdir)
                    await self.push_screen(modal)

            app = TestApp()
            async with app.run_test() as pilot:
                # Press create without entering filename
                app.screen.query_one("#create", Button).press()
                await pilot.pause()
                # Modal should still be open (not dismissed)
                assert isinstance(app.screen, AddDocumentModal)

    async def test_modal_create_adds_md_extension(self) -> None:
        """Test that .md extension is added if missing."""
        from textual.app import App
        from textual.widgets import Button, Input

        result = None

        with tempfile.TemporaryDirectory() as tmpdir:

            class TestApp(App):
                async def on_mount(self):
                    nonlocal result

                    def callback(r):
                        nonlocal result
                        result = r

                    modal = AddDocumentModal(project_path=tmpdir)
                    await self.push_screen(modal, callback)

            app = TestApp()
            async with app.run_test() as pilot:
                # Enter filename without extension
                filename_input = app.screen.query_one("#filename", Input)
                filename_input.value = "test-doc"

                # Press create
                app.screen.query_one("#create", Button).press()
                await pilot.pause()

                assert result is not None
                assert result["path"].endswith(".md")

    async def test_modal_rejects_path_traversal_double_dots(self) -> None:
        """Test that filenames with '..' are rejected."""
        from textual.app import App
        from textual.widgets import Button, Input

        result = "not_set"

        with tempfile.TemporaryDirectory() as tmpdir:

            class TestApp(App):
                async def on_mount(self):
                    nonlocal result

                    def callback(r):
                        nonlocal result
                        result = r

                    modal = AddDocumentModal(project_path=tmpdir)
                    await self.push_screen(modal, callback)

            app = TestApp()
            async with app.run_test() as pilot:
                # Try to enter path traversal sequence
                filename_input = app.screen.query_one("#filename", Input)
                filename_input.value = "../../../etc/passwd"

                # Press create
                app.screen.query_one("#create", Button).press()
                await pilot.pause()

                # Modal should still be open (not dismissed)
                assert isinstance(app.screen, AddDocumentModal)
                # Result should still be initial value (callback not called)
                assert result == "not_set"

    async def test_modal_rejects_slash_in_filename(self) -> None:
        """Test that filenames with '/' are rejected."""
        from textual.app import App
        from textual.widgets import Button, Input

        result = "not_set"

        with tempfile.TemporaryDirectory() as tmpdir:

            class TestApp(App):
                async def on_mount(self):
                    nonlocal result

                    def callback(r):
                        nonlocal result
                        result = r

                    modal = AddDocumentModal(project_path=tmpdir)
                    await self.push_screen(modal, callback)

            app = TestApp()
            async with app.run_test() as pilot:
                # Try to enter a path with slash
                filename_input = app.screen.query_one("#filename", Input)
                filename_input.value = "subdir/file.md"

                # Press create
                app.screen.query_one("#create", Button).press()
                await pilot.pause()

                # Modal should still be open (not dismissed)
                assert isinstance(app.screen, AddDocumentModal)
                # Result should still be initial value (callback not called)
                assert result == "not_set"

    async def test_modal_rejects_backslash_in_filename(self) -> None:
        """Test that filenames with backslash are rejected."""
        from textual.app import App
        from textual.widgets import Button, Input

        result = "not_set"

        with tempfile.TemporaryDirectory() as tmpdir:

            class TestApp(App):
                async def on_mount(self):
                    nonlocal result

                    def callback(r):
                        nonlocal result
                        result = r

                    modal = AddDocumentModal(project_path=tmpdir)
                    await self.push_screen(modal, callback)

            app = TestApp()
            async with app.run_test() as pilot:
                # Try to enter a path with backslash
                filename_input = app.screen.query_one("#filename", Input)
                filename_input.value = "subdir\\file.md"

                # Press create
                app.screen.query_one("#create", Button).press()
                await pilot.pause()

                # Modal should still be open (not dismissed)
                assert isinstance(app.screen, AddDocumentModal)
                # Result should still be initial value (callback not called)
                assert result == "not_set"

    async def test_modal_rejects_home_expansion(self) -> None:
        """Test that filenames starting with '~' are rejected."""
        from textual.app import App
        from textual.widgets import Button, Input

        result = "not_set"

        with tempfile.TemporaryDirectory() as tmpdir:

            class TestApp(App):
                async def on_mount(self):
                    nonlocal result

                    def callback(r):
                        nonlocal result
                        result = r

                    modal = AddDocumentModal(project_path=tmpdir)
                    await self.push_screen(modal, callback)

            app = TestApp()
            async with app.run_test() as pilot:
                # Try to enter a path with home expansion
                filename_input = app.screen.query_one("#filename", Input)
                filename_input.value = "~/secret.md"

                # Press create
                app.screen.query_one("#create", Button).press()
                await pilot.pause()

                # Modal should still be open (not dismissed)
                assert isinstance(app.screen, AddDocumentModal)
                # Result should still be initial value (callback not called)
                assert result == "not_set"

    async def test_modal_rejects_absolute_path(self) -> None:
        """Test that absolute paths are rejected."""
        from textual.app import App
        from textual.widgets import Button, Input

        result = "not_set"

        with tempfile.TemporaryDirectory() as tmpdir:

            class TestApp(App):
                async def on_mount(self):
                    nonlocal result

                    def callback(r):
                        nonlocal result
                        result = r

                    modal = AddDocumentModal(project_path=tmpdir)
                    await self.push_screen(modal, callback)

            app = TestApp()
            async with app.run_test() as pilot:
                # Try to enter an absolute path
                filename_input = app.screen.query_one("#filename", Input)
                filename_input.value = "/etc/passwd"

                # Press create
                app.screen.query_one("#create", Button).press()
                await pilot.pause()

                # Modal should still be open (not dismissed)
                assert isinstance(app.screen, AddDocumentModal)
                # Result should still be initial value (callback not called)
                assert result == "not_set"

    async def test_modal_accepts_valid_filename(self) -> None:
        """Test that valid filenames are accepted."""
        from textual.app import App
        from textual.widgets import Button, Input

        result = None

        with tempfile.TemporaryDirectory() as tmpdir:

            class TestApp(App):
                async def on_mount(self):
                    nonlocal result

                    def callback(r):
                        nonlocal result
                        result = r

                    modal = AddDocumentModal(project_path=tmpdir)
                    await self.push_screen(modal, callback)

            app = TestApp()
            async with app.run_test() as pilot:
                # Enter a valid filename
                filename_input = app.screen.query_one("#filename", Input)
                filename_input.value = "valid-doc-name_123.md"

                # Press create
                app.screen.query_one("#create", Button).press()
                await pilot.pause()

                # Should succeed
                assert result is not None
                assert result["path"].endswith("valid-doc-name_123.md")


@pytest.mark.asyncio
class TestDeleteConfirmModalAsync:
    """Async tests for DeleteConfirmModal."""

    async def test_modal_compose(self) -> None:
        """Test that modal composes correctly."""
        from textual.app import App

        class TestApp(App):
            async def on_mount(self):
                modal = DeleteConfirmModal(
                    item_name="docs/test.md",
                    item_type="document",
                )
                await self.push_screen(modal)

        app = TestApp()
        async with app.run_test():
            assert app.screen.query_one("#cancel") is not None
            assert app.screen.query_one("#delete") is not None

    async def test_modal_cancel(self) -> None:
        """Test that cancel button dismisses with False."""
        from textual.app import App
        from textual.widgets import Button

        result = None

        class TestApp(App):
            async def on_mount(self):
                nonlocal result

                def callback(r):
                    nonlocal result
                    result = r

                modal = DeleteConfirmModal(item_name="test.md")
                await self.push_screen(modal, callback)

        app = TestApp()
        async with app.run_test() as pilot:
            app.screen.query_one("#cancel", Button).press()
            await pilot.pause()
            assert result is False

    async def test_modal_confirm(self) -> None:
        """Test that delete button dismisses with True."""
        from textual.app import App
        from textual.widgets import Button

        result = None

        class TestApp(App):
            async def on_mount(self):
                nonlocal result

                def callback(r):
                    nonlocal result
                    result = r

                modal = DeleteConfirmModal(item_name="test.md")
                await self.push_screen(modal, callback)

        app = TestApp()
        async with app.run_test() as pilot:
            app.screen.query_one("#delete", Button).press()
            await pilot.pause()
            assert result is True


@pytest.mark.asyncio
class TestRenameDocumentModalAsync:
    """Async tests for RenameDocumentModal."""

    async def test_modal_compose(self) -> None:
        """Test that modal composes correctly."""
        from textual.app import App

        class TestApp(App):
            async def on_mount(self):
                modal = RenameDocumentModal(current_name="old.md")
                await self.push_screen(modal)

        app = TestApp()
        async with app.run_test():
            assert app.screen.query_one("#new-name") is not None
            assert app.screen.query_one("#cancel") is not None
            assert app.screen.query_one("#rename") is not None

    async def test_modal_cancel(self) -> None:
        """Test that cancel button dismisses with None."""
        from textual.app import App
        from textual.widgets import Button

        result = "not_called"

        class TestApp(App):
            async def on_mount(self):
                nonlocal result

                def callback(r):
                    nonlocal result
                    result = r

                modal = RenameDocumentModal(current_name="old.md")
                await self.push_screen(modal, callback)

        app = TestApp()
        async with app.run_test() as pilot:
            app.screen.query_one("#cancel", Button).press()
            await pilot.pause()
            assert result is None

    async def test_modal_rename_same_name(self) -> None:
        """Test that renaming to same name dismisses with None."""
        from textual.app import App
        from textual.widgets import Button

        result = "not_called"

        class TestApp(App):
            async def on_mount(self):
                nonlocal result

                def callback(r):
                    nonlocal result
                    result = r

                modal = RenameDocumentModal(current_name="old.md")
                await self.push_screen(modal, callback)

        app = TestApp()
        async with app.run_test() as pilot:
            # Input already has current name, just press rename
            app.screen.query_one("#rename", Button).press()
            await pilot.pause()
            assert result is None

    async def test_modal_rename_new_name(self) -> None:
        """Test renaming to a new name."""
        from textual.app import App
        from textual.widgets import Button, Input

        result = None

        class TestApp(App):
            async def on_mount(self):
                nonlocal result

                def callback(r):
                    nonlocal result
                    result = r

                modal = RenameDocumentModal(current_name="old.md")
                await self.push_screen(modal, callback)

        app = TestApp()
        async with app.run_test() as pilot:
            # Change the name
            name_input = app.screen.query_one("#new-name", Input)
            name_input.value = "new.md"

            app.screen.query_one("#rename", Button).press()
            await pilot.pause()
            assert result == "new.md"

    async def test_modal_rejects_invalid_characters(self) -> None:
        """Test that invalid characters are rejected."""
        from textual.app import App
        from textual.widgets import Button, Input

        class TestApp(App):
            async def on_mount(self):
                modal = RenameDocumentModal(current_name="old.md")
                await self.push_screen(modal)

        app = TestApp()
        async with app.run_test() as pilot:
            # Try to use invalid character
            name_input = app.screen.query_one("#new-name", Input)
            name_input.value = "invalid/name.md"

            app.screen.query_one("#rename", Button).press()
            await pilot.pause()

            # Modal should still be open (not dismissed)
            assert isinstance(app.screen, RenameDocumentModal)


@pytest.mark.asyncio
class TestDocsModeScreenCRUD:
    """Integration tests for CRUD operations in DocsModeScreen."""

    async def test_add_document_workflow(self) -> None:
        """Test the full add document workflow."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen
        from iterm_controller.widgets.doc_tree import DocTreeWidget

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create docs directory
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))

                # Press 'a' to add document
                await pilot.press("a")
                await pilot.pause()

                # Should have AddDocumentModal open
                from iterm_controller.screens.modals.add_document import (
                    AddDocumentModal,
                )

                assert isinstance(app.screen, AddDocumentModal)

    async def test_delete_document_workflow(self) -> None:
        """Test the full delete document workflow."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen
        from iterm_controller.widgets.doc_tree import DocTreeWidget

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file to delete
            readme = Path(tmpdir) / "README.md"
            readme.write_text("# Test")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))

                # Navigate to select the file
                tree = app.screen.query_one("#doc-tree", DocTreeWidget)

                # Press 'd' to delete
                await pilot.press("d")
                await pilot.pause()

                # Since no file is selected initially, should show warning
                # or if file is selected, should show delete confirmation

    async def test_rename_document_workflow(self) -> None:
        """Test the full rename document workflow."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen
        from iterm_controller.widgets.doc_tree import DocTreeWidget

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file to rename
            readme = Path(tmpdir) / "README.md"
            readme.write_text("# Test")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))

                # Press 'r' to rename
                await pilot.press("r")
                await pilot.pause()

                # Since no file is selected initially, should show warning
                # or if file is selected, should show rename modal

    async def test_create_document_helper(self) -> None:
        """Test the _create_document helper method."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen
        from iterm_controller.widgets.doc_tree import DocTreeWidget

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))

                # Get the screen and call _create_document directly
                screen = app.screen
                new_file = Path(tmpdir) / "new-doc.md"
                screen._create_document(str(new_file), "# New Document")

                await pilot.pause()

                # File should exist
                assert new_file.exists()
                assert new_file.read_text() == "# New Document"

    async def test_delete_document_helper(self) -> None:
        """Test the _delete_document helper method."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file to delete
            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("# Test")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))

                # Get the screen and call _delete_document directly
                screen = app.screen
                screen._delete_document(test_file)

                await pilot.pause()

                # File should no longer exist
                assert not test_file.exists()

    async def test_rename_document_helper(self) -> None:
        """Test the _rename_document helper method."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file to rename
            old_file = Path(tmpdir) / "old.md"
            old_file.write_text("# Old")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))

                # Get the screen and call _rename_document directly
                screen = app.screen
                screen._rename_document(old_file, "new.md")

                await pilot.pause()

                # Old file should no longer exist
                assert not old_file.exists()
                # New file should exist
                new_file = Path(tmpdir) / "new.md"
                assert new_file.exists()
                assert new_file.read_text() == "# Old"

    async def test_create_document_creates_parent_dirs(self) -> None:
        """Test that creating a document creates parent directories if needed."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))

                # Create a document in a nested directory that doesn't exist
                screen = app.screen
                new_file = Path(tmpdir) / "docs" / "nested" / "new-doc.md"
                screen._create_document(str(new_file), "# Nested Document")

                await pilot.pause()

                # File should exist with parent directories created
                assert new_file.exists()
                assert new_file.read_text() == "# Nested Document"

    async def test_preview_document_workflow(self) -> None:
        """Test the full preview document workflow."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen
        from iterm_controller.widgets.doc_tree import DocTreeWidget

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file to preview
            readme = Path(tmpdir) / "README.md"
            readme.write_text("# Test README\n\nThis is test content.")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))
                await pilot.pause()

                # Navigate to select the README.md file
                tree = app.screen.query_one("#doc-tree", DocTreeWidget)
                # The tree should have README.md as a child of root
                # Select the first file in the tree
                if tree.cursor_node and tree.cursor_node.children:
                    # Navigate down to select the file
                    await pilot.press("down")
                    await pilot.pause()

                # Press 'p' to preview
                await pilot.press("p")
                await pilot.pause()

                # Should have ArtifactPreviewModal open if a file was selected
                from iterm_controller.screens.modals.artifact_preview import (
                    ArtifactPreviewModal,
                )

                # Check if modal is open (depends on file selection)
                if isinstance(app.screen, ArtifactPreviewModal):
                    # Modal should show the file content
                    assert app.screen.artifact_name == "README.md"

    async def test_preview_document_shows_warning_for_no_selection(self) -> None:
        """Test that preview shows warning when no file is selected."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))
                await pilot.pause()

                # Press 'p' without selecting a file
                await pilot.press("p")
                await pilot.pause()

                # Should still be on DocsModeScreen (no modal opened)
                assert isinstance(app.screen, DocsModeScreen)

    async def test_preview_document_shows_warning_for_directory(self) -> None:
        """Test that preview shows warning when a directory is selected."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a docs directory
            docs_dir = Path(tmpdir) / "docs"
            docs_dir.mkdir()

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))
                await pilot.pause()

                # Select the docs directory by navigating down
                await pilot.press("down")
                await pilot.pause()

                # Press 'p' to preview a directory
                await pilot.press("p")
                await pilot.pause()

                # Should still be on DocsModeScreen (no modal for directories)
                assert isinstance(app.screen, DocsModeScreen)

    async def test_preview_document_edit_callback(self) -> None:
        """Test that preview modal edit callback opens editor."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen
        from iterm_controller.widgets.doc_tree import DocTreeWidget

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file to preview
            readme = Path(tmpdir) / "README.md"
            readme.write_text("# Test README")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))
                await pilot.pause()

                # Navigate and select file
                await pilot.press("down")
                await pilot.pause()

                tree = app.screen.query_one("#doc-tree", DocTreeWidget)
                if tree.selected_path and tree.selected_is_file:
                    # Press 'p' to preview
                    await pilot.press("p")
                    await pilot.pause()

                    from iterm_controller.screens.modals.artifact_preview import (
                        ArtifactPreviewModal,
                    )

                    if isinstance(app.screen, ArtifactPreviewModal):
                        # Press 'e' to request edit
                        await pilot.press("e")
                        await pilot.pause()

                        # Modal should be dismissed, back to DocsModeScreen
                        assert isinstance(app.screen, DocsModeScreen)


@pytest.mark.asyncio
class TestDocsModePathTraversalProtection:
    """Tests for path traversal protection in DocsModeScreen operations."""

    async def test_create_document_rejects_path_traversal(self) -> None:
        """Test that _create_document rejects path traversal attempts."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))

                # Attempt to create a file outside the project
                screen = app.screen
                malicious_path = str(Path(tmpdir) / ".." / ".." / "etc" / "cron.d" / "malicious")
                screen._create_document(malicious_path, "malicious content")

                await pilot.pause()

                # File should NOT be created outside project
                assert not Path("/etc/cron.d/malicious").exists()
                # File should NOT be created anywhere
                assert not Path(malicious_path).exists()

    async def test_create_document_rejects_absolute_path_outside_project(self) -> None:
        """Test that _create_document rejects absolute paths outside project."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            with tempfile.TemporaryDirectory() as other_tmpdir:
                app = ItermControllerApp()
                async with app.run_test() as pilot:
                    project = Project(
                        id="test-project",
                        name="Test Project",
                        path=tmpdir,
                    )
                    app.state.projects[project.id] = project

                    await app.push_screen(DocsModeScreen(project))

                    # Attempt to create a file in a different temp directory
                    screen = app.screen
                    malicious_path = str(Path(other_tmpdir) / "malicious.md")
                    screen._create_document(malicious_path, "malicious content")

                    await pilot.pause()

                    # File should NOT be created outside project
                    assert not Path(malicious_path).exists()

    async def test_create_document_allows_valid_path_inside_project(self) -> None:
        """Test that _create_document allows valid paths inside project."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))

                # Create a valid file inside project
                screen = app.screen
                valid_path = str(Path(tmpdir) / "docs" / "new-doc.md")
                screen._create_document(valid_path, "# Valid Document")

                await pilot.pause()

                # File should be created
                assert Path(valid_path).exists()
                assert Path(valid_path).read_text() == "# Valid Document"

    async def test_delete_document_rejects_path_traversal(self) -> None:
        """Test that _delete_document rejects path traversal attempts."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            with tempfile.TemporaryDirectory() as other_tmpdir:
                # Create a file in the other directory to try to delete
                target_file = Path(other_tmpdir) / "target.md"
                target_file.write_text("should not be deleted")

                app = ItermControllerApp()
                async with app.run_test() as pilot:
                    project = Project(
                        id="test-project",
                        name="Test Project",
                        path=tmpdir,
                    )
                    app.state.projects[project.id] = project

                    await app.push_screen(DocsModeScreen(project))

                    # Attempt to delete a file outside the project
                    screen = app.screen
                    screen._delete_document(target_file)

                    await pilot.pause()

                    # File should still exist (not deleted)
                    assert target_file.exists()
                    assert target_file.read_text() == "should not be deleted"

    async def test_delete_document_allows_valid_path_inside_project(self) -> None:
        """Test that _delete_document allows valid paths inside project."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file inside project to delete
            target_file = Path(tmpdir) / "to-delete.md"
            target_file.write_text("delete me")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))

                # Delete a valid file inside project
                screen = app.screen
                screen._delete_document(target_file)

                await pilot.pause()

                # File should be deleted
                assert not target_file.exists()

    async def test_rename_document_rejects_path_traversal_in_source(self) -> None:
        """Test that _rename_document rejects path traversal in source."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            with tempfile.TemporaryDirectory() as other_tmpdir:
                # Create a file in the other directory
                source_file = Path(other_tmpdir) / "source.md"
                source_file.write_text("should not be renamed")

                app = ItermControllerApp()
                async with app.run_test() as pilot:
                    project = Project(
                        id="test-project",
                        name="Test Project",
                        path=tmpdir,
                    )
                    app.state.projects[project.id] = project

                    await app.push_screen(DocsModeScreen(project))

                    # Attempt to rename a file outside the project
                    screen = app.screen
                    screen._rename_document(source_file, "renamed.md")

                    await pilot.pause()

                    # Source file should still exist with original name
                    assert source_file.exists()
                    # Renamed file should not exist in source location
                    assert not (Path(other_tmpdir) / "renamed.md").exists()

    async def test_rename_document_rejects_traversal_in_new_name(self) -> None:
        """Test that _rename_document rejects path traversal in new filename."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file inside project
            source_file = Path(tmpdir) / "source.md"
            source_file.write_text("original content")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))

                # Attempt to rename with traversal in new name
                screen = app.screen
                screen._rename_document(source_file, "../../../etc/cron.d/malicious")

                await pilot.pause()

                # Source file should still exist
                assert source_file.exists()
                # Malicious file should not be created
                assert not Path("/etc/cron.d/malicious").exists()

    async def test_rename_document_rejects_slash_in_new_name(self) -> None:
        """Test that _rename_document rejects slashes in new filename."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file inside project
            source_file = Path(tmpdir) / "source.md"
            source_file.write_text("original content")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))

                # Attempt to rename with slash in new name
                screen = app.screen
                screen._rename_document(source_file, "subdir/newname.md")

                await pilot.pause()

                # Source file should still exist (rename rejected)
                assert source_file.exists()
                # Subdirectory should not be created
                assert not (Path(tmpdir) / "subdir").exists()

    async def test_rename_document_allows_valid_rename(self) -> None:
        """Test that _rename_document allows valid renames inside project."""
        from iterm_controller.app import ItermControllerApp
        from iterm_controller.models import Project
        from iterm_controller.screens.modes.docs_mode import DocsModeScreen

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file inside project
            source_file = Path(tmpdir) / "source.md"
            source_file.write_text("original content")

            app = ItermControllerApp()
            async with app.run_test() as pilot:
                project = Project(
                    id="test-project",
                    name="Test Project",
                    path=tmpdir,
                )
                app.state.projects[project.id] = project

                await app.push_screen(DocsModeScreen(project))

                # Rename to a valid new name
                screen = app.screen
                screen._rename_document(source_file, "renamed.md")

                await pilot.pause()

                # Source file should no longer exist
                assert not source_file.exists()
                # Renamed file should exist
                new_file = Path(tmpdir) / "renamed.md"
                assert new_file.exists()
                assert new_file.read_text() == "original content"
