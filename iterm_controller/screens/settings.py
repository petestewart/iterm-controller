"""App settings.

Screen for configuring application defaults.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Select, Static

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp
    from iterm_controller.models import AutoModeConfig


class SettingsScreen(Screen):
    """Application settings.

    Provides a form for configuring application defaults including:
    - Default IDE for opening files
    - Default shell for new sessions
    - Polling interval for session monitoring
    - Notification preferences
    - Auto-mode workflow settings (via dedicated modal)
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+s", "save", "Save"),
    ]

    # IDE and shell options: format is (display, value)
    IDE_OPTIONS = [
        ("VS Code", "vscode"),
        ("Cursor", "cursor"),
        ("Vim", "vim"),
        ("Neovim", "neovim"),
        ("Sublime Text", "sublime"),
    ]

    SHELL_OPTIONS = [
        ("zsh", "zsh"),
        ("bash", "bash"),
        ("fish", "fish"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            Vertical(
                Label("Default IDE", classes="setting-label"),
                Select(
                    id="ide-select",
                    options=self.IDE_OPTIONS,
                    prompt="Select IDE...",
                ),
                Label("Default Shell", classes="setting-label"),
                Select(
                    id="shell-select",
                    options=self.SHELL_OPTIONS,
                    prompt="Select shell...",
                ),
                Label("Polling Interval (ms)", classes="setting-label"),
                Input(id="polling-input", value="500"),
                Checkbox("Enable Notifications", id="notify-checkbox", value=True),
                # Auto Mode section
                Static("Auto Mode", classes="section-header"),
                Horizontal(
                    Static("", id="auto-mode-status"),
                    Button("Configure Auto Mode...", id="configure-auto-mode"),
                    id="auto-mode-row",
                ),
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

        if app.state.config:
            settings = app.state.config.settings

            # Set IDE select - find matching option (value is the second element)
            ide_select = self.query_one("#ide-select", Select)
            ide_value = settings.default_ide
            if ide_value and any(opt[1] == ide_value for opt in self.IDE_OPTIONS):
                ide_select.value = ide_value

            # Set shell select - find matching option (value is the second element)
            shell_select = self.query_one("#shell-select", Select)
            shell_value = settings.default_shell
            if shell_value and any(opt[1] == shell_value for opt in self.SHELL_OPTIONS):
                shell_select.value = shell_value

            # Set polling interval
            polling_input = self.query_one("#polling-input", Input)
            polling_input.value = str(settings.polling_interval_ms)

            # Set notifications checkbox
            notify_checkbox = self.query_one("#notify-checkbox", Checkbox)
            notify_checkbox.value = settings.notification_enabled

            # Update auto mode status display
            self._update_auto_mode_status()

    def _update_auto_mode_status(self) -> None:
        """Update the auto mode status display."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]
        status_widget = self.query_one("#auto-mode-status", Static)

        if app.state.config:
            auto_mode = app.state.config.auto_mode
            if auto_mode.enabled:
                num_commands = len(auto_mode.stage_commands)
                status_widget.update(
                    f"[green]Enabled[/green] ({num_commands} stage commands)"
                )
            else:
                status_widget.update("[dim]Disabled[/dim]")
        else:
            status_widget.update("[dim]No config[/dim]")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel":
            self.app.pop_screen()
        elif event.button.id == "save":
            await self.action_save()
        elif event.button.id == "configure-auto-mode":
            await self._open_auto_mode_config()

    def _open_auto_mode_config(self) -> None:
        """Open the auto mode configuration modal."""
        from iterm_controller.screens.modals import AutoModeConfigModal

        app: ItermControllerApp = self.app  # type: ignore[assignment]

        if not app.state.config:
            self.notify("No configuration loaded", severity="error")
            return

        current_config = app.state.config.auto_mode
        self.app.push_screen(
            AutoModeConfigModal(current_config), self._on_auto_mode_config_result
        )

    def _on_auto_mode_config_result(self, result: "AutoModeConfig | None") -> None:
        """Handle auto mode configuration modal result.

        Args:
            result: The updated config, or None if cancelled.
        """
        if result is None:
            return

        app: ItermControllerApp = self.app  # type: ignore[assignment]

        if not app.state.config:
            return

        # Update the config with the new auto mode settings
        app.state.config.auto_mode = result

        # Save to disk immediately
        from iterm_controller.config import save_global_config

        save_global_config(app.state.config)
        self.notify("Auto mode settings saved")

        # Update the status display
        self._update_auto_mode_status()

    def _validate_polling_interval(self, value: str) -> int | None:
        """Validate polling interval input.

        Args:
            value: The string value from the input.

        Returns:
            The validated integer value, or None if invalid.
        """
        try:
            polling = int(value)
            if polling < 100:
                self.notify("Polling interval must be at least 100ms", severity="error")
                return None
            if polling > 10000:
                self.notify("Polling interval must be at most 10000ms", severity="error")
                return None
            return polling
        except ValueError:
            self.notify("Invalid polling interval - must be a number", severity="error")
            return None

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

        # Validate polling interval
        polling = self._validate_polling_interval(polling_str)
        if polling is None:
            return

        # Validate IDE selection
        if ide is None or ide == Select.BLANK:
            self.notify("Please select a default IDE", severity="error")
            return

        # Validate shell selection
        if shell is None or shell == Select.BLANK:
            self.notify("Please select a default shell", severity="error")
            return

        # Update settings in config
        app.state.config.settings.default_ide = str(ide)
        app.state.config.settings.default_shell = str(shell)
        app.state.config.settings.polling_interval_ms = polling
        app.state.config.settings.notification_enabled = notify

        # Note: auto_mode config is saved separately via the Configure button

        # Save to disk
        from iterm_controller.config import save_global_config

        save_global_config(app.state.config)

        self.notify("Settings saved successfully")
        self.app.pop_screen()
