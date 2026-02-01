"""Help modal showing keyboard shortcuts.

Displays all available keyboard shortcuts organized by context.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static


class HelpModal(ModalScreen[None]):
    """Modal showing all keyboard shortcuts."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close", show=False),
        Binding("?", "dismiss", "Close", show=False),
    ]

    CSS = """
    HelpModal {
        align: center middle;
    }

    HelpModal > Container {
        width: 70;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    HelpModal #title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid $primary;
    }

    HelpModal .section-title {
        text-style: bold;
        color: $primary;
        margin-top: 1;
    }

    HelpModal .shortcut-row {
        padding-left: 2;
    }

    HelpModal .key {
        color: $accent;
        text-style: bold;
    }

    HelpModal #footer {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
        padding-top: 1;
        border-top: solid $primary;
    }
    """

    SHORTCUTS = {
        "Global": [
            ("?", "Show this help"),
            ("q", "Quit application"),
            ("ctrl+c", "Quit immediately"),
            ("p", "Open project list"),
            ("s", "Open sessions (Control Room)"),
            (",", "Open settings"),
            ("h", "Go to home (Control Room)"),
        ],
        "Control Room": [
            ("n", "New session"),
            ("k", "Kill selected session"),
            ("enter", "Focus selected session in iTerm2"),
            ("r", "Refresh session list"),
            ("1-9", "Focus session by number"),
        ],
        "Project List": [
            ("enter", "Open selected project"),
            ("n", "Create new project"),
            ("d", "Delete selected project"),
            ("r", "Refresh project list"),
            ("escape", "Go back"),
        ],
        "Project Dashboard": [
            ("1", "Enter Plan Mode"),
            ("2", "Enter Docs Mode"),
            ("3", "Enter Work Mode"),
            ("4", "Enter Test Mode"),
            ("t", "Toggle task status"),
            ("s", "Spawn new session"),
            ("r", "Run script"),
            ("d", "Open docs picker"),
            ("g", "Show GitHub actions"),
            ("f", "Focus session in iTerm2"),
            ("k", "Kill session"),
            ("a", "Toggle auto mode"),
            ("escape", "Go back"),
        ],
        "Workflow Modes": [
            ("1", "Switch to Plan Mode"),
            ("2", "Switch to Docs Mode"),
            ("3", "Switch to Work Mode"),
            ("4", "Switch to Test Mode"),
            ("escape", "Return to dashboard"),
        ],
        "Plan Mode": [
            ("j/k or ↑/↓", "Navigate artifacts"),
            ("enter", "View artifact"),
            ("e", "Edit artifact"),
            ("c", "Create missing artifact"),
            ("s", "Spawn planning session"),
            ("r", "Refresh status"),
        ],
        "Docs Mode": [
            ("j/k or ↑/↓", "Navigate tree"),
            ("h/l or ←/→", "Collapse/expand"),
            ("enter", "Open file or toggle folder"),
            ("e", "Edit selected"),
            ("a", "Add document"),
            ("d", "Delete document"),
            ("r", "Rename document"),
            ("p", "Preview document"),
            ("x", "Refresh tree"),
        ],
        "Work Mode": [
            ("j/k or ↑/↓", "Navigate tasks"),
            ("tab", "Switch between queue/active panels"),
            ("c", "Claim task"),
            ("u", "Unclaim task"),
            ("d", "Mark task done"),
            ("s", "Spawn session for task"),
            ("f", "Focus linked session"),
            ("v", "View dependencies"),
            ("r", "Refresh"),
        ],
        "Test Mode": [
            ("j/k or ↑/↓", "Navigate test steps"),
            ("tab", "Switch between plan/tests panels"),
            ("enter", "Toggle test step"),
            ("g", "Generate TEST_PLAN.md"),
            ("s", "Spawn QA session"),
            ("r", "Run unit tests"),
            ("w", "Watch tests"),
            ("f", "Run failed tests only"),
            ("x", "Refresh"),
        ],
        "Settings": [
            ("ctrl+s", "Save settings"),
            ("escape", "Cancel and go back"),
        ],
        "Modals": [
            ("1-9", "Select numbered item"),
            ("escape", "Cancel/dismiss"),
            ("enter", "Confirm selection"),
        ],
    }

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        yield Container(
            Static("Keyboard Shortcuts", id="title"),
            VerticalScroll(
                *self._build_sections(),
                id="content",
            ),
            Static("Press [bold]Escape[/bold], [bold]q[/bold], or [bold]?[/bold] to close", id="footer"),
            id="dialog",
        )

    def _build_sections(self) -> list[Static]:
        """Build shortcut section widgets.

        Returns:
            List of Static widgets for each section.
        """
        widgets = []
        for section_name, shortcuts in self.SHORTCUTS.items():
            widgets.append(Static(f"{section_name}", classes="section-title"))
            for key, description in shortcuts:
                widgets.append(
                    Static(f"  [{key}]  {description}", classes="shortcut-row")
                )
        return widgets

    def action_dismiss(self) -> None:
        """Dismiss the modal."""
        self.dismiss(None)
