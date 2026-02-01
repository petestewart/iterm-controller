# TEST_PLAN.md Parser

## Overview

Parse and update TEST_PLAN.md files for QA verification steps. Similar to PLAN.md parser but focused on test verification checklist items.

## File Format

```markdown
# Test Plan

## Section Name

- [ ] Step description
- [~] In progress step
- [x] Completed step
- [!] Failed step with notes
  Note: Failure details here

## Another Section

- [ ] Another step
```

## Parsing

### TestStatus Enum

```python
from enum import Enum

class TestStatus(Enum):
    """Status of a test step."""
    PENDING = "pending"       # [ ]
    IN_PROGRESS = "in_progress"  # [~]
    PASSED = "passed"         # [x]
    FAILED = "failed"         # [!]
```

### TestStep Model

```python
from dataclasses import dataclass, field

@dataclass
class TestStep:
    """A single verification step from TEST_PLAN.md."""
    id: str                          # Generated ID (e.g., "func-1")
    section: str                     # Parent section name
    description: str                 # Step description
    status: TestStatus = TestStatus.PENDING
    notes: str | None = None         # Failure notes or details
    line_number: int = 0             # Line in file (for updates)
```

### TestSection Model

```python
@dataclass
class TestSection:
    """A section in TEST_PLAN.md containing test steps."""
    id: str                          # Section identifier
    title: str                       # Section title
    steps: list[TestStep] = field(default_factory=list)

    @property
    def completion_count(self) -> tuple[int, int]:
        """Return (passed, total) step counts."""
        passed = sum(1 for s in self.steps if s.status == TestStatus.PASSED)
        return (passed, len(self.steps))

    @property
    def has_failures(self) -> bool:
        """Check if section has any failed steps."""
        return any(s.status == TestStatus.FAILED for s in self.steps)
```

### TestPlan Model

```python
@dataclass
class TestPlan:
    """Parsed TEST_PLAN.md document."""
    sections: list[TestSection] = field(default_factory=list)
    title: str = "Test Plan"
    path: str = ""                   # File path

    @property
    def all_steps(self) -> list[TestStep]:
        """Flatten all steps from all sections."""
        return [step for section in self.sections for step in section.steps]

    @property
    def completion_percentage(self) -> float:
        """Return overall completion percentage."""
        steps = self.all_steps
        if not steps:
            return 0.0
        passed = sum(1 for s in steps if s.status == TestStatus.PASSED)
        return passed / len(steps) * 100

    @property
    def summary(self) -> dict[str, int]:
        """Return summary of step statuses."""
        summary = {status.value: 0 for status in TestStatus}
        for step in self.all_steps:
            summary[step.status.value] += 1
        return summary
```

## Parser Implementation

```python
import re
from pathlib import Path

# Regex patterns
SECTION_PATTERN = re.compile(r"^##\s+(.+)$")
STEP_PATTERN = re.compile(r"^-\s+\[([ x~!])\]\s+(.+)$")
NOTE_PATTERN = re.compile(r"^\s+Note:\s+(.+)$")

STATUS_MAP = {
    " ": TestStatus.PENDING,
    "~": TestStatus.IN_PROGRESS,
    "x": TestStatus.PASSED,
    "!": TestStatus.FAILED,
}

def parse_test_plan(path: str | Path) -> TestPlan:
    """Parse TEST_PLAN.md file into TestPlan object."""
    path = Path(path)
    if not path.exists():
        return TestPlan(path=str(path))

    content = path.read_text()
    lines = content.split("\n")

    plan = TestPlan(path=str(path))
    current_section: TestSection | None = None
    current_step: TestStep | None = None
    step_counter = 0

    for i, line in enumerate(lines):
        # Check for title
        if line.startswith("# ") and not plan.title:
            plan.title = line[2:].strip()
            continue

        # Check for section header
        section_match = SECTION_PATTERN.match(line)
        if section_match:
            section_id = f"section-{len(plan.sections)}"
            current_section = TestSection(
                id=section_id,
                title=section_match.group(1).strip()
            )
            plan.sections.append(current_section)
            step_counter = 0
            continue

        # Check for step
        step_match = STEP_PATTERN.match(line)
        if step_match and current_section:
            step_counter += 1
            marker = step_match.group(1)
            description = step_match.group(2).strip()

            current_step = TestStep(
                id=f"{current_section.id}-{step_counter}",
                section=current_section.title,
                description=description,
                status=STATUS_MAP.get(marker, TestStatus.PENDING),
                line_number=i + 1
            )
            current_section.steps.append(current_step)
            continue

        # Check for note (attached to previous step)
        note_match = NOTE_PATTERN.match(line)
        if note_match and current_step:
            current_step.notes = note_match.group(1).strip()
            continue

    return plan
```

## Updating

### Update Step Status

```python
def update_step_status(
    path: str | Path,
    step_id: str,
    new_status: TestStatus,
    notes: str | None = None
) -> bool:
    """Update a step's status in TEST_PLAN.md."""
    path = Path(path)
    content = path.read_text()
    lines = content.split("\n")

    # Parse to find the step
    plan = parse_test_plan(path)
    step = next((s for s in plan.all_steps if s.id == step_id), None)

    if not step:
        return False

    # Build new line
    marker = STATUS_MARKER[new_status]
    new_line = f"- [{marker}] {step.description}"

    # Replace line
    lines[step.line_number - 1] = new_line

    # Handle notes
    note_line = step.line_number  # Line after the step
    if notes:
        note_text = f"  Note: {notes}"
        if note_line < len(lines) and NOTE_PATTERN.match(lines[note_line]):
            # Replace existing note
            lines[note_line] = note_text
        else:
            # Insert new note
            lines.insert(note_line, note_text)
    elif note_line < len(lines) and NOTE_PATTERN.match(lines[note_line]):
        # Remove existing note if clearing
        del lines[note_line]

    # Write back
    path.write_text("\n".join(lines))
    return True

STATUS_MARKER = {
    TestStatus.PENDING: " ",
    TestStatus.IN_PROGRESS: "~",
    TestStatus.PASSED: "x",
    TestStatus.FAILED: "!",
}
```

### Batch Updates

```python
def update_multiple_steps(
    path: str | Path,
    updates: list[tuple[str, TestStatus, str | None]]
) -> int:
    """Update multiple steps at once. Returns count of successful updates."""
    count = 0
    for step_id, status, notes in updates:
        if update_step_status(path, step_id, status, notes):
            count += 1
    return count
```

## File Watching

```python
from watchfiles import awatch, Change

class TestPlanWatcher:
    """Watch TEST_PLAN.md for external changes."""

    def __init__(self, path: str | Path, state: "AppState"):
        self.path = Path(path)
        self.state = state
        self._current_plan: TestPlan | None = None
        self._watching = False

    async def start(self):
        """Start watching for file changes."""
        self._watching = True
        self._current_plan = parse_test_plan(self.path)

        async for changes in awatch(self.path.parent):
            if not self._watching:
                break

            for change_type, changed_path in changes:
                if Path(changed_path) == self.path:
                    await self._handle_change(change_type)

    async def stop(self):
        """Stop watching."""
        self._watching = False

    async def _handle_change(self, change_type: Change):
        """Handle file change event."""
        if change_type == Change.deleted:
            self._current_plan = None
            self.state.dispatch(StateEvent.TEST_PLAN_DELETED)
            return

        new_plan = parse_test_plan(self.path)

        if self._has_conflicts(new_plan):
            await self._show_conflict_modal(new_plan)
        else:
            self._current_plan = new_plan
            self.state.dispatch(StateEvent.TEST_PLAN_RELOADED, new_plan)

    def _has_conflicts(self, new_plan: TestPlan) -> bool:
        """Check if new plan conflicts with pending updates."""
        # Similar to PlanWatcher conflict detection
        return self.has_pending_writes

    async def update_step(self, step: TestStep):
        """Queue a step status update."""
        update_step_status(self.path, step.id, step.status, step.notes)
        self._current_plan = parse_test_plan(self.path)
```

## State Events

```python
class StateEvent(Enum):
    # ... existing events ...
    TEST_PLAN_RELOADED = "test_plan_reloaded"
    TEST_PLAN_DELETED = "test_plan_deleted"
    TEST_STEP_UPDATED = "test_step_updated"
```

## Performance Targets

- Parse time: <50ms for 100 steps
- Change detection: <1 second from file save
- Update time: <100ms for single step

## Related Specs

- [test-mode.md](./test-mode.md) - Test Mode screen
- [plan-parser.md](./plan-parser.md) - Similar parser for PLAN.md
- [models.md](./models.md) - Data model definitions
