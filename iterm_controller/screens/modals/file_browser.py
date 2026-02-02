"""File Browser modal for Docs Mode.

Modal dialog for browsing and selecting existing files from the project.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Tree
from textual.widgets.tree import TreeNode

logger = logging.getLogger(__name__)


@dataclass
class FileNode:
    """Data stored in file browser tree nodes.

    Attributes:
        path: Path to the file or directory.
        is_directory: Whether this is a directory.
        name: Display name for the node.
    """

    path: Path
    is_directory: bool
    name: str


class FileBrowserTree(Tree[FileNode]):
    """Tree widget for browsing project files.

    Displays a hierarchical tree of all files in the project,
    allowing the user to browse and select a file.
    """

    DEFAULT_CSS = """
    FileBrowserTree {
        height: 1fr;
        border: solid $surface;
        padding: 0;
    }

    FileBrowserTree > .tree--guides {
        color: $text-muted;
    }

    FileBrowserTree > .tree--cursor {
        background: $accent;
        color: $text;
    }

    FileBrowserTree:focus > .tree--cursor {
        background: $accent;
    }
    """

    # File extensions to show (docs + common project files)
    ALLOWED_EXTENSIONS = {
        ".md",
        ".txt",
        ".rst",
        ".adoc",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
    }

    def __init__(
        self,
        project_path: str | Path,
        **kwargs: Any,
    ) -> None:
        """Initialize the file browser tree.

        Args:
            project_path: Path to the project root.
            **kwargs: Additional arguments passed to Tree.
        """
        super().__init__("Files", **kwargs)
        self._project_path = Path(project_path)
        self.show_root = True
        self.guide_depth = 4

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

    def on_mount(self) -> None:
        """Build the tree when mounted."""
        self.build_tree()

    def build_tree(self) -> None:
        """Build the file browser tree from the project path."""
        self.clear()

        # Set root to project name
        self.root.set_label(self._project_path.name)
        self.root.data = FileNode(
            path=self._project_path,
            is_directory=True,
            name=self._project_path.name,
        )

        # Add all project contents
        self._add_directory_contents(self.root, self._project_path)

        # Expand root by default
        self.root.expand()

    def _add_directory_contents(
        self, parent: TreeNode[FileNode], dir_path: Path
    ) -> None:
        """Add directory contents to the tree.

        Args:
            parent: Parent node to add contents to.
            dir_path: Path to the directory to scan.
        """
        try:
            items = sorted(
                dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except PermissionError as e:
            logger.debug("Permission denied reading directory '%s': %s", dir_path, e)
            return

        for item in items:
            # Skip hidden files/directories
            if item.name.startswith("."):
                continue

            # Skip common non-doc directories
            if item.is_dir() and item.name in {
                "node_modules",
                "__pycache__",
                ".git",
                "venv",
                ".venv",
                "env",
                ".env",
                "dist",
                "build",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
                "coverage",
                ".coverage",
                "htmlcov",
            }:
                continue

            if item.is_dir():
                self._add_directory(parent, item)
            elif item.is_file() and self._is_allowed_file(item):
                self._add_file(parent, item)

    def _add_directory(
        self, parent: TreeNode[FileNode], dir_path: Path
    ) -> TreeNode[FileNode]:
        """Add a directory node to the tree.

        Args:
            parent: Parent node to add to.
            dir_path: Path to the directory.

        Returns:
            The created TreeNode for the directory.
        """
        node_data = FileNode(
            path=dir_path,
            is_directory=True,
            name=dir_path.name,
        )

        node = parent.add(f"[bold]{dir_path.name}/[/bold]", data=node_data)
        self._add_directory_contents(node, dir_path)
        return node

    def _add_file(
        self, parent: TreeNode[FileNode], file_path: Path
    ) -> TreeNode[FileNode]:
        """Add a file node to the tree.

        Args:
            parent: Parent node to add to.
            file_path: Path to the file.

        Returns:
            The created TreeNode for the file.
        """
        node_data = FileNode(
            path=file_path,
            is_directory=False,
            name=file_path.name,
        )

        return parent.add_leaf(file_path.name, data=node_data)

    def _is_allowed_file(self, path: Path) -> bool:
        """Check if a file should be shown in the browser.

        Args:
            path: Path to check.

        Returns:
            True if the file should be shown.
        """
        return path.suffix.lower() in self.ALLOWED_EXTENSIONS


class FileBrowserModal(ModalScreen[Path | None]):
    """Modal for browsing and selecting files from the project.

    Returns the selected file Path, or None if cancelled.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select", "Select"),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("left", "collapse_node", "Collapse", show=False),
        Binding("right", "expand_node", "Expand", show=False),
        Binding("h", "collapse_node", "Collapse", show=False),
        Binding("l", "expand_node", "Expand", show=False),
    ]

    DEFAULT_CSS = """
    FileBrowserModal {
        align: center middle;
    }

    FileBrowserModal #dialog {
        width: 70;
        height: 30;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    FileBrowserModal #title {
        text-style: bold;
        padding-bottom: 1;
    }

    FileBrowserModal #description {
        padding-bottom: 1;
        color: $text-muted;
    }

    FileBrowserModal #tree-container {
        height: 1fr;
        border: solid $surface-lighten-1;
        margin-bottom: 1;
    }

    FileBrowserModal FileBrowserTree {
        height: 1fr;
    }

    FileBrowserModal #selected-path {
        height: 1;
        padding: 0 1;
        color: $text-muted;
    }

    FileBrowserModal #buttons {
        height: 3;
        align: center middle;
    }

    FileBrowserModal Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        project_path: str | Path,
        title: str = "Select File",
        description: str = "Browse and select a file to add",
    ) -> None:
        """Initialize the modal.

        Args:
            project_path: Path to the project root.
            title: Modal title.
            description: Modal description.
        """
        super().__init__()
        self._project_path = Path(project_path)
        self._title = title
        self._description = description

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        yield Vertical(
            Static(self._title, id="title"),
            Static(self._description, id="description"),
            Vertical(
                FileBrowserTree(self._project_path, id="file-tree"),
                id="tree-container",
            ),
            Static("", id="selected-path"),
            Horizontal(
                Button("Cancel", variant="default", id="cancel"),
                Button("Select", variant="primary", id="select"),
                id="buttons",
            ),
            id="dialog",
        )

    def on_mount(self) -> None:
        """Focus the tree when mounted."""
        self.query_one("#file-tree", FileBrowserTree).focus()

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[FileNode]) -> None:
        """Update the selected path display when cursor moves.

        Args:
            event: The node highlighted event.
        """
        self._update_selected_path()

    def _update_selected_path(self) -> None:
        """Update the selected path display."""
        tree = self.query_one("#file-tree", FileBrowserTree)
        path_label = self.query_one("#selected-path", Static)

        if tree.selected_path:
            try:
                rel_path = tree.selected_path.relative_to(self._project_path)
                path_label.update(f"Selected: {rel_path}")
            except ValueError:
                path_label.update(f"Selected: {tree.selected_path.name}")
        else:
            path_label.update("")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button pressed event.
        """
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "select":
            self._select_file()

    def _select_file(self) -> None:
        """Select the highlighted file and dismiss."""
        tree = self.query_one("#file-tree", FileBrowserTree)

        if not tree.selected_is_file:
            self.notify("Please select a file, not a directory", severity="warning")
            return

        selected_path = tree.selected_path
        if selected_path:
            self.dismiss(selected_path)
        else:
            self.notify("No file selected", severity="warning")

    def action_cancel(self) -> None:
        """Cancel and dismiss."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Select the highlighted file."""
        self._select_file()

    def action_cursor_down(self) -> None:
        """Move cursor down in the tree."""
        tree = self.query_one("#file-tree", FileBrowserTree)
        tree.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up in the tree."""
        tree = self.query_one("#file-tree", FileBrowserTree)
        tree.action_cursor_up()

    def action_collapse_node(self) -> None:
        """Collapse the selected directory or move to parent."""
        tree = self.query_one("#file-tree", FileBrowserTree)
        node = tree.cursor_node

        if not node:
            return

        if node.data and node.data.is_directory and node.is_expanded:
            node.collapse()
        elif node.parent and node.parent != tree.root:
            tree.select_node(node.parent)
        elif node.parent == tree.root:
            tree.select_node(tree.root)

    def action_expand_node(self) -> None:
        """Expand the selected directory or enter it."""
        tree = self.query_one("#file-tree", FileBrowserTree)
        node = tree.cursor_node

        if not node or not node.data:
            return

        if node.data.is_directory:
            if not node.is_expanded:
                node.expand()
            elif node.children:
                tree.select_node(node.children[0])
