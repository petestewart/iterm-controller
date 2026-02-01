"""Docs picker modal.

Modal dialog for quick access to project documentation files.
Opens selected documentation in the configured editor.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp


# Common documentation file patterns
DOC_PATTERNS = [
    "*.md",
    "*.markdown",
    "*.txt",
    "*.rst",
    "docs/**/*.md",
    "docs/**/*.txt",
    "docs/**/*.rst",
    "documentation/**/*.md",
    "specs/**/*.md",
]

# Files to exclude (common noise)
EXCLUDE_PATTERNS = [
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    "build",
    "dist",
    ".eggs",
]


class DocsPickerModal(ModalScreen[Path | None]):
    """Modal for selecting a documentation file to open.

    Returns the selected Path, or None if cancelled.
    """

    BINDINGS = [
        Binding("1", "select_1", "Doc 1", show=False),
        Binding("2", "select_2", "Doc 2", show=False),
        Binding("3", "select_3", "Doc 3", show=False),
        Binding("4", "select_4", "Doc 4", show=False),
        Binding("5", "select_5", "Doc 5", show=False),
        Binding("6", "select_6", "Doc 6", show=False),
        Binding("7", "select_7", "Doc 7", show=False),
        Binding("8", "select_8", "Doc 8", show=False),
        Binding("9", "select_9", "Doc 9", show=False),
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    DocsPickerModal {
        align: center middle;
    }

    DocsPickerModal > Container {
        width: 70;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    DocsPickerModal #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: $text;
    }

    DocsPickerModal #doc-list {
        height: auto;
        max-height: 20;
        margin-bottom: 1;
    }

    DocsPickerModal .doc-button {
        width: 100%;
        margin-bottom: 1;
    }

    DocsPickerModal #cancel-button {
        width: 100%;
        margin-top: 1;
    }

    DocsPickerModal .doc-path {
        color: $text-muted;
        text-style: italic;
    }
    """

    def __init__(self, project_path: str | Path) -> None:
        """Initialize the docs picker modal.

        Args:
            project_path: Path to the project root directory.
        """
        super().__init__()
        self.project_path = Path(project_path)
        self._docs: list[Path] = []

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        yield Container(
            Static("Select Documentation", id="title"),
            Static("[dim]Scanning for docs...[/dim]", id="loading"),
            Vertical(id="doc-list"),
            Button("Cancel [Esc]", id="cancel-button", variant="default"),
            id="dialog",
        )

    async def on_mount(self) -> None:
        """Scan for documentation files when screen mounts."""
        # Run file scan in background to avoid blocking UI
        self._docs = await asyncio.to_thread(self._scan_docs)

        # Remove loading indicator
        loading = self.query_one("#loading", Static)
        loading.remove()

        # Populate doc list
        doc_list = self.query_one("#doc-list", Vertical)

        if not self._docs:
            doc_list.mount(Static("[dim]No documentation files found[/dim]"))
            return

        for i, doc_path in enumerate(self._docs[:9], start=1):
            # Create button with number prefix and doc name
            relative_path = doc_path.relative_to(self.project_path)
            label = f"[{i}] {doc_path.name}"
            button = Button(label, id=f"doc-{i}", classes="doc-button")
            doc_list.mount(button)

            # Add relative path preview if different from filename
            if str(relative_path) != doc_path.name:
                doc_list.mount(
                    Static(f"    [dim]{relative_path}[/dim]", classes="doc-path")
                )

    def _scan_docs(self) -> list[Path]:
        """Scan project for documentation files.

        Returns:
            List of documentation file paths, sorted by relevance.
        """
        docs: list[Path] = []
        seen: set[Path] = set()

        # Priority files (always at top if they exist)
        priority_files = [
            "README.md",
            "README.txt",
            "PLAN.md",
            "PRD.md",
            "CHANGELOG.md",
            "CONTRIBUTING.md",
        ]

        for filename in priority_files:
            path = self.project_path / filename
            if path.exists() and path not in seen:
                docs.append(path)
                seen.add(path)

        # Scan for other doc files
        for pattern in DOC_PATTERNS:
            for path in self.project_path.glob(pattern):
                if path not in seen and self._should_include(path):
                    docs.append(path)
                    seen.add(path)

        return docs

    def _should_include(self, path: Path) -> bool:
        """Check if path should be included in results.

        Args:
            path: Path to check.

        Returns:
            True if path should be included.
        """
        if not path.is_file():
            return False

        # Check if any parent directory is in exclude list
        for part in path.parts:
            if part in EXCLUDE_PATTERNS:
                return False

        return True

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "cancel-button":
            self.dismiss(None)
            return

        # Check for doc buttons (doc-1, doc-2, etc.)
        if button_id and button_id.startswith("doc-"):
            try:
                index = int(button_id.split("-")[1]) - 1
                if 0 <= index < len(self._docs):
                    await self._open_doc(self._docs[index])
            except (ValueError, IndexError):
                pass

    async def _open_doc(self, doc_path: Path) -> None:
        """Open documentation file in editor and dismiss modal.

        Args:
            doc_path: Path to the documentation file.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Get configured editor
        ide = "code"  # default to VS Code
        if app.state.config and app.state.config.settings:
            ide = app.state.config.settings.default_ide

        # Map IDE name to command
        editor_commands = {
            "vscode": ["code", str(doc_path)],
            "code": ["code", str(doc_path)],
            "cursor": ["cursor", str(doc_path)],
            "vim": ["vim", str(doc_path)],
            "nvim": ["nvim", str(doc_path)],
            "neovim": ["nvim", str(doc_path)],
            "subl": ["subl", str(doc_path)],
            "sublime": ["subl", str(doc_path)],
            "atom": ["atom", str(doc_path)],
            "nano": ["nano", str(doc_path)],
            "emacs": ["emacs", str(doc_path)],
        }

        cmd = editor_commands.get(ide.lower(), ["open", str(doc_path)])

        try:
            # Run editor command in background
            await asyncio.to_thread(
                subprocess.Popen,
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.dismiss(doc_path)
        except FileNotFoundError:
            # Editor not found, try macOS open command
            try:
                await asyncio.to_thread(
                    subprocess.Popen,
                    ["open", str(doc_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.dismiss(doc_path)
            except Exception as e:
                self.app.notify(f"Failed to open file: {e}", severity="error")

    def _select_doc(self, index: int) -> None:
        """Select doc by 0-based index."""
        if 0 <= index < len(self._docs):
            self.call_later(self._open_doc, self._docs[index])

    def action_select_1(self) -> None:
        """Select doc 1."""
        self._select_doc(0)

    def action_select_2(self) -> None:
        """Select doc 2."""
        self._select_doc(1)

    def action_select_3(self) -> None:
        """Select doc 3."""
        self._select_doc(2)

    def action_select_4(self) -> None:
        """Select doc 4."""
        self._select_doc(3)

    def action_select_5(self) -> None:
        """Select doc 5."""
        self._select_doc(4)

    def action_select_6(self) -> None:
        """Select doc 6."""
        self._select_doc(5)

    def action_select_7(self) -> None:
        """Select doc 7."""
        self._select_doc(6)

    def action_select_8(self) -> None:
        """Select doc 8."""
        self._select_doc(7)

    def action_select_9(self) -> None:
        """Select doc 9."""
        self._select_doc(8)

    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(None)
