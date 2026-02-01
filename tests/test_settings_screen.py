"""Tests for the Settings screen."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from iterm_controller.app import ItermControllerApp
from iterm_controller.models import AppConfig, AppSettings, AutoModeConfig
from iterm_controller.screens.control_room import ControlRoomScreen
from iterm_controller.screens.settings import SettingsScreen

from textual.widgets import Button, Checkbox, Input, Select


class TestSettingsScreen:
    """Tests for SettingsScreen."""

    def test_screen_has_bindings(self) -> None:
        """Test that screen has required keybindings."""
        screen = SettingsScreen()
        binding_keys = [b.key for b in screen.BINDINGS]

        assert "escape" in binding_keys  # Back
        assert "ctrl+s" in binding_keys  # Save

    def test_ide_options_defined(self) -> None:
        """Test that IDE options are defined correctly."""
        screen = SettingsScreen()
        assert len(screen.IDE_OPTIONS) > 0

        # Check format is (display, value)
        for display, value in screen.IDE_OPTIONS:
            assert isinstance(display, str)
            assert isinstance(value, str)
            assert len(display) > 0
            assert len(value) > 0

    def test_shell_options_defined(self) -> None:
        """Test that shell options are defined correctly."""
        screen = SettingsScreen()
        assert len(screen.SHELL_OPTIONS) > 0

        # Check format is (display, value)
        for display, value in screen.SHELL_OPTIONS:
            assert isinstance(display, str)
            assert isinstance(value, str)
            assert len(display) > 0
            assert len(value) > 0


@pytest.mark.asyncio
class TestSettingsScreenAsync:
    """Async tests for SettingsScreen."""

    async def test_screen_composes_widgets(self) -> None:
        """Test that screen composes required widgets."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            # Navigate to settings
            await pilot.press("comma")

            # Should be on SettingsScreen
            assert isinstance(app.screen, SettingsScreen)

            # Check for form elements
            ide_select = app.screen.query_one("#ide-select", Select)
            assert ide_select is not None

            shell_select = app.screen.query_one("#shell-select", Select)
            assert shell_select is not None

            polling_input = app.screen.query_one("#polling-input", Input)
            assert polling_input is not None

            notify_checkbox = app.screen.query_one("#notify-checkbox", Checkbox)
            assert notify_checkbox is not None

            # Auto mode is now configured via a separate button and modal
            auto_mode_button = app.screen.query_one("#configure-auto-mode", Button)
            assert auto_mode_button is not None

            save_button = app.screen.query_one("#save", Button)
            assert save_button is not None

            cancel_button = app.screen.query_one("#cancel", Button)
            assert cancel_button is not None

    async def test_loads_settings_on_mount(self) -> None:
        """Test that settings are loaded from config on mount."""
        # Create test config
        test_config = AppConfig(
            settings=AppSettings(
                default_ide="cursor",
                default_shell="fish",
                polling_interval_ms=750,
                notification_enabled=False,
            ),
            auto_mode=AutoModeConfig(
                auto_advance=True,
            ),
        )

        # Mock load_global_config to return our test config
        with patch(
            "iterm_controller.config.load_global_config",
            return_value=test_config,
        ):
            app = ItermControllerApp()
            async with app.run_test() as pilot:
                # Navigate to settings
                await pilot.press("comma")

                assert isinstance(app.screen, SettingsScreen)

                # Check values are loaded
                ide_select = app.screen.query_one("#ide-select", Select)
                assert ide_select.value == "cursor"

                shell_select = app.screen.query_one("#shell-select", Select)
                assert shell_select.value == "fish"

                polling_input = app.screen.query_one("#polling-input", Input)
                assert polling_input.value == "750"

                notify_checkbox = app.screen.query_one("#notify-checkbox", Checkbox)
                assert notify_checkbox.value is False

                # Auto mode settings are now shown via status display
                # The _update_auto_mode_status method updates the display

    async def test_escape_pops_screen(self) -> None:
        """Test that escape key returns to previous screen."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            # Navigate to settings
            await pilot.press("comma")
            assert isinstance(app.screen, SettingsScreen)

            # Press escape
            await pilot.press("escape")

            # Should be back on Control Room
            assert isinstance(app.screen, ControlRoomScreen)

    async def test_save_updates_config(self) -> None:
        """Test that save updates the config in memory."""
        test_config = AppConfig(
            settings=AppSettings(
                default_ide="vscode",
                default_shell="zsh",
                polling_interval_ms=500,
                notification_enabled=True,
            ),
            auto_mode=AutoModeConfig(auto_advance=False),
        )

        # Mock both load_global_config and save_global_config
        with patch(
            "iterm_controller.config.load_global_config",
            return_value=test_config,
        ):
            with patch("iterm_controller.config.save_global_config") as mock_save:
                app = ItermControllerApp()
                async with app.run_test() as pilot:
                    # Navigate to settings
                    await pilot.press("comma")
                    assert isinstance(app.screen, SettingsScreen)

                    # Modify polling interval
                    polling_input = app.screen.query_one("#polling-input", Input)
                    polling_input.value = "1000"

                    # Toggle notification checkbox
                    notify_checkbox = app.screen.query_one("#notify-checkbox", Checkbox)
                    notify_checkbox.value = False

                    # Note: auto_mode is now configured via the separate modal,
                    # so we don't test it here

                    # Use keyboard shortcut to save (Ctrl+S)
                    await pilot.press("ctrl+s")

                    # Check config was updated
                    assert app.state.config.settings.polling_interval_ms == 1000
                    assert app.state.config.settings.notification_enabled is False

                    # Check save was called
                    mock_save.assert_called_once()

    async def test_save_persists_to_disk(self) -> None:
        """Test that save persists settings to the config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"

            test_config = AppConfig(
                settings=AppSettings(
                    default_ide="vscode",
                    default_shell="zsh",
                    polling_interval_ms=500,
                    notification_enabled=True,
                ),
                auto_mode=AutoModeConfig(auto_advance=False),
            )

            with patch(
                "iterm_controller.config.load_global_config",
                return_value=test_config,
            ):
                with patch(
                    "iterm_controller.config.GLOBAL_CONFIG_PATH", config_path
                ):
                    app = ItermControllerApp()
                    async with app.run_test() as pilot:
                        # Navigate to settings
                        await pilot.press("comma")

                        # Modify a setting
                        polling_input = app.screen.query_one("#polling-input", Input)
                        polling_input.value = "800"

                        # Use keyboard shortcut to save
                        await pilot.press("ctrl+s")

                        # Verify file was created
                        assert config_path.exists()

                        # Verify content
                        import json
                        with open(config_path) as f:
                            saved_config = json.load(f)

                        assert saved_config["settings"]["polling_interval_ms"] == 800


class TestSettingsScreenValidation:
    """Tests for settings validation."""

    def test_validate_polling_interval_valid(self) -> None:
        """Test valid polling interval passes validation."""
        screen = SettingsScreen()
        result = screen._validate_polling_interval("500")
        assert result == 500

    def test_validate_polling_interval_invalid_not_number(self) -> None:
        """Test invalid polling interval is rejected."""
        screen = SettingsScreen()
        # Need to patch notify since we're not in a running app
        with patch.object(screen, "notify"):
            result = screen._validate_polling_interval("not-a-number")
        assert result is None

    def test_validate_polling_interval_below_minimum(self) -> None:
        """Test polling interval below minimum is rejected."""
        screen = SettingsScreen()
        with patch.object(screen, "notify"):
            result = screen._validate_polling_interval("50")
        assert result is None

    def test_validate_polling_interval_above_maximum(self) -> None:
        """Test polling interval above maximum is rejected."""
        screen = SettingsScreen()
        with patch.object(screen, "notify"):
            result = screen._validate_polling_interval("20000")
        assert result is None

    def test_validate_polling_interval_at_minimum(self) -> None:
        """Test polling interval at minimum is accepted."""
        screen = SettingsScreen()
        result = screen._validate_polling_interval("100")
        assert result == 100

    def test_validate_polling_interval_at_maximum(self) -> None:
        """Test polling interval at maximum is accepted."""
        screen = SettingsScreen()
        result = screen._validate_polling_interval("10000")
        assert result == 10000
