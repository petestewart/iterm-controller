"""Tests for spec file validation."""

import tempfile
from pathlib import Path

import pytest

from iterm_controller.models import Task, TaskStatus
from iterm_controller.spec_validator import (
    SpecValidationResult,
    _find_anchor_in_markdown,
    _heading_to_anchor,
    validate_spec_ref,
    validate_task_spec_refs,
)


class TestHeadingToAnchor:
    """Test heading to anchor conversion."""

    def test_simple_heading(self):
        """Simple headings convert to lowercase with hyphens."""
        assert _heading_to_anchor("Hello World") == "hello-world"

    def test_single_word(self):
        """Single word headings lowercase."""
        assert _heading_to_anchor("Introduction") == "introduction"

    def test_punctuation_removal(self):
        """Punctuation is removed except hyphens and underscores."""
        assert _heading_to_anchor("What's New?") == "whats-new"
        assert _heading_to_anchor("Section: Overview") == "section-overview"

    def test_preserves_hyphens(self):
        """Existing hyphens are preserved."""
        assert _heading_to_anchor("Auto-Mode") == "auto-mode"

    def test_preserves_underscores(self):
        """Underscores are preserved."""
        assert _heading_to_anchor("session_monitor") == "session_monitor"

    def test_collapses_multiple_hyphens(self):
        """Multiple hyphens are collapsed to one."""
        assert _heading_to_anchor("Section -- Overview") == "section-overview"

    def test_strips_leading_trailing_hyphens(self):
        """Leading and trailing hyphens are stripped."""
        assert _heading_to_anchor(" Heading ") == "heading"
        assert _heading_to_anchor("- Heading -") == "heading"


class TestFindAnchorInMarkdown:
    """Test anchor finding in markdown content."""

    def test_finds_h1_heading(self):
        """Finds anchor in H1 heading."""
        content = "# Hello World\nSome content"
        assert _find_anchor_in_markdown(content, "hello-world") is True

    def test_finds_h2_heading(self):
        """Finds anchor in H2 heading."""
        content = "## Feature Overview\nDetails here"
        assert _find_anchor_in_markdown(content, "feature-overview") is True

    def test_finds_h3_heading(self):
        """Finds anchor in H3 heading."""
        content = "### Implementation Details\nCode follows"
        assert _find_anchor_in_markdown(content, "implementation-details") is True

    def test_case_insensitive(self):
        """Anchor matching is case insensitive."""
        content = "# HELLO WORLD\nContent"
        assert _find_anchor_in_markdown(content, "hello-world") is True

    def test_not_found(self):
        """Returns False when anchor not found."""
        content = "# Some Heading\nContent"
        assert _find_anchor_in_markdown(content, "other-heading") is False

    def test_multiple_headings(self):
        """Finds anchor among multiple headings."""
        content = """
# First Section
Some text
## Second Section
More text
### Third Section
Even more text
"""
        assert _find_anchor_in_markdown(content, "first-section") is True
        assert _find_anchor_in_markdown(content, "second-section") is True
        assert _find_anchor_in_markdown(content, "third-section") is True
        assert _find_anchor_in_markdown(content, "fourth-section") is False


class TestValidateSpecRef:
    """Test spec reference validation."""

    def test_existing_file_valid(self, tmp_path):
        """Valid when file exists."""
        spec_file = tmp_path / "specs" / "auth.md"
        spec_file.parent.mkdir(parents=True)
        spec_file.write_text("# Authentication\nDetails here")

        result = validate_spec_ref(str(tmp_path), "specs/auth.md")
        assert result.valid is True
        assert result.error_message is None

    def test_missing_file(self, tmp_path):
        """Invalid when file does not exist."""
        result = validate_spec_ref(str(tmp_path), "specs/missing.md")
        assert result.valid is False
        assert result.error_message == "File not found"
        assert result.is_file_missing is True

    def test_existing_anchor_valid(self, tmp_path):
        """Valid when file and anchor exist."""
        spec_file = tmp_path / "specs" / "auth.md"
        spec_file.parent.mkdir(parents=True)
        spec_file.write_text("# Authentication\n## Login Flow\nDetails")

        result = validate_spec_ref(str(tmp_path), "specs/auth.md#login-flow")
        assert result.valid is True
        assert result.error_message is None

    def test_missing_anchor(self, tmp_path):
        """Invalid when file exists but anchor does not."""
        spec_file = tmp_path / "specs" / "auth.md"
        spec_file.parent.mkdir(parents=True)
        spec_file.write_text("# Authentication\n## Login Flow\nDetails")

        result = validate_spec_ref(str(tmp_path), "specs/auth.md#logout-flow")
        assert result.valid is False
        assert result.error_message == "Section 'logout-flow' not found"
        assert result.is_section_missing is True

    def test_empty_spec_ref(self, tmp_path):
        """Empty spec ref is considered valid."""
        result = validate_spec_ref(str(tmp_path), "")
        assert result.valid is True

    def test_nested_path(self, tmp_path):
        """Works with nested directory paths."""
        spec_file = tmp_path / "docs" / "specs" / "api" / "auth.md"
        spec_file.parent.mkdir(parents=True)
        spec_file.write_text("# API Auth\nContent")

        result = validate_spec_ref(str(tmp_path), "docs/specs/api/auth.md")
        assert result.valid is True

    def test_anchor_with_punctuation(self, tmp_path):
        """Handles anchors with special characters."""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("# What's New?\nContent")

        result = validate_spec_ref(str(tmp_path), "spec.md#whats-new")
        assert result.valid is True

    def test_path_traversal_with_parent_refs(self, tmp_path):
        """Rejects spec refs that try to escape project directory."""
        # Create a file outside the project directory
        result = validate_spec_ref(str(tmp_path), "../../../etc/passwd")
        assert result.valid is False
        assert result.error_message == "Path escapes project directory"

    def test_path_traversal_with_nested_parent_refs(self, tmp_path):
        """Rejects spec refs with nested parent directory references."""
        result = validate_spec_ref(str(tmp_path), "specs/../../../etc/passwd")
        assert result.valid is False
        assert result.error_message == "Path escapes project directory"

    def test_path_traversal_with_anchor(self, tmp_path):
        """Rejects path traversal even with anchor."""
        result = validate_spec_ref(str(tmp_path), "../../../etc/passwd#section")
        assert result.valid is False
        assert result.error_message == "Path escapes project directory"

    def test_path_traversal_absolute_path(self, tmp_path):
        """Rejects absolute paths outside project."""
        result = validate_spec_ref(str(tmp_path), "/etc/passwd")
        assert result.valid is False
        assert result.error_message == "Path escapes project directory"

    def test_valid_relative_path_within_project(self, tmp_path):
        """Allows valid relative paths that stay within project."""
        # Create nested structure
        spec_file = tmp_path / "docs" / "specs" / "auth.md"
        spec_file.parent.mkdir(parents=True)
        spec_file.write_text("# Auth\nContent")

        # A path with .. that still resolves within project
        result = validate_spec_ref(str(tmp_path), "docs/specs/../specs/auth.md")
        assert result.valid is True


class TestValidateTaskSpecRefs:
    """Test batch task spec validation."""

    def test_validates_multiple_tasks(self, tmp_path):
        """Validates spec refs across multiple tasks."""
        # Create spec files
        spec1 = tmp_path / "specs" / "auth.md"
        spec1.parent.mkdir(parents=True)
        spec1.write_text("# Auth Spec\nContent")

        tasks = [
            Task(id="1.1", title="Task 1", spec_ref="specs/auth.md"),
            Task(id="1.2", title="Task 2", spec_ref="specs/missing.md"),
            Task(id="1.3", title="Task 3"),  # No spec_ref
        ]

        results = validate_task_spec_refs(str(tmp_path), tasks)

        assert "1.1" in results
        assert results["1.1"].valid is True

        assert "1.2" in results
        assert results["1.2"].valid is False

        # Task without spec_ref should not be in results
        assert "1.3" not in results

    def test_empty_task_list(self, tmp_path):
        """Handles empty task list."""
        results = validate_task_spec_refs(str(tmp_path), [])
        assert results == {}


class TestSpecValidationResult:
    """Test SpecValidationResult properties."""

    def test_valid_result(self):
        """Valid result has no errors."""
        result = SpecValidationResult(valid=True)
        assert result.valid is True
        assert result.error_message is None
        assert result.is_file_missing is False
        assert result.is_section_missing is False

    def test_file_missing_result(self):
        """File missing result is correctly identified."""
        result = SpecValidationResult(valid=False, error_message="File not found")
        assert result.valid is False
        assert result.is_file_missing is True
        assert result.is_section_missing is False

    def test_section_missing_result(self):
        """Section missing result is correctly identified."""
        result = SpecValidationResult(
            valid=False, error_message="Section 'login' not found"
        )
        assert result.valid is False
        assert result.is_file_missing is False
        assert result.is_section_missing is True

    def test_path_traversal_result(self):
        """Path traversal result is correctly identified."""
        result = SpecValidationResult(
            valid=False, error_message="Path escapes project directory"
        )
        assert result.valid is False
        assert result.is_file_missing is False
        assert result.is_section_missing is False
