"""TEST_PLAN.md parsing and updates.

Parses markdown test checklists with status markers:
- [ ] pending
- [~] in progress
- [x] passed
- [!] failed (with optional notes)

Also provides TestPlanUpdater for updating TEST_PLAN.md files while preserving formatting.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .exceptions import TestPlanParseError, TestPlanWriteError, record_error
from .models import TestPlan, TestSection, TestStatus, TestStep

logger = logging.getLogger(__name__)


# =============================================================================
# Status Mappings
# =============================================================================

# Map from checkbox markers to TestStatus
STATUS_FROM_MARKER: dict[str, TestStatus] = {
    " ": TestStatus.PENDING,
    "~": TestStatus.IN_PROGRESS,
    "x": TestStatus.PASSED,
    "!": TestStatus.FAILED,
}

# Map from TestStatus to checkbox markers
STATUS_TO_MARKER: dict[TestStatus, str] = {
    TestStatus.PENDING: " ",
    TestStatus.IN_PROGRESS: "~",
    TestStatus.PASSED: "x",
    TestStatus.FAILED: "!",
}


# =============================================================================
# Parser
# =============================================================================


class TestPlanParser:
    """Parses TEST_PLAN.md files into structured data."""

    # Pattern for section headers (## Section Name)
    SECTION_PATTERN = re.compile(r"^##\s+(.+)$")

    # Pattern for test steps (- [ ] Step description)
    # Captures: marker (space, x, ~, !) and description
    STEP_PATTERN = re.compile(r"^-\s+\[([ x~!])\]\s+(.+)$")

    # Pattern for notes (indented, starts with "Note:")
    NOTE_PATTERN = re.compile(r"^\s+Note:\s+(.+)$")

    def parse(self, content: str) -> TestPlan:
        """Parse TEST_PLAN.md content into TestPlan object.

        Args:
            content: The raw markdown content of the test plan.

        Returns:
            Parsed TestPlan object with sections and steps.
        """
        plan = TestPlan()
        lines = content.split("\n")

        current_section: TestSection | None = None
        current_step: TestStep | None = None
        step_counter = 0

        for line_num, line in enumerate(lines, start=1):
            # Check for title (# Test Plan)
            if line.startswith("# ") and plan.title == "Test Plan":
                plan.title = line[2:].strip()
                continue

            # Check for section header (## Section Name)
            section_match = self.SECTION_PATTERN.match(line)
            if section_match:
                section_id = f"section-{len(plan.sections)}"
                current_section = TestSection(
                    id=section_id,
                    title=section_match.group(1).strip(),
                )
                plan.sections.append(current_section)
                step_counter = 0
                current_step = None
                continue

            # Check for test step (- [ ] Description)
            step_match = self.STEP_PATTERN.match(line)
            if step_match and current_section is not None:
                step_counter += 1
                marker = step_match.group(1)
                description = step_match.group(2).strip()

                current_step = TestStep(
                    id=f"{current_section.id}-{step_counter}",
                    section=current_section.title,
                    description=description,
                    status=STATUS_FROM_MARKER.get(marker, TestStatus.PENDING),
                    line_number=line_num,
                )
                current_section.steps.append(current_step)
                continue

            # Check for note (attached to previous step)
            note_match = self.NOTE_PATTERN.match(line)
            if note_match and current_step is not None:
                current_step.notes = note_match.group(1).strip()
                continue

        return plan

    def parse_file(self, path: Path) -> TestPlan:
        """Parse TEST_PLAN.md file from disk.

        Args:
            path: Path to the TEST_PLAN.md file.

        Returns:
            Parsed TestPlan object. If file doesn't exist, returns empty plan.

        Raises:
            TestPlanParseError: If the file cannot be read or parsed.
        """
        path = Path(path)

        if not path.exists():
            logger.debug("TEST_PLAN.md does not exist at %s, returning empty plan", path)
            return TestPlan(path=str(path))

        try:
            content = path.read_text(encoding="utf-8")
            logger.debug("Read TEST_PLAN.md from %s (%d bytes)", path, len(content))
        except OSError as e:
            logger.error("Failed to read TEST_PLAN.md: %s", e)
            record_error(e)
            raise TestPlanParseError(
                f"Failed to read TEST_PLAN.md: {e}",
                file_path=str(path),
                cause=e,
            ) from e

        try:
            plan = self.parse(content)
            plan.path = str(path)
            logger.debug(
                "Parsed %d sections with %d total steps",
                len(plan.sections),
                len(plan.all_steps),
            )
            return plan
        except Exception as e:
            logger.error("Failed to parse TEST_PLAN.md content: %s", e)
            record_error(e)
            raise TestPlanParseError(
                f"Failed to parse TEST_PLAN.md content: {e}",
                file_path=str(path),
                cause=e,
            ) from e


# =============================================================================
# Updater
# =============================================================================


class TestPlanUpdater:
    """Updates TEST_PLAN.md files while preserving formatting."""

    # Pattern for step lines to match and replace
    STEP_LINE_PATTERN = re.compile(r"^(-\s+\[)([ x~!])(\]\s+.+)$")

    def update_step_status(
        self,
        content: str,
        step_id: str,
        new_status: TestStatus,
        notes: str | None = None,
    ) -> str:
        """Update a step's status in TEST_PLAN.md content.

        Args:
            content: The TEST_PLAN.md file content.
            step_id: The step ID to update (e.g., "section-0-1").
            new_status: The new status to set.
            notes: Optional notes to add (typically for failed steps).

        Returns:
            Updated content with the step status changed.

        Raises:
            TestPlanWriteError: If the step cannot be found.
        """
        # Parse to find the step
        parser = TestPlanParser()
        plan = parser.parse(content)

        step = next((s for s in plan.all_steps if s.id == step_id), None)
        if step is None:
            raise TestPlanWriteError(
                f"Step not found: {step_id}",
                step_id=step_id,
            )

        lines = content.split("\n")
        line_idx = step.line_number - 1  # Convert to 0-indexed

        if line_idx >= len(lines):
            raise TestPlanWriteError(
                f"Invalid line number for step: {step_id}",
                step_id=step_id,
                context={"line_number": step.line_number, "total_lines": len(lines)},
            )

        # Build the new line
        new_marker = STATUS_TO_MARKER[new_status]
        match = self.STEP_LINE_PATTERN.match(lines[line_idx])

        if not match:
            raise TestPlanWriteError(
                f"Cannot parse step line for update: {step_id}",
                step_id=step_id,
                context={"line": lines[line_idx][:50]},
            )

        # Replace the marker
        lines[line_idx] = f"{match.group(1)}{new_marker}{match.group(3)}"

        # Handle notes
        note_line_idx = line_idx + 1

        # Check if there's an existing note line
        has_existing_note = (
            note_line_idx < len(lines)
            and TestPlanParser.NOTE_PATTERN.match(lines[note_line_idx]) is not None
        )

        if notes:
            note_text = f"  Note: {notes}"
            if has_existing_note:
                # Replace existing note
                lines[note_line_idx] = note_text
            else:
                # Insert new note
                lines.insert(note_line_idx, note_text)
        elif has_existing_note:
            # Remove existing note if clearing notes
            del lines[note_line_idx]

        return "\n".join(lines)

    def update_step_status_in_file(
        self,
        path: Path,
        step_id: str,
        new_status: TestStatus,
        notes: str | None = None,
    ) -> None:
        """Update a step's status in a TEST_PLAN.md file.

        Args:
            path: Path to the TEST_PLAN.md file.
            step_id: The step ID to update (e.g., "section-0-1").
            new_status: The new status to set.
            notes: Optional notes to add (typically for failed steps).

        Raises:
            TestPlanParseError: If the file cannot be read.
            TestPlanWriteError: If the file cannot be written or step not found.
        """
        path = Path(path)

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.error("Failed to read TEST_PLAN.md for update: %s", e)
            record_error(e)
            raise TestPlanParseError(
                f"Failed to read TEST_PLAN.md: {e}",
                file_path=str(path),
                cause=e,
            ) from e

        updated_content = self.update_step_status(content, step_id, new_status, notes)

        try:
            path.write_text(updated_content, encoding="utf-8")
            logger.info(
                "Updated step %s to %s in %s",
                step_id,
                new_status.value,
                path,
            )
        except OSError as e:
            logger.error("Failed to write TEST_PLAN.md: %s", e)
            record_error(e)
            raise TestPlanWriteError(
                f"Failed to write TEST_PLAN.md: {e}",
                file_path=str(path),
                step_id=step_id,
                cause=e,
            ) from e

    def update_multiple_steps(
        self,
        path: Path,
        updates: list[tuple[str, TestStatus, str | None]],
    ) -> int:
        """Update multiple steps at once.

        Args:
            path: Path to the TEST_PLAN.md file.
            updates: List of (step_id, status, notes) tuples.

        Returns:
            Count of successful updates.
        """
        count = 0
        for step_id, status, notes in updates:
            try:
                self.update_step_status_in_file(path, step_id, status, notes)
                count += 1
            except (TestPlanParseError, TestPlanWriteError) as e:
                logger.warning("Failed to update step %s: %s", step_id, e)
        return count


# =============================================================================
# Convenience Functions
# =============================================================================


def parse_test_plan(path: str | Path) -> TestPlan:
    """Parse a TEST_PLAN.md file.

    Args:
        path: Path to the TEST_PLAN.md file.

    Returns:
        Parsed TestPlan object.
    """
    parser = TestPlanParser()
    return parser.parse_file(Path(path))


def update_test_step_status(
    path: str | Path,
    step_id: str,
    new_status: TestStatus,
    notes: str | None = None,
) -> bool:
    """Update a step's status in a TEST_PLAN.md file.

    Args:
        path: Path to the TEST_PLAN.md file.
        step_id: The step ID to update.
        new_status: The new status to set.
        notes: Optional notes to add.

    Returns:
        True if update succeeded, False otherwise.
    """
    try:
        updater = TestPlanUpdater()
        updater.update_step_status_in_file(Path(path), step_id, new_status, notes)
        return True
    except (TestPlanParseError, TestPlanWriteError) as e:
        logger.error("Failed to update test step status: %s", e)
        return False
