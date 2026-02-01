"""Auto mode configuration modal.

Modal dialog for configuring auto mode workflow automation settings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static

from iterm_controller.models import AutoModeConfig, WorkflowStage

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp


# Default commands for each stage
DEFAULT_STAGE_COMMANDS: dict[str, str] = {
    "planning": "claude /prd",
    "execute": "claude /plan",
    "review": "claude /review",
}


class AutoModeConfigModal(ModalScreen[AutoModeConfig | None]):
    """Modal for configuring auto mode settings.

    Allows users to:
    - Enable/disable auto mode
    - Configure stage commands for each workflow stage
    - Toggle auto-advance behavior
    - Configure confirmation requirements
    - Set designated session for command execution
    """

    CSS = """
    AutoModeConfigModal {
        align: center middle;
    }

    AutoModeConfigModal > Container {
        width: 70;
        max-height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    .section-title {
        text-style: bold;
        margin-top: 1;
        color: $text;
    }

    .stage-label {
        margin-top: 1;
        color: $text-muted;
    }

    .stage-input {
        margin-bottom: 0;
    }

    #form-container {
        height: auto;
        max-height: 30;
        overflow-y: auto;
    }

    #buttons {
        margin-top: 1;
        height: auto;
    }

    #buttons Button {
        margin-right: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("escape", "cancel", "Cancel"),
    ]

    # Workflow stages that can have commands configured
    CONFIGURABLE_STAGES = [
        (WorkflowStage.PLANNING, "Planning", "Command when entering planning stage"),
        (WorkflowStage.EXECUTE, "Execute", "Command when entering execute stage"),
        (WorkflowStage.REVIEW, "Review", "Command when entering review stage"),
        (WorkflowStage.PR, "PR", "Command when entering PR stage"),
    ]

    def __init__(self, config: AutoModeConfig | None = None) -> None:
        """Initialize the modal.

        Args:
            config: Current auto mode configuration to edit.
        """
        super().__init__()
        self._initial_config = config or AutoModeConfig()

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        config = self._initial_config

        yield Container(
            Static("Auto Mode Configuration", id="title"),
            Vertical(
                # Enable/disable section
                Checkbox(
                    "Enable Auto Mode",
                    id="enabled-checkbox",
                    value=config.enabled,
                ),
                # Behavior settings
                Static("Behavior", classes="section-title"),
                Checkbox(
                    "Auto-advance when stage completes",
                    id="auto-advance-checkbox",
                    value=config.auto_advance,
                ),
                Checkbox(
                    "Require confirmation before running commands",
                    id="require-confirmation-checkbox",
                    value=config.require_confirmation,
                ),
                # Designated session
                Static("Designated Session (optional)", classes="section-title"),
                Input(
                    value=config.designated_session or "",
                    placeholder="Session name to run commands in",
                    id="designated-session-input",
                ),
                # Stage commands section
                Static("Stage Commands", classes="section-title"),
                *self._compose_stage_inputs(config),
                id="form-container",
            ),
            Horizontal(
                Button("Cancel", variant="default", id="cancel"),
                Button("Reset to Defaults", variant="warning", id="reset"),
                Button("Save", variant="primary", id="save"),
                id="buttons",
            ),
            id="dialog",
        )

    def _compose_stage_inputs(
        self, config: AutoModeConfig
    ) -> list[Label | Input]:
        """Compose input fields for each stage command.

        Args:
            config: The current configuration.

        Returns:
            List of Label and Input widgets for stage commands.
        """
        widgets: list[Label | Input] = []

        for stage, label, placeholder in self.CONFIGURABLE_STAGES:
            current_command = config.stage_commands.get(stage.value, "")
            widgets.append(
                Label(f"{label} Stage:", classes="stage-label")
            )
            widgets.append(
                Input(
                    value=current_command,
                    placeholder=placeholder,
                    id=f"stage-{stage.value}-input",
                    classes="stage-input",
                )
            )

        return widgets

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel":
            self.action_cancel()
        elif event.button.id == "reset":
            await self._reset_to_defaults()
        elif event.button.id == "save":
            self.action_save()

    async def _reset_to_defaults(self) -> None:
        """Reset all fields to default values."""
        # Reset checkboxes
        self.query_one("#enabled-checkbox", Checkbox).value = False
        self.query_one("#auto-advance-checkbox", Checkbox).value = True
        self.query_one("#require-confirmation-checkbox", Checkbox).value = True

        # Reset designated session
        self.query_one("#designated-session-input", Input).value = ""

        # Reset stage commands to defaults
        for stage, _, _ in self.CONFIGURABLE_STAGES:
            input_widget = self.query_one(f"#stage-{stage.value}-input", Input)
            default_cmd = DEFAULT_STAGE_COMMANDS.get(stage.value, "")
            input_widget.value = default_cmd

        self.notify("Reset to default values")

    def _build_config(self) -> AutoModeConfig:
        """Build an AutoModeConfig from the current form values.

        Returns:
            The configured AutoModeConfig.
        """
        # Get checkbox values
        enabled = self.query_one("#enabled-checkbox", Checkbox).value
        auto_advance = self.query_one("#auto-advance-checkbox", Checkbox).value
        require_confirmation = self.query_one(
            "#require-confirmation-checkbox", Checkbox
        ).value

        # Get designated session
        designated_session_str = self.query_one(
            "#designated-session-input", Input
        ).value.strip()
        designated_session = designated_session_str if designated_session_str else None

        # Build stage commands dict
        stage_commands: dict[str, str] = {}
        for stage, _, _ in self.CONFIGURABLE_STAGES:
            input_widget = self.query_one(f"#stage-{stage.value}-input", Input)
            command = input_widget.value.strip()
            if command:
                stage_commands[stage.value] = command

        return AutoModeConfig(
            enabled=enabled,
            stage_commands=stage_commands,
            auto_advance=auto_advance,
            require_confirmation=require_confirmation,
            designated_session=designated_session,
        )

    def action_save(self) -> None:
        """Save the configuration and close the modal."""
        config = self._build_config()
        self.dismiss(config)

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.dismiss(None)
