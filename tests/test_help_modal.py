"""Tests for HelpModal."""

import pytest

from iterm_controller.screens.modals.help_modal import HelpModal


class TestHelpModalShortcuts:
    """Tests for HelpModal shortcuts dictionary."""

    def test_help_modal_has_global_shortcuts(self) -> None:
        """Test that help modal has Global shortcuts section."""
        assert "Global" in HelpModal.SHORTCUTS
        global_shortcuts = HelpModal.SHORTCUTS["Global"]
        keys = [s[0] for s in global_shortcuts]
        assert "?" in keys
        assert "q" in keys
        assert "p" in keys

    def test_help_modal_has_workflow_modes_section(self) -> None:
        """Test that help modal has Workflow Modes section."""
        assert "Workflow Modes" in HelpModal.SHORTCUTS
        mode_shortcuts = HelpModal.SHORTCUTS["Workflow Modes"]
        keys = [s[0] for s in mode_shortcuts]
        # Should have 1-4 keys for mode switching
        assert "1" in keys
        assert "2" in keys
        assert "3" in keys
        assert "4" in keys
        assert "escape" in keys

    def test_help_modal_workflow_modes_has_descriptions(self) -> None:
        """Test that Workflow Modes shortcuts have proper descriptions."""
        mode_shortcuts = HelpModal.SHORTCUTS["Workflow Modes"]
        descriptions = {s[0]: s[1] for s in mode_shortcuts}

        assert "Plan" in descriptions["1"]
        assert "Docs" in descriptions["2"]
        assert "Work" in descriptions["3"]
        assert "Test" in descriptions["4"]
        assert "dashboard" in descriptions["escape"].lower()

    def test_help_modal_has_plan_mode_section(self) -> None:
        """Test that help modal has Plan Mode section."""
        assert "Plan Mode" in HelpModal.SHORTCUTS
        plan_shortcuts = HelpModal.SHORTCUTS["Plan Mode"]
        keys = [s[0] for s in plan_shortcuts]
        # Key bindings from plan_mode.py
        assert any("j" in k or "↑" in k for k in keys)  # Navigation
        assert "enter" in keys
        assert "e" in keys  # Edit
        assert "c" in keys  # Create
        assert "s" in keys  # Spawn
        assert "r" in keys  # Refresh

    def test_help_modal_has_docs_mode_section(self) -> None:
        """Test that help modal has Docs Mode section."""
        assert "Docs Mode" in HelpModal.SHORTCUTS
        docs_shortcuts = HelpModal.SHORTCUTS["Docs Mode"]
        keys = [s[0] for s in docs_shortcuts]
        assert any("j" in k for k in keys)  # Navigation
        assert any("h" in k or "←" in k for k in keys)  # Collapse
        assert "enter" in keys
        assert "e" in keys  # Edit
        assert "a" in keys  # Add
        assert "d" in keys  # Delete
        assert "r" in keys  # Rename
        assert "p" in keys  # Preview

    def test_help_modal_has_work_mode_section(self) -> None:
        """Test that help modal has Work Mode section."""
        assert "Work Mode" in HelpModal.SHORTCUTS
        work_shortcuts = HelpModal.SHORTCUTS["Work Mode"]
        keys = [s[0] for s in work_shortcuts]
        assert any("j" in k for k in keys)  # Navigation
        assert "tab" in keys  # Switch panels
        assert "c" in keys  # Claim
        assert "u" in keys  # Unclaim
        assert "d" in keys  # Done
        assert "s" in keys  # Spawn

    def test_help_modal_has_test_mode_section(self) -> None:
        """Test that help modal has Test Mode section."""
        assert "Test Mode" in HelpModal.SHORTCUTS
        test_shortcuts = HelpModal.SHORTCUTS["Test Mode"]
        keys = [s[0] for s in test_shortcuts]
        assert any("j" in k for k in keys)  # Navigation
        assert "tab" in keys  # Switch panels
        assert "enter" in keys  # Toggle step
        assert "g" in keys  # Generate
        assert "s" in keys  # Spawn QA
        assert "r" in keys  # Run tests

    def test_help_modal_project_dashboard_has_mode_shortcuts(self) -> None:
        """Test that Project Dashboard section includes mode navigation keys."""
        assert "Project Dashboard" in HelpModal.SHORTCUTS
        dashboard_shortcuts = HelpModal.SHORTCUTS["Project Dashboard"]
        keys = [s[0] for s in dashboard_shortcuts]
        # Should have 1-4 keys for entering modes
        assert "1" in keys
        assert "2" in keys
        assert "3" in keys
        assert "4" in keys


class TestHelpModalBuildSections:
    """Tests for HelpModal _build_sections method."""

    def test_build_sections_creates_widgets_for_all_sections(self) -> None:
        """Test that _build_sections creates widgets for all shortcut sections."""
        modal = HelpModal()
        widgets = modal._build_sections()

        # Should have widgets for each section (title + shortcuts)
        assert len(widgets) > 0

        # Find section titles
        section_titles_found = []
        for widget in widgets:
            if hasattr(widget, "renderable"):
                text = str(widget.renderable)
                for section_name in HelpModal.SHORTCUTS.keys():
                    if section_name in text:
                        section_titles_found.append(section_name)

        # All sections should be represented
        for section_name in HelpModal.SHORTCUTS.keys():
            assert section_name in section_titles_found

    def test_build_sections_includes_workflow_modes(self) -> None:
        """Test that _build_sections includes Workflow Modes section."""
        modal = HelpModal()
        widgets = modal._build_sections()

        # Check that at least one widget mentions "Workflow Modes"
        found_workflow_modes = False
        for widget in widgets:
            if hasattr(widget, "renderable"):
                text = str(widget.renderable)
                if "Workflow Modes" in text:
                    found_workflow_modes = True
                    break

        assert found_workflow_modes
