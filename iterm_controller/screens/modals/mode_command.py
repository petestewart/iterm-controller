"""Mode command confirmation modal.

Modal dialog for confirming command execution when entering a workflow mode.
See specs/auto-mode.md#mode-command-modal for specification.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from iterm_controller.models import WorkflowMode


class ModeCommandModal(ModalScreen[bool]):
    """Modal for confirming mode command execution.

    This modal is shown when entering a workflow mode that has a
    configured auto mode command. The user can choose to run the
    command or skip it.
    """

    BINDINGS = [
        Binding("enter", "confirm", "Run Command"),
        Binding("escape", "cancel", "Skip"),
    ]

    DEFAULT_CSS = """
    ModeCommandModal {
        align: center middle;
    }

    ModeCommandModal #dialog {
        width: 60;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: thick $primary;
    }

    ModeCommandModal #title {
        text-style: bold;
        text-align: center;
        width: 100%;
        margin-bottom: 1;
    }

    ModeCommandModal #content {
        margin-bottom: 1;
    }

    ModeCommandModal #command {
        margin: 1 0;
        padding: 0 2;
    }

    ModeCommandModal #buttons {
        width: 100%;
        height: auto;
        align: center middle;
    }

    ModeCommandModal Button {
        margin: 0 1;
    }
    """

    def __init__(self, mode: WorkflowMode, command: str) -> None:
        """Initialize the modal.

        Args:
            mode: The workflow mode being entered.
            command: The command that will be executed.
        """
        super().__init__()
        self.mode = mode
        self.command = command

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        yield Container(
            Static(f"Entering {self.mode.value.title()} Mode", id="title"),
            Vertical(
                Static(""),
                Static("Run planning command?"),
                Static(f"  [bold cyan]{self.command}[/bold cyan]", id="command"),
                Static(""),
                id="content",
            ),
            Horizontal(
                Button("[Enter] Run", id="confirm", variant="primary"),
                Button("[Esc] Skip", id="cancel", variant="default"),
                id="buttons",
            ),
            id="dialog",
        )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "confirm":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_confirm(self) -> None:
        """Confirm command execution."""
        self.dismiss(True)

    def action_cancel(self) -> None:
        """Cancel command execution."""
        self.dismiss(False)
