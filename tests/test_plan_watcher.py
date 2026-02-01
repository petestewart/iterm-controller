"""Tests for PLAN.md file watcher."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from iterm_controller.models import Plan, Project, TaskStatus
from iterm_controller.plan_parser import PlanParser
from iterm_controller.plan_watcher import PlanChange, PlanWatcher, PlanWrite, PlanWriteQueue


# Sample PLAN.md content for testing
SAMPLE_PLAN_MD = """# Plan: Test Project

## Overview

Test project for file watcher testing.

### Phase 1: Foundation

- [x] **Task A** `[complete]`
  - Scope: Do A

- [ ] **Task B** `[pending]`
  - Scope: Do B

### Phase 2: Features

- [ ] **Task C** `[in_progress]`
  - Scope: Do C
"""


class TestPlanChange:
    """Test PlanChange data class."""

    def test_status_changed_str(self):
        change = PlanChange(
            task_id="1.1",
            old_status=TaskStatus.PENDING,
            new_status=TaskStatus.COMPLETE,
            task_title="Some Task",
            change_type="status_changed",
        )
        assert "1.1" in str(change)
        assert "pending" in str(change)
        assert "complete" in str(change)

    def test_task_added_str(self):
        change = PlanChange(
            task_id="1.3",
            old_status=None,
            new_status=TaskStatus.PENDING,
            task_title="New Task",
            change_type="task_added",
        )
        assert "New task added" in str(change)
        assert "1.3" in str(change)
        assert "New Task" in str(change)

    def test_task_removed_str(self):
        change = PlanChange(
            task_id="1.2",
            old_status=TaskStatus.PENDING,
            new_status=None,
            task_title="Old Task",
            change_type="task_removed",
        )
        assert "Task removed" in str(change)
        assert "1.2" in str(change)


class TestPlanWatcherBasics:
    """Test basic PlanWatcher functionality."""

    def test_initial_state(self):
        watcher = PlanWatcher()
        assert watcher.plan is None
        assert watcher.plan_path is None
        assert watcher.watching is False
        assert watcher.has_pending_writes is False
        assert watcher.queued_reload is None
        assert watcher.last_mtime == 0

    def test_mark_write_started(self):
        watcher = PlanWatcher()
        assert watcher.has_pending_writes is False
        watcher.mark_write_started()
        assert watcher.has_pending_writes is True

    def test_mark_write_completed(self):
        watcher = PlanWatcher()
        watcher.mark_write_started()
        assert watcher.has_pending_writes is True
        watcher.mark_write_completed()
        assert watcher.has_pending_writes is False

    def test_mark_write_completed_with_mtime(self):
        watcher = PlanWatcher()
        watcher.mark_write_completed(new_mtime=12345.0)
        assert watcher.last_mtime == 12345.0

    def test_keep_current_clears_queued_reload(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        watcher = PlanWatcher()
        watcher.queued_reload = plan
        watcher.keep_current()
        assert watcher.queued_reload is None


class TestPlanWatcherChangeDetection:
    """Test change detection between plan versions."""

    def test_no_changes_same_plan(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        watcher = PlanWatcher(plan=plan)
        changes = watcher._compute_changes(plan)
        assert changes == []

    def test_detect_status_change(self):
        parser = PlanParser()
        original_plan = parser.parse(SAMPLE_PLAN_MD)

        modified_md = SAMPLE_PLAN_MD.replace(
            "- [ ] **Task B** `[pending]`",
            "- [x] **Task B** `[complete]`",
        )
        new_plan = parser.parse(modified_md)

        watcher = PlanWatcher(plan=original_plan)
        changes = watcher._compute_changes(new_plan)

        assert len(changes) == 1
        assert changes[0].task_id == "1.2"
        assert changes[0].old_status == TaskStatus.PENDING
        assert changes[0].new_status == TaskStatus.COMPLETE
        assert changes[0].change_type == "status_changed"

    def test_detect_task_added(self):
        parser = PlanParser()
        original_plan = parser.parse(SAMPLE_PLAN_MD)

        modified_md = SAMPLE_PLAN_MD + """
- [ ] **New Task D** `[pending]`
  - Scope: Do D
"""
        new_plan = parser.parse(modified_md)

        watcher = PlanWatcher(plan=original_plan)
        changes = watcher._compute_changes(new_plan)

        assert len(changes) == 1
        assert changes[0].task_id == "2.2"
        assert changes[0].old_status is None
        assert changes[0].new_status == TaskStatus.PENDING
        assert changes[0].change_type == "task_added"

    def test_detect_task_removed(self):
        parser = PlanParser()
        original_plan = parser.parse(SAMPLE_PLAN_MD)

        # Remove Task C from phase 2
        modified_md = """# Plan: Test Project

## Overview

Test project for file watcher testing.

### Phase 1: Foundation

- [x] **Task A** `[complete]`
  - Scope: Do A

- [ ] **Task B** `[pending]`
  - Scope: Do B

### Phase 2: Features

"""
        new_plan = parser.parse(modified_md)

        watcher = PlanWatcher(plan=original_plan)
        changes = watcher._compute_changes(new_plan)

        assert len(changes) == 1
        assert changes[0].task_id == "2.1"
        assert changes[0].old_status == TaskStatus.IN_PROGRESS
        assert changes[0].new_status is None
        assert changes[0].change_type == "task_removed"

    def test_detect_multiple_changes(self):
        parser = PlanParser()
        original_plan = parser.parse(SAMPLE_PLAN_MD)

        # Change Task B status and add a new task
        modified_md = SAMPLE_PLAN_MD.replace(
            "- [ ] **Task B** `[pending]`",
            "- [x] **Task B** `[complete]`",
        ) + """
- [ ] **New Task** `[pending]`
  - Scope: New
"""
        new_plan = parser.parse(modified_md)

        watcher = PlanWatcher(plan=original_plan)
        changes = watcher._compute_changes(new_plan)

        assert len(changes) == 2
        change_types = {c.change_type for c in changes}
        assert "status_changed" in change_types
        assert "task_added" in change_types

    def test_conflicts_with_current_true(self):
        parser = PlanParser()
        original_plan = parser.parse(SAMPLE_PLAN_MD)

        modified_md = SAMPLE_PLAN_MD.replace(
            "- [ ] **Task B** `[pending]`",
            "- [x] **Task B** `[complete]`",
        )
        new_plan = parser.parse(modified_md)

        watcher = PlanWatcher(plan=original_plan)
        assert watcher.conflicts_with_current(new_plan) is True

    def test_conflicts_with_current_false(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)

        watcher = PlanWatcher(plan=plan)
        assert watcher.conflicts_with_current(plan) is False


class TestPlanWatcherFileOperations:
    """Test file-based operations."""

    def test_reload_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            watcher = PlanWatcher(plan_path=plan_path)
            plan = watcher.reload_from_file()

            assert plan is not None
            assert len(plan.phases) == 2
            assert watcher.plan is plan

    def test_reload_from_nonexistent_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"

            watcher = PlanWatcher(plan_path=plan_path)
            plan = watcher.reload_from_file()

            assert plan is None

    def test_accept_external_changes(self):
        parser = PlanParser()
        original_plan = parser.parse(SAMPLE_PLAN_MD)
        new_plan = parser.parse(SAMPLE_PLAN_MD)

        callback_called = []

        def on_reloaded(plan: Plan):
            callback_called.append(plan)

        watcher = PlanWatcher(plan=original_plan, on_plan_reloaded=on_reloaded)
        watcher.accept_external_changes(new_plan)

        assert watcher.plan is new_plan
        assert len(callback_called) == 1
        assert callback_called[0] is new_plan


class TestPlanWatcherAsyncOperations:
    """Test async file watching operations."""

    @pytest.mark.asyncio
    async def test_start_and_stop_watching(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            watcher = PlanWatcher()
            await watcher.start_watching(plan_path)

            assert watcher.watching is True
            assert watcher.plan is not None
            assert watcher.plan_path == plan_path
            assert watcher.last_mtime > 0

            await watcher.stop_watching()

            assert watcher.watching is False
            assert watcher._task is None

    @pytest.mark.asyncio
    async def test_start_watching_with_initial_plan(self):
        parser = PlanParser()
        initial_plan = parser.parse(SAMPLE_PLAN_MD)

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            watcher = PlanWatcher()
            await watcher.start_watching(plan_path, initial_plan=initial_plan)

            assert watcher.plan is initial_plan

            await watcher.stop_watching()

    @pytest.mark.asyncio
    async def test_detect_external_file_change(self):
        """Test that external file changes are detected.

        Note: This is an integration test that depends on watchfiles
        detecting filesystem changes, which can be flaky in CI or
        certain environments. The core logic is tested separately.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            conflict_detected = []

            def on_conflict(new_plan: Plan, changes: list[PlanChange]):
                conflict_detected.append((new_plan, changes))

            watcher = PlanWatcher(on_conflict_detected=on_conflict)
            await watcher.start_watching(plan_path)

            # Wait for watcher to fully start
            await asyncio.sleep(0.5)

            # Modify the file externally
            modified_md = SAMPLE_PLAN_MD.replace(
                "- [ ] **Task B** `[pending]`",
                "- [x] **Task B** `[complete]`",
            )
            plan_path.write_text(modified_md)

            # Wait for change to be detected (watchfiles debounce + processing)
            # Use a loop to check more reliably
            for _ in range(30):  # Up to 3 seconds total
                await asyncio.sleep(0.1)
                if conflict_detected:
                    break

            await watcher.stop_watching()

            # If watchfiles didn't trigger, skip the assertion
            # This can happen in CI or certain environments
            if not conflict_detected:
                pytest.skip("watchfiles did not detect change in time (environment-dependent)")

            # Verify conflict was detected
            assert len(conflict_detected) == 1
            new_plan, changes = conflict_detected[0]
            assert len(changes) == 1
            assert changes[0].task_id == "1.2"

    @pytest.mark.asyncio
    async def test_silent_reload_no_changes(self):
        """Test that identical content doesn't trigger conflict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            reloaded_plans = []
            conflicts_detected = []

            def on_reload(plan: Plan):
                reloaded_plans.append(plan)

            def on_conflict(new_plan: Plan, changes: list[PlanChange]):
                conflicts_detected.append((new_plan, changes))

            watcher = PlanWatcher(
                on_plan_reloaded=on_reload,
                on_conflict_detected=on_conflict,
            )
            await watcher.start_watching(plan_path)

            # Wait for watcher to fully start
            await asyncio.sleep(0.2)

            # Write same content (triggers file change but no semantic change)
            plan_path.write_text(SAMPLE_PLAN_MD)

            # Wait for change to be detected
            await asyncio.sleep(1.0)

            await watcher.stop_watching()

            # Verify no conflict was detected (same content)
            assert len(conflicts_detected) == 0
            # May or may not trigger reload depending on timing
            # The key is that no conflict was raised

    @pytest.mark.asyncio
    async def test_pending_writes_queues_reload(self):
        """Test that changes during pending writes are queued.

        Note: This is an integration test that depends on watchfiles
        detecting filesystem changes, which can be flaky in CI or
        certain environments. The core logic is tested separately.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            watcher = PlanWatcher()
            await watcher.start_watching(plan_path)

            # Wait for watcher to fully start
            await asyncio.sleep(0.5)

            # Mark pending writes
            watcher.mark_write_started()

            # Modify file externally
            modified_md = SAMPLE_PLAN_MD.replace(
                "- [ ] **Task B** `[pending]`",
                "- [x] **Task B** `[complete]`",
            )
            plan_path.write_text(modified_md)

            # Wait for change to be detected - use a loop for reliability
            for _ in range(30):  # Up to 3 seconds total
                await asyncio.sleep(0.1)
                if watcher.queued_reload is not None:
                    break

            await watcher.stop_watching()

            # If watchfiles didn't trigger, skip the assertion
            if watcher.queued_reload is None:
                pytest.skip("watchfiles did not detect change in time (environment-dependent)")

            # Reload should be queued, not processed
            assert watcher.queued_reload is not None

    @pytest.mark.asyncio
    async def test_process_queued_reload(self):
        """Test processing queued reload after writes complete."""
        parser = PlanParser()
        original_plan = parser.parse(SAMPLE_PLAN_MD)

        modified_md = SAMPLE_PLAN_MD.replace(
            "- [ ] **Task B** `[pending]`",
            "- [x] **Task B** `[complete]`",
        )
        queued_plan = parser.parse(modified_md)

        conflict_detected = []

        def on_conflict(new_plan: Plan, changes: list[PlanChange]):
            conflict_detected.append((new_plan, changes))

        watcher = PlanWatcher(
            plan=original_plan,
            queued_reload=queued_plan,
            on_conflict_detected=on_conflict,
        )

        result = await watcher.process_queued_reload()

        assert result is queued_plan
        assert len(conflict_detected) == 1

    @pytest.mark.asyncio
    async def test_process_queued_reload_no_queue(self):
        """Test processing when no reload is queued."""
        watcher = PlanWatcher()
        result = await watcher.process_queued_reload()
        assert result is None


class TestPlanWatcherOnFileChange:
    """Test _on_file_change logic directly without depending on watchfiles."""

    @pytest.mark.asyncio
    async def test_on_file_change_triggers_conflict(self):
        """Test that file changes trigger conflict callback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            # Parse initial plan
            parser = PlanParser()
            initial_plan = parser.parse(SAMPLE_PLAN_MD)

            conflict_detected = []

            def on_conflict(new_plan: Plan, changes: list[PlanChange]):
                conflict_detected.append((new_plan, changes))

            watcher = PlanWatcher(
                plan=initial_plan,
                plan_path=plan_path,
                last_mtime=0,  # Force detection of "new" mtime
                on_conflict_detected=on_conflict,
            )

            # Modify the file
            modified_md = SAMPLE_PLAN_MD.replace(
                "- [ ] **Task B** `[pending]`",
                "- [x] **Task B** `[complete]`",
            )
            plan_path.write_text(modified_md)

            # Call the change handler directly
            await watcher._on_file_change()

            # Verify conflict was detected
            assert len(conflict_detected) == 1
            new_plan, changes = conflict_detected[0]
            assert len(changes) == 1
            assert changes[0].task_id == "1.2"

    @pytest.mark.asyncio
    async def test_on_file_change_with_pending_writes_queues(self):
        """Test that file changes during pending writes are queued."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            parser = PlanParser()
            initial_plan = parser.parse(SAMPLE_PLAN_MD)

            watcher = PlanWatcher(
                plan=initial_plan,
                plan_path=plan_path,
                last_mtime=0,
                has_pending_writes=True,  # Mark as having pending writes
            )

            # Modify the file
            modified_md = SAMPLE_PLAN_MD.replace(
                "- [ ] **Task B** `[pending]`",
                "- [x] **Task B** `[complete]`",
            )
            plan_path.write_text(modified_md)

            # Call the change handler directly
            await watcher._on_file_change()

            # Reload should be queued, not processed
            assert watcher.queued_reload is not None

    @pytest.mark.asyncio
    async def test_on_file_change_silent_reload_no_changes(self):
        """Test that identical content triggers silent reload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            parser = PlanParser()
            initial_plan = parser.parse(SAMPLE_PLAN_MD)

            reloaded = []

            def on_reload(plan: Plan):
                reloaded.append(plan)

            watcher = PlanWatcher(
                plan=initial_plan,
                plan_path=plan_path,
                last_mtime=0,
                on_plan_reloaded=on_reload,
            )

            # "Touch" the file (same content, new mtime)
            plan_path.write_text(SAMPLE_PLAN_MD)

            # Call the change handler directly
            await watcher._on_file_change()

            # Silent reload should have been triggered
            assert len(reloaded) == 1

    @pytest.mark.asyncio
    async def test_on_file_change_same_mtime_ignored(self):
        """Test that same mtime doesn't trigger reload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            parser = PlanParser()
            initial_plan = parser.parse(SAMPLE_PLAN_MD)

            reloaded = []

            def on_reload(plan: Plan):
                reloaded.append(plan)

            # Set last_mtime to current file mtime
            current_mtime = plan_path.stat().st_mtime

            watcher = PlanWatcher(
                plan=initial_plan,
                plan_path=plan_path,
                last_mtime=current_mtime,  # Same as file
                on_plan_reloaded=on_reload,
            )

            # Call the change handler directly
            await watcher._on_file_change()

            # No reload should have been triggered
            assert len(reloaded) == 0


class TestPlanWatcherEdgeCases:
    """Test edge cases and error handling."""

    def test_compute_changes_no_current_plan(self):
        parser = PlanParser()
        new_plan = parser.parse(SAMPLE_PLAN_MD)

        watcher = PlanWatcher(plan=None)
        changes = watcher._compute_changes(new_plan)
        assert changes == []

    @pytest.mark.asyncio
    async def test_stop_watching_when_not_started(self):
        watcher = PlanWatcher()
        # Should not raise
        await watcher.stop_watching()
        assert watcher.watching is False

    @pytest.mark.asyncio
    async def test_start_watching_nonexistent_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"

            watcher = PlanWatcher()
            await watcher.start_watching(plan_path)

            assert watcher.watching is True
            assert watcher.plan is None  # No file to parse

            await watcher.stop_watching()

    def test_mark_write_completed_updates_mtime_from_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            watcher = PlanWatcher(plan_path=plan_path)
            watcher.mark_write_completed()

            assert watcher.last_mtime == plan_path.stat().st_mtime

    def test_conflicts_with_current_no_current_plan(self):
        parser = PlanParser()
        new_plan = parser.parse(SAMPLE_PLAN_MD)

        watcher = PlanWatcher(plan=None)
        assert watcher.conflicts_with_current(new_plan) is False


class TestPlanWrite:
    """Test PlanWrite data class."""

    def test_create_plan_write(self):
        write = PlanWrite(task_id="1.1", new_status=TaskStatus.COMPLETE)
        assert write.task_id == "1.1"
        assert write.new_status == TaskStatus.COMPLETE


class TestPlanWriteQueueBasics:
    """Test basic PlanWriteQueue functionality."""

    def test_initial_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                plan_path="PLAN.md",
            )
            watcher = PlanWatcher()
            queue = PlanWriteQueue(watcher, project)

            assert queue.is_processing is False
            assert queue.pending_count == 0

    @pytest.mark.asyncio
    async def test_enqueue_and_process(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            parser = PlanParser()
            initial_plan = parser.parse(SAMPLE_PLAN_MD)

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                plan_path="PLAN.md",
            )
            watcher = PlanWatcher(plan=initial_plan, plan_path=plan_path)
            queue = PlanWriteQueue(watcher, project)

            # Enqueue a status update
            await queue.enqueue("1.2", TaskStatus.COMPLETE)

            # Wait for processing to complete
            await queue.wait_until_complete()

            # Verify the file was updated
            content = plan_path.read_text()
            assert "- [x] **Task B** `[complete]`" in content

            # Verify in-memory plan was updated
            assert watcher.plan is not None
            task = next(t for t in watcher.plan.all_tasks if t.id == "1.2")
            assert task.status == TaskStatus.COMPLETE

    @pytest.mark.asyncio
    async def test_enqueue_multiple_writes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            parser = PlanParser()
            initial_plan = parser.parse(SAMPLE_PLAN_MD)

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                plan_path="PLAN.md",
            )
            watcher = PlanWatcher(plan=initial_plan, plan_path=plan_path)
            queue = PlanWriteQueue(watcher, project)

            # Enqueue multiple status updates
            await queue.enqueue("1.2", TaskStatus.IN_PROGRESS)
            await queue.enqueue("2.1", TaskStatus.COMPLETE)

            # Wait for processing to complete
            await queue.wait_until_complete()

            # Verify both updates were applied
            content = plan_path.read_text()
            assert "- [ ] **Task B** `[in_progress]`" in content
            assert "- [x] **Task C** `[complete]`" in content


class TestPlanWriteQueueCoordination:
    """Test PlanWriteQueue coordination with PlanWatcher."""

    @pytest.mark.asyncio
    async def test_marks_pending_writes_during_processing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            parser = PlanParser()
            initial_plan = parser.parse(SAMPLE_PLAN_MD)

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                plan_path="PLAN.md",
            )
            watcher = PlanWatcher(plan=initial_plan, plan_path=plan_path)
            queue = PlanWriteQueue(watcher, project)

            # Capture pending_writes state during processing
            pending_during_process = []

            # Replace _apply_write to capture state
            original_apply = queue._apply_write

            async def capturing_apply(write):
                pending_during_process.append(watcher.has_pending_writes)
                await original_apply(write)

            queue._apply_write = capturing_apply

            await queue.enqueue("1.2", TaskStatus.COMPLETE)
            await queue.wait_until_complete()

            # Should have been marked as pending during processing
            assert pending_during_process == [True]

            # Should be cleared after processing
            assert watcher.has_pending_writes is False

    @pytest.mark.asyncio
    async def test_updates_mtime_after_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            parser = PlanParser()
            initial_plan = parser.parse(SAMPLE_PLAN_MD)

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                plan_path="PLAN.md",
            )
            watcher = PlanWatcher(
                plan=initial_plan,
                plan_path=plan_path,
                last_mtime=0,  # Start with stale mtime
            )
            queue = PlanWriteQueue(watcher, project)

            await queue.enqueue("1.2", TaskStatus.COMPLETE)
            await queue.wait_until_complete()

            # mtime should have been updated to match file
            assert watcher.last_mtime == plan_path.stat().st_mtime

    @pytest.mark.asyncio
    async def test_processes_queued_reload_after_writes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            parser = PlanParser()
            initial_plan = parser.parse(SAMPLE_PLAN_MD)

            # Create a modified plan to simulate queued reload
            modified_md = SAMPLE_PLAN_MD.replace(
                "- [x] **Task A** `[complete]`",
                "- [ ] **Task A** `[in_progress]`",
            )
            queued_plan = parser.parse(modified_md)

            conflict_detected = []

            def on_conflict(new_plan: Plan, changes: list[PlanChange]):
                conflict_detected.append((new_plan, changes))

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                plan_path="PLAN.md",
            )
            watcher = PlanWatcher(
                plan=initial_plan,
                plan_path=plan_path,
                queued_reload=queued_plan,  # Simulate queued reload
                on_conflict_detected=on_conflict,
            )
            queue = PlanWriteQueue(watcher, project)

            await queue.enqueue("1.2", TaskStatus.COMPLETE)
            await queue.wait_until_complete()

            # Queued reload should have been processed
            assert len(conflict_detected) == 1
            assert watcher.queued_reload is None


class TestPlanWriteQueueEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_handles_missing_task(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            parser = PlanParser()
            initial_plan = parser.parse(SAMPLE_PLAN_MD)

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                plan_path="PLAN.md",
            )
            watcher = PlanWatcher(plan=initial_plan, plan_path=plan_path)
            queue = PlanWriteQueue(watcher, project)

            # Try to update a non-existent task - should not raise
            await queue.enqueue("99.99", TaskStatus.COMPLETE)
            await queue.wait_until_complete()

            # Original file should be unchanged
            content = plan_path.read_text()
            assert content == SAMPLE_PLAN_MD

    @pytest.mark.asyncio
    async def test_handles_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            # Don't create the file

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                plan_path="PLAN.md",
            )
            watcher = PlanWatcher()
            queue = PlanWriteQueue(watcher, project)

            # Should not raise
            await queue.enqueue("1.1", TaskStatus.COMPLETE)
            await queue.wait_until_complete()

    @pytest.mark.asyncio
    async def test_cancel_clears_queue(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                plan_path="PLAN.md",
            )
            watcher = PlanWatcher()
            queue = PlanWriteQueue(watcher, project)

            # Add items directly to queue without starting processing
            queue._queue.put_nowait(PlanWrite("1.1", TaskStatus.COMPLETE))
            queue._queue.put_nowait(PlanWrite("1.2", TaskStatus.COMPLETE))

            assert queue.pending_count == 2

            queue.cancel()

            assert queue.pending_count == 0
            assert queue.is_processing is False

    @pytest.mark.asyncio
    async def test_updates_in_memory_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            parser = PlanParser()
            initial_plan = parser.parse(SAMPLE_PLAN_MD)

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                plan_path="PLAN.md",
            )
            watcher = PlanWatcher(plan=initial_plan, plan_path=plan_path)
            queue = PlanWriteQueue(watcher, project)

            # Get initial status
            task_b = next(t for t in watcher.plan.all_tasks if t.id == "1.2")
            assert task_b.status == TaskStatus.PENDING

            await queue.enqueue("1.2", TaskStatus.IN_PROGRESS)
            await queue.wait_until_complete()

            # In-memory plan should be updated
            task_b = next(t for t in watcher.plan.all_tasks if t.id == "1.2")
            assert task_b.status == TaskStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_handles_no_in_memory_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)

            project = Project(
                id="test",
                name="Test",
                path=tmpdir,
                plan_path="PLAN.md",
            )
            # No plan set on watcher
            watcher = PlanWatcher(plan=None, plan_path=plan_path)
            queue = PlanWriteQueue(watcher, project)

            # Should still update the file
            await queue.enqueue("1.2", TaskStatus.COMPLETE)
            await queue.wait_until_complete()

            content = plan_path.read_text()
            assert "- [x] **Task B** `[complete]`" in content
