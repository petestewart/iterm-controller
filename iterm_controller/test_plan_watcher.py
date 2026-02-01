"""File watching for TEST_PLAN.md changes.

Watches TEST_PLAN.md files for external changes using watchfiles.
Detects changes within 1 second and triggers reload or conflict resolution.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Any

from watchfiles import awatch, Change

from .exceptions import TestPlanParseError, TestPlanWriteError, record_error
from .models import TestPlan, TestStatus, TestStep, Project
from .test_plan_parser import TestPlanParser, TestPlanUpdater

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .screens.modals import TestPlanConflictModal


@dataclass
class TestStepChange:
    """Represents a change detected between two test plan versions."""

    step_id: str
    old_status: TestStatus | None
    new_status: TestStatus | None
    step_description: str
    change_type: str  # "status_changed", "step_added", "step_removed"

    def __str__(self) -> str:
        if self.change_type == "status_changed":
            old = self.old_status.value if self.old_status else "none"
            new = self.new_status.value if self.new_status else "none"
            return f"Step {self.step_id} status: {old} → {new}"
        elif self.change_type == "step_added":
            return f"New step added: {self.step_id} {self.step_description}"
        elif self.change_type == "step_removed":
            return f"Step removed: {self.step_id}"
        return f"Unknown change: {self.step_id}"


@dataclass
class TestPlanWatcher:
    """Watches TEST_PLAN.md for external changes.

    Provides:
    - Async file watching using watchfiles
    - Change detection comparing in-memory plan with file
    - Conflict resolution when external changes conflict with pending writes
    - Silent reload when no conflicts exist
    """

    test_plan: TestPlan | None = None
    plan_path: Path | None = None
    watching: bool = False
    has_pending_writes: bool = False
    queued_reload: TestPlan | None = None
    last_mtime: float = 0

    # Callbacks
    on_plan_reloaded: Callable[[TestPlan], None] | None = None
    on_plan_deleted: Callable[[], None] | None = None
    on_plan_created: Callable[[TestPlan], None] | None = None
    on_conflict_detected: Callable[[TestPlan, list[TestStepChange]], None] | None = None

    # Internal state
    _task: asyncio.Task | None = field(default=None, repr=False)
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    async def start_watching(self, path: Path, initial_plan: TestPlan | None = None) -> None:
        """Start watching a TEST_PLAN.md file.

        Args:
            path: Path to the TEST_PLAN.md file to watch
            initial_plan: Optional initial plan state (avoids immediate re-parse)
        """
        self.plan_path = path
        self.watching = True
        self._stop_event.clear()

        # Initialize with current file state
        if initial_plan:
            self.test_plan = initial_plan
        elif path.exists():
            parser = TestPlanParser()
            self.test_plan = parser.parse_file(path)

        # Track initial mtime
        if path.exists():
            self.last_mtime = path.stat().st_mtime

        # Start the watch loop
        self._task = asyncio.create_task(self._watch_loop())

    async def stop_watching(self) -> None:
        """Stop watching the TEST_PLAN.md file."""
        self.watching = False
        self._stop_event.set()

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _watch_loop(self) -> None:
        """Main watch loop that monitors file changes."""
        if self.plan_path is None:
            return

        # Don't try to watch if the parent directory doesn't exist
        if not self.plan_path.parent.exists():
            logger.debug(
                "Parent directory %s does not exist, skipping watch",
                self.plan_path.parent
            )
            return

        try:
            async for changes in awatch(
                self.plan_path.parent,
                stop_event=self._stop_event,
                debounce=100,  # 100ms debounce for rapid changes
                rust_timeout=500,  # Check every 500ms
            ):
                if not self.watching:
                    break

                for change_type, change_path in changes:
                    if Path(change_path) == self.plan_path:
                        await self._on_file_change(change_type)
        except asyncio.CancelledError:
            pass

    async def _on_file_change(self, change_type: Change) -> None:
        """Handle file change event."""
        if self.plan_path is None:
            logger.debug("Plan path is None, skipping change")
            return

        # Handle deletion
        if change_type == Change.deleted or not self.plan_path.exists():
            self.test_plan = None
            logger.info("TEST_PLAN.md was deleted")
            if self.on_plan_deleted:
                self.on_plan_deleted()
            return

        # Check if this is our own write
        try:
            current_mtime = self.plan_path.stat().st_mtime
        except OSError as e:
            logger.warning("Failed to stat TEST_PLAN.md: %s", e)
            return

        if current_mtime == self.last_mtime:
            return
        self.last_mtime = current_mtime

        # Parse new content
        parser = TestPlanParser()
        try:
            new_plan = parser.parse_file(self.plan_path)
            logger.debug("Parsed external change to TEST_PLAN.md")
        except TestPlanParseError as e:
            # If parsing fails, log and ignore this change
            logger.warning("Failed to parse external TEST_PLAN.md change: %s", e)
            record_error(e)
            return
        except Exception as e:
            logger.error("Unexpected error parsing TEST_PLAN.md: %s", e)
            record_error(e)
            return

        if self.has_pending_writes:
            # Queue reload for after our write completes
            self.queued_reload = new_plan
            logger.debug("Queued TEST_PLAN.md reload (pending writes)")
        elif self.test_plan is None:
            # File was created (no previous plan)
            self.test_plan = new_plan
            logger.info("TEST_PLAN.md was created")
            if self.on_plan_created:
                self.on_plan_created(new_plan)
            elif self.on_plan_reloaded:
                # Fall back to reload callback if no creation callback
                self.on_plan_reloaded(new_plan)
        else:
            # Check for conflicts
            changes = self._compute_changes(new_plan)
            if changes:
                # Conflict detected
                logger.info(
                    "Detected %d external changes to TEST_PLAN.md", len(changes)
                )
                if self.on_conflict_detected:
                    self.on_conflict_detected(new_plan, changes)
            else:
                # Silent reload (no meaningful changes)
                self.test_plan = new_plan
                logger.debug("Silent reload of TEST_PLAN.md (no status changes)")
                if self.on_plan_reloaded:
                    self.on_plan_reloaded(new_plan)

    def _compute_changes(self, new_plan: TestPlan) -> list[TestStepChange]:
        """Compute list of changes between current and new plan.

        Args:
            new_plan: The newly parsed plan

        Returns:
            List of TestStepChange objects describing the differences
        """
        if self.test_plan is None:
            return []

        changes: list[TestStepChange] = []

        # Build step maps
        current_steps = {s.id: s for s in self.test_plan.all_steps}
        new_steps = {s.id: s for s in new_plan.all_steps}

        # Check for status changes and new steps
        for step_id, new_step in new_steps.items():
            if step_id not in current_steps:
                changes.append(
                    TestStepChange(
                        step_id=step_id,
                        old_status=None,
                        new_status=new_step.status,
                        step_description=new_step.description,
                        change_type="step_added",
                    )
                )
            elif current_steps[step_id].status != new_step.status:
                changes.append(
                    TestStepChange(
                        step_id=step_id,
                        old_status=current_steps[step_id].status,
                        new_status=new_step.status,
                        step_description=new_step.description,
                        change_type="status_changed",
                    )
                )

        # Check for removed steps
        for step_id, current_step in current_steps.items():
            if step_id not in new_steps:
                changes.append(
                    TestStepChange(
                        step_id=step_id,
                        old_status=current_step.status,
                        new_status=None,
                        step_description=current_step.description,
                        change_type="step_removed",
                    )
                )

        return changes

    def conflicts_with_current(self, new_plan: TestPlan) -> bool:
        """Check if new plan conflicts with current state.

        A conflict exists if any step statuses differ between versions.

        Args:
            new_plan: The newly parsed plan

        Returns:
            True if there are conflicts, False otherwise
        """
        return bool(self._compute_changes(new_plan))

    def mark_write_started(self) -> None:
        """Mark that a write operation is starting.

        Call this before writing to TEST_PLAN.md to prevent
        treating our own write as an external change.
        """
        self.has_pending_writes = True

    def mark_write_completed(self, new_mtime: float | None = None) -> None:
        """Mark that a write operation has completed.

        Args:
            new_mtime: Optional new modification time to track
        """
        if new_mtime is not None:
            self.last_mtime = new_mtime
        elif self.plan_path and self.plan_path.exists():
            self.last_mtime = self.plan_path.stat().st_mtime

        self.has_pending_writes = False

    async def process_queued_reload(self) -> TestPlan | None:
        """Process any queued reload after writes complete.

        Returns:
            The queued plan if there was one, None otherwise
        """
        if self.queued_reload:
            queued = self.queued_reload
            self.queued_reload = None

            changes = self._compute_changes(queued)
            if changes and self.on_conflict_detected:
                self.on_conflict_detected(queued, changes)
            else:
                self.test_plan = queued
                if self.on_plan_reloaded:
                    self.on_plan_reloaded(queued)

            return queued
        return None

    def reload_from_file(self) -> TestPlan | None:
        """Force reload the plan from disk.

        Returns:
            The reloaded plan, or None if file doesn't exist

        Raises:
            TestPlanParseError: If the file cannot be read or parsed.
        """
        if self.plan_path is None or not self.plan_path.exists():
            logger.debug("Cannot reload: plan path is None or doesn't exist")
            return None

        parser = TestPlanParser()
        try:
            self.test_plan = parser.parse_file(self.plan_path)
            self.last_mtime = self.plan_path.stat().st_mtime
            logger.info("Reloaded TEST_PLAN.md from %s", self.plan_path)
            return self.test_plan
        except TestPlanParseError:
            raise
        except OSError as e:
            logger.error("Failed to stat TEST_PLAN.md after reload: %s", e)
            record_error(e)
            raise TestPlanParseError(
                f"Failed to access TEST_PLAN.md: {e}",
                file_path=str(self.plan_path),
                cause=e,
            ) from e

    def accept_external_changes(self, new_plan: TestPlan) -> None:
        """Accept external changes and update the current plan.

        Args:
            new_plan: The new plan to accept
        """
        self.test_plan = new_plan
        if self.on_plan_reloaded:
            self.on_plan_reloaded(new_plan)

    def keep_current(self) -> None:
        """Keep current plan and discard external changes.

        This just clears any queued reload without changing the plan.
        """
        self.queued_reload = None

    async def update_step(self, step: TestStep) -> None:
        """Update a step's status in the file.

        This is a convenience method that marks writes, updates the file,
        and refreshes the in-memory plan.

        Args:
            step: The step with updated status and notes.
        """
        if self.plan_path is None:
            logger.warning("Cannot update step: no plan path set")
            return

        self.mark_write_started()
        try:
            updater = TestPlanUpdater()
            updater.update_step_status_in_file(
                self.plan_path, step.id, step.status, step.notes
            )
            # Refresh in-memory plan
            parser = TestPlanParser()
            self.test_plan = parser.parse_file(self.plan_path)
        finally:
            self.mark_write_completed()

    def handle_conflict_resolution(self, result: str, new_plan: TestPlan) -> None:
        """Handle the result of the conflict resolution modal.

        Args:
            result: The modal result ("reload", "keep", or "later")
            new_plan: The new plan that was in conflict
        """
        if result == "reload":
            self.accept_external_changes(new_plan)
        elif result == "keep":
            self.keep_current()
        # "later" means do nothing - the modal was dismissed without action


@dataclass
class TestStepWrite:
    """A pending write operation for TEST_PLAN.md."""

    step_id: str
    new_status: TestStatus
    notes: str | None = None


class TestPlanWriteQueue:
    """Manages pending writes to TEST_PLAN.md with conflict handling.

    This class queues write operations to TEST_PLAN.md and processes them
    in order, coordinating with the TestPlanWatcher to avoid treating
    our own writes as external changes. It also handles conflicts
    that may arise if external changes occur during write processing.

    Usage:
        watcher = TestPlanWatcher(...)
        queue = TestPlanWriteQueue(watcher, project)

        # Queue a status update
        await queue.enqueue("section-0-1", TestStatus.PASSED)
    """

    def __init__(self, watcher: TestPlanWatcher, project: Project) -> None:
        """Initialize the write queue.

        Args:
            watcher: The TestPlanWatcher to coordinate with
            project: The project whose TEST_PLAN.md we're updating
        """
        self.watcher = watcher
        self.project = project
        self._queue: asyncio.Queue[TestStepWrite] = asyncio.Queue()
        self._processing = False
        self._process_task: asyncio.Task | None = None

    async def enqueue(
        self,
        step_id: str,
        new_status: TestStatus,
        notes: str | None = None,
    ) -> None:
        """Add a write operation to the queue.

        If no processing is in progress, starts processing immediately.
        Otherwise, the write is queued for later processing.

        Args:
            step_id: The step ID to update (e.g., "section-0-1")
            new_status: The new status to set
            notes: Optional notes (typically for failed steps)
        """
        await self._queue.put(
            TestStepWrite(step_id=step_id, new_status=new_status, notes=notes)
        )
        if not self._processing:
            self._process_task = asyncio.create_task(self._process_queue())

    async def _process_queue(self) -> None:
        """Process all queued write operations.

        Marks pending writes on the watcher before starting, and
        clears the flag after all writes are complete. Handles
        any queued reloads after processing finishes.
        """
        self._processing = True
        self.watcher.mark_write_started()

        try:
            while not self._queue.empty():
                write = await self._queue.get()
                await self._apply_write(write)
                self._queue.task_done()

            # Check for queued reload after writes complete
            await self.watcher.process_queued_reload()
        finally:
            self.watcher.mark_write_completed()
            self._processing = False
            self._process_task = None

    async def _apply_write(self, write: TestStepWrite) -> None:
        """Apply a single write operation to TEST_PLAN.md.

        Updates both the file on disk and the in-memory plan state.

        Args:
            write: The write operation to apply

        Note:
            Errors are logged but not raised to allow queue processing to continue.
        """
        plan_path = self.project.full_test_plan_path
        if not plan_path.exists():
            logger.warning("TEST_PLAN.md does not exist at %s", plan_path)
            return

        # Read current content
        try:
            content = plan_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.error("Failed to read TEST_PLAN.md for write: %s", e)
            record_error(e)
            return

        # Apply the update
        updater = TestPlanUpdater()
        try:
            new_content = updater.update_step_status(
                content, write.step_id, write.new_status, write.notes
            )
        except TestPlanWriteError as e:
            # Step not found - skip this write
            logger.warning("Failed to update step %s: %s", write.step_id, e)
            return
        except Exception as e:
            logger.error("Unexpected error updating step %s: %s", write.step_id, e)
            record_error(e)
            return

        # Write to disk
        try:
            plan_path.write_text(new_content, encoding="utf-8")
            logger.debug("Wrote step %s status update to TEST_PLAN.md", write.step_id)
        except OSError as e:
            logger.error("Failed to write TEST_PLAN.md: %s", e)
            record_error(e)
            return

        # Update mtime tracking to avoid detecting our own write
        try:
            self.watcher.last_mtime = plan_path.stat().st_mtime
        except OSError as e:
            logger.warning("Failed to update mtime after write: %s", e)

        # Update in-memory plan if watcher has one
        if self.watcher.test_plan:
            for step in self.watcher.test_plan.all_steps:
                if step.id == write.step_id:
                    step.status = write.new_status
                    step.notes = write.notes
                    break

    @property
    def is_processing(self) -> bool:
        """Check if the queue is currently processing writes."""
        return self._processing

    @property
    def pending_count(self) -> int:
        """Get the number of pending writes in the queue."""
        return self._queue.qsize()

    async def wait_until_complete(self) -> None:
        """Wait until all pending writes have been processed.

        This is useful for testing or when you need to ensure
        all writes are complete before proceeding.
        """
        if self._process_task is not None:
            await self._process_task

    def cancel(self) -> None:
        """Cancel any pending processing.

        Clears the queue without processing remaining writes.
        Does not affect writes already in progress.
        """
        if self._process_task is not None and not self._process_task.done():
            self._process_task.cancel()

        # Clear the queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break

        self._processing = False
        self.watcher.mark_write_completed()
