"""Documentation tree widget for Docs Mode.

Tree view widget for navigating project documentation files.
Displays docs/, specs/, documentation/, root-level files, and external URL references.

See specs/docs-mode.md for full specification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

from textual.message import Message
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

if TYPE_CHECKING:
    from iterm_controller.models import DocReference

# Directories to scan for documentation
DOC_DIRECTORIES = [
    "docs/",
    "specs/",
    "documentation/",
]

# Root-level documentation files to include
DOC_FILES = [
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
]

# File extensions recognized as documentation
DOC_EXTENSIONS = {".md", ".txt", ".rst", ".adoc"}


@dataclass
class DocNode:
    """Data stored in tree nodes.

    Attributes:
        path: Path to the file or directory (None for URL references).
        is_directory: Whether this is a directory.
        name: Display name for the node.
        is_url: Whether this is an external URL reference.
        url: The URL for external references.
        reference_id: ID of the DocReference for URL nodes.
        category: Category for URL references (for grouping).
    """

    path: Path | None
    is_directory: bool
    name: str
    is_url: bool = False
    url: str = ""
    reference_id: str = ""
    category: str = ""


class DocTreeWidget(Tree[DocNode]):
    """Tree widget for documentation files.

    Displays a hierarchical tree of project documentation including:
    - docs/ directory and contents
    - specs/ directory and contents
    - documentation/ directory and contents
    - Root-level files (README.md, CHANGELOG.md, etc.)
    - External URL references

    Keys:
        - Arrow keys or j/k: Navigate
        - Enter: Open file in editor / expand folder / open URL
        - Left/Right: Collapse/Expand folder
    """

    DEFAULT_CSS = """
    DocTreeWidget {
        height: 1fr;
        border: solid $surface;
        padding: 1;
    }

    DocTreeWidget > .tree--guides {
        color: $text-muted;
    }

    DocTreeWidget > .tree--cursor {
        background: $accent;
        color: $text;
    }

    DocTreeWidget:focus > .tree--cursor {
        background: $accent;
    }
    """

    class FileSelected(Message):
        """Posted when a file is selected (Enter pressed on a file)."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    class DirectorySelected(Message):
        """Posted when a directory is selected."""

        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    class UrlSelected(Message):
        """Posted when a URL reference is selected (Enter pressed on URL)."""

        def __init__(self, url: str, reference_id: str, title: str) -> None:
            super().__init__()
            self.url = url
            self.reference_id = reference_id
            self.title = title

    def __init__(
        self,
        project_path: str | Path | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the documentation tree widget.

        Args:
            project_path: Path to the project root.
            **kwargs: Additional arguments passed to Tree.
        """
        super().__init__("Documentation", **kwargs)
        self._project_path: Path | None = (
            Path(project_path) if project_path else None
        )
        self._doc_references: list[DocReference] = []
        self.show_root = True
        self.guide_depth = 3

    @property
    def selected_path(self) -> Path | None:
        """Get the path of the currently selected node.

        Returns:
            Path to the selected file/directory, or None if nothing selected or URL node.
        """
        if self.cursor_node and self.cursor_node.data:
            return self.cursor_node.data.path
        return None

    @property
    def selected_is_file(self) -> bool:
        """Check if the selected node is a file (not directory, not URL)."""
        if self.cursor_node and self.cursor_node.data:
            data = self.cursor_node.data
            return not data.is_directory and not data.is_url and data.path is not None
        return False

    @property
    def selected_is_directory(self) -> bool:
        """Check if the selected node is a directory."""
        if self.cursor_node and self.cursor_node.data:
            return self.cursor_node.data.is_directory
        return False

    @property
    def selected_is_url(self) -> bool:
        """Check if the selected node is a URL reference."""
        if self.cursor_node and self.cursor_node.data:
            return self.cursor_node.data.is_url
        return False

    @property
    def selected_url(self) -> str | None:
        """Get the URL of the currently selected URL node.

        Returns:
            URL string if a URL node is selected, None otherwise.
        """
        if self.cursor_node and self.cursor_node.data and self.cursor_node.data.is_url:
            return self.cursor_node.data.url
        return None

    @property
    def selected_reference_id(self) -> str | None:
        """Get the reference ID of the currently selected URL node.

        Returns:
            Reference ID string if a URL node is selected, None otherwise.
        """
        if self.cursor_node and self.cursor_node.data and self.cursor_node.data.is_url:
            return self.cursor_node.data.reference_id
        return None

    def set_project(
        self,
        project_path: str | Path,
        doc_references: list[DocReference] | None = None,
    ) -> None:
        """Set the project path and rebuild the tree.

        Args:
            project_path: Path to the project root.
            doc_references: List of external URL references to display.
        """
        self._project_path = Path(project_path)
        self._doc_references = doc_references or []
        self.build_tree()

    def build_tree(self) -> None:
        """Build the documentation tree from the project path."""
        # Clear existing tree
        self.clear()

        if not self._project_path:
            return

        # Set root label to project name
        self.root.set_label(self._project_path.name)
        self.root.data = DocNode(
            path=self._project_path,
            is_directory=True,
            name=self._project_path.name,
        )

        # Add documentation directories
        for dir_name in DOC_DIRECTORIES:
            dir_path = self._project_path / dir_name.rstrip("/")
            if dir_path.exists() and dir_path.is_dir():
                self._add_directory(self.root, dir_path)

        # Add root-level documentation files
        for file_name in DOC_FILES:
            file_path = self._project_path / file_name
            if file_path.exists() and file_path.is_file():
                self._add_file(self.root, file_path)

        # Add external URL references section if any exist
        if self._doc_references:
            self._add_references_section(self.root)

        # Expand root by default
        self.root.expand()

    def _add_references_section(self, parent: TreeNode[DocNode]) -> None:
        """Add the external references section to the tree.

        Args:
            parent: Parent node to add to.
        """
        # Create the "External References" folder node
        refs_node_data = DocNode(
            path=None,
            is_directory=True,
            name="External References",
        )
        refs_node = parent.add(
            "[bold cyan]🔗 External References[/bold cyan]",
            data=refs_node_data,
        )

        # Group references by category
        categorized: dict[str, list[DocReference]] = {}
        uncategorized: list[DocReference] = []

        for ref in self._doc_references:
            if ref.category:
                if ref.category not in categorized:
                    categorized[ref.category] = []
                categorized[ref.category].append(ref)
            else:
                uncategorized.append(ref)

        # Add categorized references
        for category, refs in sorted(categorized.items()):
            category_node_data = DocNode(
                path=None,
                is_directory=True,
                name=category,
                category=category,
            )
            category_node = refs_node.add(
                f"[bold]{category}[/bold]",
                data=category_node_data,
            )
            for ref in refs:
                self._add_url_reference(category_node, ref)

        # Add uncategorized references directly
        for ref in uncategorized:
            self._add_url_reference(refs_node, ref)

    def _add_url_reference(
        self, parent: TreeNode[DocNode], ref: DocReference
    ) -> TreeNode[DocNode]:
        """Add a URL reference node to the tree.

        Args:
            parent: Parent node to add to.
            ref: The DocReference to add.

        Returns:
            The created TreeNode.
        """
        node_data = DocNode(
            path=None,
            is_directory=False,
            name=ref.title,
            is_url=True,
            url=ref.url,
            reference_id=ref.id,
            category=ref.category,
        )

        # Use link emoji and styled text for URLs
        return parent.add_leaf(
            f"[cyan]🌐[/cyan] {ref.title}",
            data=node_data,
        )

    def _add_directory(
        self, parent: TreeNode[DocNode], dir_path: Path
    ) -> TreeNode[DocNode]:
        """Add a directory node to the tree.

        Args:
            parent: Parent node to add to.
            dir_path: Path to the directory.

        Returns:
            The created TreeNode for the directory.
        """
        node_data = DocNode(
            path=dir_path,
            is_directory=True,
            name=dir_path.name,
        )

        # Create folder node (expandable)
        node = parent.add(f"[bold]{dir_path.name}/[/bold]", data=node_data)

        # Add contents sorted: directories first, then files
        try:
            items = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError as e:
            logger.debug("Permission denied reading directory '%s': %s", dir_path, e)
            return node

        for item in items:
            if item.is_dir():
                # Skip hidden directories
                if not item.name.startswith("."):
                    self._add_directory(node, item)
            elif item.is_file() and self._is_doc_file(item):
                self._add_file(node, item)

        return node

    def _add_file(
        self, parent: TreeNode[DocNode], file_path: Path
    ) -> TreeNode[DocNode]:
        """Add a file node to the tree.

        Args:
            parent: Parent node to add to.
            file_path: Path to the file.

        Returns:
            The created TreeNode for the file.
        """
        node_data = DocNode(
            path=file_path,
            is_directory=False,
            name=file_path.name,
        )

        # Create leaf node (not expandable)
        return parent.add_leaf(file_path.name, data=node_data)

    def _is_doc_file(self, path: Path) -> bool:
        """Check if a file is a documentation file.

        Args:
            path: Path to check.

        Returns:
            True if the file is a documentation file.
        """
        # Skip hidden files
        if path.name.startswith("."):
            return False

        # Check extension
        return path.suffix.lower() in DOC_EXTENSIONS

    def on_tree_node_selected(self, event: Tree.NodeSelected[DocNode]) -> None:
        """Handle node selection (Enter key).

        For files: Post FileSelected message.
        For directories: Toggle expansion.
        For URLs: Post UrlSelected message.

        Args:
            event: The node selection event.
        """
        event.stop()

        node = event.node
        if not node.data:
            return

        if node.data.is_directory:
            # Toggle directory expansion
            node.toggle()
            if node.data.path:
                self.post_message(self.DirectorySelected(node.data.path))
        elif node.data.is_url:
            # Post URL selected message
            self.post_message(
                self.UrlSelected(
                    url=node.data.url,
                    reference_id=node.data.reference_id,
                    title=node.data.name,
                )
            )
        elif node.data.path:
            # Post file selected message
            self.post_message(self.FileSelected(node.data.path))

    def refresh_tree(self) -> None:
        """Refresh the tree to reflect filesystem changes."""
        # Store current selection
        selected_path = self.selected_path
        selected_ref_id = self.selected_reference_id

        # Rebuild tree
        self.build_tree()

        # Try to restore selection
        if selected_path:
            self._select_by_path(selected_path)
        elif selected_ref_id:
            self._select_by_reference_id(selected_ref_id)

    def update_references(self, doc_references: list[DocReference]) -> None:
        """Update the doc references and refresh the tree.

        Args:
            doc_references: New list of external URL references.
        """
        self._doc_references = doc_references
        self.refresh_tree()

    def _select_by_path(self, target_path: Path) -> bool:
        """Select a node by its path.

        Args:
            target_path: Path to select.

        Returns:
            True if the node was found and selected.
        """

        def _find_node(node: TreeNode[DocNode]) -> TreeNode[DocNode] | None:
            """Recursively search for a node with the given path."""
            if node.data and node.data.path == target_path:
                return node
            for child in node.children:
                result = _find_node(child)
                if result:
                    return result
            return None

        found = _find_node(self.root)
        if found:
            self.select_node(found)
            return True
        return False

    def _select_by_reference_id(self, reference_id: str) -> bool:
        """Select a URL reference node by its reference ID.

        Args:
            reference_id: Reference ID to select.

        Returns:
            True if the node was found and selected.
        """

        def _find_node(node: TreeNode[DocNode]) -> TreeNode[DocNode] | None:
            """Recursively search for a node with the given reference ID."""
            if node.data and node.data.reference_id == reference_id:
                return node
            for child in node.children:
                result = _find_node(child)
                if result:
                    return result
            return None

        found = _find_node(self.root)
        if found:
            self.select_node(found)
            return True
        return False
