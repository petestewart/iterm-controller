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

## Artifact Existence Check

```python
def check_artifact_status(project: Project) -> dict[str, ArtifactStatus]:
    """Check existence and status of planning artifacts."""
    path = Path(project.path)

    return {
        "PROBLEM.md": check_file(path / "PROBLEM.md"),
        "PRD.md": check_file(path / "PRD.md"),
        "specs/": check_specs_dir(path / "specs"),
        "PLAN.md": check_plan_file(path / "PLAN.md"),
    }

@dataclass
class ArtifactStatus:
    exists: bool
    description: str = ""  # e.g., "4 spec files" or "12 tasks"
```

## Integration with Auto Mode

Plan Mode monitors artifact existence for stage transitions:

- When PRD.md exists (or marked unneeded) AND PLAN.md has ≥1 task → Planning stage complete
- Can trigger `stage_commands.planning` from Auto Mode config

```python
async def check_planning_complete(self) -> bool:
    """Check if planning stage is complete."""
    status = check_artifact_status(self.project)

    prd_ready = status["PRD.md"].exists or self.project.prd_unneeded
    plan_ready = status["PLAN.md"].exists and self._has_tasks()

    return prd_ready and plan_ready
```

## Inline Preview

When viewing an artifact with `Enter`, show inline preview:

```
┌────────────────────────────────────────────────────────────────┐
│ PRD.md Preview                                      [e] Edit   │
├────────────────────────────────────────────────────────────────┤
│ # PRD: My Project                                              │
│                                                                │
│ ## Problem Statement                                           │
│ Users need a way to manage their terminal sessions...          │
│                                                                │
│ ## Proposed Solution                                           │
│ Build a TUI application that...                                │
│                                                                │
│ [Press Esc to close, e to edit in external editor]             │
└────────────────────────────────────────────────────────────────┘
```

## Widget Implementation

```python
class PlanModeScreen(ModeScreen):
    """Plan Mode - planning artifacts management."""

    BINDINGS = [
        *ModeScreen.BINDINGS,
        ("c", "create_artifact", "Create"),
        ("e", "edit_artifact", "Edit"),
        ("s", "spawn_planning", "Spawn"),
        ("enter", "view_artifact", "View"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            ArtifactListWidget(id="artifacts"),
            WorkflowBarWidget(id="workflow"),
            id="main"
        )
        yield Footer()

    async def on_mount(self):
        """Load artifact status."""
        status = check_artifact_status(self.project)
        widget = self.query_one("#artifacts", ArtifactListWidget)
        await widget.refresh(status)
```

## Related Specs

- [workflow-modes.md](./workflow-modes.md) - Mode system overview
- [auto-mode.md](./auto-mode.md) - Stage automation
- [plan-parser.md](./plan-parser.md) - PLAN.md parsing
