"""Security utilities for iTerm Controller.

This module provides centralized security functions for:
- Path validation to prevent directory traversal attacks
- Safe file path handling within project boundaries

All file operations that accept user-provided paths should use these utilities
to ensure paths stay within allowed directories.
"""

from __future__ import annotations

import os
from pathlib import Path


class PathTraversalError(Exception):
    """Raised when a path traversal attack is detected.

    This occurs when a path attempts to escape its allowed directory,
    typically using sequences like '../' or absolute paths pointing
    outside the project root.
    """

    def __init__(
        self,
        message: str,
        *,
        attempted_path: str | None = None,
        allowed_root: str | None = None,
    ) -> None:
        self.attempted_path = attempted_path
        self.allowed_root = allowed_root
        super().__init__(message)

    def __str__(self) -> str:
        parts = [self.args[0]]
        if self.attempted_path:
            parts.append(f"attempted_path={self.attempted_path}")
        if self.allowed_root:
            parts.append(f"allowed_root={self.allowed_root}")
        return " ".join(parts)


def validate_path_in_project(
    path: Path | str,
    project_root: Path | str,
    *,
    must_exist: bool = False,
) -> Path:
    """Validate that a path stays within the project directory.

    This function prevents directory traversal attacks by ensuring that
    resolved paths are within the allowed project root. It handles:
    - Relative paths with '..' components
    - Symbolic links that might escape the project
    - Absolute paths that point outside the project

    Args:
        path: The path to validate (relative or absolute).
        project_root: The project root directory that paths must stay within.
        must_exist: If True, also verify the path exists.

    Returns:
        The resolved absolute path if valid.

    Raises:
        PathTraversalError: If the path would escape the project directory.
        FileNotFoundError: If must_exist=True and the path doesn't exist.

    Examples:
        >>> validate_path_in_project("specs/auth.md", "/project")
        PosixPath('/project/specs/auth.md')

        >>> validate_path_in_project("../../../etc/passwd", "/project")
        Raises PathTraversalError

        >>> validate_path_in_project("/etc/passwd", "/project")
        Raises PathTraversalError
    """
    # Convert to Path objects
    path = Path(path) if isinstance(path, str) else path
    project_root = Path(project_root) if isinstance(project_root, str) else project_root

    # Resolve the project root to an absolute path (following symlinks)
    try:
        resolved_root = project_root.resolve(strict=True)
    except (FileNotFoundError, OSError):
        # If project root doesn't exist, use resolve without strict
        resolved_root = project_root.resolve()

    # Build the full path
    if path.is_absolute():
        full_path = path
    else:
        full_path = project_root / path

    # Resolve the full path (following symlinks)
    # Use strict=False to allow checking non-existent paths
    try:
        resolved_path = full_path.resolve(strict=must_exist)
    except FileNotFoundError:
        raise FileNotFoundError(f"Path does not exist: {path}")

    # Check if the resolved path is within the project root
    # Use os.path.commonpath for reliable prefix checking
    try:
        common = Path(os.path.commonpath([resolved_path, resolved_root]))
        if common != resolved_root:
            raise PathTraversalError(
                "Path escapes project directory",
                attempted_path=str(path),
                allowed_root=str(project_root),
            )
    except ValueError:
        # ValueError from commonpath means paths are on different drives (Windows)
        # or otherwise incompatible
        raise PathTraversalError(
            "Path escapes project directory (different root)",
            attempted_path=str(path),
            allowed_root=str(project_root),
        )

    return resolved_path


def is_path_in_project(
    path: Path | str,
    project_root: Path | str,
) -> bool:
    """Check if a path stays within the project directory.

    This is a convenience wrapper around validate_path_in_project that
    returns a boolean instead of raising an exception.

    Args:
        path: The path to check (relative or absolute).
        project_root: The project root directory.

    Returns:
        True if the path is within the project, False otherwise.

    Examples:
        >>> is_path_in_project("specs/auth.md", "/project")
        True

        >>> is_path_in_project("../../../etc/passwd", "/project")
        False
    """
    try:
        validate_path_in_project(path, project_root, must_exist=False)
        return True
    except (PathTraversalError, FileNotFoundError):
        return False


def validate_filename(
    filename: str,
    *,
    allow_subdirs: bool = False,
) -> str:
    """Validate a filename to prevent path traversal.

    This function validates that a filename doesn't contain path traversal
    sequences or other dangerous characters.

    Args:
        filename: The filename to validate.
        allow_subdirs: If True, allow '/' for subdirectory paths.
                       If False, reject any path separators.

    Returns:
        The validated filename (stripped of whitespace).

    Raises:
        PathTraversalError: If the filename contains traversal sequences.
        ValueError: If the filename is empty or contains invalid characters.

    Examples:
        >>> validate_filename("document.md")
        'document.md'

        >>> validate_filename("../secret.txt")
        Raises PathTraversalError

        >>> validate_filename("subdir/doc.md", allow_subdirs=True)
        'subdir/doc.md'

        >>> validate_filename("subdir/doc.md", allow_subdirs=False)
        Raises PathTraversalError
    """
    # Strip whitespace
    filename = filename.strip()

    if not filename:
        raise ValueError("Filename cannot be empty")

    # Check for null bytes (could be used to truncate strings)
    if "\x00" in filename:
        raise PathTraversalError(
            "Filename contains null byte",
            attempted_path=filename,
        )

    # Check for parent directory references
    if ".." in filename:
        raise PathTraversalError(
            "Filename contains parent directory reference (..)",
            attempted_path=filename,
        )

    # Check for path separators if not allowed
    if not allow_subdirs:
        if "/" in filename or "\\" in filename:
            raise PathTraversalError(
                "Filename contains path separator",
                attempted_path=filename,
            )

    # Check for backslash (Windows path separator - disallow even on Unix for safety)
    if "\\" in filename:
        raise PathTraversalError(
            "Filename contains backslash",
            attempted_path=filename,
        )

    # Check for absolute path indicators
    if filename.startswith("/"):
        raise PathTraversalError(
            "Filename cannot be an absolute path",
            attempted_path=filename,
        )

    # Check for leading ~ (home directory expansion)
    if filename.startswith("~"):
        raise PathTraversalError(
            "Filename cannot start with ~ (home directory)",
            attempted_path=filename,
        )

    return filename


def safe_join(
    base_dir: Path | str,
    *parts: str,
) -> Path:
    """Safely join path components within a base directory.

    This function joins path components and validates that the result
    stays within the base directory. It's a safer alternative to
    Path.joinpath() when dealing with untrusted input.

    Args:
        base_dir: The base directory that the path must stay within.
        *parts: Path components to join.

    Returns:
        The joined and validated path.

    Raises:
        PathTraversalError: If the resulting path escapes the base directory.

    Examples:
        >>> safe_join("/project", "docs", "readme.md")
        PosixPath('/project/docs/readme.md')

        >>> safe_join("/project", "..", "etc", "passwd")
        Raises PathTraversalError
    """
    base_dir = Path(base_dir) if isinstance(base_dir, str) else base_dir

    # Validate each part individually first
    for part in parts:
        # Allow subdirs since we're joining multiple parts
        validate_filename(part, allow_subdirs=True)

    # Join and validate the full path
    full_path = base_dir.joinpath(*parts)
    return validate_path_in_project(full_path, base_dir)
