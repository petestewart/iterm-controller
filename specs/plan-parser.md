# PLAN.md Parser

## Overview

Parsing, updating, and watching PLAN.md files for task tracking and workflow management.

## File Format

PLAN.md follows a structured markdown format:

```markdown
# Plan: Project Name

## Overview
Brief description of the project...

**Success criteria:**
- Criterion 1
- Criterion 2

## Tasks

### Phase 1: Foundation

- [ ] **Task title** `[pending]`
  - Spec: specs/component.md#section
  - Scope: What's in scope
  - Acceptance: How to verify completion

- [x] **Completed task** `[complete]`
  - Spec: specs/other.md
  - Scope: Already done

### Phase 2: Features

- [ ] **Blocked task** `[blocked]`
  - Depends: 1.1, 1.2
  - Scope: Can't start until dependencies done
```

## Parsing

```python
import re
from dataclasses import dataclass
from pathlib import Path

class PlanParser:
    """Parses PLAN.md files into structured data."""

    PHASE_PATTERN = re.compile(r'^###\s+Phase\s+(\d+):\s+(.+)$', re.MULTILINE)
    TASK_PATTERN = re.compile(
        r'^-\s+\[([ x])\]\s+\*\*(.+?)\*\*\s+`\[(\w+)\]`',
        re.MULTILINE
    )
    METADATA_PATTERN = re.compile(r'^\s+-\s+(\w+):\s+(.+)$', re.MULTILINE)

    def parse(self, content: str) -> Plan:
        """Parse PLAN.md content into Plan object."""
        plan = Plan()

        # Extract overview
        overview_match = re.search(r'^## Overview\s*\n(.*?)(?=^##|\Z)', content, re.MULTILINE | re.DOTALL)
        if overview_match:
            plan.overview = overview_match.group(1).strip()

        # Extract success criteria
        criteria_match = re.search(r'\*\*Success criteria:\*\*\s*\n((?:-\s+.+\n?)+)', content)
        if criteria_match:
            plan.success_criteria = [
                line.strip('- \n') for line in criteria_match.group(1).split('\n')
                if line.strip().startswith('-')
            ]

        # Parse phases and tasks
        phases = self._parse_phases(content)
        plan.phases = phases

        # Resolve dependencies
        self._resolve_dependencies(plan)

        return plan

    def _parse_phases(self, content: str) -> list[Phase]:
        """Parse all phases from content."""
        phases = []
        phase_matches = list(self.PHASE_PATTERN.finditer(content))

        for i, match in enumerate(phase_matches):
            phase_id = match.group(1)
            phase_title = match.group(2)

            # Get content until next phase or end
            start = match.end()
            end = phase_matches[i + 1].start() if i + 1 < len(phase_matches) else len(content)
            phase_content = content[start:end]

            tasks = self._parse_tasks(phase_content, phase_id)
            phases.append(Phase(id=phase_id, title=phase_title, tasks=tasks))

        return phases

    def _parse_tasks(self, content: str, phase_id: str) -> list[Task]:
        """Parse tasks from phase content."""
        tasks = []
        task_matches = list(self.TASK_PATTERN.finditer(content))

        for i, match in enumerate(task_matches):
            checkbox = match.group(1)
            title = match.group(2)
            status_str = match.group(3)

            # Get task content until next task
            start = match.end()
            end = task_matches[i + 1].start() if i + 1 < len(task_matches) else len(content)
            task_content = content[start:end]

            # Parse metadata
            metadata = self._parse_metadata(task_content)

            task = Task(
                id=f"{phase_id}.{i + 1}",
                title=title,
                status=self._parse_status(status_str, checkbox),
                spec_ref=metadata.get('Spec'),
                scope=metadata.get('Scope', ''),
                acceptance=metadata.get('Acceptance', ''),
                depends=self._parse_depends(metadata.get('Depends', '')),
            )
            tasks.append(task)

        return tasks

    def _parse_metadata(self, content: str) -> dict[str, str]:
        """Parse metadata lines from task content."""
        metadata = {}
        for match in self.METADATA_PATTERN.finditer(content):
            key = match.group(1)
            value = match.group(2).strip()
            metadata[key] = value
        return metadata

    def _parse_status(self, status_str: str, checkbox: str) -> TaskStatus:
        """Convert status string to enum."""
        status_map = {
            'pending': TaskStatus.PENDING,
            'in_progress': TaskStatus.IN_PROGRESS,
            'complete': TaskStatus.COMPLETE,
            'skipped': TaskStatus.SKIPPED,
            'blocked': TaskStatus.BLOCKED,
        }
        return status_map.get(status_str.lower(), TaskStatus.PENDING)

    def _parse_depends(self, depends_str: str) -> list[str]:
        """Parse dependency list."""
        if not depends_str:
            return []
        return [d.strip() for d in depends_str.split(',') if d.strip()]

    def _resolve_dependencies(self, plan: Plan):
        """Mark tasks as blocked based on incomplete dependencies."""
        task_map = {t.id: t for t in plan.all_tasks}

        for task in plan.all_tasks:
            if task.depends:
                for dep_id in task.depends:
                    dep = task_map.get(dep_id)
                    if dep and dep.status not in (TaskStatus.COMPLETE, TaskStatus.SKIPPED):
                        task.status = TaskStatus.BLOCKED
                        break
```

## Updating

```python
class PlanUpdater:
    """Updates PLAN.md files while preserving formatting."""

    def update_task_status(
        self,
        content: str,
        task_id: str,
        new_status: TaskStatus
    ) -> str:
        """Update a task's status in PLAN.md content."""
        # Find the task line
        pattern = re.compile(
            rf'^(-\s+\[)([ x])(\]\s+\*\*.+?\*\*\s+`\[)\w+(\]`)',
            re.MULTILINE
        )

        # Track which task we're updating
        phase_id, task_num = task_id.split('.')
        current_phase = None
        task_count = 0

        def replacer(match):
            nonlocal current_phase, task_count

            # Determine current phase from context
            # (simplified - real impl tracks phase headers)
            task_count += 1

            if f"{phase_id}.{task_count}" == task_id:
                checkbox = 'x' if new_status == TaskStatus.COMPLETE else ' '
                status_str = new_status.value
                return f"{match.group(1)}{checkbox}{match.group(3)}{status_str}{match.group(4)}"
            return match.group(0)

        return pattern.sub(replacer, content)

    def add_task(
        self,
        content: str,
        phase_id: str,
        task: Task
    ) -> str:
        """Add a new task to a phase."""
        # Find the phase
        phase_pattern = re.compile(
            rf'^###\s+Phase\s+{phase_id}:\s+.+$',
            re.MULTILINE
        )

        match = phase_pattern.search(content)
        if not match:
            raise ValueError(f"Phase {phase_id} not found")

        # Find insertion point (after last task in phase)
        next_phase = re.search(r'^###\s+Phase', content[match.end():], re.MULTILINE)
        insert_pos = match.end() + next_phase.start() if next_phase else len(content)

        # Format new task
        task_md = self._format_task(task)

        return content[:insert_pos] + "\n" + task_md + content[insert_pos:]

    def _format_task(self, task: Task) -> str:
        """Format task as markdown."""
        checkbox = 'x' if task.status == TaskStatus.COMPLETE else ' '
        lines = [
            f"- [{checkbox}] **{task.title}** `[{task.status.value}]`"
        ]

        if task.spec_ref:
            lines.append(f"  - Spec: {task.spec_ref}")
        if task.depends:
            lines.append(f"  - Depends: {', '.join(task.depends)}")
        if task.scope:
            lines.append(f"  - Scope: {task.scope}")
        if task.acceptance:
            lines.append(f"  - Acceptance: {task.acceptance}")

        return "\n".join(lines)
```

## File Watching

```python
import asyncio
from watchfiles import awatch

class PlanWatcher:
    """Watches PLAN.md for external changes."""

    def __init__(self, state: AppState):
        self.state = state
        self.watching = False
        self._task: asyncio.Task | None = None
        self.has_pending_writes = False
        self.queued_reload: Plan | None = None
        self.last_mtime: float = 0

    async def start_watching(self, path: Path):
        """Start watching a PLAN.md file."""
        self.watching = True
        self._task = asyncio.create_task(self._watch_loop(path))

    async def stop_watching(self):
        """Stop watching."""
        self.watching = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _watch_loop(self, path: Path):
        """Main watch loop."""
        async for changes in awatch(path.parent):
            if not self.watching:
                break

            for change_type, change_path in changes:
                if Path(change_path) == path:
                    await self.on_file_change(path)

    async def on_file_change(self, path: Path):
        """Handle external file change."""
        # Check if this is our own write
        mtime = path.stat().st_mtime
        if mtime == self.last_mtime:
            return
        self.last_mtime = mtime

        # Parse new content
        parser = PlanParser()
        new_plan = parser.parse(path.read_text())

        if self.has_pending_writes:
            # Queue reload for after our write completes
            self.queued_reload = new_plan
        elif self.conflicts_with_current(new_plan):
            # Show conflict resolution modal
            await self.show_conflict_modal(new_plan)
        else:
            # Silent reload
            self.state.plan = new_plan
            self.state.emit(StateEvent.PLAN_RELOADED, plan=new_plan)

    def conflicts_with_current(self, new_plan: Plan) -> bool:
        """Check if new plan conflicts with current state."""
        current = self.state.plan
        if not current:
            return False

        # Compare task statuses
        current_statuses = {t.id: t.status for t in current.all_tasks}
        new_statuses = {t.id: t.status for t in new_plan.all_tasks}

        return current_statuses != new_statuses

    async def show_conflict_modal(self, new_plan: Plan):
        """Show conflict resolution modal."""
        self.state.emit(StateEvent.PLAN_CONFLICT, new_plan=new_plan)
```

## Conflict Resolution

```python
class PlanConflictModal(ModalScreen):
    """Modal for resolving PLAN.md conflicts."""

    BINDINGS = [
        ("r", "reload", "Reload"),
        ("k", "keep", "Keep Current"),
        ("escape", "dismiss", "Decide Later"),
    ]

    def __init__(self, current: Plan, new: Plan):
        super().__init__()
        self.current = current
        self.new = new
        self.changes = self._compute_changes()

    def _compute_changes(self) -> list[str]:
        """Compute list of changes between plans."""
        changes = []
        current_tasks = {t.id: t for t in self.current.all_tasks}
        new_tasks = {t.id: t for t in self.new.all_tasks}

        for task_id, new_task in new_tasks.items():
            if task_id not in current_tasks:
                changes.append(f"• New task added: {task_id} {new_task.title}")
            elif current_tasks[task_id].status != new_task.status:
                old_status = current_tasks[task_id].status.value
                new_status = new_task.status.value
                changes.append(f"• Task {task_id} status: {old_status} → {new_status}")

        for task_id in current_tasks:
            if task_id not in new_tasks:
                changes.append(f"• Task removed: {task_id}")

        return changes

    def compose(self) -> ComposeResult:
        yield Container(
            Static("PLAN.md Changed", classes="modal-title"),
            Static("The plan file was modified externally."),
            Static(""),
            Static("Changes detected:"),
            *[Static(change) for change in self.changes[:10]],
            Static(""),
            Horizontal(
                Button("[R] Reload", id="reload"),
                Button("[K] Keep current", id="keep"),
            ),
            classes="modal-content"
        )
```

## Write Queue Management

```python
class PlanWriteQueue:
    """Manages pending writes to PLAN.md with conflict handling."""

    def __init__(self, watcher: PlanWatcher):
        self.watcher = watcher
        self._queue: asyncio.Queue[PlanWrite] = asyncio.Queue()
        self._processing = False

    @dataclass
    class PlanWrite:
        task_id: str
        new_status: TaskStatus

    async def enqueue(self, task_id: str, new_status: TaskStatus):
        """Add a write to the queue."""
        await self._queue.put(self.PlanWrite(task_id, new_status))
        if not self._processing:
            asyncio.create_task(self._process_queue())

    async def _process_queue(self):
        """Process queued writes."""
        self._processing = True
        self.watcher.has_pending_writes = True

        try:
            while not self._queue.empty():
                write = await self._queue.get()
                await self._apply_write(write)

            # Check for queued reload after writes complete
            if self.watcher.queued_reload:
                new_plan = self.watcher.queued_reload
                self.watcher.queued_reload = None
                await self.watcher.show_conflict_modal(new_plan)
        finally:
            self.watcher.has_pending_writes = False
            self._processing = False

    async def _apply_write(self, write: PlanWrite):
        """Apply a single write to PLAN.md."""
        plan_path = self.watcher.state.active_project.full_plan_path
        content = plan_path.read_text()

        updater = PlanUpdater()
        new_content = updater.update_task_status(
            content, write.task_id, write.new_status
        )

        # Update mtime tracking before write
        self.watcher.last_mtime = plan_path.stat().st_mtime
        plan_path.write_text(new_content)
        self.watcher.last_mtime = plan_path.stat().st_mtime
```
