# DEPRECATED - Workflow Modes

> **DEPRECATION NOTICE**: This spec was deprecated on 2026-02-02.
>
> Workflow modes (Plan, Docs, Work, Test) have been replaced by a unified Project Screen
> with collapsible sections. See [ui.md](../ui.md) for the new architecture.
>
> This file is kept for historical reference only.

---

# Workflow Modes

## Overview

Dedicated screens for different project activities. Users navigate to modes via keyboard shortcuts from Project Dashboard. Each mode provides a focused view optimized for a specific type of work.

## Mode Types

| Key | Mode | Purpose |
|-----|------|---------|
| `1` | Plan Mode | Planning artifacts management |
| `2` | Docs Mode | Documentation tree browser |
| `3` | Work Mode | Task execution and session tracking |
| `4` | Test Mode | QA testing and unit test runner |

## Navigation

From Project Dashboard:
- `1` → Plan Mode Screen
- `2` → Docs Mode Screen
- `3` → Work Mode Screen
- `4` → Test Mode Screen
- `Esc` from any mode → Back to Project Dashboard

## Mode Persistence

The application remembers the last active mode for each project:

```python
@dataclass
class Project:
    # ... existing fields ...
    last_mode: WorkflowMode | None = None  # Persisted mode
```

**Behavior:**
- On project open, restore last mode (or default to Dashboard if None)
- Mode changes automatically saved to project state
- Persists across app restarts

## WorkflowMode Enum

```python
from enum import Enum

class WorkflowMode(Enum):
    """Project workflow modes."""
    PLAN = "plan"      # Planning artifacts
    DOCS = "docs"      # Documentation management
    WORK = "work"      # Task execution
    TEST = "test"      # QA and unit testing
```

## Screen Base Class

All mode screens share common navigation bindings:

```python
class ModeScreen(Screen):
    """Base class for workflow mode screens."""

    BINDINGS = [
        ("1", "switch_mode('plan')", "Plan"),
        ("2", "switch_mode('docs')", "Docs"),
        ("3", "switch_mode('work')", "Work"),
        ("4", "switch_mode('test')", "Test"),
        ("escape", "back_to_dashboard", "Back"),
    ]

    def __init__(self, project: Project):
        super().__init__()
        self.project = project

    async def action_switch_mode(self, mode: str):
        """Switch to another mode."""
        self.project.last_mode = WorkflowMode(mode)
        # Push appropriate mode screen

    async def action_back_to_dashboard(self):
        """Return to project dashboard."""
        self.app.pop_screen()
```

## Mode Indicator

Each mode screen displays a mode indicator in the header:

```
┌────────────────────────────────────────────────────────────────┐
│ my-project                           [Plan] 1 2 3 4   [?] Help │
├────────────────────────────────────────────────────────────────┤
```

The current mode is highlighted, and all mode shortcuts are visible.

## Integration with Auto Mode

Auto mode can trigger mode-specific commands when workflow stages change:

```python
@dataclass
class AutoModeConfig:
    # ... existing fields ...
    mode_commands: dict[str, str] = field(default_factory=dict)
    # e.g., {"plan": "claude /prd", "test": "claude /qa"}
```

See [auto-mode.md](./auto-mode.md) for details.

## Related Specs

- [plan-mode.md](./plan-mode.md) - Plan Mode screen specification
- [docs-mode.md](./docs-mode.md) - Docs Mode screen specification
- [work-mode.md](./work-mode.md) - Work Mode screen specification
- [test-mode.md](./test-mode.md) - Test Mode screen specification
- [ui.md](./ui.md) - Screen hierarchy and layouts
