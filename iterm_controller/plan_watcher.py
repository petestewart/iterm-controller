"""File watching for PLAN.md changes.

Watches PLAN.md files for external changes using watchfiles.
Detects changes within 1 second and triggers reload or conflict resolution.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, TYPE_CHECKING

from watchfiles import awatch, Change

from .models import Plan, TaskStatus
from .plan_parser import PlanParser

if TYPE_CHECKING:
    from .screens.modals import PlanConflictModal


class StateEvent(Enum):
    """Events emitted by the plan watcher."""

    PLAN_RELOADED = "plan_reloaded"
    PLAN_CONFLICT = "plan_conflict"


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
            return

        # Check if this is our own write
        current_mtime = self.plan_path.stat().st_mtime
        if current_mtime == self.last_mtime:
            return
        self.last_mtime = current_mtime

        # Parse new content
        parser = PlanParser()
        try:
            new_plan = parser.parse_file(self.plan_path)
        except Exception:
            # If parsing fails, ignore this change
            return

        if self.has_pending_writes:
            # Queue reload for after our write completes
            self.queued_reload = new_plan
        else:
            # Check for conflicts
            changes = self._compute_changes(new_plan)
            if changes:
                # Conflict detected
                if self.on_conflict_detected:
                    self.on_conflict_detected(new_plan, changes)
            else:
                # Silent reload (no meaningful changes)
                self.plan = new_plan
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
        """
        if self.plan_path is None or not self.plan_path.exists():
            return None

        parser = PlanParser()
        self.plan = parser.parse_file(self.plan_path)
        self.last_mtime = self.plan_path.stat().st_mtime
        return self.plan

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
