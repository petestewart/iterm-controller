"""Spec file validation.

Validates that spec references in PLAN.md tasks point to existing files
and sections. Invalid references show warnings in the UI but don't prevent
task operations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SpecValidationResult:
    """Result of validating a spec reference."""

    valid: bool
    error_message: str | None = None

    @property
    def is_file_missing(self) -> bool:
        """Check if the error is due to a missing file."""
        return self.error_message == "File not found"

    @property
    def is_section_missing(self) -> bool:
        """Check if the error is due to a missing section."""
        return (
            self.error_message is not None
            and self.error_message.startswith("Section")
            and self.error_message.endswith("not found")
        )


def validate_spec_ref(project_path: str, spec_ref: str) -> SpecValidationResult:
    """Validate that a spec reference exists.

    Checks that the referenced file exists, and if an anchor is specified,
    that the file contains a matching markdown heading.

    Args:
        project_path: Absolute path to the project root directory.
        spec_ref: The spec reference (e.g., "specs/auth.md" or "specs/auth.md#login").

    Returns:
        SpecValidationResult indicating whether the reference is valid
        and any error message if not.

    Examples:
        >>> validate_spec_ref("/path/to/project", "specs/auth.md")
        SpecValidationResult(valid=True, error_message=None)

        >>> validate_spec_ref("/path/to/project", "specs/missing.md")
        SpecValidationResult(valid=False, error_message="File not found")

        >>> validate_spec_ref("/path/to/project", "specs/auth.md#missing-section")
        SpecValidationResult(valid=False, error_message="Section 'missing-section' not found")
    """
    if not spec_ref:
        return SpecValidationResult(valid=True)

    # Parse file path and optional anchor
    if "#" in spec_ref:
        file_path, anchor = spec_ref.split("#", 1)
    else:
        file_path, anchor = spec_ref, None

    # Construct full path
    full_path = Path(project_path) / file_path

    # Check if file exists
    if not full_path.exists():
        return SpecValidationResult(valid=False, error_message="File not found")

    # Check anchor if specified
    if anchor:
        try:
            content = full_path.read_text()
            if not _find_anchor_in_markdown(content, anchor):
                return SpecValidationResult(
                    valid=False, error_message=f"Section '{anchor}' not found"
                )
        except (OSError, UnicodeDecodeError):
            # If we can't read the file, consider the anchor invalid
            return SpecValidationResult(
                valid=False, error_message=f"Section '{anchor}' not found"
            )

    return SpecValidationResult(valid=True)


def _find_anchor_in_markdown(content: str, anchor: str) -> bool:
    """Check if a markdown anchor exists in the content.

    Anchors match markdown headings (any level: #, ##, ###, etc.).
    The match is case-insensitive.

    Args:
        content: The markdown file content.
        anchor: The anchor to find (without the # prefix).

    Returns:
        True if a matching heading is found, False otherwise.
    """
    # Normalize anchor for comparison
    anchor_lower = anchor.lower()

    # Look for markdown headings that match the anchor
    # Headings can be: # Heading, ## Heading, ### Heading, etc.
    heading_pattern = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)

    for match in heading_pattern.finditer(content):
        heading_text = match.group(1).strip()
        # Convert heading to anchor format: lowercase, spaces to hyphens
        heading_anchor = _heading_to_anchor(heading_text)
        if heading_anchor == anchor_lower:
            return True

    return False


def _heading_to_anchor(heading_text: str) -> str:
    """Convert a markdown heading to an anchor ID.

    Follows GitHub-style markdown anchor conversion:
    - Lowercase the text
    - Replace spaces with hyphens
    - Remove punctuation except hyphens and underscores

    Args:
        heading_text: The heading text (without the # prefix).

    Returns:
        The anchor ID.
    """
    # Lowercase
    result = heading_text.lower()

    # Replace spaces with hyphens
    result = result.replace(" ", "-")

    # Remove punctuation except hyphens, underscores, and alphanumerics
    result = re.sub(r"[^\w\-]", "", result)

    # Collapse multiple hyphens
    result = re.sub(r"-+", "-", result)

    # Strip leading/trailing hyphens
    result = result.strip("-")

    return result


def validate_task_spec_refs(
    project_path: str, tasks: list
) -> dict[str, SpecValidationResult]:
    """Validate all spec references in a list of tasks.

    Args:
        project_path: Absolute path to the project root directory.
        tasks: List of Task objects to validate.

    Returns:
        Dictionary mapping task IDs to their spec validation results.
        Only includes tasks that have spec_ref set.
    """
    results: dict[str, SpecValidationResult] = {}

    for task in tasks:
        if task.spec_ref:
            results[task.id] = validate_spec_ref(project_path, task.spec_ref)

    return results
