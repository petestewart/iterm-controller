"""Docs section widget for Project Screen.

Displays collapsible section showing documentation files.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Button, Static

if TYPE_CHECKING:
    from iterm_controller.models import DocReference, Project

logger = logging.getLogger(__name__)

# Documentation directories to scan
DOC_DIRECTORIES = ["docs/", "specs/", "documentation/"]

# Root-level documentation files
DOC_FILES = ["README.md", "CHANGELOG.md", "CONTRIBUTING.md"]

# File extensions for documentation
DOC_EXTENSIONS = {".md", ".txt", ".rst", ".adoc"}


class DocsSection(Static):
    """Documentation section with collapsible content.

    Displays a collapsible section showing documentation files:
    - Files from docs/, specs/, documentation/ directories
    - Root-level files (README.md, CHANGELOG.md, etc.)
    - External URL references

    Example display:
        -- Docs ----------------------------------------
        > • docs/architecture.md
          • docs/api-design.md
          • specs/models.md
          🌐 API Documentation
        [+] Add doc...
    """

    DEFAULT_CSS = """
    DocsSection {
        height: auto;
        min-height: 6;
        padding: 0 1;
        border: solid $surface-lighten-1;
        margin-bottom: 1;
    }

    DocsSection .section-header {
        color: $text;
        text-style: bold;
        margin-bottom: 1;
    }

    DocsSection .section-header-collapsed {
        color: $text-muted;
        text-style: bold;
        margin-bottom: 0;
    }

    DocsSection #docs-container {
        height: auto;
        padding-left: 1;
    }

    DocsSection #add-doc-btn {
        margin-top: 1;
        width: auto;
        min-width: 16;
    }
    """

    class DocSelected(Message):
        """Posted when a document is selected."""

        def __init__(
            self,
            doc_path: Path | None,
            doc_name: str,
            is_url: bool = False,
            url: str = "",
        ) -> None:
            super().__init__()
            self.doc_path = doc_path
            self.doc_name = doc_name
            self.is_url = is_url
            self.url = url

    class AddDocRequested(Message):
        """Posted when user requests to add a document."""

        pass

    def __init__(
        self,
        project: Project | None = None,
        collapsed: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the docs section widget.

        Args:
            project: Project to show docs for.
            collapsed: Whether to start collapsed.
            **kwargs: Additional arguments passed to Static.
        """
        # Initialize instance attributes before calling super().__init__
        # because Textual's Static may call refresh() during initialization
        self._project = project
        self._collapsed = collapsed
        self._doc_files: list[tuple[str, Path]] = []  # (display_name, path)
        self._url_references: list[DocReference] = []
        self._selected_index = 0
        super().__init__(**kwargs)

    @property
    def project(self) -> Project | None:
        """Get the current project."""
        return self._project

    @property
    def collapsed(self) -> bool:
        """Get collapsed state."""
        return self._collapsed

    @property
    def selected_item(self) -> tuple[str, Path | None, bool, str] | None:
        """Get the currently selected item.

        Returns:
            Tuple of (name, path, is_url, url) or None if no selection.
        """
        if not self._project or self._collapsed:
            return None
        items = self._get_all_items()
        if 0 <= self._selected_index < len(items):
            return items[self._selected_index]
        return None

    def _get_all_items(self) -> list[tuple[str, Path | None, bool, str]]:
        """Get all selectable items.

        Returns:
            List of (name, path, is_url, url) tuples.
        """
        items: list[tuple[str, Path | None, bool, str]] = []

        # Add file items
        for display_name, path in self._doc_files:
            items.append((display_name, path, False, ""))

        # Add URL references
        for ref in self._url_references:
            items.append((ref.title, None, True, ref.url))

        return items

    def set_project(self, project: Project) -> None:
        """Set the project and refresh docs.

        Args:
            project: Project to show docs for.
        """
        self._project = project
        self.refresh_docs()

    def toggle_collapsed(self) -> None:
        """Toggle section collapsed state."""
        self._collapsed = not self._collapsed
        self.refresh()

    def refresh_docs(self) -> None:
        """Scan for documentation files and refresh display."""
        self._doc_files = []
        self._url_references = []

        if not self._project:
            self.refresh()
            return

        project_path = Path(self._project.path)

        # Scan documentation directories
        for dir_name in DOC_DIRECTORIES:
            dir_path = project_path / dir_name.rstrip("/")
            if dir_path.exists() and dir_path.is_dir():
                self._scan_directory(dir_path, dir_name.rstrip("/"))

        # Add root-level documentation files
        for file_name in DOC_FILES:
            file_path = project_path / file_name
            if file_path.exists() and file_path.is_file():
                self._doc_files.append((file_name, file_path))

        # Load URL references from project
        if self._project.doc_references:
            self._url_references = list(self._project.doc_references)

        # Reset selection if out of bounds
        items = self._get_all_items()
        if self._selected_index >= len(items):
            self._selected_index = max(0, len(items) - 1)

        self.refresh()

    def _scan_directory(self, dir_path: Path, prefix: str) -> None:
        """Scan a directory for documentation files.

        Args:
            dir_path: Directory path to scan.
            prefix: Display prefix for files (e.g., "docs").
        """
        try:
            for item in sorted(dir_path.iterdir()):
                if item.is_file() and self._is_doc_file(item):
                    display_name = f"{prefix}/{item.name}"
                    self._doc_files.append((display_name, item))
                elif item.is_dir() and not item.name.startswith("."):
                    # Recurse into subdirectories
                    self._scan_directory(item, f"{prefix}/{item.name}")
        except PermissionError as e:
            logger.debug("Permission denied reading directory '%s': %s", dir_path, e)

    def _is_doc_file(self, path: Path) -> bool:
        """Check if a file is a documentation file.

        Args:
            path: Path to check.

        Returns:
            True if the file is a documentation file.
        """
        if path.name.startswith("."):
            return False
        return path.suffix.lower() in DOC_EXTENSIONS

    def select_next(self) -> None:
        """Select the next item."""
        if self._collapsed:
            return
        items = self._get_all_items()
        if items:
            self._selected_index = min(self._selected_index + 1, len(items) - 1)
            self.refresh()

    def select_previous(self) -> None:
        """Select the previous item."""
        if self._collapsed:
            return
        if self._selected_index > 0:
            self._selected_index -= 1
            self.refresh()

    def action_select_doc(self) -> None:
        """Handle selection of current document."""
        selected = self.selected_item
        if selected:
            name, path, is_url, url = selected
            self.post_message(self.DocSelected(path, name, is_url, url))

    def action_add_doc(self) -> None:
        """Handle request to add a document."""
        self.post_message(self.AddDocRequested())

    def compose(self) -> "ComposeResult":  # type: ignore[name-defined]
        """Compose the widget content."""
        from textual.app import ComposeResult

        # Section header
        collapse_icon = ">" if self._collapsed else "v"
        header_class = "section-header-collapsed" if self._collapsed else "section-header"
        yield Static(f"{collapse_icon} Docs", classes=header_class, id="section-header")

        if not self._collapsed:
            yield Vertical(id="docs-container")
            yield Button("[+] Add doc...", id="add-doc-btn")

    def on_mount(self) -> None:
        """Initialize when mounted."""
        if self._project:
            self.refresh_docs()
        else:
            self.refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "add-doc-btn":
            self.action_add_doc()

    def _render_doc_item(
        self,
        name: str,
        is_url: bool,
        is_selected: bool,
    ) -> Text:
        """Render a single doc item row.

        Args:
            name: Display name.
            is_url: Whether this is a URL reference.
            is_selected: Whether this item is selected.

        Returns:
            Rich Text object for the row.
        """
        text = Text()

        # Selection indicator
        if is_selected:
            text.append("> ", style="bold cyan")
        else:
            text.append("  ")

        # Icon based on type
        if is_url:
            text.append("🌐 ", style="cyan")
        else:
            text.append("• ", style="green")

        # Name
        name_style = "bold" if is_selected else ""
        text.append(name, style=name_style)

        # Edit hint for selected items
        if is_selected:
            text.append(" [e]", style="dim cyan")

        return text

    def _update_docs_display(self, container: Vertical) -> None:
        """Update the docs container with current items."""
        container.remove_children()

        if not self._project:
            container.mount(Static("[dim]No project selected[/dim]"))
            return

        items = self._get_all_items()
        if not items:
            container.mount(Static("[dim]No documentation files[/dim]"))
            return

        # Build content
        lines: list[Text] = []
        for idx, (name, _path, is_url, _url) in enumerate(items):
            is_selected = idx == self._selected_index
            lines.append(self._render_doc_item(name, is_url, is_selected))

        # Combine into single content
        content = Text()
        for i, line in enumerate(lines):
            if i > 0:
                content.append("\n")
            content.append_text(line)

        container.mount(Static(content, id="docs-content"))

    def refresh(self, *args: Any, **kwargs: Any) -> None:
        """Override refresh to update docs display."""
        # Update section header
        try:
            header = self.query_one("#section-header", Static)
            collapse_icon = ">" if self._collapsed else "v"
            header.update(f"{collapse_icon} Docs")
            header.set_class(self._collapsed, "section-header-collapsed")
            header.set_class(not self._collapsed, "section-header")
        except Exception:
            pass

        # Update docs if not collapsed
        if not self._collapsed:
            try:
                container = self.query_one("#docs-container", Vertical)
                self._update_docs_display(container)
            except Exception:
                pass

        super().refresh(*args, **kwargs)

    def get_doc_count(self) -> int:
        """Get total number of documents.

        Returns:
            Count of files and URL references.
        """
        return len(self._doc_files) + len(self._url_references)
