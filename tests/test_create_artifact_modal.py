"""Tests for create artifact modal."""

from unittest.mock import MagicMock

import pytest

from iterm_controller.screens.modals import CreateArtifactModal, CreateArtifactResult


class TestCreateArtifactModalInit:
    """Test CreateArtifactModal initialization."""

    def test_create_modal_with_command(self) -> None:
        modal = CreateArtifactModal("PRD.md", "claude /prd")
        assert modal is not None

    def test_create_modal_without_command(self) -> None:
        modal = CreateArtifactModal("custom.md", None)
        assert modal is not None

    def test_modal_is_modal_screen(self) -> None:
        from textual.screen import ModalScreen

        modal = CreateArtifactModal("PRD.md", "claude /prd")
        assert isinstance(modal, ModalScreen)

    def test_modal_stores_artifact_name(self) -> None:
        modal = CreateArtifactModal("PROBLEM.md", "claude /problem-statement")
        assert modal._artifact_name == "PROBLEM.md"

    def test_modal_stores_agent_command(self) -> None:
        modal = CreateArtifactModal("PLAN.md", "claude /plan")
        assert modal._agent_command == "claude /plan"

    def test_modal_stores_none_command(self) -> None:
        modal = CreateArtifactModal("custom.md", None)
        assert modal._agent_command is None


class TestCreateArtifactModalActions:
    """Test CreateArtifactModal action methods."""

    def test_action_create_with_agent_when_command_exists(self) -> None:
        modal = CreateArtifactModal("PRD.md", "claude /prd")

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_create_with_agent()

        assert dismissed_with == ["agent"]

    def test_action_create_with_agent_does_nothing_without_command(self) -> None:
        modal = CreateArtifactModal("custom.md", None)

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_create_with_agent()

        assert dismissed_with == []

    def test_action_create_manually(self) -> None:
        modal = CreateArtifactModal("PRD.md", "claude /prd")

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_create_manually()

        assert dismissed_with == ["manual"]

    def test_action_cancel(self) -> None:
        modal = CreateArtifactModal("PRD.md", "claude /prd")

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_cancel()

        assert dismissed_with == ["cancel"]


class TestCreateArtifactModalBindings:
    """Test CreateArtifactModal keyboard bindings."""

    def test_bindings_exist(self) -> None:
        modal = CreateArtifactModal("PRD.md", "claude /prd")

        binding_keys = [b.key for b in modal.BINDINGS]

        assert "a" in binding_keys
        assert "m" in binding_keys
        assert "escape" in binding_keys

    def test_a_binding_action(self) -> None:
        modal = CreateArtifactModal("PRD.md", "claude /prd")

        bindings = {b.key: b.action for b in modal.BINDINGS}

        assert bindings["a"] == "create_with_agent"

    def test_m_binding_action(self) -> None:
        modal = CreateArtifactModal("PRD.md", "claude /prd")

        bindings = {b.key: b.action for b in modal.BINDINGS}

        assert bindings["m"] == "create_manually"

    def test_escape_binding_action(self) -> None:
        modal = CreateArtifactModal("PRD.md", "claude /prd")

        bindings = {b.key: b.action for b in modal.BINDINGS}

        assert bindings["escape"] == "cancel"


class TestCreateArtifactModalButtonPressed:
    """Test CreateArtifactModal on_button_pressed handler."""

    def test_agent_button_triggers_agent(self) -> None:
        modal = CreateArtifactModal("PRD.md", "claude /prd")

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        event = MagicMock()
        event.button.id = "agent"

        modal.on_button_pressed(event)

        assert dismissed_with == ["agent"]

    def test_manual_button_triggers_manual(self) -> None:
        modal = CreateArtifactModal("PRD.md", "claude /prd")

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        event = MagicMock()
        event.button.id = "manual"

        modal.on_button_pressed(event)

        assert dismissed_with == ["manual"]

    def test_cancel_button_triggers_cancel(self) -> None:
        modal = CreateArtifactModal("PRD.md", "claude /prd")

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        event = MagicMock()
        event.button.id = "cancel"

        modal.on_button_pressed(event)

        assert dismissed_with == ["cancel"]

    def test_unknown_button_does_nothing(self) -> None:
        modal = CreateArtifactModal("PRD.md", "claude /prd")

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        event = MagicMock()
        event.button.id = "unknown"

        modal.on_button_pressed(event)

        assert dismissed_with == []


class TestCreateArtifactModalCompose:
    """Test CreateArtifactModal composition."""

    def test_modal_has_compose_method(self) -> None:
        modal = CreateArtifactModal("PRD.md", "claude /prd")

        # Just verify the method exists and is callable
        assert hasattr(modal, "compose")
        assert callable(modal.compose)


class TestCreateArtifactModalCSS:
    """Test CreateArtifactModal CSS styling."""

    def test_has_default_css(self) -> None:
        assert hasattr(CreateArtifactModal, "DEFAULT_CSS")
        assert CreateArtifactModal.DEFAULT_CSS is not None
        assert len(CreateArtifactModal.DEFAULT_CSS) > 0

    def test_css_contains_modal_styles(self) -> None:
        css = CreateArtifactModal.DEFAULT_CSS
        assert "CreateArtifactModal" in css
        assert "align" in css
        assert "center" in css


class TestCreateArtifactModalReturnTypes:
    """Test that CreateArtifactModal returns correct types."""

    def test_agent_action_returns_agent_string(self) -> None:
        modal = CreateArtifactModal("PRD.md", "claude /prd")

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_create_with_agent()

        result = dismissed_with[0]
        assert result == "agent"
        assert result in ("agent", "manual", "cancel")

    def test_manual_action_returns_manual_string(self) -> None:
        modal = CreateArtifactModal("PRD.md", "claude /prd")

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_create_manually()

        result = dismissed_with[0]
        assert result == "manual"
        assert result in ("agent", "manual", "cancel")

    def test_cancel_action_returns_cancel_string(self) -> None:
        modal = CreateArtifactModal("PRD.md", "claude /prd")

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_cancel()

        result = dismissed_with[0]
        assert result == "cancel"
        assert result in ("agent", "manual", "cancel")


class TestCreateArtifactModalAllArtifacts:
    """Test CreateArtifactModal with different artifact types."""

    @pytest.mark.parametrize(
        "artifact_name,command",
        [
            ("PROBLEM.md", "claude /problem-statement"),
            ("PRD.md", "claude /prd"),
            ("specs/", "claude /specs"),
            ("PLAN.md", "claude /plan"),
        ],
    )
    def test_can_create_modal_for_standard_artifacts(
        self, artifact_name: str, command: str
    ) -> None:
        modal = CreateArtifactModal(artifact_name, command)
        assert modal._artifact_name == artifact_name
        assert modal._agent_command == command

    def test_can_create_modal_for_custom_artifact_without_command(self) -> None:
        modal = CreateArtifactModal("custom-spec.md", None)
        assert modal._artifact_name == "custom-spec.md"
        assert modal._agent_command is None
