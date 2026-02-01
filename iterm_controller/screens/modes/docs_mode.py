"""Docs Mode screen.

Documentation tree browser for managing project documentation.

See specs/docs-mode.md for full specification.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Footer, Header, Static

from iterm_controller.models import WorkflowMode
from iterm_controller.screens.mode_screen import ModeScreen
from iterm_controller.widgets.doc_tree import DocTreeWidget

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp
    from iterm_controller.models import Project

logger = logging.getLogger(__name__)


# Editor command mapping (mirrors docs_picker.py and plan_mode.py)
EDITOR_COMMANDS = {
    "vscode": "code",
    "code": "code",
    "cursor": "cursor",
    "vim": "vim",
    "nvim": "nvim",
    "neovim": "nvim",
    "subl": "subl",
    "sublime": "subl",
    "atom": "atom",
    "nano": "nano",
    "emacs": "emacs",
}


class DocsModeScreen(ModeScreen):
    """Docs Mode screen for documentation management.

    This screen displays a tree view of documentation files:
    - docs/ directory
    - specs/ directory
    - documentation/ directory
    - README.md and CHANGELOG.md

    Users can navigate, add, edit, and delete documentation files.

    Layout:
        ┌────────────────────────────────────────────────────────────────┐
        │ my-project                           [Docs] 1 2 3 4   [?] Help │
        ├────────────────────────────────────────────────────────────────┤
        │ Documentation                                                  │
        │ ┌────────────────────────────────────────────────────────────┐ │
        │ │ ▼ docs/                                                    │ │
        │ │   ├─ getting-started.md                                    │ │
        │ │   ▼ architecture/                                          │ │
        │ │     ├─ overview.md                                         │ │
        │ │ ▼ specs/                                                   │ │
        │ │   ├─ README.md                                             │ │
        │ │ README.md                                                  │ │
        │ │ CHANGELOG.md                                               │ │
        │ └────────────────────────────────────────────────────────────┘ │
        ├────────────────────────────────────────────────────────────────┤
        │ ↑↓ Navigate  Enter Open  a Add  d Delete  r Rename  p Preview │
        └────────────────────────────────────────────────────────────────┘
    """

    CURRENT_MODE = WorkflowMode.DOCS

    BINDINGS = [
        *ModeScreen.BINDINGS,
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("enter", "open_selected", "Open"),
        Binding("e", "edit_selected", "Edit"),
        Binding("a", "add_document", "Add"),
        Binding("d", "delete_document", "Delete"),
        Binding("r", "rename_document", "Rename"),
        Binding("p", "preview_document", "Preview"),
        Binding("x", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    DocsModeScreen {
        layout: vertical;
    }

    DocsModeScreen #main {
        height: 1fr;
        padding: 1;
    }

    DocsModeScreen #tree-container {
        height: 1fr;
    }

    DocsModeScreen #tree-title {
        dock: top;
        text-style: bold;
        padding: 0 0 1 0;
    }

    DocsModeScreen DocTreeWidget {
        height: 1fr;
    }

    DocsModeScreen #status-bar {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    """

    def __init__(self, project: Project) -> None:
        """Initialize the Docs Mode screen.

        Args:
            project: The project to display.
        """
        super().__init__(project)

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            Vertical(
                Static("Documentation", id="tree-title"),
                DocTreeWidget(id="doc-tree"),
                id="tree-container",
            ),
            Static("", id="status-bar"),
            id="main",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Load data when screen mounts."""
        await super().on_mount()
        self._build_tree()
        self._update_status_bar()
        # Focus the tree widget
        self.query_one("#doc-tree", DocTreeWidget).focus()

    def _build_tree(self) -> None:
        """Build the documentation tree."""
        tree = self.query_one("#doc-tree", DocTreeWidget)
        tree.set_project(self.project.path)

    def _update_status_bar(self) -> None:
        """Update the status bar with current selection info."""
        tree = self.query_one("#doc-tree", DocTreeWidget)
        status_bar = self.query_one("#status-bar", Static)

        selected_path = tree.selected_path
        if selected_path:
            # Show relative path
            try:
                rel_path = selected_path.relative_to(self.project.path)
                status_bar.update(f"Selected: {rel_path}")
            except ValueError:
                status_bar.update(f"Selected: {selected_path.name}")
        else:
            status_bar.update("")

    # =========================================================================
    # Navigation Actions
    # =========================================================================

    def action_cursor_down(self) -> None:
        """Move cursor down in the tree."""
        tree = self.query_one("#doc-tree", DocTreeWidget)
        tree.action_cursor_down()
        self._update_status_bar()

    def action_cursor_up(self) -> None:
        """Move cursor up in the tree."""
        tree = self.query_one("#doc-tree", DocTreeWidget)
        tree.action_cursor_up()
        self._update_status_bar()

    def action_open_selected(self) -> None:
        """Open the selected item (file: edit, directory: expand/collapse)."""
        tree = self.query_one("#doc-tree", DocTreeWidget)

        if tree.selected_is_file:
            self.action_edit_selected()
        elif tree.selected_is_directory:
            # Toggle expansion - handled by tree widget's node selection
            if tree.cursor_node:
                tree.cursor_node.toggle()

    # =========================================================================
    # File Operations
    # =========================================================================

    def action_edit_selected(self) -> None:
        """Open the selected file in the configured editor."""
        tree = self.query_one("#doc-tree", DocTreeWidget)
        selected_path = tree.selected_path

        if not selected_path:
            self.notify("No file selected", severity="warning")
            return

        if not selected_path.exists():
            self.notify(f"{selected_path.name} does not exist", severity="warning")
            return

        # Get configured editor
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        ide = "code"  # default to VS Code
        if app.state.config and app.state.config.settings:
            ide = app.state.config.settings.default_ide

        # Get editor command
        editor_cmd = EDITOR_COMMANDS.get(ide.lower(), "open")

        # Open file in editor
        self._open_in_editor(selected_path, editor_cmd)

    def action_preview_document(self) -> None:
        """Preview the selected markdown document inline."""
        tree = self.query_one("#doc-tree", DocTreeWidget)
        selected_path = tree.selected_path

        if not selected_path:
            self.notify("No file selected", severity="warning")
            return

        if not selected_path.exists():
            self.notify(f"{selected_path.name} does not exist", severity="warning")
            return

        if tree.selected_is_directory:
            self.notify("Cannot preview a directory", severity="warning")
            return

        # Import and show preview modal
        from iterm_controller.screens.modals.artifact_preview import ArtifactPreviewModal

        def handle_preview_result(result: str | None) -> None:
            """Handle the result from the preview modal."""
            if result == "edit":
                self.action_edit_selected()

        self.app.push_screen(
            ArtifactPreviewModal(
                artifact_name=selected_path.name,
                artifact_path=selected_path,
            ),
            handle_preview_result,
        )

    def action_add_document(self) -> None:
        """Add a new document."""
        tree = self.query_one("#doc-tree", DocTreeWidget)

        # Determine default location based on selection
        default_dir = self.project.path
        if tree.selected_path:
            if tree.selected_is_directory:
                default_dir = str(tree.selected_path)
            else:
                default_dir = str(tree.selected_path.parent)

        # Show add document modal
        from iterm_controller.screens.modals.add_document import AddDocumentModal

        def handle_add_result(result: dict | None) -> None:
            """Handle the result from the add document modal."""
            if result:
                self._create_document(result["path"], result.get("content", ""))

        self.app.push_screen(
            AddDocumentModal(
                project_path=self.project.path,
                default_directory=default_dir,
            ),
            handle_add_result,
        )

    def action_delete_document(self) -> None:
        """Delete the selected document."""
        tree = self.query_one("#doc-tree", DocTreeWidget)
        selected_path = tree.selected_path

        if not selected_path:
            self.notify("No file selected", severity="warning")
            return

        if not selected_path.exists():
            self.notify(f"{selected_path.name} does not exist", severity="warning")
            return

        # Don't allow deleting directories (too dangerous)
        if tree.selected_is_directory:
            self.notify("Cannot delete directories from here", severity="warning")
            return

        # Show delete confirmation modal
        from iterm_controller.screens.modals.delete_confirm import DeleteConfirmModal

        def handle_delete_result(confirmed: bool) -> None:
            """Handle the result from the delete confirmation modal."""
            if confirmed:
                self._delete_document(selected_path)

        try:
            rel_path = selected_path.relative_to(self.project.path)
        except ValueError:
            rel_path = selected_path

        self.app.push_screen(
            DeleteConfirmModal(
                item_name=str(rel_path),
                item_type="document",
            ),
            handle_delete_result,
        )

    def action_rename_document(self) -> None:
        """Rename the selected document."""
        tree = self.query_one("#doc-tree", DocTreeWidget)
        selected_path = tree.selected_path

        if not selected_path:
            self.notify("No file selected", severity="warning")
            return

        if not selected_path.exists():
            self.notify(f"{selected_path.name} does not exist", severity="warning")
            return

        # Don't allow renaming directories (too complex)
        if tree.selected_is_directory:
            self.notify("Cannot rename directories from here", severity="warning")
            return

        # Show rename modal
        from iterm_controller.screens.modals.rename_document import RenameDocumentModal

        def handle_rename_result(new_name: str | None) -> None:
            """Handle the result from the rename modal."""
            if new_name:
                self._rename_document(selected_path, new_name)

        self.app.push_screen(
            RenameDocumentModal(current_name=selected_path.name),
            handle_rename_result,
        )

    def action_refresh(self) -> None:
        """Refresh the documentation tree."""
        tree = self.query_one("#doc-tree", DocTreeWidget)
        tree.refresh_tree()
        self._update_status_bar()
        self.notify("Tree refreshed")

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _open_in_editor(self, path: Path, editor_cmd: str) -> None:
        """Open a file in the configured editor.

        Args:
            path: Path to the file to open.
            editor_cmd: The editor command to use.
        """

        async def _do_open() -> None:
            try:
                cmd = [editor_cmd, str(path)]
                await asyncio.to_thread(
                    subprocess.Popen,
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.notify(f"Opened {path.name} in {editor_cmd}")
            except FileNotFoundError:
                # Editor not found, try macOS open command
                try:
                    await asyncio.to_thread(
                        subprocess.Popen,
                        ["open", str(path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    self.notify(f"Opened {path.name}")
                except Exception as e:
                    self.notify(f"Failed to open {path.name}: {e}", severity="error")
            except Exception as e:
                self.notify(f"Failed to open {path.name}: {e}", severity="error")

        self.call_later(_do_open)

    def _create_document(self, path: str, content: str = "") -> None:
        """Create a new document file.

        Args:
            path: Full path to the new document.
            content: Initial content for the document.
        """
        file_path = Path(path)

        try:
            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Create the file
            file_path.write_text(content)

            # Refresh tree and notify
            tree = self.query_one("#doc-tree", DocTreeWidget)
            tree.refresh_tree()
            self._update_status_bar()
            self.notify(f"Created {file_path.name}")

            # Open in editor
            self.action_edit_selected()

        except Exception as e:
            logger.exception("Failed to create document")
            self.notify(f"Failed to create document: {e}", severity="error")

    def _delete_document(self, path: Path) -> None:
        """Delete a document file.

        Args:
            path: Path to the file to delete.
        """
        try:
            path.unlink()

            # Refresh tree and notify
            tree = self.query_one("#doc-tree", DocTreeWidget)
            tree.refresh_tree()
            self._update_status_bar()
            self.notify(f"Deleted {path.name}")

        except Exception as e:
            logger.exception("Failed to delete document")
            self.notify(f"Failed to delete document: {e}", severity="error")

    def _rename_document(self, path: Path, new_name: str) -> None:
        """Rename a document file.

        Args:
            path: Path to the file to rename.
            new_name: New filename.
        """
        try:
            new_path = path.parent / new_name
            path.rename(new_path)

            # Refresh tree and notify
            tree = self.query_one("#doc-tree", DocTreeWidget)
            tree.refresh_tree()
            self._update_status_bar()
            self.notify(f"Renamed to {new_name}")

        except Exception as e:
            logger.exception("Failed to rename document")
            self.notify(f"Failed to rename document: {e}", severity="error")

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def on_doc_tree_widget_file_selected(
        self, event: DocTreeWidget.FileSelected
    ) -> None:
        """Handle file selection from tree widget.

        Args:
            event: The file selected event.
        """
        self._update_status_bar()
        # Open in editor when file is selected (via Enter)
        self.action_edit_selected()

    def on_doc_tree_widget_directory_selected(
        self, event: DocTreeWidget.DirectorySelected
    ) -> None:
        """Handle directory selection from tree widget.

        Args:
            event: The directory selected event.
        """
        self._update_status_bar()
