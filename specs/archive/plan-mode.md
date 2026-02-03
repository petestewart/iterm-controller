# DEPRECATED - Plan Mode Screen

> **DEPRECATION NOTICE**: This spec was deprecated on 2026-02-02.
>
> Plan Mode has been replaced by the "Planning Section" in the unified Project Screen.
> See [ui.md](../ui.md) for the new architecture.
>
> This file is kept for historical reference only.

---

# Plan Mode Screen

## Overview

Displays planning artifacts status and provides actions to create, view, and edit them. This mode helps users track the planning phase of a project.

## Artifacts Tracked

| Artifact | Path | Purpose |
|----------|------|---------|
| PROBLEM.md | `{project}/PROBLEM.md` | Problem statement |
| PRD.md | `{project}/PRD.md` | Product requirements document |
| specs/ | `{project}/specs/` | Technical specifications directory |
| PLAN.md | `{project}/PLAN.md` | Implementation task list |

## Layout

```
┌────────────────────────────────────────────────────────────────┐
│ my-project                           [Plan] 1 2 3 4   [?] Help │
├────────────────────────────────────────────────────────────────┤
│ Planning Artifacts                                             │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ ✓ PROBLEM.md          Problem statement                    │ │
│ │ ✓ PRD.md              Product requirements                 │ │
│ │ ✓ specs/              4 spec files                         │ │
│ │   └─ README.md        Technical overview                   │ │
│ │   └─ models.md        Data models                          │ │
│ │   └─ ui.md            UI screens                           │ │
│ │   └─ api.md           API endpoints                        │ │
│ │ ○ PLAN.md             No tasks yet                         │ │
│ └────────────────────────────────────────────────────────────┘ │
│                                                                │
│ Workflow Stage: Planning                                       │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ [Planning] → Execute → Review → PR → Done                  │ │
│ └────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────┤
│ c Create  e Edit  s Spawn  Enter View  Esc Back               │
└────────────────────────────────────────────────────────────────┘
```

## Status Indicators

| Icon | Meaning |
|------|---------|
| ✓ | Artifact exists |
| ○ | Artifact missing |
| ● | Artifact has content/items |

For specs/ directory, show count of `.md` files.

## Actions

| Key | Action | Description |
|-----|--------|-------------|
| `Enter` | View | Open selected artifact in editor or preview inline |
| `c` | Create | Create missing artifact (launches Claude command) |
| `e` | Edit | Edit selected artifact in configured editor |
| `s` | Spawn | Spawn a planning session (runs configured command) |
| `Esc` | Back | Return to project dashboard |

## Create Artifact Commands

When creating missing artifacts, launch Claude with appropriate command:

```python
ARTIFACT_COMMANDS = {
    "PROBLEM.md": "claude /problem-statement",
    "PRD.md": "claude /prd",
    "specs/": "claude /specs",
    "PLAN.md": "claude /plan",
}
```
