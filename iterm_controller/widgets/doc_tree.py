"""Documentation tree widget for Docs Mode.

Tree view widget for navigating project documentation files.
Displays docs/, specs/, documentation/, and root-level files.

See specs/docs-mode.md for full specification.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from textual.message import Message
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

if TYPE_CHECKING:
    pass

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
        path: Path to the file or directory.
        is_directory: Whether this is a directory.
        name: Display name for the node.
    """

    path: Path
    is_directory: bool
    name: str


class DocTreeWidget(Tree[DocNode]):
    """Tree widget for documentation files.

    Displays a hierarchical tree of project documentation including:
    - docs/ directory and contents
    - specs/ directory and contents
    - documentation/ directory and contents
    - Root-level files (README.md, CHANGELOG.md, etc.)

    Keys:
        - Arrow keys or j/k: Navigate
        - Enter: Open file in editor / expand folder
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
        self.show_root = True
        self.guide_depth = 3

    @property
    def selected_path(self) -> Path | None:
        """Get the path of the currently selected node.

        Returns:
            Path to the selected file/directory, or None if nothing selected.
        """
        if self.cursor_node and self.cursor_node.data:
            return self.cursor_node.data.path
        return None

    @property
    def selected_is_file(self) -> bool:
        """Check if the selected node is a file."""
        if self.cursor_node and self.cursor_node.data:
            return not self.cursor_node.data.is_directory
        return False

    @property
    def selected_is_directory(self) -> bool:
        """Check if the selected node is a directory."""
        if self.cursor_node and self.cursor_node.data:
            return self.cursor_node.data.is_directory
        return False

    def set_project(self, project_path: str | Path) -> None:
        """Set the project path and rebuild the tree.

        Args:
            project_path: Path to the project root.
        """
        self._project_path = Path(project_path)
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

        # Expand root by default
        self.root.expand()

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
        except PermissionError:
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
            self.post_message(self.DirectorySelected(node.data.path))
        else:
            # Post file selected message
            self.post_message(self.FileSelected(node.data.path))

    def refresh_tree(self) -> None:
        """Refresh the tree to reflect filesystem changes."""
        # Store current selection
        selected_path = self.selected_path

        # Rebuild tree
        self.build_tree()

        # Try to restore selection
        if selected_path:
            self._select_by_path(selected_path)

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
