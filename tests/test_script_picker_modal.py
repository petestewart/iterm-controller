"""Tests for script picker modal."""

import pytest

from iterm_controller.models import SessionTemplate
from iterm_controller.screens.modals import ScriptPickerModal


class TestScriptPickerModalInit:
    """Test ScriptPickerModal initialization."""

    def test_create_modal(self):
        modal = ScriptPickerModal()
        assert modal is not None

    def test_modal_is_modal_screen(self):
        from textual.screen import ModalScreen

        modal = ScriptPickerModal()
        assert isinstance(modal, ModalScreen)

    def test_modal_has_empty_templates_initially(self):
        modal = ScriptPickerModal()
        assert modal._templates == []


class TestScriptPickerModalActions:
    """Test ScriptPickerModal action methods."""

    def test_action_cancel_returns_none(self):
        modal = ScriptPickerModal()

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_cancel()

        assert dismissed_with == [None]

    def test_action_select_1_returns_first_template(self):
        modal = ScriptPickerModal()
        template = SessionTemplate(id="test", name="Test", command="echo test")
        modal._templates = [template]

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_select_1()

        assert dismissed_with == [template]

    def test_action_select_1_with_no_templates_does_nothing(self):
        modal = ScriptPickerModal()
        modal._templates = []

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_select_1()

        # Should not dismiss with empty templates
        assert dismissed_with == []

    def test_action_select_2_returns_second_template(self):
        modal = ScriptPickerModal()
        template1 = SessionTemplate(id="test1", name="Test 1", command="echo 1")
        template2 = SessionTemplate(id="test2", name="Test 2", command="echo 2")
        modal._templates = [template1, template2]

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_select_2()

        assert dismissed_with == [template2]

    def test_action_select_out_of_range_does_nothing(self):
        modal = ScriptPickerModal()
        template = SessionTemplate(id="test", name="Test", command="echo test")
        modal._templates = [template]

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        # Try to select index 5 when only 1 template exists
        modal.action_select_5()

        assert dismissed_with == []


class TestScriptPickerModalSelectTemplate:
    """Test ScriptPickerModal _select_template method."""

    def test_select_template_valid_index(self):
        modal = ScriptPickerModal()
        template = SessionTemplate(id="test", name="Test", command="echo test")
        modal._templates = [template]

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal._select_template(0)

        assert dismissed_with == [template]

    def test_select_template_invalid_index(self):
        modal = ScriptPickerModal()
        modal._templates = []

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal._select_template(0)

        assert dismissed_with == []

    def test_select_template_negative_index(self):
        modal = ScriptPickerModal()
        template = SessionTemplate(id="test", name="Test", command="echo test")
        modal._templates = [template]

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal._select_template(-1)

        assert dismissed_with == []


class TestScriptPickerModalBindings:
    """Test ScriptPickerModal keyboard bindings."""

    def test_bindings_exist(self):
        modal = ScriptPickerModal()

        binding_keys = [b.key for b in modal.BINDINGS]

        # Should have bindings for 1-9 and escape
        assert "1" in binding_keys
        assert "2" in binding_keys
        assert "9" in binding_keys
        assert "escape" in binding_keys

    def test_escape_binding_action(self):
        modal = ScriptPickerModal()

        bindings = {b.key: b.action for b in modal.BINDINGS}

        assert bindings["escape"] == "cancel"

    def test_number_binding_actions(self):
        modal = ScriptPickerModal()

        bindings = {b.key: b.action for b in modal.BINDINGS}

        assert bindings["1"] == "select_1"
        assert bindings["2"] == "select_2"
        assert bindings["9"] == "select_9"


class TestScriptPickerModalCompose:
    """Test ScriptPickerModal composition."""

    def test_compose_returns_widgets(self):
        modal = ScriptPickerModal()

        # compose returns a generator of widgets
        widgets = list(modal.compose())

        # Should have at least one container with content
        assert len(widgets) > 0

    def test_compose_has_container(self):
        from textual.containers import Container

        modal = ScriptPickerModal()
        widgets = list(modal.compose())

        # Should have a container
        containers = [w for w in widgets if isinstance(w, Container)]
        assert len(containers) >= 1


class TestScriptPickerModalCSS:
    """Test ScriptPickerModal CSS styling."""

    def test_has_default_css(self):
        assert hasattr(ScriptPickerModal, "DEFAULT_CSS")
        assert ScriptPickerModal.DEFAULT_CSS is not None
        assert len(ScriptPickerModal.DEFAULT_CSS) > 0

    def test_css_contains_modal_styles(self):
        css = ScriptPickerModal.DEFAULT_CSS
        assert "ScriptPickerModal" in css
        assert "align" in css
        assert "center" in css


class TestScriptPickerModalReturnType:
    """Test that ScriptPickerModal returns correct types."""

    def test_returns_session_template_on_selection(self):
        modal = ScriptPickerModal()
        template = SessionTemplate(id="test", name="Test", command="echo test")
        modal._templates = [template]

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_select_1()

        result = dismissed_with[0]
        assert isinstance(result, SessionTemplate)
        assert result.id == "test"
        assert result.name == "Test"
        assert result.command == "echo test"

    def test_returns_none_on_cancel(self):
        modal = ScriptPickerModal()

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_cancel()

        result = dismissed_with[0]
        assert result is None


class TestScriptPickerModalAllSelectionActions:
    """Test all selection action methods (1-9)."""

    def test_all_selection_actions_exist(self):
        modal = ScriptPickerModal()

        # All action methods should exist
        assert hasattr(modal, "action_select_1")
        assert hasattr(modal, "action_select_2")
        assert hasattr(modal, "action_select_3")
        assert hasattr(modal, "action_select_4")
        assert hasattr(modal, "action_select_5")
        assert hasattr(modal, "action_select_6")
        assert hasattr(modal, "action_select_7")
        assert hasattr(modal, "action_select_8")
        assert hasattr(modal, "action_select_9")

    def test_each_action_selects_correct_index(self):
        # Create templates
        templates = [
            SessionTemplate(id=f"t{i}", name=f"Template {i}", command=f"echo {i}")
            for i in range(1, 10)
        ]

        # Test each action
        for i in range(1, 10):
            modal = ScriptPickerModal()
            modal._templates = templates

            dismissed_with = []
            modal.dismiss = lambda result, dw=dismissed_with: dw.append(result)

            action_method = getattr(modal, f"action_select_{i}")
            action_method()

            assert len(dismissed_with) == 1
            assert dismissed_with[0].id == f"t{i}"
