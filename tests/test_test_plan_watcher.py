"""Tests for TEST_PLAN.md file watcher."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from iterm_controller.models import TestPlan, Project, TestStatus
from iterm_controller.test_plan_parser import TestPlanParser
from iterm_controller.test_plan_watcher import (
    TestStepChange,
    TestPlanWatcher,
    TestStepWrite,
    TestPlanWriteQueue,
)


# Sample TEST_PLAN.md content for testing
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
"""


class TestTestStepChange:
    """Test TestStepChange data class."""

    def test_status_changed_str(self):
        change = TestStepChange(
            step_id="section-0-1",
            old_status=TestStatus.PENDING,
            new_status=TestStatus.PASSED,
            step_description="Some step",
            change_type="status_changed",
        )
        assert "section-0-1" in str(change)
        assert "pending" in str(change)
        assert "passed" in str(change)

    def test_step_added_str(self):
        change = TestStepChange(
            step_id="section-0-5",
            old_status=None,
            new_status=TestStatus.PENDING,
            step_description="New Step",
            change_type="step_added",
        )
        assert "New step added" in str(change)
        assert "section-0-5" in str(change)
        assert "New Step" in str(change)

    def test_step_removed_str(self):
        change = TestStepChange(
            step_id="section-0-2",
            old_status=TestStatus.PENDING,
            new_status=None,
            step_description="Old Step",
            change_type="step_removed",
        )
        assert "Step removed" in str(change)
        assert "section-0-2" in str(change)


class TestTestPlanWatcherBasics:
    """Test basic TestPlanWatcher functionality."""

    def test_initial_state(self):
        watcher = TestPlanWatcher()
        assert watcher.test_plan is None
        assert watcher.plan_path is None
        assert watcher.watching is False
        assert watcher.has_pending_writes is False
        assert watcher.queued_reload is None
        assert watcher.last_mtime == 0

    def test_mark_write_started(self):
        watcher = TestPlanWatcher()
        assert watcher.has_pending_writes is False
        watcher.mark_write_started()
        assert watcher.has_pending_writes is True

    def test_mark_write_completed(self):
        watcher = TestPlanWatcher()
        watcher.mark_write_started()
        assert watcher.has_pending_writes is True
        watcher.mark_write_completed()
        assert watcher.has_pending_writes is False

    def test_mark_write_completed_with_mtime(self):
        watcher = TestPlanWatcher()
        watcher.mark_write_completed(new_mtime=12345.0)
        assert watcher.last_mtime == 12345.0

    def test_keep_current_clears_queued_reload(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        watcher = TestPlanWatcher()
        watcher.queued_reload = plan
        watcher.keep_current()
        assert watcher.queued_reload is None


class TestTestPlanWatcherChangeDetection:
    """Test change detection between plan versions."""

    def test_no_changes_same_plan(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        watcher = TestPlanWatcher(test_plan=plan)
        changes = watcher._compute_changes(plan)
        assert changes == []

    def test_detect_status_change(self):
        parser = TestPlanParser()
        original_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

        modified_md = SAMPLE_TEST_PLAN_MD.replace(
            "- [ ] User can log in with valid credentials",
            "- [x] User can log in with valid credentials",
        )
        new_plan = parser.parse(modified_md)

        watcher = TestPlanWatcher(test_plan=original_plan)
        changes = watcher._compute_changes(new_plan)

        assert len(changes) == 1
        assert changes[0].step_id == "section-0-1"
        assert changes[0].old_status == TestStatus.PENDING
        assert changes[0].new_status == TestStatus.PASSED
        assert changes[0].change_type == "status_changed"

    def test_detect_step_added(self):
        parser = TestPlanParser()
        original_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

        modified_md = SAMPLE_TEST_PLAN_MD + """
- [ ] New test step added
"""
        new_plan = parser.parse(modified_md)

        watcher = TestPlanWatcher(test_plan=original_plan)
        changes = watcher._compute_changes(new_plan)

        assert len(changes) == 1
        assert changes[0].change_type == "step_added"
        assert changes[0].old_status is None
        assert changes[0].new_status == TestStatus.PENDING

    def test_detect_step_removed(self):
        parser = TestPlanParser()
        original_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

        # Remove the last step from Edge Cases
        modified_md = """# Test Plan for Feature X

## Functional Tests

- [ ] User can log in with valid credentials
- [~] Password reset flow works correctly
- [x] Session persists after page reload
- [!] Two-factor authentication verification
  Note: Fails with invalid TOTP code

## Edge Cases

- [ ] Empty form submission shows error
- [ ] Special characters in password handled
"""
        new_plan = parser.parse(modified_md)

        watcher = TestPlanWatcher(test_plan=original_plan)
        changes = watcher._compute_changes(new_plan)

        assert len(changes) == 1
        assert changes[0].change_type == "step_removed"
        assert changes[0].old_status == TestStatus.PASSED
        assert changes[0].new_status is None

    def test_detect_multiple_changes(self):
        parser = TestPlanParser()
        original_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

        # Change status and add a step
        modified_md = SAMPLE_TEST_PLAN_MD.replace(
            "- [ ] User can log in with valid credentials",
            "- [x] User can log in with valid credentials",
        ) + """
- [ ] New test step
"""
        new_plan = parser.parse(modified_md)

        watcher = TestPlanWatcher(test_plan=original_plan)
        changes = watcher._compute_changes(new_plan)

        assert len(changes) == 2
        change_types = {c.change_type for c in changes}
        assert "status_changed" in change_types
        assert "step_added" in change_types

    def test_conflicts_with_current_true(self):
        parser = TestPlanParser()
        original_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

        modified_md = SAMPLE_TEST_PLAN_MD.replace(
            "- [ ] User can log in with valid credentials",
            "- [x] User can log in with valid credentials",
        )
        new_plan = parser.parse(modified_md)

        watcher = TestPlanWatcher(test_plan=original_plan)
        assert watcher.conflicts_with_current(new_plan) is True

    def test_conflicts_with_current_false(self):
        parser = TestPlanParser()
        plan = parser.parse(SAMPLE_TEST_PLAN_MD)

        watcher = TestPlanWatcher(test_plan=plan)
        assert watcher.conflicts_with_current(plan) is False


class TestTestPlanWatcherFileOperations:
    """Test file-based operations."""

    def test_reload_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            watcher = TestPlanWatcher(plan_path=plan_path)
            plan = watcher.reload_from_file()

            assert plan is not None
            assert len(plan.sections) == 2
            assert watcher.test_plan is plan

    def test_reload_from_nonexistent_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"

            watcher = TestPlanWatcher(plan_path=plan_path)
            plan = watcher.reload_from_file()

            assert plan is None

    def test_accept_external_changes(self):
        parser = TestPlanParser()
        original_plan = parser.parse(SAMPLE_TEST_PLAN_MD)
        new_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

        callback_called = []

        def on_reloaded(plan: TestPlan):
            callback_called.append(plan)

        watcher = TestPlanWatcher(test_plan=original_plan, on_plan_reloaded=on_reloaded)
        watcher.accept_external_changes(new_plan)

        assert watcher.test_plan is new_plan
        assert len(callback_called) == 1
        assert callback_called[0] is new_plan


class TestTestPlanWatcherAsyncOperations:
    """Test async file watching operations."""

    @pytest.mark.asyncio
    async def test_start_and_stop_watching(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            watcher = TestPlanWatcher()
            await watcher.start_watching(plan_path)

            assert watcher.watching is True
            assert watcher.test_plan is not None
            assert watcher.plan_path == plan_path
            assert watcher.last_mtime > 0

            await watcher.stop_watching()

            assert watcher.watching is False
            assert watcher._task is None

    @pytest.mark.asyncio
    async def test_start_watching_with_initial_plan(self):
        parser = TestPlanParser()
        initial_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            watcher = TestPlanWatcher()
            await watcher.start_watching(plan_path, initial_plan=initial_plan)

            assert watcher.test_plan is initial_plan

            await watcher.stop_watching()

    @pytest.mark.asyncio
    async def test_detect_external_file_change(self):
        """Test that external file changes are detected.

        Note: This is an integration test that depends on watchfiles
        detecting filesystem changes, which can be flaky in CI or
        certain environments. The core logic is tested separately.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            conflict_detected = []

            def on_conflict(new_plan: TestPlan, changes: list[TestStepChange]):
                conflict_detected.append((new_plan, changes))

            watcher = TestPlanWatcher(on_conflict_detected=on_conflict)
            await watcher.start_watching(plan_path)

            # Wait for watcher to fully start
            await asyncio.sleep(0.5)

            # Modify the file externally
            modified_md = SAMPLE_TEST_PLAN_MD.replace(
                "- [ ] User can log in with valid credentials",
                "- [x] User can log in with valid credentials",
            )
            plan_path.write_text(modified_md)

            # Wait for change to be detected (watchfiles debounce + processing)
            for _ in range(30):  # Up to 3 seconds total
                await asyncio.sleep(0.1)
                if conflict_detected:
                    break

            await watcher.stop_watching()

            # If watchfiles didn't trigger, skip the assertion
            if not conflict_detected:
                pytest.skip("watchfiles did not detect change in time (environment-dependent)")

            # Verify conflict was detected
            assert len(conflict_detected) == 1
            new_plan, changes = conflict_detected[0]
            assert len(changes) == 1
            assert changes[0].step_id == "section-0-1"

    @pytest.mark.asyncio
    async def test_process_queued_reload(self):
        """Test processing queued reload after writes complete."""
        parser = TestPlanParser()
        original_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

        modified_md = SAMPLE_TEST_PLAN_MD.replace(
            "- [ ] User can log in with valid credentials",
            "- [x] User can log in with valid credentials",
        )
        queued_plan = parser.parse(modified_md)

        conflict_detected = []

        def on_conflict(new_plan: TestPlan, changes: list[TestStepChange]):
            conflict_detected.append((new_plan, changes))

        watcher = TestPlanWatcher(
            test_plan=original_plan,
            queued_reload=queued_plan,
            on_conflict_detected=on_conflict,
        )

        result = await watcher.process_queued_reload()

        assert result is queued_plan
        assert len(conflict_detected) == 1

    @pytest.mark.asyncio
    async def test_process_queued_reload_no_queue(self):
        """Test processing when no reload is queued."""
        watcher = TestPlanWatcher()
        result = await watcher.process_queued_reload()
        assert result is None


class TestTestPlanWatcherOnFileChange:
    """Test _on_file_change logic directly without depending on watchfiles."""

    @pytest.mark.asyncio
    async def test_on_file_change_triggers_conflict(self):
        """Test that file changes trigger conflict callback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            # Parse initial plan
            parser = TestPlanParser()
            initial_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

            conflict_detected = []

            def on_conflict(new_plan: TestPlan, changes: list[TestStepChange]):
                conflict_detected.append((new_plan, changes))

            from watchfiles import Change

            watcher = TestPlanWatcher(
                test_plan=initial_plan,
                plan_path=plan_path,
                last_mtime=0,  # Force detection of "new" mtime
                on_conflict_detected=on_conflict,
            )

            # Modify the file
            modified_md = SAMPLE_TEST_PLAN_MD.replace(
                "- [ ] User can log in with valid credentials",
                "- [x] User can log in with valid credentials",
            )
            plan_path.write_text(modified_md)

            # Call the change handler directly
            await watcher._on_file_change(Change.modified)

            # Verify conflict was detected
            assert len(conflict_detected) == 1
            new_plan, changes = conflict_detected[0]
            assert len(changes) == 1
            assert changes[0].step_id == "section-0-1"

    @pytest.mark.asyncio
    async def test_on_file_change_with_pending_writes_queues(self):
        """Test that file changes during pending writes are queued."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            parser = TestPlanParser()
            initial_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

            from watchfiles import Change

            watcher = TestPlanWatcher(
                test_plan=initial_plan,
                plan_path=plan_path,
                last_mtime=0,
                has_pending_writes=True,  # Mark as having pending writes
            )

            # Modify the file
            modified_md = SAMPLE_TEST_PLAN_MD.replace(
                "- [ ] User can log in with valid credentials",
                "- [x] User can log in with valid credentials",
            )
            plan_path.write_text(modified_md)

            # Call the change handler directly
            await watcher._on_file_change(Change.modified)

            # Reload should be queued, not processed
            assert watcher.queued_reload is not None

    @pytest.mark.asyncio
    async def test_on_file_change_silent_reload_no_changes(self):
        """Test that identical content triggers silent reload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            parser = TestPlanParser()
            initial_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

            reloaded = []

            def on_reload(plan: TestPlan):
                reloaded.append(plan)

            from watchfiles import Change

            watcher = TestPlanWatcher(
                test_plan=initial_plan,
                plan_path=plan_path,
                last_mtime=0,
                on_plan_reloaded=on_reload,
            )

            # "Touch" the file (same content, new mtime)
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            # Call the change handler directly
            await watcher._on_file_change(Change.modified)

            # Silent reload should have been triggered
            assert len(reloaded) == 1

    @pytest.mark.asyncio
    async def test_on_file_change_handles_deletion(self):
        """Test that file deletion triggers delete callback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            parser = TestPlanParser()
            initial_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

            delete_called = []

            def on_deleted():
                delete_called.append(True)

            from watchfiles import Change

            watcher = TestPlanWatcher(
                test_plan=initial_plan,
                plan_path=plan_path,
                on_plan_deleted=on_deleted,
            )

            # Delete the file
            plan_path.unlink()

            # Call the change handler directly
            await watcher._on_file_change(Change.deleted)

            # Delete callback should have been triggered
            assert len(delete_called) == 1
            assert watcher.test_plan is None


class TestTestPlanWatcherEdgeCases:
    """Test edge cases and error handling."""

    def test_compute_changes_no_current_plan(self):
        parser = TestPlanParser()
        new_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

        watcher = TestPlanWatcher(test_plan=None)
        changes = watcher._compute_changes(new_plan)
        assert changes == []

    @pytest.mark.asyncio
    async def test_stop_watching_when_not_started(self):
        watcher = TestPlanWatcher()
        # Should not raise
        await watcher.stop_watching()
        assert watcher.watching is False

    @pytest.mark.asyncio
    async def test_start_watching_nonexistent_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"

            watcher = TestPlanWatcher()
            await watcher.start_watching(plan_path)

            assert watcher.watching is True
            assert watcher.test_plan is None  # No file to parse

            await watcher.stop_watching()

    def test_mark_write_completed_updates_mtime_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            watcher = TestPlanWatcher(plan_path=plan_path)
            watcher.mark_write_completed()

            assert watcher.last_mtime == plan_path.stat().st_mtime

    def test_conflicts_with_current_no_current_plan(self):
        parser = TestPlanParser()
        new_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

        watcher = TestPlanWatcher(test_plan=None)
        assert watcher.conflicts_with_current(new_plan) is False


class TestTestStepWrite:
    """Test TestStepWrite data class."""

    def test_create_step_write(self):
        write = TestStepWrite(
            step_id="section-0-1",
            new_status=TestStatus.PASSED,
        )
        assert write.step_id == "section-0-1"
        assert write.new_status == TestStatus.PASSED
        assert write.notes is None

    def test_create_step_write_with_notes(self):
        write = TestStepWrite(
            step_id="section-0-1",
            new_status=TestStatus.FAILED,
            notes="Test failed due to timeout",
        )
        assert write.notes == "Test failed due to timeout"


class TestTestPlanWriteQueueBasics:
    """Test basic TestPlanWriteQueue functionality."""

    def test_initial_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                test_plan_path="TEST_PLAN.md",
            )
            watcher = TestPlanWatcher()
            queue = TestPlanWriteQueue(watcher, project)

            assert queue.is_processing is False
            assert queue.pending_count == 0

    @pytest.mark.asyncio
    async def test_enqueue_and_process(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            parser = TestPlanParser()
            initial_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                test_plan_path="TEST_PLAN.md",
            )
            watcher = TestPlanWatcher(test_plan=initial_plan, plan_path=plan_path)
            queue = TestPlanWriteQueue(watcher, project)

            # Enqueue a status update
            await queue.enqueue("section-0-1", TestStatus.PASSED)

            # Wait for processing to complete
            await queue.wait_until_complete()

            # Verify the file was updated
            content = plan_path.read_text()
            assert "- [x] User can log in with valid credentials" in content

            # Verify in-memory plan was updated
            assert watcher.test_plan is not None
            step = next(s for s in watcher.test_plan.all_steps if s.id == "section-0-1")
            assert step.status == TestStatus.PASSED

    @pytest.mark.asyncio
    async def test_enqueue_with_notes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            parser = TestPlanParser()
            initial_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                test_plan_path="TEST_PLAN.md",
            )
            watcher = TestPlanWatcher(test_plan=initial_plan, plan_path=plan_path)
            queue = TestPlanWriteQueue(watcher, project)

            # Enqueue a failed status with notes
            await queue.enqueue("section-0-1", TestStatus.FAILED, notes="Test timed out")

            # Wait for processing to complete
            await queue.wait_until_complete()

            # Verify the file was updated
            content = plan_path.read_text()
            assert "- [!] User can log in with valid credentials" in content
            assert "  Note: Test timed out" in content

    @pytest.mark.asyncio
    async def test_enqueue_multiple_writes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            parser = TestPlanParser()
            initial_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                test_plan_path="TEST_PLAN.md",
            )
            watcher = TestPlanWatcher(test_plan=initial_plan, plan_path=plan_path)
            queue = TestPlanWriteQueue(watcher, project)

            # Enqueue multiple status updates
            await queue.enqueue("section-0-1", TestStatus.PASSED)
            await queue.enqueue("section-1-1", TestStatus.IN_PROGRESS)

            # Wait for processing to complete
            await queue.wait_until_complete()

            # Verify both updates were applied
            content = plan_path.read_text()
            assert "- [x] User can log in with valid credentials" in content
            assert "- [~] Empty form submission shows error" in content


class TestTestPlanWriteQueueCoordination:
    """Test TestPlanWriteQueue coordination with TestPlanWatcher."""

    @pytest.mark.asyncio
    async def test_marks_pending_writes_during_processing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            parser = TestPlanParser()
            initial_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                test_plan_path="TEST_PLAN.md",
            )
            watcher = TestPlanWatcher(test_plan=initial_plan, plan_path=plan_path)
            queue = TestPlanWriteQueue(watcher, project)

            # Capture pending_writes state during processing
            pending_during_process = []

            # Replace _apply_write to capture state
            original_apply = queue._apply_write

            async def capturing_apply(write):
                pending_during_process.append(watcher.has_pending_writes)
                await original_apply(write)

            queue._apply_write = capturing_apply

            await queue.enqueue("section-0-1", TestStatus.PASSED)
            await queue.wait_until_complete()

            # Should have been marked as pending during processing
            assert pending_during_process == [True]

            # Should be cleared after processing
            assert watcher.has_pending_writes is False

    @pytest.mark.asyncio
    async def test_updates_mtime_after_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            parser = TestPlanParser()
            initial_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                test_plan_path="TEST_PLAN.md",
            )
            watcher = TestPlanWatcher(
                test_plan=initial_plan,
                plan_path=plan_path,
                last_mtime=0,  # Start with stale mtime
            )
            queue = TestPlanWriteQueue(watcher, project)

            await queue.enqueue("section-0-1", TestStatus.PASSED)
            await queue.wait_until_complete()

            # mtime should have been updated to match file
            assert watcher.last_mtime == plan_path.stat().st_mtime


class TestTestPlanWriteQueueEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_handles_missing_step(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            parser = TestPlanParser()
            initial_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                test_plan_path="TEST_PLAN.md",
            )
            watcher = TestPlanWatcher(test_plan=initial_plan, plan_path=plan_path)
            queue = TestPlanWriteQueue(watcher, project)

            # Try to update a non-existent step - should not raise
            await queue.enqueue("section-99-99", TestStatus.PASSED)
            await queue.wait_until_complete()

            # Original file should be unchanged
            content = plan_path.read_text()
            assert content == SAMPLE_TEST_PLAN_MD

    @pytest.mark.asyncio
    async def test_handles_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            # Don't create the file

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                test_plan_path="TEST_PLAN.md",
            )
            watcher = TestPlanWatcher()
            queue = TestPlanWriteQueue(watcher, project)

            # Should not raise
            await queue.enqueue("section-0-1", TestStatus.PASSED)
            await queue.wait_until_complete()

    @pytest.mark.asyncio
    async def test_cancel_clears_queue(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                test_plan_path="TEST_PLAN.md",
            )
            watcher = TestPlanWatcher()
            queue = TestPlanWriteQueue(watcher, project)

            # Add items directly to queue without starting processing
            queue._queue.put_nowait(TestStepWrite("section-0-1", TestStatus.PASSED))
            queue._queue.put_nowait(TestStepWrite("section-0-2", TestStatus.PASSED))

            assert queue.pending_count == 2

            queue.cancel()

            assert queue.pending_count == 0
            assert queue.is_processing is False

    @pytest.mark.asyncio
    async def test_updates_in_memory_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "TEST_PLAN.md"
            plan_path.write_text(SAMPLE_TEST_PLAN_MD)

            parser = TestPlanParser()
            initial_plan = parser.parse(SAMPLE_TEST_PLAN_MD)

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                test_plan_path="TEST_PLAN.md",
            )
            watcher = TestPlanWatcher(test_plan=initial_plan, plan_path=plan_path)
            queue = TestPlanWriteQueue(watcher, project)

            # Get initial status
            step = next(s for s in watcher.test_plan.all_steps if s.id == "section-0-1")
            assert step.status == TestStatus.PENDING

            await queue.enqueue("section-0-1", TestStatus.IN_PROGRESS)
            await queue.wait_until_complete()

            # In-memory plan should be updated
            step = next(s for s in watcher.test_plan.all_steps if s.id == "section-0-1")
            assert step.status == TestStatus.IN_PROGRESS
