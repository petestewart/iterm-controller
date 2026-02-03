# DEPRECATED - Work Mode Screen

> **DEPRECATION NOTICE**: This spec was deprecated on 2026-02-02.
>
> Work Mode has been replaced by the "Tasks Section" in the unified Project Screen.
> See [ui.md](../ui.md) for the new architecture.
>
> This file is kept for historical reference only.

---

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
