"""Tests for document CRUD operations in Docs Mode.

Tests for AddDocumentModal, DeleteConfirmModal, RenameDocumentModal.
DocsModeScreen integration tests were removed in task 27.9.3.
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


# TestDocsModeScreenCRUD and TestDocsModePathTraversalProtection were removed
# in task 27.9.3 as they depended on DocsModeScreen which has been deprecated
