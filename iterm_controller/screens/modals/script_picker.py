"""Script picker modal.

Modal dialog for selecting and running project scripts (session templates)
in new sessions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from iterm_controller.models import SessionTemplate

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp


class ScriptPickerModal(ModalScreen[SessionTemplate | None]):
    """Modal for selecting a session template to spawn.

    Returns the selected SessionTemplate, or None if cancelled.
    """

    BINDINGS = [
        Binding("1", "select_1", "Template 1", show=False),
        Binding("2", "select_2", "Template 2", show=False),
        Binding("3", "select_3", "Template 3", show=False),
        Binding("4", "select_4", "Template 4", show=False),
        Binding("5", "select_5", "Template 5", show=False),
        Binding("6", "select_6", "Template 6", show=False),
        Binding("7", "select_7", "Template 7", show=False),
        Binding("8", "select_8", "Template 8", show=False),
        Binding("9", "select_9", "Template 9", show=False),
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    ScriptPickerModal {
        align: center middle;
    }

    ScriptPickerModal > Container {
        width: 60;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    ScriptPickerModal #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: $text;
    }

    ScriptPickerModal #template-list {
        height: auto;
        max-height: 20;
        margin-bottom: 1;
    }

    ScriptPickerModal .template-button {
        width: 100%;
        margin-bottom: 1;
    }

    ScriptPickerModal #cancel-button {
        width: 100%;
        margin-top: 1;
    }

    ScriptPickerModal .template-command {
        color: $text-muted;
        text-style: italic;
    }
    """

    def __init__(self) -> None:
        """Initialize the script picker modal."""
        super().__init__()
        self._templates: list[SessionTemplate] = []

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        yield Container(
            Static("Select Script to Run", id="title"),
            Static("[dim]Loading templates...[/dim]", id="loading"),
            Vertical(id="template-list"),
            Button("Cancel [Esc]", id="cancel-button", variant="default"),
            id="dialog",
        )

    async def on_mount(self) -> None:
        """Load session templates from config."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Get templates from config
        if app.state.config and app.state.config.session_templates:
            self._templates = app.state.config.session_templates
        else:
            self._templates = []

        # Remove loading indicator
        loading = self.query_one("#loading", Static)
        loading.remove()

        # Populate template list
        template_list = self.query_one("#template-list", Vertical)

        if not self._templates:
            template_list.mount(
                Static("[dim]No session templates configured[/dim]")
            )
            return

        for i, template in enumerate(self._templates[:9], start=1):
            # Create button with number prefix and template info
            label = f"[{i}] {template.name}"
            button = Button(label, id=f"template-{i}", classes="template-button")
            template_list.mount(button)

            # Add command preview
            cmd_preview = template.command[:40] + "..." if len(template.command) > 40 else template.command
            template_list.mount(
                Static(f"    [dim]{cmd_preview}[/dim]", classes="template-command")
            )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "cancel-button":
            self.dismiss(None)
            return

        # Check for template buttons (template-1, template-2, etc.)
        if button_id and button_id.startswith("template-"):
            try:
                index = int(button_id.split("-")[1]) - 1
                if 0 <= index < len(self._templates):
                    self.dismiss(self._templates[index])
            except (ValueError, IndexError) as e:
                logger.debug("Invalid template button index '%s': %s", button_id, e)

    def _select_template(self, index: int) -> None:
        """Select template by 0-based index."""
        if 0 <= index < len(self._templates):
            self.dismiss(self._templates[index])

    def action_select_1(self) -> None:
        """Select template 1."""
        self._select_template(0)

    def action_select_2(self) -> None:
        """Select template 2."""
        self._select_template(1)

    def action_select_3(self) -> None:
        """Select template 3."""
        self._select_template(2)

    def action_select_4(self) -> None:
        """Select template 4."""
        self._select_template(3)

    def action_select_5(self) -> None:
        """Select template 5."""
        self._select_template(4)

    def action_select_6(self) -> None:
        """Select template 6."""
        self._select_template(5)

    def action_select_7(self) -> None:
        """Select template 7."""
        self._select_template(6)

    def action_select_8(self) -> None:
        """Select template 8."""
        self._select_template(7)

    def action_select_9(self) -> None:
        """Select template 9."""
        self._select_template(8)

    def action_cancel(self) -> None:
        """Cancel and close modal."""
        self.dismiss(None)
