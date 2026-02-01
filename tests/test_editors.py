"""Tests for editors.py module."""

import pytest

from iterm_controller.editors import EDITOR_COMMANDS, get_editor_command


class TestEditorCommands:
    """Tests for EDITOR_COMMANDS constant."""

    def test_vscode_mappings(self) -> None:
        """Test VS Code related mappings."""
        assert EDITOR_COMMANDS["vscode"] == "code"
        assert EDITOR_COMMANDS["code"] == "code"

    def test_cursor_mapping(self) -> None:
        """Test Cursor editor mapping."""
        assert EDITOR_COMMANDS["cursor"] == "cursor"

    def test_vim_mappings(self) -> None:
        """Test Vim family mappings."""
        assert EDITOR_COMMANDS["vim"] == "vim"
        assert EDITOR_COMMANDS["nvim"] == "nvim"
        assert EDITOR_COMMANDS["neovim"] == "nvim"

    def test_sublime_mappings(self) -> None:
        """Test Sublime Text mappings."""
        assert EDITOR_COMMANDS["subl"] == "subl"
        assert EDITOR_COMMANDS["sublime"] == "subl"

    def test_other_editor_mappings(self) -> None:
        """Test other editor mappings."""
        assert EDITOR_COMMANDS["atom"] == "atom"
        assert EDITOR_COMMANDS["nano"] == "nano"
        assert EDITOR_COMMANDS["emacs"] == "emacs"

    def test_all_values_are_strings(self) -> None:
        """Ensure all values in the mapping are strings."""
        for key, value in EDITOR_COMMANDS.items():
            assert isinstance(key, str), f"Key {key!r} is not a string"
            assert isinstance(value, str), f"Value for {key} is not a string"

    def test_all_keys_are_lowercase(self) -> None:
        """Ensure all keys are lowercase for consistent lookup."""
        for key in EDITOR_COMMANDS:
            assert key == key.lower(), f"Key {key!r} is not lowercase"


class TestGetEditorCommand:
    """Tests for get_editor_command function."""

    def test_known_editor(self) -> None:
        """Test looking up a known editor."""
        assert get_editor_command("vscode") == "code"
        assert get_editor_command("neovim") == "nvim"

    def test_case_insensitive(self) -> None:
        """Test that lookup is case-insensitive."""
        assert get_editor_command("VSCODE") == "code"
        assert get_editor_command("VsCode") == "code"
        assert get_editor_command("NEOVIM") == "nvim"

    def test_unknown_editor_returns_none(self) -> None:
        """Test that unknown editors return None."""
        assert get_editor_command("unknown") is None
        assert get_editor_command("nonexistent") is None
        assert get_editor_command("") is None

    def test_direct_command_name(self) -> None:
        """Test looking up direct command names."""
        # Commands that map to themselves
        assert get_editor_command("vim") == "vim"
        assert get_editor_command("nano") == "nano"
        assert get_editor_command("emacs") == "emacs"
