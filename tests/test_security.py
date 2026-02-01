"""Tests for security utilities (path validation)."""

import os
import tempfile
from pathlib import Path

import pytest

from iterm_controller.security import (
    PathTraversalError,
    is_path_in_project,
    safe_join,
    validate_filename,
    validate_path_in_project,
)


class TestValidatePathInProject:
    """Test path validation within project boundaries."""

    def test_relative_path_within_project(self, tmp_path):
        """Relative paths within project are valid."""
        # Create the file
        spec_file = tmp_path / "specs" / "auth.md"
        spec_file.parent.mkdir(parents=True)
        spec_file.touch()

        result = validate_path_in_project("specs/auth.md", tmp_path)
        assert result == tmp_path / "specs" / "auth.md"

    def test_nested_relative_path(self, tmp_path):
        """Nested relative paths are valid."""
        nested = tmp_path / "docs" / "api" / "v1" / "spec.md"
        nested.parent.mkdir(parents=True)
        nested.touch()

        result = validate_path_in_project("docs/api/v1/spec.md", tmp_path)
        assert result == tmp_path / "docs" / "api" / "v1" / "spec.md"

    def test_path_traversal_with_double_dots(self, tmp_path):
        """Path traversal with '..' is rejected."""
        with pytest.raises(PathTraversalError) as exc_info:
            validate_path_in_project("../../../etc/passwd", tmp_path)

        assert "escapes project directory" in str(exc_info.value)
        assert exc_info.value.attempted_path == "../../../etc/passwd"

    def test_path_traversal_hidden_in_path(self, tmp_path):
        """Path traversal hidden in middle of path is rejected."""
        with pytest.raises(PathTraversalError):
            validate_path_in_project("docs/../../../etc/passwd", tmp_path)

    def test_absolute_path_outside_project(self, tmp_path):
        """Absolute paths outside project are rejected."""
        with pytest.raises(PathTraversalError) as exc_info:
            validate_path_in_project("/etc/passwd", tmp_path)

        assert "escapes project directory" in str(exc_info.value)

    def test_absolute_path_inside_project(self, tmp_path):
        """Absolute paths inside project are valid."""
        file_path = tmp_path / "docs" / "readme.md"
        file_path.parent.mkdir(parents=True)
        file_path.touch()

        result = validate_path_in_project(str(file_path), tmp_path)
        assert result == file_path

    def test_current_dir_reference(self, tmp_path):
        """Current directory references are valid."""
        file_path = tmp_path / "readme.md"
        file_path.touch()

        result = validate_path_in_project("./readme.md", tmp_path)
        assert result == file_path

    def test_multiple_current_dir_references(self, tmp_path):
        """Multiple './' references are valid."""
        file_path = tmp_path / "docs" / "spec.md"
        file_path.parent.mkdir()
        file_path.touch()

        result = validate_path_in_project("./docs/./spec.md", tmp_path)
        assert result == file_path

    def test_symlink_within_project(self, tmp_path):
        """Symlinks that resolve within project are valid."""
        # Create target file
        target = tmp_path / "real" / "file.md"
        target.parent.mkdir()
        target.touch()

        # Create symlink
        link = tmp_path / "link_to_file.md"
        link.symlink_to(target)

        result = validate_path_in_project("link_to_file.md", tmp_path)
        assert result == target

    def test_symlink_escaping_project(self, tmp_path):
        """Symlinks that escape project directory are rejected."""
        # Create a directory outside the project
        with tempfile.TemporaryDirectory() as outside_dir:
            outside_file = Path(outside_dir) / "secret.txt"
            outside_file.write_text("secret data")

            # Create symlink inside project pointing outside
            link = tmp_path / "sneaky_link"
            link.symlink_to(outside_file)

            with pytest.raises(PathTraversalError):
                validate_path_in_project("sneaky_link", tmp_path, must_exist=True)

    def test_must_exist_with_existing_file(self, tmp_path):
        """must_exist=True passes for existing files."""
        file_path = tmp_path / "exists.md"
        file_path.touch()

        result = validate_path_in_project("exists.md", tmp_path, must_exist=True)
        assert result == file_path

    def test_must_exist_with_missing_file(self, tmp_path):
        """must_exist=True raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            validate_path_in_project("nonexistent.md", tmp_path, must_exist=True)

    def test_must_exist_false_for_nonexistent_path(self, tmp_path):
        """must_exist=False allows nonexistent paths (for creating files)."""
        result = validate_path_in_project("new/file.md", tmp_path, must_exist=False)
        assert result == tmp_path / "new" / "file.md"

    def test_path_object_input(self, tmp_path):
        """Works with Path objects as well as strings."""
        file_path = tmp_path / "docs.md"
        file_path.touch()

        result = validate_path_in_project(Path("docs.md"), tmp_path)
        assert result == file_path

    def test_path_object_project_root(self, tmp_path):
        """Works with Path object as project root."""
        file_path = tmp_path / "file.md"
        file_path.touch()

        result = validate_path_in_project("file.md", Path(str(tmp_path)))
        assert result == file_path

    def test_empty_path(self, tmp_path):
        """Empty path resolves to project root (current directory)."""
        result = validate_path_in_project("", tmp_path)
        assert result == tmp_path.resolve()

    def test_dot_only_path(self, tmp_path):
        """Single dot path resolves to project root."""
        result = validate_path_in_project(".", tmp_path)
        assert result == tmp_path.resolve()


class TestIsPathInProject:
    """Test the boolean helper function."""

    def test_valid_path_returns_true(self, tmp_path):
        """Returns True for valid paths."""
        assert is_path_in_project("docs/spec.md", tmp_path) is True

    def test_traversal_returns_false(self, tmp_path):
        """Returns False for path traversal attempts."""
        assert is_path_in_project("../../../etc/passwd", tmp_path) is False

    def test_absolute_outside_returns_false(self, tmp_path):
        """Returns False for absolute paths outside project."""
        assert is_path_in_project("/etc/passwd", tmp_path) is False

    def test_absolute_inside_returns_true(self, tmp_path):
        """Returns True for absolute paths inside project."""
        path_inside = tmp_path / "docs" / "file.md"
        assert is_path_in_project(str(path_inside), tmp_path) is True


class TestValidateFilename:
    """Test filename validation."""

    def test_simple_filename(self):
        """Simple filenames are valid."""
        assert validate_filename("document.md") == "document.md"

    def test_filename_with_hyphen(self):
        """Filenames with hyphens are valid."""
        assert validate_filename("my-document.md") == "my-document.md"

    def test_filename_with_underscore(self):
        """Filenames with underscores are valid."""
        assert validate_filename("my_document.md") == "my_document.md"

    def test_filename_with_numbers(self):
        """Filenames with numbers are valid."""
        assert validate_filename("doc123.md") == "doc123.md"

    def test_strips_whitespace(self):
        """Whitespace is stripped from filenames."""
        assert validate_filename("  file.md  ") == "file.md"

    def test_empty_filename(self):
        """Empty filenames are rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_filename("")
        assert "empty" in str(exc_info.value).lower()

    def test_whitespace_only_filename(self):
        """Whitespace-only filenames are rejected."""
        with pytest.raises(ValueError):
            validate_filename("   ")

    def test_double_dot_rejected(self):
        """Filenames with '..' are rejected."""
        with pytest.raises(PathTraversalError) as exc_info:
            validate_filename("../secret.txt")
        assert "parent directory" in str(exc_info.value).lower()

    def test_hidden_double_dot_rejected(self):
        """Hidden '..' sequences are rejected."""
        with pytest.raises(PathTraversalError):
            validate_filename("foo..bar")

    def test_slash_rejected_by_default(self):
        """Forward slashes are rejected by default."""
        with pytest.raises(PathTraversalError):
            validate_filename("subdir/file.md")

    def test_slash_allowed_with_flag(self):
        """Forward slashes allowed with allow_subdirs=True."""
        result = validate_filename("subdir/file.md", allow_subdirs=True)
        assert result == "subdir/file.md"

    def test_backslash_always_rejected(self):
        """Backslashes are always rejected (even with allow_subdirs)."""
        with pytest.raises(PathTraversalError):
            validate_filename("subdir\\file.md")

        with pytest.raises(PathTraversalError):
            validate_filename("subdir\\file.md", allow_subdirs=True)

    def test_absolute_path_rejected(self):
        """Absolute paths (starting with /) are rejected."""
        with pytest.raises(PathTraversalError):
            validate_filename("/etc/passwd")

    def test_home_expansion_rejected(self):
        """Home directory expansion (~) is rejected."""
        with pytest.raises(PathTraversalError):
            validate_filename("~/secret.txt")

    def test_null_byte_rejected(self):
        """Null bytes are rejected (could truncate strings)."""
        with pytest.raises(PathTraversalError):
            validate_filename("file.md\x00.txt")

    def test_nested_subdirs_allowed(self):
        """Nested subdirectories allowed with flag."""
        result = validate_filename("a/b/c/file.md", allow_subdirs=True)
        assert result == "a/b/c/file.md"

    def test_double_dot_in_subdir_rejected(self):
        """Double dots in subdir paths are rejected."""
        with pytest.raises(PathTraversalError):
            validate_filename("docs/../../../etc/passwd", allow_subdirs=True)


class TestSafeJoin:
    """Test safe path joining."""

    def test_simple_join(self, tmp_path):
        """Simple path components join correctly."""
        result = safe_join(tmp_path, "docs", "readme.md")
        assert result == tmp_path / "docs" / "readme.md"

    def test_single_component(self, tmp_path):
        """Single component joins correctly."""
        result = safe_join(tmp_path, "file.md")
        assert result == tmp_path / "file.md"

    def test_many_components(self, tmp_path):
        """Many components join correctly."""
        result = safe_join(tmp_path, "a", "b", "c", "d", "file.md")
        assert result == tmp_path / "a" / "b" / "c" / "d" / "file.md"

    def test_traversal_rejected(self, tmp_path):
        """Path traversal in components is rejected."""
        with pytest.raises(PathTraversalError):
            safe_join(tmp_path, "..", "etc", "passwd")

    def test_traversal_hidden_in_middle(self, tmp_path):
        """Traversal hidden in middle component is rejected."""
        with pytest.raises(PathTraversalError):
            safe_join(tmp_path, "docs", "..", "..", "etc", "passwd")

    def test_string_base_dir(self, tmp_path):
        """Works with string base directory."""
        result = safe_join(str(tmp_path), "docs", "file.md")
        assert result == tmp_path / "docs" / "file.md"


class TestPathTraversalError:
    """Test the PathTraversalError exception."""

    def test_basic_message(self):
        """Basic error message works."""
        error = PathTraversalError("Access denied")
        assert str(error) == "Access denied"

    def test_with_attempted_path(self):
        """Error includes attempted path."""
        error = PathTraversalError(
            "Access denied", attempted_path="../etc/passwd"
        )
        assert "../etc/passwd" in str(error)
        assert error.attempted_path == "../etc/passwd"

    def test_with_allowed_root(self):
        """Error includes allowed root."""
        error = PathTraversalError(
            "Access denied",
            attempted_path="../etc/passwd",
            allowed_root="/project",
        )
        assert "/project" in str(error)
        assert error.allowed_root == "/project"

    def test_inherits_from_exception(self):
        """PathTraversalError is an Exception."""
        error = PathTraversalError("test")
        assert isinstance(error, Exception)


class TestRealWorldScenarios:
    """Test real-world attack scenarios."""

    def test_spec_ref_traversal_attack(self, tmp_path):
        """Spec ref like '../../../etc/passwd' is caught."""
        with pytest.raises(PathTraversalError):
            validate_path_in_project("../../../etc/passwd", tmp_path)

    def test_document_creation_attack(self, tmp_path):
        """Creating document with traversal path is caught."""
        # This simulates what add_document modal should do
        filename = "../../../etc/cron.d/malicious"
        with pytest.raises(PathTraversalError):
            validate_filename(filename)

    def test_encoded_traversal_in_filename(self, tmp_path):
        """URL-encoded traversal sequences don't bypass validation."""
        # Note: The actual URL decoding would happen before this,
        # but the '..' should still be caught
        with pytest.raises(PathTraversalError):
            validate_filename("..%2F..%2Fetc%2Fpasswd")

    def test_unicode_traversal_attempt(self, tmp_path):
        """Unicode tricks don't bypass validation."""
        # Various Unicode tricks that might be attempted
        test_cases = [
            "..／etc/passwd",  # Fullwidth solidus
            "..\uFF0Fetc/passwd",  # Fullwidth solidus
        ]
        # Note: these may not trigger traversal if they don't resolve
        # to actual '..' sequences, but the key is they shouldn't
        # escape the project

        for case in test_cases:
            # The .. should still be caught even with unicode tricks
            if ".." in case:
                with pytest.raises(PathTraversalError):
                    validate_filename(case)

    def test_case_sensitivity(self, tmp_path):
        """Path traversal works regardless of case."""
        # On case-insensitive filesystems, this might matter
        with pytest.raises(PathTraversalError):
            validate_path_in_project("../../../ETC/PASSWD", tmp_path)
