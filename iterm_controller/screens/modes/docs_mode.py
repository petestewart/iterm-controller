"""Docs Mode screen.

Documentation tree browser for managing project documentation.

See specs/docs-mode.md for full specification.
"""

from __future__ import annotations

import logging
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Footer, Header, Static

from iterm_controller.editors import EDITOR_COMMANDS
from iterm_controller.models import DocReference, WorkflowMode
from iterm_controller.screens.mode_screen import ModeScreen
from iterm_controller.security import (
    EditorValidationError,
    PathTraversalError,
    get_safe_editor_command,
    validate_filename,
    validate_path_in_project,
)
from iterm_controller.widgets.doc_tree import DocTreeWidget
from iterm_controller.widgets.mode_indicator import ModeIndicatorWidget

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp
    from iterm_controller.models import Project

logger = logging.getLogger(__name__)


class DocsModeScreen(ModeScreen):
    """Docs Mode screen for documentation management.

    This screen displays a tree view of documentation files:
    - docs/ directory
    - specs/ directory
    - documentation/ directory
    - README.md and CHANGELOG.md
    - External URL references

    Users can navigate, add, edit, and delete documentation files and URLs.

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
        │ │ ▼ External References                                      │ │
        │ │   🌐 Textual Docs                                          │ │
        │ │   🌐 iTerm2 API                                            │ │
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
        Binding("left", "collapse_node", "Collapse", show=False),
        Binding("right", "expand_node", "Expand", show=False),
        Binding("h", "collapse_node", "Collapse", show=False),
        Binding("l", "expand_node", "Expand", show=False),
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

    DocsModeScreen #mode-indicator {
        dock: top;
        width: 100%;
        height: 1;
        background: $surface;
        padding: 0 1;
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
        yield ModeIndicatorWidget(current_mode=self.CURRENT_MODE, id="mode-indicator")
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
        tree.set_project(self.project.path, self.project.doc_references)

    def _update_status_bar(self) -> None:
        """Update the status bar with current selection info."""
        tree = self.query_one("#doc-tree", DocTreeWidget)
        status_bar = self.query_one("#status-bar", Static)

        # Check for URL selection first
        if tree.selected_is_url:
            url = tree.selected_url
            if url:
                # Truncate long URLs
                display_url = url if len(url) <= 60 else url[:57] + "..."
                status_bar.update(f"🔗 {display_url}")
            return

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

    def action_collapse_node(self) -> None:
        """Collapse the selected directory or move to parent.

        Behavior per spec:
        - If on expanded directory: collapse it
        - If on collapsed directory or file: move to parent directory
        """
        tree = self.query_one("#doc-tree", DocTreeWidget)
        node = tree.cursor_node

        if not node:
            return

        # If node is expanded directory, collapse it
        if node.data and node.data.is_directory and node.is_expanded:
            node.collapse()
        # Otherwise, move to parent (if not at root)
        elif node.parent and node.parent != tree.root:
            tree.select_node(node.parent)
            self._update_status_bar()
        elif node.parent == tree.root:
            # At top-level, move to root
            tree.select_node(tree.root)
            self._update_status_bar()

    def action_expand_node(self) -> None:
        """Expand the selected directory or enter it.

        Behavior per spec:
        - If on collapsed directory: expand it
        - If on expanded directory: move to first child
        - If on file: open it
        """
        tree = self.query_one("#doc-tree", DocTreeWidget)
        node = tree.cursor_node

        if not node or not node.data:
            return

        if node.data.is_directory:
            if not node.is_expanded:
                # Expand collapsed directory
                node.expand()
            elif node.children:
                # Move to first child if expanded
                tree.select_node(node.children[0])
                self._update_status_bar()
        else:
            # On a file: open it
            self.action_edit_selected()

    def action_open_selected(self) -> None:
        """Open the selected item (file: edit, directory: expand/collapse, URL: open in browser)."""
        tree = self.query_one("#doc-tree", DocTreeWidget)

        if tree.selected_is_url:
            self._open_url(tree.selected_url)
        elif tree.selected_is_file:
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

        # Get editor command - validated against allowlist
        editor_cmd = EDITOR_COMMANDS.get(ide.lower())
        if editor_cmd:
            # Validate the command from the mapping
            editor_cmd = get_safe_editor_command(editor_cmd, fallback="open")
        else:
            # Try to validate the IDE setting directly (might be a command)
            editor_cmd = get_safe_editor_command(ide, fallback="open")

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
        """Add a new document or URL reference."""
        from iterm_controller.screens.modals.add_content_type import (
            AddContentTypeModal,
            ContentType,
        )

        def handle_type_selection(content_type: ContentType | None) -> None:
            """Handle the content type selection."""
            if content_type == ContentType.FILE:
                self._show_add_file_modal()
            elif content_type == ContentType.BROWSE:
                self._show_file_browser_modal()
            elif content_type == ContentType.URL:
                self._show_add_url_modal()

        self.app.push_screen(AddContentTypeModal(), handle_type_selection)

    def _show_add_file_modal(self) -> None:
        """Show the add file modal."""
        tree = self.query_one("#doc-tree", DocTreeWidget)

        # Determine default location based on selection
        default_dir = self.project.path
        if tree.selected_path:
            if tree.selected_is_directory:
                default_dir = str(tree.selected_path)
            else:
                default_dir = str(tree.selected_path.parent)

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

    def _show_file_browser_modal(self) -> None:
        """Show the file browser modal for selecting an existing file."""
        from iterm_controller.screens.modals.file_browser import FileBrowserModal

        def handle_browse_result(result: Path | None) -> None:
            """Handle the result from the file browser modal."""
            if result:
                self._add_existing_file(result)

        self.app.push_screen(
            FileBrowserModal(
                project_path=self.project.path,
                title="Select File to Add",
                description="Browse and select an existing file to include in documentation",
            ),
            handle_browse_result,
        )

    def _add_existing_file(self, file_path: Path) -> None:
        """Add an existing file to the documentation tree.

        If the file is already in a documentation directory (docs/, specs/, etc.),
        it's already visible in the tree. If it's elsewhere in the project,
        we copy it to a documentation directory.

        Args:
            file_path: Path to the file to add.
        """
        project_path = Path(self.project.path)

        # Validate file is within project
        try:
            rel_path = file_path.relative_to(project_path)
        except ValueError:
            self.notify(
                "Cannot add files from outside the project",
                severity="error",
            )
            return

        rel_parts = rel_path.parts

        # Check if already in a doc directory or is a root doc file
        doc_dirs = {"docs", "specs", "documentation"}
        root_docs = {"README.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE"}

        already_in_tree = (
            (rel_parts and rel_parts[0] in doc_dirs)
            or (len(rel_parts) == 1 and rel_parts[0] in root_docs)
        )

        if already_in_tree:
            self.notify(f"{rel_path} is already in the documentation tree")
            tree = self.query_one("#doc-tree", DocTreeWidget)
            tree.refresh_tree()
            self._update_status_bar()
            return

        # File is in project but not in doc directories - copy it to docs/
        self._copy_file_to_docs(file_path, rel_path)

    def _copy_file_to_docs(self, source_path: Path, rel_path: Path) -> None:
        """Copy a file to the docs directory.

        Args:
            source_path: Absolute path to the source file.
            rel_path: Path relative to project root.
        """
        import shutil

        project_path = Path(self.project.path)
        docs_dir = project_path / "docs"

        # Create docs directory if needed
        docs_dir.mkdir(parents=True, exist_ok=True)

        # Determine destination path
        dest_path = docs_dir / source_path.name

        # Handle name collision
        counter = 1
        base_name = source_path.stem
        extension = source_path.suffix
        while dest_path.exists():
            dest_path = docs_dir / f"{base_name}_{counter}{extension}"
            counter += 1

        try:
            shutil.copy2(source_path, dest_path)
            tree = self.query_one("#doc-tree", DocTreeWidget)
            tree.refresh_tree()
            self._update_status_bar()
            self.notify(f"Copied {source_path.name} to docs/")
        except Exception as e:
            logger.exception("Failed to copy file to docs")
            self.notify(f"Failed to copy file: {e}", severity="error")

    def _show_add_url_modal(self, existing_reference: DocReference | None = None) -> None:
        """Show the add/edit URL reference modal.

        Args:
            existing_reference: Optional existing reference to edit.
        """
        from iterm_controller.screens.modals.add_reference import AddReferenceModal

        def handle_add_result(result: DocReference | None) -> None:
            """Handle the result from the add reference modal."""
            if result:
                self._save_url_reference(result, existing_reference)

        self.app.push_screen(
            AddReferenceModal(existing_reference=existing_reference),
            handle_add_result,
        )

    def action_delete_document(self) -> None:
        """Delete the selected document or URL reference."""
        tree = self.query_one("#doc-tree", DocTreeWidget)

        # Handle URL reference deletion
        if tree.selected_is_url:
            ref_id = tree.selected_reference_id
            if ref_id:
                self._delete_url_reference(ref_id)
            return

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
        """Rename the selected document or edit URL reference."""
        tree = self.query_one("#doc-tree", DocTreeWidget)

        # Handle URL reference editing
        if tree.selected_is_url:
            ref_id = tree.selected_reference_id
            if ref_id:
                existing = self._get_reference_by_id(ref_id)
                if existing:
                    self._show_add_url_modal(existing_reference=existing)
            return

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
        # Update doc references from project before refreshing
        tree.update_references(self.project.doc_references)
        self._update_status_bar()
        self.notify("Tree refreshed")

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _create_document(self, path: str, content: str = "") -> None:
        """Create a new document file.

        Args:
            path: Full path to the new document.
            content: Initial content for the document.
        """
        file_path = Path(path)

        try:
            # Validate path stays within project directory
            validate_path_in_project(file_path, self.project.path)
        except PathTraversalError as e:
            logger.warning("Path traversal attempt blocked: %s", e)
            self.notify("Invalid path: cannot create files outside project", severity="error")
            return

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
            # Validate path stays within project directory
            validate_path_in_project(path, self.project.path)
        except PathTraversalError as e:
            logger.warning("Path traversal attempt blocked: %s", e)
            self.notify("Invalid path: cannot delete files outside project", severity="error")
            return

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
            # Validate source path stays within project directory
            validate_path_in_project(path, self.project.path)
        except PathTraversalError as e:
            logger.warning("Path traversal attempt blocked on source: %s", e)
            self.notify("Invalid path: cannot rename files outside project", severity="error")
            return

        try:
            # Validate new filename doesn't contain traversal sequences
            validate_filename(new_name, allow_subdirs=False)
        except (PathTraversalError, ValueError) as e:
            logger.warning("Invalid filename rejected: %s", e)
            self.notify(f"Invalid filename: {e}", severity="error")
            return

        new_path = path.parent / new_name

        try:
            # Validate destination path also stays within project
            validate_path_in_project(new_path, self.project.path)
        except PathTraversalError as e:
            logger.warning("Path traversal attempt blocked on destination: %s", e)
            self.notify("Invalid path: cannot rename files outside project", severity="error")
            return

        try:
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
    # URL Reference Operations
    # =========================================================================

    def _open_url(self, url: str | None) -> None:
        """Open a URL in the default web browser.

        Args:
            url: URL to open.
        """
        if not url:
            self.notify("No URL selected", severity="warning")
            return

        try:
            webbrowser.open(url)
            self.notify(f"Opened {url}")
        except Exception as e:
            logger.exception("Failed to open URL")
            self.notify(f"Failed to open URL: {e}", severity="error")

    def _get_reference_by_id(self, ref_id: str) -> DocReference | None:
        """Get a DocReference by its ID.

        Args:
            ref_id: Reference ID to find.

        Returns:
            The DocReference if found, None otherwise.
        """
        for ref in self.project.doc_references:
            if ref.id == ref_id:
                return ref
        return None

    def _save_url_reference(
        self,
        reference: DocReference,
        existing: DocReference | None = None,
    ) -> None:
        """Save a URL reference to the project.

        Args:
            reference: The DocReference to save.
            existing: Optional existing reference to replace.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Update or add the reference
        if existing:
            # Replace existing reference
            for idx, ref in enumerate(self.project.doc_references):
                if ref.id == existing.id:
                    self.project.doc_references[idx] = reference
                    break
            action = "Updated"
        else:
            # Add new reference
            self.project.doc_references.append(reference)
            action = "Added"

        # Save the project with updated doc_references
        app.state.update_project(self.project, persist=True)

        # Refresh tree
        tree = self.query_one("#doc-tree", DocTreeWidget)
        tree.update_references(self.project.doc_references)
        self._update_status_bar()
        self.notify(f"{action} reference: {reference.title}")

    def _delete_url_reference(self, ref_id: str) -> None:
        """Delete a URL reference from the project.

        Args:
            ref_id: ID of the reference to delete.
        """
        reference = self._get_reference_by_id(ref_id)
        if not reference:
            self.notify("Reference not found", severity="error")
            return

        # Show delete confirmation modal
        from iterm_controller.screens.modals.delete_confirm import DeleteConfirmModal

        def handle_delete_result(confirmed: bool) -> None:
            """Handle the result from the delete confirmation modal."""
            if confirmed:
                self._do_delete_url_reference(ref_id, reference.title)

        self.app.push_screen(
            DeleteConfirmModal(
                item_name=reference.title,
                item_type="reference",
            ),
            handle_delete_result,
        )

    def _do_delete_url_reference(self, ref_id: str, title: str) -> None:
        """Actually delete the URL reference after confirmation.

        Args:
            ref_id: ID of the reference to delete.
            title: Title for the notification.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Remove the reference
        self.project.doc_references = [
            ref for ref in self.project.doc_references if ref.id != ref_id
        ]

        # Save the project with updated doc_references
        app.state.update_project(self.project, persist=True)

        # Refresh tree
        tree = self.query_one("#doc-tree", DocTreeWidget)
        tree.update_references(self.project.doc_references)
        self._update_status_bar()
        self.notify(f"Deleted reference: {title}")

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

    def on_doc_tree_widget_url_selected(
        self, event: DocTreeWidget.UrlSelected
    ) -> None:
        """Handle URL reference selection from tree widget.

        Args:
            event: The URL selected event.
        """
        self._update_status_bar()
        # Open URL in browser when selected (via Enter)
        self._open_url(event.url)
