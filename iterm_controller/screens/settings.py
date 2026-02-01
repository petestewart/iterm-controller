"""App settings.

Screen for configuring application defaults.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Select

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp


class SettingsScreen(Screen):
    """Application settings."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            Vertical(
                Label("Default IDE"),
                Select(
                    id="ide-select",
                    options=[
                        ("vscode", "VS Code"),
                        ("cursor", "Cursor"),
                        ("vim", "Vim"),
                    ],
                ),
                Label("Default Shell"),
                Select(
                    id="shell-select",
                    options=[
                        ("zsh", "zsh"),
                        ("bash", "bash"),
                        ("fish", "fish"),
                    ],
                ),
                Label("Polling Interval (ms)"),
                Input(id="polling-input", value="500"),
                Checkbox("Enable Notifications", id="notify-checkbox", value=True),
                Checkbox("Auto-advance Workflow", id="auto-advance-checkbox", value=False),
                Horizontal(
                    Button("Cancel", variant="default", id="cancel"),
                    Button("Save Settings", variant="primary", id="save"),
                    id="buttons",
                ),
                id="form",
            ),
            id="main",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize settings from config."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        if app.state.config and app.state.config.settings:
            settings = app.state.config.settings

            # Set polling interval
            polling_input = self.query_one("#polling-input", Input)
            polling_input.value = str(settings.polling_interval_ms)

            # Set checkboxes
            notify_checkbox = self.query_one("#notify-checkbox", Checkbox)
            notify_checkbox.value = settings.notification_enabled

            # Note: Select value initialization is handled via default in compose
            # Setting value directly on Select can cause issues before mount completes

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel":
            self.app.pop_screen()
        elif event.button.id == "save":
            await self.action_save()

    async def action_save(self) -> None:
        """Save settings to config."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        if not app.state.config:
            self.notify("No configuration loaded", severity="error")
            return

        # Get values from form
        ide = self.query_one("#ide-select", Select).value
        shell = self.query_one("#shell-select", Select).value
        polling_str = self.query_one("#polling-input", Input).value
        notify = self.query_one("#notify-checkbox", Checkbox).value

        try:
            polling = int(polling_str)
        except ValueError:
            self.notify("Invalid polling interval", severity="error")
            return

        # Update config
        app.state.config.settings.default_ide = str(ide)
        app.state.config.settings.default_shell = str(shell)
        app.state.config.settings.polling_interval_ms = polling
        app.state.config.settings.notification_enabled = notify

        # Save to disk
        from iterm_controller.config import save_global_config

        save_global_config(app.state.config)

        self.notify("Settings saved")
        self.app.pop_screen()
