"""Stage advance confirmation modal.

Modal dialog for confirming workflow stage advancement.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from iterm_controller.models import WorkflowStage


class StageAdvanceModal(ModalScreen[bool]):
    """Modal for confirming workflow stage advancement."""

    BINDINGS = [
        Binding("enter", "confirm", "Run Command"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, stage: WorkflowStage, command: str) -> None:
        """Initialize the modal.

        Args:
            stage: The stage we're advancing to.
            command: The command that will be executed.
        """
        super().__init__()
        self.stage = stage
        self.command = command

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        yield Container(
            Static(f"Advance to {self.stage.value.title()}?", id="title"),
            Vertical(
                Static(""),
                Static("The following command will run:"),
                Static(f"  [bold cyan]{self.command}[/bold cyan]", id="command"),
                Static(""),
                id="content",
            ),
            Horizontal(
                Button("[Enter] Run", id="confirm", variant="primary"),
                Button("[Esc] Cancel", id="cancel", variant="default"),
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
        """Confirm stage advancement."""
        self.dismiss(True)

    def action_cancel(self) -> None:
        """Cancel stage advancement."""
        self.dismiss(False)
