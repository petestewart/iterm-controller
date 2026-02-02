"""Tests for artifact preview modal."""

from pathlib import Path

import pytest

from iterm_controller.screens.modals import ArtifactPreviewModal, ArtifactPreviewResult


class TestArtifactPreviewModalInit:
    """Test ArtifactPreviewModal initialization."""

    def test_create_modal(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)
        assert modal is not None

    def test_modal_is_modal_screen(self, tmp_path: Path) -> None:
        from textual.screen import ModalScreen

        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)
        assert isinstance(modal, ModalScreen)

    def test_modal_stores_artifact_name(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "PRD.md"
        artifact_path.write_text("# PRD")

        modal = ArtifactPreviewModal("PRD.md", artifact_path)
        assert modal.artifact_name == "PRD.md"

    def test_modal_stores_artifact_path(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "PRD.md"
        artifact_path.write_text("# PRD")

        modal = ArtifactPreviewModal("PRD.md", artifact_path)
        assert modal.artifact_path == artifact_path


class TestArtifactPreviewModalLoadContent:
    """Test ArtifactPreviewModal _load_content method."""

    def test_load_content_reads_file(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test Content\n\nSome text here.")

        modal = ArtifactPreviewModal("test.md", artifact_path)
        modal._load_content()

        assert modal._content == "# Test Content\n\nSome text here."

    def test_load_content_handles_missing_file(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "nonexistent.md"

        modal = ArtifactPreviewModal("nonexistent.md", artifact_path)
        modal._load_content()

        assert modal._content == ""

    def test_load_content_handles_empty_file(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "empty.md"
        artifact_path.write_text("")

        modal = ArtifactPreviewModal("empty.md", artifact_path)
        modal._load_content()

        assert modal._content == ""

    def test_load_content_handles_unicode(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "unicode.md"
        artifact_path.write_text("# Unicode: \u2713 \u2717 \u2022")

        modal = ArtifactPreviewModal("unicode.md", artifact_path)
        modal._load_content()

        assert "\u2713" in modal._content
        assert "\u2717" in modal._content


class TestArtifactPreviewModalActions:
    """Test ArtifactPreviewModal action methods."""

    def test_action_edit_dismisses_with_edit(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_edit()

        assert dismissed_with == ["edit"]

    def test_action_agent_dismisses_with_agent(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_agent()

        assert dismissed_with == ["agent"]

    def test_action_close_dismisses_with_close(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_close()

        assert dismissed_with == ["close"]


class TestArtifactPreviewModalBindings:
    """Test ArtifactPreviewModal keyboard bindings."""

    def test_bindings_exist(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)

        binding_keys = [b.key for b in modal.BINDINGS]

        assert "e" in binding_keys
        assert "a" in binding_keys
        assert "escape" in binding_keys
        assert "q" in binding_keys

    def test_e_binding_action(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)

        bindings = {b.key: b.action for b in modal.BINDINGS}

        assert bindings["e"] == "edit"

    def test_a_binding_action(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)

        bindings = {b.key: b.action for b in modal.BINDINGS}

        assert bindings["a"] == "agent"

    def test_escape_binding_action(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)

        bindings = {b.key: b.action for b in modal.BINDINGS}

        assert bindings["escape"] == "close"

    def test_q_binding_action(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)

        bindings = {b.key: b.action for b in modal.BINDINGS}

        assert bindings["q"] == "close"


class TestArtifactPreviewModalCompose:
    """Test ArtifactPreviewModal composition.

    Note: compose() requires an active app context which is complex to set up
    in unit tests. We test that the modal can be instantiated and has the
    expected structure via integration tests instead.
    """

    def test_modal_has_compose_method(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)

        # Just verify the method exists and is callable
        assert hasattr(modal, "compose")
        assert callable(modal.compose)


class TestArtifactPreviewModalCSS:
    """Test ArtifactPreviewModal CSS styling."""

    def test_has_default_css(self) -> None:
        assert hasattr(ArtifactPreviewModal, "DEFAULT_CSS")
        assert ArtifactPreviewModal.DEFAULT_CSS is not None
        assert len(ArtifactPreviewModal.DEFAULT_CSS) > 0

    def test_css_contains_modal_styles(self) -> None:
        css = ArtifactPreviewModal.DEFAULT_CSS
        assert "ArtifactPreviewModal" in css
        assert "align" in css
        assert "center" in css


class TestArtifactPreviewModalReturnType:
    """Test that ArtifactPreviewModal returns correct types."""

    def test_edit_action_returns_edit_string(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_edit()

        result = dismissed_with[0]
        assert result == "edit"
        # Type check: result should be compatible with ArtifactPreviewResult
        assert result in ("edit", "agent", "close")

    def test_agent_action_returns_agent_string(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_agent()

        result = dismissed_with[0]
        assert result == "agent"
        # Type check: result should be compatible with ArtifactPreviewResult
        assert result in ("edit", "agent", "close")

    def test_close_action_returns_close_string(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_close()

        result = dismissed_with[0]
        assert result == "close"
        assert result in ("edit", "agent", "close")


class TestArtifactPreviewModalButtonPressed:
    """Test ArtifactPreviewModal on_button_pressed handler."""

    def test_edit_button_triggers_edit_action(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        # Mock button press event
        event = MagicMock()
        event.button.id = "edit"

        modal.on_button_pressed(event)

        assert dismissed_with == ["edit"]

    def test_agent_button_triggers_agent_action(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        # Mock button press event
        event = MagicMock()
        event.button.id = "agent"

        modal.on_button_pressed(event)

        assert dismissed_with == ["agent"]

    def test_close_button_triggers_close_action(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        # Mock button press event
        event = MagicMock()
        event.button.id = "close"

        modal.on_button_pressed(event)

        assert dismissed_with == ["close"]

    def test_unknown_button_does_nothing(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        artifact_path = tmp_path / "test.md"
        artifact_path.write_text("# Test")

        modal = ArtifactPreviewModal("test.md", artifact_path)

        dismissed_with: list = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        # Mock button press event with unknown id
        event = MagicMock()
        event.button.id = "unknown"

        modal.on_button_pressed(event)

        assert dismissed_with == []
