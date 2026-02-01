"""File watching for PLAN.md changes.

Watches PLAN.md files for external changes using watchfiles.
Detects changes within 1 second and triggers reload or conflict resolution.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, TYPE_CHECKING

from watchfiles import awatch, Change

from .exceptions import PlanConflictError, PlanParseError, PlanWriteError, record_error
from .models import Plan, Project, TaskStatus
from .plan_parser import PlanParser, PlanUpdater

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .screens.modals import PlanConflictModal


@dataclass
class PlanChange:
    """Represents a change detected between two plan versions."""

    task_id: str
    old_status: TaskStatus | None
    new_status: TaskStatus | None
    task_title: str
    change_type: str  # "status_changed", "task_added", "task_removed"

    def __str__(self) -> str:
        if self.change_type == "status_changed":
            return f"Task {self.task_id} status: {self.old_status.value if self.old_status else 'none'} → {self.new_status.value if self.new_status else 'none'}"
        elif self.change_type == "task_added":
            return f"New task added: {self.task_id} {self.task_title}"
        elif self.change_type == "task_removed":
            return f"Task removed: {self.task_id}"
        return f"Unknown change: {self.task_id}"


@dataclass
class PlanWatcher:
    """Watches PLAN.md for external changes.

    Provides:
    - Async file watching using watchfiles
    - Change detection comparing in-memory plan with file
    - Conflict resolution when external changes conflict with pending writes
    - Silent reload when no conflicts exist
    """

    plan: Plan | None = None
    plan_path: Path | None = None
    watching: bool = False
    has_pending_writes: bool = False
    queued_reload: Plan | None = None
    last_mtime: float = 0

    # Callbacks
    on_plan_reloaded: Callable[[Plan], None] | None = None
    on_conflict_detected: Callable[[Plan, list[PlanChange]], None] | None = None

    # Internal state
    _task: asyncio.Task | None = field(default=None, repr=False)
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event, repr=False)

    async def start_watching(self, path: Path, initial_plan: Plan | None = None) -> None:
        """Start watching a PLAN.md file.

        Args:
            path: Path to the PLAN.md file to watch
            initial_plan: Optional initial plan state (avoids immediate re-parse)
        """
        self.plan_path = path
        self.watching = True
        self._stop_event.clear()

        # Initialize with current file state
        if initial_plan:
            self.plan = initial_plan
        elif path.exists():
            parser = PlanParser()
            self.plan = parser.parse_file(path)

        # Track initial mtime
        if path.exists():
            self.last_mtime = path.stat().st_mtime

        # Start the watch loop
        self._task = asyncio.create_task(self._watch_loop())

    async def stop_watching(self) -> None:
        """Stop watching the PLAN.md file."""
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
                        if change_type in (Change.modified, Change.added):
                            await self._on_file_change()
        except asyncio.CancelledError:
            pass

    async def _on_file_change(self) -> None:
        """Handle file change event."""
        if self.plan_path is None or not self.plan_path.exists():
            logger.debug("Plan path is None or doesn't exist, skipping change")
            return

        # Check if this is our own write
        try:
            current_mtime = self.plan_path.stat().st_mtime
        except OSError as e:
            logger.warning("Failed to stat PLAN.md: %s", e)
            return

        if current_mtime == self.last_mtime:
            return
        self.last_mtime = current_mtime

        # Parse new content
        parser = PlanParser()
        try:
            new_plan = parser.parse_file(self.plan_path)
            logger.debug("Parsed external change to PLAN.md")
        except PlanParseError as e:
            # If parsing fails, log and ignore this change
            logger.warning("Failed to parse external PLAN.md change: %s", e)
            record_error(e)
            return
        except Exception as e:
            logger.error("Unexpected error parsing PLAN.md: %s", e)
            record_error(e)
            return

        if self.has_pending_writes:
            # Queue reload for after our write completes
            self.queued_reload = new_plan
            logger.debug("Queued PLAN.md reload (pending writes)")
        else:
            # Check for conflicts
            changes = self._compute_changes(new_plan)
            if changes:
                # Conflict detected
                logger.info(
                    "Detected %d external changes to PLAN.md", len(changes)
                )
                if self.on_conflict_detected:
                    self.on_conflict_detected(new_plan, changes)
            else:
                # Silent reload (no meaningful changes)
                self.plan = new_plan
                logger.debug("Silent reload of PLAN.md (no status changes)")
                if self.on_plan_reloaded:
                    self.on_plan_reloaded(new_plan)

    def _compute_changes(self, new_plan: Plan) -> list[PlanChange]:
        """Compute list of changes between current and new plan.

        Args:
            new_plan: The newly parsed plan

        Returns:
            List of PlanChange objects describing the differences
        """
        if self.plan is None:
            return []

        changes: list[PlanChange] = []

        # Build task maps
        current_tasks = {t.id: t for t in self.plan.all_tasks}
        new_tasks = {t.id: t for t in new_plan.all_tasks}

        # Check for status changes and new tasks
        for task_id, new_task in new_tasks.items():
            if task_id not in current_tasks:
                changes.append(
                    PlanChange(
                        task_id=task_id,
                        old_status=None,
                        new_status=new_task.status,
                        task_title=new_task.title,
                        change_type="task_added",
                    )
                )
            elif current_tasks[task_id].status != new_task.status:
                changes.append(
                    PlanChange(
                        task_id=task_id,
                        old_status=current_tasks[task_id].status,
                        new_status=new_task.status,
                        task_title=new_task.title,
                        change_type="status_changed",
                    )
                )

        # Check for removed tasks
        for task_id, current_task in current_tasks.items():
            if task_id not in new_tasks:
                changes.append(
                    PlanChange(
                        task_id=task_id,
                        old_status=current_task.status,
                        new_status=None,
                        task_title=current_task.title,
                        change_type="task_removed",
                    )
                )

        return changes

    def conflicts_with_current(self, new_plan: Plan) -> bool:
        """Check if new plan conflicts with current state.

        A conflict exists if any task statuses differ between versions.

        Args:
            new_plan: The newly parsed plan

        Returns:
            True if there are conflicts, False otherwise
        """
        return bool(self._compute_changes(new_plan))

    def mark_write_started(self) -> None:
        """Mark that a write operation is starting.

        Call this before writing to PLAN.md to prevent
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

    async def process_queued_reload(self) -> Plan | None:
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
                self.plan = queued
                if self.on_plan_reloaded:
                    self.on_plan_reloaded(queued)

            return queued
        return None

    def reload_from_file(self) -> Plan | None:
        """Force reload the plan from disk.

        Returns:
            The reloaded plan, or None if file doesn't exist

        Raises:
            PlanParseError: If the file cannot be read or parsed.
        """
        if self.plan_path is None or not self.plan_path.exists():
            logger.debug("Cannot reload: plan path is None or doesn't exist")
            return None

        parser = PlanParser()
        try:
            self.plan = parser.parse_file(self.plan_path)
            self.last_mtime = self.plan_path.stat().st_mtime
            logger.info("Reloaded PLAN.md from %s", self.plan_path)
            return self.plan
        except PlanParseError:
            raise
        except OSError as e:
            logger.error("Failed to stat PLAN.md after reload: %s", e)
            record_error(e)
            raise PlanParseError(
                f"Failed to access PLAN.md: {e}",
                file_path=str(self.plan_path),
                cause=e,
            ) from e

    async def reload_from_file_async(self) -> Plan | None:
        """Force reload the plan from disk asynchronously.

        Uses asyncio.to_thread to avoid blocking the event loop during file I/O.

        Returns:
            The reloaded plan, or None if file doesn't exist

        Raises:
            PlanParseError: If the file cannot be read or parsed.
        """
        if self.plan_path is None or not self.plan_path.exists():
            logger.debug("Cannot reload: plan path is None or doesn't exist")
            return None

        parser = PlanParser()
        try:
            self.plan = await parser.parse_file_async(self.plan_path)
            self.last_mtime = self.plan_path.stat().st_mtime
            logger.info("Reloaded PLAN.md from %s", self.plan_path)
            return self.plan
        except PlanParseError:
            raise
        except OSError as e:
            logger.error("Failed to stat PLAN.md after reload: %s", e)
            record_error(e)
            raise PlanParseError(
                f"Failed to access PLAN.md: {e}",
                file_path=str(self.plan_path),
                cause=e,
            ) from e

    def accept_external_changes(self, new_plan: Plan) -> None:
        """Accept external changes and update the current plan.

        Args:
            new_plan: The new plan to accept
        """
        self.plan = new_plan
        if self.on_plan_reloaded:
            self.on_plan_reloaded(new_plan)

    def keep_current(self) -> None:
        """Keep current plan and discard external changes.

        This just clears any queued reload without changing the plan.
        """
        self.queued_reload = None

    def create_conflict_modal(
        self,
        new_plan: Plan,
        changes: list[PlanChange],
    ) -> "PlanConflictModal":
        """Create a conflict resolution modal.

        Args:
            new_plan: The newly parsed plan from disk
            changes: List of detected changes

        Returns:
            A PlanConflictModal instance ready to be pushed onto the app
        """
        from .screens.modals import PlanConflictModal

        if self.plan is None:
            raise ValueError("Cannot create conflict modal without current plan")

        return PlanConflictModal(
            current_plan=self.plan,
            new_plan=new_plan,
            changes=changes,
        )

    def handle_conflict_resolution(self, result: str, new_plan: Plan) -> None:
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
class PlanWrite:
    """A pending write operation for PLAN.md."""

    task_id: str
    new_status: TaskStatus


class PlanWriteQueue:
    """Manages pending writes to PLAN.md with conflict handling.

    This class queues write operations to PLAN.md and processes them
    in order, coordinating with the PlanWatcher to avoid treating
    our own writes as external changes. It also handles conflicts
    that may arise if external changes occur during write processing.

    Usage:
        watcher = PlanWatcher(...)
        queue = PlanWriteQueue(watcher, project)

        # Queue a status update
        await queue.enqueue("2.1", TaskStatus.COMPLETE)
    """

    def __init__(self, watcher: PlanWatcher, project: Project) -> None:
        """Initialize the write queue.

        Args:
            watcher: The PlanWatcher to coordinate with
            project: The project whose PLAN.md we're updating
        """
        self.watcher = watcher
        self.project = project
        self._queue: asyncio.Queue[PlanWrite] = asyncio.Queue()
        self._processing = False
        self._process_task: asyncio.Task | None = None
        self._enqueue_lock = asyncio.Lock()

    async def enqueue(self, task_id: str, new_status: TaskStatus) -> None:
        """Add a write operation to the queue.

        If no processing is in progress, starts processing immediately.
        Otherwise, the write is queued for later processing.

        Uses a lock to prevent race conditions when multiple enqueues happen
        before the processing task has started.

        Args:
            task_id: The task ID to update (e.g., "2.1")
            new_status: The new status to set
        """
        async with self._enqueue_lock:
            await self._queue.put(PlanWrite(task_id=task_id, new_status=new_status))
            if not self._processing:
                self._processing = True  # Set immediately to prevent race
                self._process_task = asyncio.create_task(self._process_queue())

    async def _process_queue(self) -> None:
        """Process all queued write operations.

        Marks pending writes on the watcher before starting, and
        clears the flag after all writes are complete. Handles
        any queued reloads after processing finishes.

        Note: _processing is set to True in enqueue() before this task starts.
        """
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

    async def _apply_write(self, write: PlanWrite) -> None:
        """Apply a single write operation to PLAN.md.

        Updates both the file on disk and the in-memory plan state.
        Uses asyncio.to_thread for file I/O to avoid blocking the event loop.

        Args:
            write: The write operation to apply

        Note:
            Errors are logged but not raised to allow queue processing to continue.
        """
        plan_path = self.project.full_plan_path
        if not plan_path.exists():
            logger.warning("PLAN.md does not exist at %s", plan_path)
            return

        # Read current content asynchronously
        try:
            content = await asyncio.to_thread(plan_path.read_text, encoding="utf-8")
        except OSError as e:
            logger.error("Failed to read PLAN.md for write: %s", e)
            record_error(e)
            return

        # Apply the update
        updater = PlanUpdater()
        try:
            new_content = updater.update_task_status(
                content, write.task_id, write.new_status
            )
        except PlanWriteError as e:
            # Task or phase not found - skip this write
            logger.warning("Failed to update task %s: %s", write.task_id, e)
            return
        except Exception as e:
            logger.error("Unexpected error updating task %s: %s", write.task_id, e)
            record_error(e)
            return

        # Write to disk asynchronously
        try:
            await asyncio.to_thread(plan_path.write_text, new_content, encoding="utf-8")
            logger.debug("Wrote task %s status update to PLAN.md", write.task_id)
        except OSError as e:
            logger.error("Failed to write PLAN.md: %s", e)
            record_error(e)
            return

        # Update mtime tracking to avoid detecting our own write
        try:
            self.watcher.last_mtime = plan_path.stat().st_mtime
        except OSError as e:
            logger.warning("Failed to update mtime after write: %s", e)

        # Update in-memory plan if watcher has one using O(1) lookup
        if self.watcher.plan:
            task = self.watcher.plan.get_task_by_id(write.task_id)
            if task:
                task.status = write.new_status

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
