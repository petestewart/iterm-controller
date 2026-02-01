# Auto Mode

## Overview

Workflow stage automation with stage-specific commands that execute when phases complete.

## Workflow Stages

```
Planning  →  Execute  →  Review  →  PR  →  Done
```

## Stage Completion Triggers

| Stage | Completes When |
|-------|---------------|
| Planning | PRD exists (or marked unneeded) AND PLAN.md has ≥1 task |
| Execute | All tasks in PLAN.md are `Complete` or `Skipped` |
| Review | User manually advances (or configured review criteria met) |
| PR | PR merged on GitHub |
| Done | Terminal state |

## Configuration

```python
from dataclasses import dataclass, field
from enum import Enum

class WorkflowStage(Enum):
    PLANNING = "planning"
    EXECUTE = "execute"
    REVIEW = "review"
    PR = "pr"
    DONE = "done"

@dataclass
class AutoModeConfig:
    """Auto mode workflow configuration."""
    enabled: bool = False
    stage_commands: dict[str, str] = field(default_factory=dict)
    # e.g., {"planning": "claude /prd", "execute": "claude /plan", "review": "claude /review"}

    auto_advance: bool = True          # Automatically advance stages
    require_confirmation: bool = True  # Prompt before running stage command
    designated_session: str | None = None  # Session to run commands in
```

## Stage Inference

```python
@dataclass
class WorkflowState:
    """Current workflow state for a project."""
    stage: WorkflowStage = WorkflowStage.PLANNING
    prd_exists: bool = False
    prd_unneeded: bool = False
    pr_url: str | None = None
    pr_merged: bool = False

    @classmethod
    def infer_stage(
        cls,
        plan: "Plan",
        github_status: "GitHubStatus | None",
        prd_exists: bool = False,
        prd_unneeded: bool = False
    ) -> "WorkflowState":
        """Infer workflow stage from plan and GitHub state."""
        state = cls()
        state.prd_exists = prd_exists
        state.prd_unneeded = prd_unneeded

        # Check PR status first (highest priority)
        if github_status and github_status.pr:
            state.pr_url = github_status.pr.url
            state.pr_merged = github_status.pr.merged

            if state.pr_merged:
                state.stage = WorkflowStage.DONE
                return state

            state.stage = WorkflowStage.PR
            return state

        # Check task completion
        all_tasks = plan.all_tasks
        if all_tasks:
            all_done = all(
                t.status in (TaskStatus.COMPLETE, TaskStatus.SKIPPED)
                for t in all_tasks
            )
            if all_done:
                state.stage = WorkflowStage.REVIEW
                return state

            # Has tasks = executing
            state.stage = WorkflowStage.EXECUTE
            return state

        # Check planning completion
        if (prd_exists or prd_unneeded) and all_tasks:
            state.stage = WorkflowStage.EXECUTE
            return state

        return state
```

## Auto Mode Controller

```python
class AutoModeController:
    """Controls automatic workflow stage advancement."""

    def __init__(
        self,
        config: AutoModeConfig,
        state: "AppState",
        iterm: "ItermController"
    ):
        self.config = config
        self.state = state
        self.iterm = iterm
        self._current_stage: WorkflowStage | None = None

    async def on_plan_change(self, plan: "Plan"):
        """Handle PLAN.md changes."""
        if not self.config.enabled:
            return

        # Re-evaluate stage
        github_status = await self.state.github.get_status(
            self.state.active_project
        )

        new_workflow = WorkflowState.infer_stage(
            plan,
            github_status,
            prd_exists=self._check_prd_exists(),
            prd_unneeded=self.state.prd_unneeded
        )

        if new_workflow.stage != self._current_stage:
            await self._handle_stage_change(
                self._current_stage,
                new_workflow.stage
            )
            self._current_stage = new_workflow.stage

    async def _handle_stage_change(
        self,
        old_stage: WorkflowStage | None,
        new_stage: WorkflowStage
    ):
        """Handle workflow stage transition."""
        if not self.config.auto_advance:
            return

        command = self.config.stage_commands.get(new_stage.value)
        if not command:
            return

        if self.config.require_confirmation:
            # Show confirmation modal
            confirmed = await self._show_advance_modal(new_stage, command)
            if not confirmed:
                return

        await self._execute_stage_command(command)

    async def _show_advance_modal(
        self,
        stage: WorkflowStage,
        command: str
    ) -> bool:
        """Show confirmation modal for stage advancement."""
        modal = StageAdvanceModal(stage, command)
        return await self.state.app.push_screen_wait(modal)

    async def _execute_stage_command(self, command: str):
        """Execute stage command in designated session."""
        session_id = self.config.designated_session

        if session_id:
            session = await self.iterm.app.async_get_session_by_id(session_id)
            if session:
                await session.async_send_text(command + "\n")
                return

        # Fall back to current session
        current = self.iterm.app.current_terminal_window
        if current and current.current_tab:
            session = current.current_tab.current_session
            await session.async_send_text(command + "\n")

    def _check_prd_exists(self) -> bool:
        """Check if PRD file exists for project."""
        project = self.state.active_project
        if not project:
            return False

        prd_path = Path(project.path) / "PRD.md"
        return prd_path.exists()
```

## Stage Advance Modal

```python
class StageAdvanceModal(ModalScreen):
    """Confirmation modal for stage advancement."""

    BINDINGS = [
        ("enter", "confirm", "Run Command"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, stage: WorkflowStage, command: str):
        super().__init__()
        self.stage = stage
        self.command = command

    def compose(self) -> ComposeResult:
        yield Container(
            Static(f"Advance to {self.stage.value.title()}?", classes="modal-title"),
            Static(""),
            Static("The following command will run:"),
            Static(f"  {self.command}", classes="code"),
            Static(""),
            Horizontal(
                Button("[Enter] Run", id="confirm", variant="primary"),
                Button("[Esc] Cancel", id="cancel"),
            ),
            classes="modal-content"
        )

    async def action_confirm(self):
        self.dismiss(True)

    async def action_cancel(self):
        self.dismiss(False)
```

## Workflow Bar Widget

```python
class WorkflowBarWidget(Static):
    """Displays workflow stage progression."""

    STAGES = [
        WorkflowStage.PLANNING,
        WorkflowStage.EXECUTE,
        WorkflowStage.REVIEW,
        WorkflowStage.PR,
        WorkflowStage.DONE,
    ]

    def __init__(self, state: "WorkflowState", **kwargs):
        super().__init__(**kwargs)
        self.workflow_state = state

    def render(self) -> str:
        """Render the workflow bar."""
        parts = []
        current = self.workflow_state.stage

        for stage in self.STAGES:
            name = stage.value.title()

            if stage == current:
                # Current stage - highlighted
                parts.append(f"[bold white on blue] {name} [/]")
            elif self._is_complete(stage, current):
                # Completed stage - green with checkmark
                parts.append(f"[green]{name} ✓[/green]")
            else:
                # Future stage - dimmed
                parts.append(f"[dim]{name}[/dim]")

        return " → ".join(parts)

    def _is_complete(
        self,
        stage: WorkflowStage,
        current: WorkflowStage
    ) -> bool:
        """Check if a stage is complete."""
        order = {s: i for i, s in enumerate(self.STAGES)}
        return order[stage] < order[current]
```

## Integration

```python
class AutoModeIntegration:
    """Integrates auto mode with plan watcher."""

    def __init__(
        self,
        config: AutoModeConfig,
        plan_watcher: "PlanWatcher",
        state: "AppState",
        iterm: "ItermController"
    ):
        self.controller = AutoModeController(config, state, iterm)
        self.plan_watcher = plan_watcher

        # Subscribe to plan changes
        state.subscribe(
            StateEvent.PLAN_RELOADED,
            self._on_plan_reloaded
        )

    async def _on_plan_reloaded(self, plan: "Plan"):
        """Handle plan reload event."""
        await self.controller.on_plan_change(plan)
```

## Example Stage Commands

```json
{
  "auto_mode": {
    "enabled": true,
    "auto_advance": true,
    "require_confirmation": true,
    "designated_session": "claude",
    "stage_commands": {
      "planning": "claude /prd",
      "execute": "claude /plan",
      "review": "claude /review"
    }
  }
}
```

## State Transitions

```
┌──────────┐
│ PLANNING │
└────┬─────┘
     │ PRD exists AND ≥1 task
     ▼
┌──────────┐
│ EXECUTE  │
└────┬─────┘
     │ All tasks Complete/Skipped
     ▼
┌──────────┐
│ REVIEW   │
└────┬─────┘
     │ Manual advance OR criteria met
     ▼
┌──────────┐
│    PR    │
└────┬─────┘
     │ PR merged
     ▼
┌──────────┐
│   DONE   │
└──────────┘
```
