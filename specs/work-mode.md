# Work Mode Screen

## Overview

Task-centric view for claiming and executing tasks from PLAN.md. Shows task queue, active work, and sessions assigned to tasks.

## Layout

```
┌────────────────────────────────────────────────────────────────┐
│ my-project                           [Work] 1 2 3 4   [?] Help │
├────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────┬──────────────────────────────┐ │
│ │ Task Queue           5 left │ Active Work                  │ │
│ │ ┌───────────────────────────┤ ┌──────────────────────────┐ │ │
│ │ │ ○ 2.1 Add auth middleware │ │ ● 1.3 Build API layer    │ │ │
│ │ │ ⊘ 2.2 Create login form   │ │   Session: claude-main   │ │ │
│ │ │ ⊘ 2.3 Session persistence │ │   Started: 10 min ago    │ │ │
│ │ │ ○ 3.1 Write unit tests    │ │   Status: Working        │ │ │
│ │ │ ○ 3.2 Integration tests   │ │                          │ │ │
│ │ └───────────────────────────┤ │ ● 1.4 Add health checks  │ │ │
│ │                             │ │   Session: claude-2      │ │ │
│ │ Blocked: 2                  │ │   Started: 5 min ago     │ │ │
│ │   2.2 ← 2.1                 │ │   Status: Waiting        │ │ │
│ │   2.3 ← 2.1, 2.2            │ └──────────────────────────┘ │ │
│ └─────────────────────────────┴──────────────────────────────┘ │
│                                                                │
│ Sessions                                                       │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ ● claude-main    Task 1.3    Working   [f]                 │ │
│ │ ⧖ claude-2       Task 1.4    Waiting   [f]                 │ │
│ │ ○ dev-server     —          Idle      [f]                  │ │
│ └────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────┤
│ c Claim  s Spawn  u Unclaim  d Done  f Focus  Esc Back        │
└────────────────────────────────────────────────────────────────┘
```

## Task Queue

Shows pending tasks that can be claimed:

- **Available**: Tasks with no blockers (○ icon)
- **Blocked**: Tasks waiting on dependencies (⊘ icon, dimmed)

Tasks are ordered by:
1. Phase order
2. Dependencies (available before blocked)
3. Task ID

## Active Work Panel

Shows tasks currently in progress:

```python
@dataclass
class ActiveTask:
    task: Task
    session_id: str | None       # Assigned session
    started_at: datetime
    session_status: AttentionState
```

## Actions

| Key | Action | Description |
|-----|--------|-------------|
| `c` | Claim | Claim selected task (mark as in_progress) |
| `s` | Spawn | Spawn session for selected task |
| `u` | Unclaim | Unclaim task (back to pending) |
| `d` | Done | Mark task as complete |
| `f` | Focus | Focus the session assigned to selected task |
| `Tab` | Switch panel | Switch between queue and active work |
| `Esc` | Back | Return to project dashboard |

## Task-Session Linking

When spawning a session for a task:

```python
async def spawn_for_task(self, task: Task) -> ManagedSession:
    """Spawn a session linked to a task."""
    # Update task with session assignment
    task.session_id = session.id
    task.status = TaskStatus.IN_PROGRESS

    # Store task context in session
    session.metadata["task_id"] = task.id
    session.metadata["task_title"] = task.title

    # Optionally send task context to Claude
    if self.config.send_task_context:
        await session.send_text(f"# Working on: {task.title}\n")
        if task.spec_ref:
            await session.send_text(f"# Spec: {task.spec_ref}\n")

    return session
```

## Claim Workflow

1. User selects task in queue
2. Press `c` to claim
3. Task moves from queue to active work
4. Task status updated to `in_progress` in PLAN.md
5. Optionally spawn session with `s`

## Session Templates for Tasks

Configure task-specific session templates:

```json
{
  "session_templates": [
    {
      "id": "claude-task",
      "name": "Claude (Task)",
      "command": "claude",
      "task_context": true,
      "context_format": "Working on: {task.title}\nSpec: {task.spec_ref}"
    }
  ]
}
```

## Blocked Task View

Shows dependency chains for blocked tasks:

```
Blocked: 2
  2.2 Create login form ← 2.1 Add auth middleware
  2.3 Session persistence ← 2.1, 2.2
```

Pressing `v` on a blocked task shows full dependency chain:

```
┌────────────────────────────────────────────────────────────────┐
│ Task Dependencies: 2.3 Session persistence                     │
├────────────────────────────────────────────────────────────────┤
│ This task is blocked by:                                       │
│                                                                │
│   ○ 2.1 Add auth middleware (pending)                          │
│     └─ No blockers                                             │
│   ⊘ 2.2 Create login form (blocked)                            │
│     └─ Blocked by: 2.1                                         │
│                                                                │
│ [Press Esc to close]                                           │
└────────────────────────────────────────────────────────────────┘
```

## Widget Implementation

```python
class WorkModeScreen(ModeScreen):
    """Work Mode - task execution view."""

    BINDINGS = [
        *ModeScreen.BINDINGS,
        ("c", "claim_task", "Claim"),
        ("s", "spawn_session", "Spawn"),
        ("u", "unclaim_task", "Unclaim"),
        ("d", "mark_done", "Done"),
        ("f", "focus_session", "Focus"),
        ("tab", "switch_panel", "Switch"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(
                Vertical(
                    TaskQueueWidget(id="queue"),
                    BlockedTasksWidget(id="blocked"),
                    id="left-panel"
                ),
                Vertical(
                    ActiveWorkWidget(id="active"),
                    id="right-panel"
                ),
            ),
            SessionListWidget(id="sessions"),
            id="main"
        )
        yield Footer()

    async def action_claim_task(self):
        """Claim the selected task."""
        queue = self.query_one("#queue", TaskQueueWidget)
        task = queue.selected_task

        if task and not task.is_blocked:
            task.status = TaskStatus.IN_PROGRESS
            await self.state.plan_watcher.update_task(task)
            await self.refresh_panels()

    async def action_spawn_session(self):
        """Spawn session for selected task."""
        task = self._get_selected_task()
        if task:
            session = await self.spawn_for_task(task)
            self.notify(f"Spawned session for {task.id}")
```

## Progress Summary

Footer shows progress summary:

```
Progress: 3/10 complete (30%)  |  2 in progress  |  2 blocked
```

## Related Specs

- [workflow-modes.md](./workflow-modes.md) - Mode system overview
- [plan-parser.md](./plan-parser.md) - PLAN.md parsing and updating
- [session-monitor.md](./session-monitor.md) - Session status tracking
