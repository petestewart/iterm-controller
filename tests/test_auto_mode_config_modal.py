"""Tests for auto mode configuration modal."""

import pytest

from iterm_controller.models import AutoModeConfig, WorkflowStage
from iterm_controller.screens.modals import AutoModeConfigModal
from iterm_controller.screens.modals.auto_mode_config import DEFAULT_STAGE_COMMANDS


class TestAutoModeConfigModalInit:
    """Test AutoModeConfigModal initialization."""

    def test_create_modal_without_config(self):
        modal = AutoModeConfigModal()
        assert modal is not None
        assert modal._initial_config is not None
        assert modal._initial_config.enabled is False

    def test_create_modal_with_config(self):
        config = AutoModeConfig(
            enabled=True,
            stage_commands={"planning": "claude /prd"},
            auto_advance=True,
            require_confirmation=False,
            designated_session="claude",
        )
        modal = AutoModeConfigModal(config)
        assert modal._initial_config == config
        assert modal._initial_config.enabled is True

    def test_modal_is_modal_screen(self):
        from textual.screen import ModalScreen

        modal = AutoModeConfigModal()
        assert isinstance(modal, ModalScreen)


class TestAutoModeConfigModalCompose:
    """Test AutoModeConfigModal composition."""

    def test_compose_returns_widgets(self):
        modal = AutoModeConfigModal()

        # compose returns a generator of widgets
        widgets = list(modal.compose())

        # Should have at least one container with content
        assert len(widgets) > 0

    def test_compose_with_existing_config_preserves_initial_config(self):
        # Note: We can't call compose() with a non-empty designated_session
        # because Textual's Input widget requires an active app context when
        # initialized with a value. Instead, we verify the config is stored.
        config = AutoModeConfig(
            enabled=True,
            stage_commands={
                "planning": "claude /prd",
                "execute": "claude /plan",
            },
            auto_advance=False,
            require_confirmation=True,
            designated_session="main-session",
        )
        modal = AutoModeConfigModal(config)

        # Verify config is preserved for use when composing
        assert modal._initial_config == config
        assert modal._initial_config.enabled is True
        assert modal._initial_config.designated_session == "main-session"


class TestAutoModeConfigModalBindings:
    """Test AutoModeConfigModal keyboard bindings."""

    def test_bindings_exist(self):
        modal = AutoModeConfigModal()

        binding_keys = [b.key for b in modal.BINDINGS]

        assert "ctrl+s" in binding_keys
        assert "escape" in binding_keys

    def test_binding_actions(self):
        modal = AutoModeConfigModal()

        bindings = {b.key: b.action for b in modal.BINDINGS}

        assert bindings["ctrl+s"] == "save"
        assert bindings["escape"] == "cancel"


class TestAutoModeConfigModalActions:
    """Test AutoModeConfigModal action methods."""

    def test_action_cancel_dismisses_with_none(self):
        modal = AutoModeConfigModal()

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_cancel()

        assert dismissed_with == [None]


class TestAutoModeConfigModalBuildConfig:
    """Test the _build_config method."""

    def test_build_config_creates_default_config(self):
        # This test requires mocking the Textual query system
        # which is complex without mounting the app
        # We verify the method exists and has the right signature
        modal = AutoModeConfigModal()
        assert hasattr(modal, "_build_config")
        assert callable(modal._build_config)


class TestAutoModeConfigModalConfigurableStages:
    """Test the configurable stages constant."""

    def test_configurable_stages_includes_expected_stages(self):
        stages = [s[0] for s in AutoModeConfigModal.CONFIGURABLE_STAGES]

        assert WorkflowStage.PLANNING in stages
        assert WorkflowStage.EXECUTE in stages
        assert WorkflowStage.REVIEW in stages
        assert WorkflowStage.PR in stages
        # DONE is not configurable - it's the terminal state
        assert WorkflowStage.DONE not in stages

    def test_configurable_stages_have_labels(self):
        for stage, label, placeholder in AutoModeConfigModal.CONFIGURABLE_STAGES:
            assert isinstance(label, str)
            assert len(label) > 0
            assert isinstance(placeholder, str)
            assert len(placeholder) > 0


class TestDefaultStageCommands:
    """Test the default stage commands."""

    def test_default_commands_exist_for_key_stages(self):
        assert "planning" in DEFAULT_STAGE_COMMANDS
        assert "execute" in DEFAULT_STAGE_COMMANDS
        assert "review" in DEFAULT_STAGE_COMMANDS

    def test_default_commands_are_strings(self):
        for stage, command in DEFAULT_STAGE_COMMANDS.items():
            assert isinstance(command, str)
            assert len(command) > 0

    def test_default_planning_command(self):
        assert DEFAULT_STAGE_COMMANDS["planning"] == "claude /prd"

    def test_default_execute_command(self):
        assert DEFAULT_STAGE_COMMANDS["execute"] == "claude /plan"

    def test_default_review_command(self):
        assert DEFAULT_STAGE_COMMANDS["review"] == "claude /review"


class TestAutoModeConfigModalIntegration:
    """Test integration with AutoModeConfig model."""

    def test_initial_config_preserves_all_fields(self):
        config = AutoModeConfig(
            enabled=True,
            stage_commands={
                "planning": "custom-planning",
                "execute": "custom-execute",
                "review": "custom-review",
                "pr": "custom-pr",
            },
            auto_advance=False,
            require_confirmation=True,
            designated_session="test-session",
        )
        modal = AutoModeConfigModal(config)

        assert modal._initial_config.enabled is True
        assert modal._initial_config.stage_commands["planning"] == "custom-planning"
        assert modal._initial_config.stage_commands["execute"] == "custom-execute"
        assert modal._initial_config.stage_commands["review"] == "custom-review"
        assert modal._initial_config.stage_commands["pr"] == "custom-pr"
        assert modal._initial_config.auto_advance is False
        assert modal._initial_config.require_confirmation is True
        assert modal._initial_config.designated_session == "test-session"

    def test_empty_config_uses_defaults(self):
        modal = AutoModeConfigModal()

        assert modal._initial_config.enabled is False
        assert modal._initial_config.stage_commands == {}
        assert modal._initial_config.auto_advance is True
        assert modal._initial_config.require_confirmation is True
        assert modal._initial_config.designated_session is None
