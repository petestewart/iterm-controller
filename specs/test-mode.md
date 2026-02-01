# Test Mode Screen

## Overview

Two testing modes: QA testing via TEST_PLAN.md checklist and unit test runner. Primary focus is on TEST_PLAN.md for manual/agent verification steps.

## Layout

```
┌────────────────────────────────────────────────────────────────┐
│ my-project                           [Test] 1 2 3 4   [?] Help │
├────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────┬──────────────────────────────┐ │
│ │ TEST_PLAN.md        Progress│ Unit Tests                   │ │
│ │                             │                              │ │
│ │ ▼ Functional Tests    3/5   │ Last run: 2 min ago          │ │
│ │   [x] User login works      │ Status: ✓ 42 passed          │ │
│ │   [x] Error on bad password │         ✗ 2 failed           │ │
│ │   [~] Session persistence   │         ○ 1 skipped          │ │
│ │   [ ] Password reset flow   │                              │ │
│ │   [ ] OAuth integration     │ Failed:                      │ │
│ │                             │   test_auth.py::test_timeout │ │
│ │ ▼ UI Tests            0/3   │   test_api.py::test_rate_lim │ │
│ │   [ ] Button colors match   │                              │ │
│ │   [ ] Responsive on mobile  │ ┌──────────────────────────┐ │ │
│ │   [ ] Accessibility check   │ │ [r] Run  [w] Watch  [f]  │ │ │
│ │                             │ │     Failed Only          │ │ │
│ └─────────────────────────────┴──────────────────────────────┘ │
│                                                                │
│ QA Session                                                     │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ ⧖ qa-agent    Verifying step 3    Waiting   [f]            │ │
│ └────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────┤
│ Enter Toggle  g Generate  s Spawn QA  r Run Tests  Esc Back   │
└────────────────────────────────────────────────────────────────┘
```

## Primary: TEST_PLAN.md Testing

### Purpose

QA checklist that agents verify step-by-step. Claude drafts the test plan, user refines it, then a QA agent executes verification.

### Workflow

1. **Generate**: Claude drafts TEST_PLAN.md from PRD/specs (`g` key)
2. **Refine**: User edits steps as needed
3. **Execute**: QA agent session verifies steps (`s` key)
4. **Track**: Steps marked as passed/failed as agent progresses

### TEST_PLAN.md Format

```markdown
# Test Plan

## Functional Tests

- [ ] Verify user can log in with valid credentials
- [ ] Verify error message shows for invalid password
- [ ] Verify session persists after page refresh
- [ ] Verify password reset email is sent

## UI Tests

- [ ] Verify button colors match design spec
- [ ] Verify responsive layout on mobile viewport
- [ ] Verify keyboard navigation works

## Integration Tests

- [ ] Verify API rate limiting works correctly
- [ ] Verify webhook delivery succeeds
```

### Step Statuses

| Marker | Status | Meaning |
|--------|--------|---------|
| `[ ]` | Pending | Not yet tested |
| `[~]` | In Progress | Currently being verified |
| `[x]` | Passed | Verification succeeded |
| `[!]` | Failed | Verification failed |

### Step with Notes

Failed steps can include notes:

```markdown
- [!] Verify session persists after page refresh
  Note: Session lost after 30 seconds, expected 24 hours
```

## Secondary: Unit Test Runner

### Test Command Detection

Auto-detect from project files:

```python
TEST_DETECTION_ORDER = [
    ("pytest.ini", "pytest"),
    ("pyproject.toml", "pytest"),  # Check for [tool.pytest]
    ("package.json", "npm test"),  # Check for "test" script
    ("Makefile", "make test"),     # Check for test target
    ("Cargo.toml", "cargo test"),
    ("go.mod", "go test ./..."),
]
```

### Configuration Override

Project config can specify custom test command:

```json
{
  "test_command": "pytest -v tests/",
  "test_watch_command": "pytest-watch"
}
```

### Unit Test Actions

| Key | Action | Description |
|-----|--------|-------------|
| `r` | Run | Run all tests |
| `w` | Watch | Start watch mode (if supported) |
| `f` | Failed | Run only failed tests |

## Actions

| Key | Action | Description |
|-----|--------|-------------|
| `Enter` | Toggle | Toggle step status (pending → in_progress → passed/failed) |
| `g` | Generate | Generate TEST_PLAN.md from PRD/specs |
| `s` | Spawn QA | Spawn QA agent session |
| `r` | Run Tests | Run unit tests |
| `w` | Watch | Start test watch mode |
| `f` | Failed Only | Run only failed unit tests |
| `Tab` | Switch panel | Switch between TEST_PLAN and unit tests |
| `Esc` | Back | Return to project dashboard |

## Generate TEST_PLAN.md

Pressing `g` launches Claude to generate test plan:

```python
async def generate_test_plan(self):
    """Generate TEST_PLAN.md from project artifacts."""
    command = "claude /qa --generate"
    await self.spawn_session("qa-generator", command)
```

The `/qa` command reads PRD.md and specs/ to create comprehensive test steps.

## QA Agent Session

Spawning a QA session (`s` key):

```python
async def spawn_qa_session(self):
    """Spawn QA agent to execute TEST_PLAN.md."""
    command = f"claude /qa --execute {self.project.path}/TEST_PLAN.md"
    session = await self.spawn_session("qa-agent", command)

    # Link session to test plan
    session.metadata["test_plan_path"] = self.test_plan_path
```

The QA agent:
1. Reads TEST_PLAN.md
2. Executes each step
3. Updates step status in the file
4. Reports results

## Widget Implementation

```python
class TestModeScreen(ModeScreen):
    """Test Mode - QA testing and unit tests."""

    BINDINGS = [
        *ModeScreen.BINDINGS,
        ("enter", "toggle_step", "Toggle"),
        ("g", "generate_plan", "Generate"),
        ("s", "spawn_qa", "Spawn QA"),
        ("r", "run_tests", "Run"),
        ("w", "watch_tests", "Watch"),
        ("f", "run_failed", "Failed"),
        ("tab", "switch_panel", "Switch"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Horizontal(
                Vertical(
                    TestPlanWidget(id="test-plan"),
                    id="left-panel"
                ),
                Vertical(
                    UnitTestWidget(id="unit-tests"),
                    id="right-panel"
                ),
            ),
            SessionListWidget(id="qa-session", filter="qa"),
            id="main"
        )
        yield Footer()

    async def action_toggle_step(self):
        """Toggle selected test step status."""
        widget = self.query_one("#test-plan", TestPlanWidget)
        step = widget.selected_step

        if step:
            # Cycle: pending → in_progress → passed → pending
            next_status = self._next_status(step.status)
            step.status = next_status
            await self.test_plan_watcher.update_step(step)

    async def action_run_tests(self):
        """Run unit tests."""
        command = self._detect_test_command()
        await self.run_in_panel(command)
```

## Progress Display

```
TEST_PLAN.md: 3/8 passed (37%)  |  1 in progress  |  1 failed
Unit Tests: 42/45 passed  |  2 failed  |  1 skipped
```

## Related Specs

- [workflow-modes.md](./workflow-modes.md) - Mode system overview
- [test-plan-parser.md](./test-plan-parser.md) - TEST_PLAN.md parsing
