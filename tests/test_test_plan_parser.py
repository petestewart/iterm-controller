"""Tests for TEST_PLAN.md parser and updater."""

import tempfile
from pathlib import Path

import pytest

from iterm_controller.exceptions import TestPlanParseError, TestPlanWriteError
from iterm_controller.models import TestPlan, TestSection, TestStatus, TestStep
from iterm_controller.test_plan_parser import (
    TestPlanParser,
    TestPlanUpdater,
    parse_test_plan,
    update_test_step_status,
)


# =============================================================================
# Sample TEST_PLAN.md Content for Testing
# =============================================================================

SAMPLE_TEST_PLAN_MD = """# Test Plan for Feature X

## Functional Tests

- [ ] User can log in with valid credentials
- [~] Password reset flow works correctly
- [x] Session persists after page reload
- [!] Two-factor authentication verification
  Note: Fails with invalid TOTP code

## Edge Cases

- [ ] Empty form submission shows error
- [ ] Special characters in password handled
- [x] Login throttling after 5 failed attempts

## Performance Tests

- [ ] Login completes within 2 seconds
- [ ] Password hash computation is fast enough
"""

MINIMAL_TEST_PLAN_MD = """# Test Plan

## Basic Tests

- [ ] Single test step
"""

EMPTY_SECTIONS_MD = """# Test Plan

## Empty Section

## Another Section

- [ ] Only step here
"""


# =============================================================================
# TestPlanParser Tests
# =============================================================================


class TestTestPlanParser:
    """Test TestPlanParser class."""

    def test_parse_empty_content(self):
        parser = TestPlanParser()
        plan = parser.parse("")
        assert plan.sections == []
        assert plan.title == "Test Plan"

    def test_parse_title(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        assert plan.title == "Test Plan for Feature X"

    def test_parse_default_title(self):
        parser = TestPlanParser()
        plan = parser.parse("## Section\n- [ ] Step")
        assert plan.title == "Test Plan"

    def test_parse_sections(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        assert len(plan.sections) == 3
        assert plan.sections[0].title == "Functional Tests"
        assert plan.sections[1].title == "Edge Cases"
        assert plan.sections[2].title == "Performance Tests"

    def test_parse_section_ids(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        assert plan.sections[0].id == "section-0"
        assert plan.sections[1].id == "section-1"
        assert plan.sections[2].id == "section-2"

    def test_parse_steps_count(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        assert len(plan.sections[0].steps) == 4  # Functional Tests
        assert len(plan.sections[1].steps) == 3  # Edge Cases
        assert len(plan.sections[2].steps) == 2  # Performance Tests

    def test_parse_step_ids(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        # First section steps
        assert plan.sections[0].steps[0].id == "section-0-1"
        assert plan.sections[0].steps[1].id == "section-0-2"
        assert plan.sections[0].steps[2].id == "section-0-3"
        assert plan.sections[0].steps[3].id == "section-0-4"
        # Second section steps
        assert plan.sections[1].steps[0].id == "section-1-1"

    def test_parse_step_descriptions(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        assert plan.sections[0].steps[0].description == "User can log in with valid credentials"
        assert plan.sections[0].steps[1].description == "Password reset flow works correctly"
        assert plan.sections[1].steps[0].description == "Empty form submission shows error"

    def test_parse_step_section_reference(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        assert plan.sections[0].steps[0].section == "Functional Tests"
        assert plan.sections[1].steps[0].section == "Edge Cases"

    def test_parse_pending_status(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        assert plan.sections[0].steps[0].status == TestStatus.PENDING

    def test_parse_in_progress_status(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        assert plan.sections[0].steps[1].status == TestStatus.IN_PROGRESS

    def test_parse_passed_status(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        assert plan.sections[0].steps[2].status == TestStatus.PASSED

    def test_parse_failed_status(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        assert plan.sections[0].steps[3].status == TestStatus.FAILED

    def test_parse_notes(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        # Step 4 has notes
        assert plan.sections[0].steps[3].notes == "Fails with invalid TOTP code"
        # Other steps have no notes
        assert plan.sections[0].steps[0].notes is None
        assert plan.sections[0].steps[1].notes is None

    def test_parse_line_numbers(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        # Verify line numbers are captured (1-indexed)
        # Line 5 is the first step (after title, blank, section header, blank)
        assert plan.sections[0].steps[0].line_number > 0
        # Line numbers should be sequential within a section
        assert (
            plan.sections[0].steps[1].line_number > plan.sections[0].steps[0].line_number
        )

    def test_parse_minimal_plan(self):
        parser = TestPlanParser()
        plan = parser.parse(MINIMAL_TEST_PLAN_MD)
        assert len(plan.sections) == 1
        assert plan.sections[0].title == "Basic Tests"
        assert len(plan.sections[0].steps) == 1
        assert plan.sections[0].steps[0].description == "Single test step"

    def test_parse_empty_sections_skipped(self):
        parser = TestPlanParser()
        plan = parser.parse(EMPTY_SECTIONS_MD)
        # Both sections are created, but first one has no steps
        assert len(plan.sections) == 2
        assert len(plan.sections[0].steps) == 0
        assert len(plan.sections[1].steps) == 1


class TestTestPlanParserFile:
    """Test parsing from files."""

    def test_parse_file(self):
        parser = TestPlanParser()
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)
            plan = parser.parse_file(plan_path)
            assert len(plan.sections) == 3
            assert plan.path == str(plan_path)

    def test_parse_nonexistent_file_returns_empty_plan(self):
        parser = TestPlanParser()
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "NONEXISTENT.md"
            plan = parser.parse_file(plan_path)
            assert plan.sections == []
            assert plan.path == str(plan_path)

    def test_parse_file_convenience_function(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)
            plan = parse_test_plan(plan_path)
            assert len(plan.sections) == 3


class TestTestPlanParserAllStatuses:
    """Test parsing of all status markers."""

    def test_parse_all_status_markers(self):
        plan_md = """# Test Plan

## Status Tests

- [ ] Pending step (space)
- [~] In progress step (tilde)
- [x] Passed step (x)
- [!] Failed step (exclamation)
"""
        parser = TestPlanParser()
        plan = parser.parse(plan_md)
        steps = plan.sections[0].steps
        assert steps[0].status == TestStatus.PENDING
        assert steps[1].status == TestStatus.IN_PROGRESS
        assert steps[2].status == TestStatus.PASSED
        assert steps[3].status == TestStatus.FAILED

    def test_unknown_marker_defaults_to_pending(self):
        # The regex only matches [ x~!], so unknown markers won't match
        plan_md = """# Test Plan

## Test

- [?] Unknown marker
"""
        parser = TestPlanParser()
        plan = parser.parse(plan_md)
        # Should not match as a step since [?] isn't in the pattern
        assert len(plan.sections[0].steps) == 0


# =============================================================================
# TestPlan Properties Tests
# =============================================================================


class TestTestPlanProperties:
    """Test TestPlan computed properties."""

    def test_all_steps(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        all_steps = plan.all_steps
        assert len(all_steps) == 9  # 4 + 3 + 2

    def test_completion_percentage_none_passed(self):
        plan_md = """# Test Plan

## Tests

- [ ] Step 1
- [ ] Step 2
- [ ] Step 3
"""
        parser = TestPlanParser()
        plan = parser.parse(plan_md)
        assert plan.completion_percentage == 0.0

    def test_completion_percentage_all_passed(self):
        plan_md = """# Test Plan

## Tests

- [x] Step 1
- [x] Step 2
- [x] Step 3
"""
        parser = TestPlanParser()
        plan = parser.parse(plan_md)
        assert plan.completion_percentage == 100.0

    def test_completion_percentage_partial(self):
        plan_md = """# Test Plan

## Tests

- [x] Step 1
- [ ] Step 2
- [x] Step 3
- [ ] Step 4
"""
        parser = TestPlanParser()
        plan = parser.parse(plan_md)
        assert plan.completion_percentage == 50.0

    def test_completion_percentage_empty_plan(self):
        parser = TestPlanParser()
        plan = parser.parse("")
        assert plan.completion_percentage == 0.0

    def test_summary(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        summary = plan.summary
        # From sample:
        # Functional Tests: 1 pending, 1 in_progress, 1 passed, 1 failed = 4
        # Edge Cases: 2 pending, 1 passed = 3
        # Performance Tests: 2 pending = 2
        # Total: 5 pending, 1 in_progress, 2 passed, 1 failed
        assert summary["pending"] == 5
        assert summary["in_progress"] == 1
        assert summary["passed"] == 2
        assert summary["failed"] == 1


class TestTestSectionProperties:
    """Test TestSection computed properties."""

    def test_completion_count(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        # Functional Tests: 1 passed out of 4
        assert plan.sections[0].completion_count == (1, 4)
        # Edge Cases: 1 passed out of 3
        assert plan.sections[1].completion_count == (1, 3)

    def test_has_failures_true(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        # Functional Tests has a failed step
        assert plan.sections[0].has_failures is True

    def test_has_failures_false(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        # Edge Cases has no failed steps
        assert plan.sections[1].has_failures is False


# =============================================================================
# TestPlanUpdater Tests
# =============================================================================


class TestTestPlanUpdater:
    """Test TestPlanUpdater class."""

    def test_update_pending_to_passed(self):
        plan_md = """# Test Plan

## Tests

- [ ] Step 1
- [ ] Step 2
"""
        updater = TestPlanUpdater()
        result = updater.update_step_status(plan_md, "section-0-1", TestStatus.PASSED)

        assert "- [x] Step 1" in result
        assert "- [ ] Step 2" in result

    def test_update_pending_to_in_progress(self):
        plan_md = """# Test Plan

## Tests

- [ ] Step 1
"""
        updater = TestPlanUpdater()
        result = updater.update_step_status(
            plan_md, "section-0-1", TestStatus.IN_PROGRESS
        )

        assert "- [~] Step 1" in result

    def test_update_pending_to_failed(self):
        plan_md = """# Test Plan

## Tests

- [ ] Step 1
"""
        updater = TestPlanUpdater()
        result = updater.update_step_status(plan_md, "section-0-1", TestStatus.FAILED)

        assert "- [!] Step 1" in result

    def test_update_passed_to_pending(self):
        plan_md = """# Test Plan

## Tests

- [x] Step 1
"""
        updater = TestPlanUpdater()
        result = updater.update_step_status(plan_md, "section-0-1", TestStatus.PENDING)

        assert "- [ ] Step 1" in result

    def test_update_specific_step_in_section(self):
        plan_md = """# Test Plan

## Tests

- [ ] Step 1
- [ ] Step 2
- [ ] Step 3
"""
        updater = TestPlanUpdater()
        result = updater.update_step_status(plan_md, "section-0-2", TestStatus.PASSED)

        assert "- [ ] Step 1" in result
        assert "- [x] Step 2" in result
        assert "- [ ] Step 3" in result

    def test_update_step_in_second_section(self):
        plan_md = """# Test Plan

## First Section

- [x] Step 1A
- [x] Step 1B

## Second Section

- [ ] Step 2A
- [ ] Step 2B
"""
        updater = TestPlanUpdater()
        result = updater.update_step_status(plan_md, "section-1-1", TestStatus.PASSED)

        # First section unchanged
        assert "- [x] Step 1A" in result
        assert "- [x] Step 1B" in result
        # Second section first step updated
        assert "- [x] Step 2A" in result
        # Second section second step unchanged
        assert "- [ ] Step 2B" in result

    def test_update_nonexistent_step_raises(self):
        plan_md = """# Test Plan

## Tests

- [ ] Step 1
"""
        updater = TestPlanUpdater()
        with pytest.raises(TestPlanWriteError, match="Step not found"):
            updater.update_step_status(plan_md, "section-99-1", TestStatus.PASSED)

    def test_add_notes_to_failed_step(self):
        plan_md = """# Test Plan

## Tests

- [ ] Step 1
- [ ] Step 2
"""
        updater = TestPlanUpdater()
        result = updater.update_step_status(
            plan_md,
            "section-0-1",
            TestStatus.FAILED,
            notes="Failed due to timeout",
        )

        assert "- [!] Step 1" in result
        assert "  Note: Failed due to timeout" in result
        # Step 2 should be unchanged
        assert "- [ ] Step 2" in result

    def test_update_existing_notes(self):
        plan_md = """# Test Plan

## Tests

- [!] Step 1
  Note: Original note
- [ ] Step 2
"""
        updater = TestPlanUpdater()
        result = updater.update_step_status(
            plan_md,
            "section-0-1",
            TestStatus.FAILED,
            notes="Updated note",
        )

        assert "  Note: Updated note" in result
        assert "Original note" not in result

    def test_remove_notes_when_passing(self):
        plan_md = """# Test Plan

## Tests

- [!] Step 1
  Note: Error details
- [ ] Step 2
"""
        updater = TestPlanUpdater()
        result = updater.update_step_status(
            plan_md,
            "section-0-1",
            TestStatus.PASSED,
            notes=None,  # Clear notes
        )

        assert "- [x] Step 1" in result
        assert "Note:" not in result


class TestTestPlanUpdaterFileOperations:
    """Test file operations."""

    def test_update_step_status_in_file(self):
        plan_md = """# Test Plan

## Tests

- [ ] Step 1
- [ ] Step 2
"""
        updater = TestPlanUpdater()

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(plan_md)

            updater.update_step_status_in_file(
                plan_path, "section-0-1", TestStatus.PASSED
            )

            result = plan_path.read_text()
            assert "- [x] Step 1" in result
            assert "- [ ] Step 2" in result

    def test_update_step_status_in_file_with_notes(self):
        plan_md = """# Test Plan

## Tests

- [ ] Step 1
"""
        updater = TestPlanUpdater()

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(plan_md)

            updater.update_step_status_in_file(
                plan_path,
                "section-0-1",
                TestStatus.FAILED,
                notes="Assertion failed",
            )

            result = plan_path.read_text()
            assert "- [!] Step 1" in result
            assert "  Note: Assertion failed" in result

    def test_update_multiple_steps(self):
        plan_md = """# Test Plan

## Tests

- [ ] Step 1
- [ ] Step 2
- [ ] Step 3
"""
        updater = TestPlanUpdater()

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(plan_md)

            updates = [
                ("section-0-1", TestStatus.PASSED, None),
                ("section-0-2", TestStatus.FAILED, "Error!"),
                ("section-0-3", TestStatus.IN_PROGRESS, None),
            ]
            count = updater.update_multiple_steps(plan_path, updates)

            assert count == 3
            result = plan_path.read_text()
            assert "- [x] Step 1" in result
            assert "- [!] Step 2" in result
            assert "  Note: Error!" in result
            assert "- [~] Step 3" in result

    def test_convenience_function_success(self):
        plan_md = """# Test Plan

## Tests

- [ ] Step 1
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(plan_md)

            result = update_test_step_status(
                plan_path, "section-0-1", TestStatus.PASSED
            )

            assert result is True
            content = plan_path.read_text()
            assert "- [x] Step 1" in content

    def test_convenience_function_failure(self):
        plan_md = """# Test Plan

## Tests

- [ ] Step 1
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(plan_md)

            result = update_test_step_status(
                plan_path, "nonexistent-step", TestStatus.PASSED
            )

            assert result is False


class TestTestPlanRoundTrip:
    """Test that updates can be parsed back correctly."""

    def test_update_and_parse_roundtrip(self):
        plan_md = """# Test Plan

## Tests

- [ ] Step 1
- [ ] Step 2
- [ ] Step 3
"""
        updater = TestPlanUpdater()
        parser = TestPlanParser()

        # Update step 2 to passed
        updated = updater.update_step_status(plan_md, "section-0-2", TestStatus.PASSED)

        # Parse the result
        plan = parser.parse(updated)

        # Verify the update was parsed correctly
        assert plan.sections[0].steps[0].status == TestStatus.PENDING
        assert plan.sections[0].steps[1].status == TestStatus.PASSED
        assert plan.sections[0].steps[2].status == TestStatus.PENDING

    def test_update_with_notes_roundtrip(self):
        plan_md = """# Test Plan

## Tests

- [ ] Step 1
"""
        updater = TestPlanUpdater()
        parser = TestPlanParser()

        # Update to failed with notes
        updated = updater.update_step_status(
            plan_md,
            "section-0-1",
            TestStatus.FAILED,
            notes="Test failure reason",
        )

        # Parse the result
        plan = parser.parse(updated)

        # Verify notes were preserved
        assert plan.sections[0].steps[0].status == TestStatus.FAILED
        assert plan.sections[0].steps[0].notes == "Test failure reason"

    def test_multiple_updates_roundtrip(self):
        plan_md = """# Test Plan

## Section A

- [ ] Step A1
- [ ] Step A2

## Section B

- [ ] Step B1
- [ ] Step B2
"""
        updater = TestPlanUpdater()
        parser = TestPlanParser()

        # Multiple sequential updates
        content = plan_md
        content = updater.update_step_status(content, "section-0-1", TestStatus.PASSED)
        content = updater.update_step_status(
            content, "section-0-2", TestStatus.IN_PROGRESS
        )
        content = updater.update_step_status(
            content, "section-1-1", TestStatus.FAILED, notes="Bug found"
        )
        content = updater.update_step_status(content, "section-1-2", TestStatus.PASSED)

        # Parse final result
        plan = parser.parse(content)

        # Verify all updates
        assert plan.sections[0].steps[0].status == TestStatus.PASSED
        assert plan.sections[0].steps[1].status == TestStatus.IN_PROGRESS
        assert plan.sections[1].steps[0].status == TestStatus.FAILED
        assert plan.sections[1].steps[0].notes == "Bug found"
        assert plan.sections[1].steps[1].status == TestStatus.PASSED


class TestEdgeCases:
    """Test edge cases and unusual inputs."""

    def test_step_with_special_characters(self):
        plan_md = """# Test Plan

## Tests

- [ ] Step with "quotes" and 'apostrophes'
- [ ] Step with [brackets] and (parentheses)
- [ ] Step with code `inline code`
"""
        parser = TestPlanParser()
        plan = parser.parse(plan_md)

        assert (
            plan.sections[0].steps[0].description
            == 'Step with "quotes" and \'apostrophes\''
        )
        assert (
            plan.sections[0].steps[1].description
            == "Step with [brackets] and (parentheses)"
        )
        assert plan.sections[0].steps[2].description == "Step with code `inline code`"

    def test_section_with_extra_text(self):
        plan_md = """# Test Plan

## Tests - Additional Info

- [ ] Step 1
"""
        parser = TestPlanParser()
        plan = parser.parse(plan_md)

        assert plan.sections[0].title == "Tests - Additional Info"

    def test_multiple_notes_last_wins(self):
        # When multiple Note: lines appear, the last one wins (overwrites)
        plan_md = """# Test Plan

## Tests

- [!] Failed step
  Note: First note
  Note: Second note overwrites
- [ ] Next step
"""
        parser = TestPlanParser()
        plan = parser.parse(plan_md)

        # The second note overwrites the first
        assert plan.sections[0].steps[0].notes == "Second note overwrites"

    def test_whitespace_handling(self):
        plan_md = """# Test Plan

## Tests

- [ ]   Step with extra spaces
- [ ] Normal step
"""
        parser = TestPlanParser()
        plan = parser.parse(plan_md)

        # Description should be trimmed
        assert plan.sections[0].steps[0].description == "Step with extra spaces"
        assert plan.sections[0].steps[1].description == "Normal step"
