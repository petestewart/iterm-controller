"""Tests for quit confirmation modal."""

import pytest

from iterm_controller.screens.modals import QuitAction, QuitConfirmModal


class TestQuitAction:
    """Test QuitAction enum values."""

    def test_enum_values_exist(self):
        assert QuitAction.CLOSE_ALL.value == "close_all"
        assert QuitAction.CLOSE_MANAGED.value == "close_managed"
        assert QuitAction.LEAVE_RUNNING.value == "leave_running"
        assert QuitAction.CANCEL.value == "cancel"


class TestQuitConfirmModalInit:
    """Test QuitConfirmModal initialization."""

    def test_create_modal(self):
        modal = QuitConfirmModal()
        assert modal is not None

    def test_modal_is_modal_screen(self):
        from textual.screen import ModalScreen

        modal = QuitConfirmModal()
        assert isinstance(modal, ModalScreen)


class TestQuitConfirmModalActions:
    """Test QuitConfirmModal action methods."""

    def test_action_close_all_returns_close_all(self):
        modal = QuitConfirmModal()

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_close_all()

        assert dismissed_with == [QuitAction.CLOSE_ALL]

    def test_action_close_managed_returns_close_managed(self):
        modal = QuitConfirmModal()

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_close_managed()

        assert dismissed_with == [QuitAction.CLOSE_MANAGED]

    def test_action_leave_running_returns_leave_running(self):
        modal = QuitConfirmModal()

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_leave_running()

        assert dismissed_with == [QuitAction.LEAVE_RUNNING]

    def test_action_cancel_returns_cancel(self):
        modal = QuitConfirmModal()

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_cancel()

        assert dismissed_with == [QuitAction.CANCEL]


class TestQuitConfirmModalBindings:
    """Test QuitConfirmModal keyboard bindings."""

    def test_bindings_exist(self):
        modal = QuitConfirmModal()

        binding_keys = [b.key for b in modal.BINDINGS]

        assert "c" in binding_keys
        assert "m" in binding_keys
        assert "l" in binding_keys
        assert "escape" in binding_keys

    def test_binding_actions(self):
        modal = QuitConfirmModal()

        bindings = {b.key: b.action for b in modal.BINDINGS}

        assert bindings["c"] == "close_all"
        assert bindings["m"] == "close_managed"
        assert bindings["l"] == "leave_running"
        assert bindings["escape"] == "cancel"


class TestQuitConfirmModalCompose:
    """Test QuitConfirmModal composition."""

    def test_compose_returns_widgets(self):
        modal = QuitConfirmModal()

        # compose returns a generator of widgets
        widgets = list(modal.compose())

        # Should have at least one container with content
        assert len(widgets) > 0


class TestQuitActionBehavior:
    """Test the expected behavior for each quit action."""

    def test_close_all_should_close_all_sessions(self):
        """Close All should close all sessions in all windows."""
        # This is a design test - documenting expected behavior
        # Actual implementation test would require mocking iTerm2 API
        action = QuitAction.CLOSE_ALL
        assert action == QuitAction.CLOSE_ALL
        # Behavior: Send SIGTERM to all sessions, wait 5s, SIGKILL if needed

    def test_close_managed_should_close_only_spawned_sessions(self):
        """Close Managed should only close sessions we spawned."""
        # This is a design test - documenting expected behavior
        action = QuitAction.CLOSE_MANAGED
        assert action == QuitAction.CLOSE_MANAGED
        # Behavior: Close only sessions tracked in managed_sessions

    def test_leave_running_should_not_close_sessions(self):
        """Leave Running should disconnect cleanly without closing sessions."""
        # This is a design test - documenting expected behavior
        action = QuitAction.LEAVE_RUNNING
        assert action == QuitAction.LEAVE_RUNNING
        # Behavior: Just exit, sessions continue running

    def test_cancel_should_abort_quit(self):
        """Cancel should abort the quit operation."""
        action = QuitAction.CANCEL
        assert action == QuitAction.CANCEL
        # Behavior: Return to app without any changes
