# Technical Specification: iTerm2 Project Orchestrator

## Overview

A Python-based TUI application that serves as a "control room" for development projects. It manages terminal sessions through iTerm2's Python API, monitors session output for attention-needed states, and provides unified visibility across multiple projects.

**Core value proposition:** One command to open a project and have all dev environment tabs spawn, configured, and monitored.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Textual TUI App                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ Control Room│  │  Project    │  │  Settings   │              │
│  │   Screen    │  │  Dashboard  │  │   Screen    │              │
│  └──────┬──────┘  └──────┬──────┘  └─────────────┘              │
│         │                │                                       │
│         │         ┌──────┴──────────────────────────┐           │
│         │         │      Workflow Modes             │           │
│         │         │  ┌────┐┌────┐┌────┐┌────┐      │           │
│         │         │  │Plan││Docs││Work││Test│      │           │
│         │         │  │Mode││Mode││Mode││Mode│      │           │
│         │         │  └────┘└────┘└────┘└────┘      │           │
│         │         └─────────────────────────────────┘           │
│         │                │                                       │
│         └────────┬───────┘                                       │
│                  ▼                                               │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                     App State Manager                        ││
│  │  - Projects, Sessions, Settings                              ││
│  │  - Event dispatch                                            ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  iTerm2     │  │  Plan       │  │  GitHub     │  │  Notifier   │
│  Controller │  │  Parser     │  │  (gh CLI)   │  │  (macOS)    │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
         │              │
         │              ├── PLAN.md Parser
         │              └── TEST_PLAN.md Parser
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     iTerm2 Python API                           │
│  - Session creation (tabs/panes)                                │
│  - Output polling                                               │
│  - Notifications (terminate, prompt, layout)                    │
└─────────────────────────────────────────────────────────────────┘
```

## Components

| Component | Spec | Description |
|-----------|------|-------------|
| App Entry & State | [app.md](./app.md) | Main Textual app, state management, event system |
| Data Models | [models.md](./models.md) | Core dataclasses (Project, Session, Config, Task, etc.) |
| iTerm2 Integration | [iterm.md](./iterm.md) | Session spawning, output monitoring, window/tab management |
| TUI Screens | [ui.md](./ui.md) | Control Room, Project Dashboard, Settings, modals |
| PLAN.md Parser | [plan-parser.md](./plan-parser.md) | Parsing, updating, and watching PLAN.md files |
| GitHub Integration | [github.md](./github.md) | Branch sync, PR status via `gh` CLI, graceful degradation |
| Notifications | [notifications.md](./notifications.md) | macOS notification center integration |
| Configuration | [config.md](./config.md) | JSON persistence, merging, project templates |
| Session Monitor | [session-monitor.md](./session-monitor.md) | Output polling, attention state detection patterns |
| Health Checks | [health-checks.md](./health-checks.md) | HTTP endpoint polling, status display |
| Auto Mode | [auto-mode.md](./auto-mode.md) | Workflow stage automation, phase completion triggers |

### Workflow Modes

| Component | Spec | Description |
|-----------|------|-------------|
| Workflow Modes | [workflow-modes.md](./workflow-modes.md) | Mode system overview, navigation, persistence |
| Plan Mode | [plan-mode.md](./plan-mode.md) | Planning artifacts screen (PROBLEM.md, PRD.md, specs/, PLAN.md) |
| Docs Mode | [docs-mode.md](./docs-mode.md) | Documentation tree browser, add/edit/organize docs |
| Work Mode | [work-mode.md](./work-mode.md) | Task-centric view, claim/assign tasks, session tracking |
| Test Mode | [test-mode.md](./test-mode.md) | QA testing (TEST_PLAN.md) and unit test runner |
| TEST_PLAN.md Parser | [test-plan-parser.md](./test-plan-parser.md) | Parsing, updating, watching TEST_PLAN.md files |

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **TUI Framework** | Textual 2.x | Rich widget library, async-native, reactive state, active development |
| **Code Structure** | Single package | Simpler imports, easy navigation, refactor to modular if needed |
| **Persistence** | JSON files | Human-readable, easy to debug, sufficient for config data |
| **Task Tracking** | PLAN.md | Source of truth stays in repo, editable by humans/Claude |
| **Session Monitoring** | Polling (500ms) | iTerm2 API design—no push for output, polling is responsive enough |
| **GitHub Integration** | `gh` CLI | Already installed/authenticated, avoids token management |
| **Notifications** | `terminal-notifier` | Reliable macOS integration, simple CLI interface |
| **Serialization** | `dataclasses` + `dacite` | Standard library dataclasses, dacite for JSON→dataclass |
| **Async** | Native `asyncio` | Required by iTerm2 API, works well with Textual |
| **Testing** | `pytest` + `pytest-asyncio` | Industry standard, good async support |

## Key Features Specification

### Health Checks

Health checks verify that services are running by polling HTTP endpoints.

**Configuration:**
```python
@dataclass
class HealthCheck:
    name: str                        # Display name (e.g., "API Health")
    url: str                         # URL with optional {env.VAR} placeholders
    method: str = "GET"              # HTTP method
    expected_status: int = 200       # Expected response code
    timeout_seconds: float = 5.0     # Request timeout
    interval_seconds: float = 10.0   # Polling interval (0 = manual only)
    service: str | None = None       # Links to script name for context
```

**Implementation:**
1. On project open, spawn async task for each health check with `interval_seconds > 0`
2. Resolve `{env.VAR}` placeholders from parsed environment
3. Use `httpx.AsyncClient` with timeout for requests
4. Update `HealthStatus` enum: `UNKNOWN` → `CHECKING` → `HEALTHY`/`UNHEALTHY`
5. Display in status bar: `Health: API ● Web ●` (green) or `API ✗` (red)

**Error Handling:**
- Connection refused → `UNHEALTHY`
- Timeout → `UNHEALTHY`
- Wrong status code → `UNHEALTHY`
- All checks stop when project closes

---

### Auto Mode Workflow

Auto mode enables hands-off project lifecycle progression with stage-specific commands.

**Workflow Stages:**
```
Planning  →  Execute  →  Review  →  PR  →  Done
```

**Stage Completion Triggers:**

| Stage | Completes When |
|-------|---------------|
| Planning | PRD exists (or marked unneeded) AND PLAN.md has ≥1 task |
| Execute | All tasks in PLAN.md are `Complete` or `Skipped` |
| Review | User manually advances (or configured review criteria met) |
| PR | PR merged on GitHub |
| Done | Terminal state |

**Auto Mode Configuration:**
```python
@dataclass
class AutoModeConfig:
    enabled: bool = False
    stage_commands: dict[WorkflowStage, str] = field(default_factory=dict)
    # e.g., {PLANNING: "claude /prd", EXECUTE: "claude /plan", REVIEW: "claude /review"}

    auto_advance: bool = True          # Automatically advance stages
    require_confirmation: bool = True  # Prompt before running stage command
```

**Implementation:**
1. File watcher detects PLAN.md changes
2. Re-evaluate `WorkflowState.infer_stage()`
3. If stage changed and `auto_advance` enabled:
   - If `require_confirmation`: show modal "Advance to {stage}? Run: {command}"
   - Execute `stage_commands[new_stage]` in designated session
4. Update workflow bar display

---

### Window Launch

Launch a new iTerm2 window with a predefined set of tabs/sessions.

**Window Layout Configuration:**
```python
@dataclass
class WindowLayout:
    id: str                              # Layout identifier
    name: str                            # Display name
    tabs: list[TabLayout]                # Tabs to create

@dataclass
class TabLayout:
    name: str                            # Tab title
    sessions: list[SessionLayout]        # Panes within tab

@dataclass
class SessionLayout:
    template_id: str                     # Which SessionTemplate to use
    split: str = "none"                  # "none", "horizontal", "vertical"
    size_percent: int = 50               # Split size percentage
```

**Implementation:**
1. `await iterm2.Window.async_create(connection)` - create new window
2. For each `TabLayout`:
   - Create tab: `await window.async_create_tab()`
   - For each `SessionLayout`:
     - If first: use tab's default session
     - Otherwise: split pane per `split` direction
   - Send command from referenced `SessionTemplate`
3. Register all sessions in `WindowState.managed_tab_ids`

**Stored in:** Global config under `window_layouts: list[WindowLayout]`

---

### Quit Confirmation

When quitting with active sessions, offer three options.

**Modal Display:**
```
┌────────────────────────────────────────┐
│  Quit Application                      │
├────────────────────────────────────────┤
│  You have 4 active sessions:           │
│    ● API Server                        │
│    ● Web Client                        │
│    ● Tests                             │
│    ● Claude                            │
│                                        │
│  > [C] Close all sessions and quit     │
│    [M] Close managed sessions only     │
│    [L] Leave sessions running          │
│    [Esc] Cancel                        │
└────────────────────────────────────────┘
```

**Option Behaviors:**

| Option | Action |
|--------|--------|
| **Close all** | Send SIGTERM to all sessions in managed windows, wait for exit (timeout 5s), SIGKILL if needed, then exit app |
| **Close managed only** | Close only sessions we spawned (tracked in `WindowState.managed_tab_ids`), leave pre-existing tabs |
| **Leave running** | Detach from iTerm2 connection, sessions continue running, exit app |

**Implementation:**
```python
async def handle_quit(action: QuitAction):
    if action == QuitAction.CLOSE_ALL:
        for tab in window_state.tabs:
            await close_tab(tab.tab_id)
    elif action == QuitAction.CLOSE_MANAGED:
        for tab_id in window_state.managed_tab_ids:
            await close_tab(tab_id)
    # LEAVE_RUNNING: just exit, no cleanup
    app.exit()
```

---

### PLAN.md Conflict Resolution

Handle external edits to PLAN.md while dashboard is open.

**Strategy: Detect and Prompt**

1. Use `watchfiles` to monitor PLAN.md for changes
2. On external change detected:
   - Parse new file content
   - Compare with in-memory `Plan` object
   - If differences found → show reload modal

**Reload Modal:**
```
┌────────────────────────────────────────┐
│  PLAN.md Changed                       │
├────────────────────────────────────────┤
│  The plan file was modified externally.│
│                                        │
│  Changes detected:                     │
│  • Task 2.1 status: In Progress → Done │
│  • New task added: 2.4 Add logging     │
│                                        │
│  > [R] Reload from file                │
│    [K] Keep current (discard changes)  │
│    [Esc] Decide later                  │
└────────────────────────────────────────┘
```

**Conflict Cases:**
- **No conflict**: External edit to task we're not actively viewing → auto-reload
- **Viewing conflict**: Editing same task → prompt with diff
- **Write conflict**: We have pending writes → queue our write, then reload

**Implementation:**
```python
class PlanWatcher:
    async def on_file_change(self, path: str):
        new_plan = parse_plan_file(path)
        if self.has_pending_writes:
            self.queued_reload = new_plan
        elif self.conflicts_with_current(new_plan):
            await self.show_conflict_modal(new_plan)
        else:
            self.state.plan = new_plan  # Silent reload
```

---

### Session Attention Detection

Patterns for detecting when a session needs user attention.

**Attention States:**
```python
class AttentionState(Enum):
    WAITING = "waiting"   # Needs user input (highest priority)
    WORKING = "working"   # Actively producing output
    IDLE = "idle"         # At prompt, not doing anything
```

**Detection Heuristics:**

| Pattern | Example | State | Confidence |
|---------|---------|-------|------------|
| Question mark at line end | `"Should I use JWT?"` | WAITING | High |
| Known confirmation prompts | `[y/N]`, `Continue?`, `Press Enter` | WAITING | High |
| Claude clarification patterns | `"I have a question:"`, `"Before I proceed:"` | WAITING | High |
| Shell prompt detected | `$`, `❯`, `%` at line start | IDLE | High |
| Recent output (< 2s ago) | Any new content | WORKING | Medium |
| Long pause after partial line | Incomplete sentence, no newline | WAITING | Low |

**Claude-Specific Patterns:**
```python
CLAUDE_WAITING_PATTERNS = [
    r"\?\s*$",                          # Ends with question mark
    r"I have a question",
    r"Before I proceed",
    r"Could you clarify",
    r"Which would you prefer",
    r"Should I",
    r"Do you want me to",
    r"Please confirm",
    r"\[yes/no\]",
    r"\(y/n\)",
]

CLAUDE_WORKING_PATTERNS = [
    r"^Reading ",
    r"^Writing ",
    r"^Searching ",
    r"^Running ",
    r"Creating .+\.\.\.",
    r"Analyzing ",
]
```

**State Transition Logic:**
```python
def determine_attention_state(session: ManagedSession, new_output: str) -> AttentionState:
    # Check for waiting patterns first (highest priority)
    for pattern in WAITING_PATTERNS:
        if re.search(pattern, new_output, re.IGNORECASE):
            return AttentionState.WAITING

    # Check if at shell prompt
    if is_shell_prompt(new_output):
        return AttentionState.IDLE

    # Recent output means working
    if session.last_activity and (now() - session.last_activity) < timedelta(seconds=2):
        return AttentionState.WORKING

    return AttentionState.IDLE
```

---

### Configuration Merging

Merge global config with project-local overrides.

**File Precedence:**
1. `~/.config/iterm-controller/config.json` (global defaults)
2. `{project}/.iterm-controller.json` (project overrides)

**Merge Strategy: Deep Merge with Override**

```python
def merge_configs(global_config: dict, project_config: dict) -> dict:
    """
    - Scalars: project overrides global
    - Lists: project replaces global (no merge)
    - Dicts: recursive merge
    - None in project: removes key from global
    """
    result = copy.deepcopy(global_config)
    for key, value in project_config.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result
```

**Example:**
```json
// Global: ~/.config/iterm-controller/config.json
{
  "settings": {
    "default_ide": "vscode",
    "polling_interval_ms": 500
  }
}

// Project: ./my-project/.iterm-controller.json
{
  "settings": {
    "default_ide": "cursor"  // Override
    // polling_interval_ms inherits 500
  },
  "scripts": {
    "start": {"command": "npm run dev"}  // Project-specific
  }
}

// Result:
{
  "settings": {
    "default_ide": "cursor",
    "polling_interval_ms": 500
  },
  "scripts": {
    "start": {"command": "npm run dev"}
  }
}
```

---

### GitHub Integration Error Handling

Graceful degradation when `gh` CLI is unavailable.

**Availability Check:**
```python
async def check_gh_available() -> tuple[bool, str | None]:
    """Returns (available, error_message)"""
    try:
        result = await run_command("gh", "auth", "status")
        if result.returncode == 0:
            return (True, None)
        return (False, "Not authenticated. Run: gh auth login")
    except FileNotFoundError:
        return (False, "gh CLI not installed")
```

**Degradation Behavior:**

| State | UI Behavior |
|-------|-------------|
| `gh` not installed | GitHub panel hidden, no errors shown |
| `gh` not authenticated | GitHub panel shows "Not authenticated" with hint |
| `gh` authenticated | Full functionality |
| API rate limited | Show cached data with "Rate limited" indicator |
| Network error | Show cached data with "Offline" indicator |

**Implementation:**
```python
class GitHubIntegration:
    def __init__(self):
        self.available = False
        self.error_message: str | None = None
        self.cached_status: GitHubStatus | None = None

    async def initialize(self):
        self.available, self.error_message = await check_gh_available()

    async def get_status(self, project: Project) -> GitHubStatus | None:
        if not self.available:
            return None
        try:
            status = await fetch_github_status(project)
            self.cached_status = status
            return status
        except Exception as e:
            # Return cached on error
            return self.cached_status
```

---

### Task Dependency Visualization

Display blocked tasks and their dependencies.

**Display Strategy: Inline with Dimming**

```
▼ Phase 2: Core Features                    0/3
  ⧖ 2.1 Add user auth middleware    ← Claude [a]
  ⊘ 2.2 Create login form           blocked by 2.1
  ⊘ 2.3 Add session persistence     blocked by 2.1, 2.2
```

**Visual Indicators:**
- `⊘` - Blocked status icon
- Dimmed/grayed text for blocked tasks
- "blocked by X, Y" suffix showing dependencies
- Blocked tasks not selectable for "Start Working"

**Interaction:**
- Hover/select blocked task → show tooltip with blocker details
- Press `v` on blocked task → show dependency chain
- Attempting to start blocked task → show error toast

**Implementation in `task_list.py`:**
```python
def render_task(task: Task) -> RenderResult:
    if task.is_blocked:
        blockers = ", ".join(task.depends)
        return Dim(f"⊘ {task.id} {task.title}  blocked by {blockers}")
    # ... normal rendering
```

---

### Spec File Validation

Validate that referenced spec files exist.

**Validation Points:**
1. On project open
2. On PLAN.md reload
3. When displaying task details

**Behavior:**

| Scenario | Display |
|----------|---------|
| Spec file exists | `Spec: specs/auth.md` (clickable link) |
| Spec file missing | `Spec: specs/auth.md ⚠ (not found)` |
| Spec anchor missing | `Spec: specs/auth.md#login ⚠ (section not found)` |

**Implementation:**
```python
def validate_spec_ref(project_path: str, spec_ref: str) -> tuple[bool, str | None]:
    """Returns (valid, error_message)"""
    if "#" in spec_ref:
        file_path, anchor = spec_ref.split("#", 1)
    else:
        file_path, anchor = spec_ref, None

    full_path = Path(project_path) / file_path
    if not full_path.exists():
        return (False, "File not found")

    if anchor:
        content = full_path.read_text()
        # Check for markdown heading matching anchor
        if f"# {anchor}" not in content.lower():
            return (False, f"Section '{anchor}' not found")

    return (True, None)
```

**No blocking**: Invalid spec refs show warning but don't prevent task operations.

## Package Structure

```
iterm_controller/
├── __init__.py
├── __main__.py           # Entry point: python -m iterm_controller
├── app.py                # Main Textual app class
├── state.py              # AppState, event system
├── models.py             # All dataclasses (Project, Session, Task, etc.)
├── config.py             # Config loading/saving, merging, paths
├── iterm_api.py          # iTerm2 connection, session management
├── session_monitor.py    # Output polling, attention detection
├── plan_parser.py        # PLAN.md parsing and updates
├── plan_watcher.py       # File watching for PLAN.md changes
├── github.py             # gh CLI wrapper with graceful degradation
├── notifications.py      # macOS notification sender
├── env_parser.py         # .env file parsing
├── health_checker.py     # HTTP health check polling
├── auto_mode.py          # Workflow stage automation
├── window_layouts.py     # Predefined window/tab layout management
├── screens/
│   ├── __init__.py
│   ├── control_room.py   # Main dashboard showing all sessions
│   ├── project_list.py   # Project browser
│   ├── project_dashboard.py  # Single project view
│   ├── new_project.py    # Project creation form
│   ├── settings.py       # App settings
│   └── modals/
│       ├── __init__.py
│       ├── quit_confirm.py   # Quit options: close all/managed/leave
│       ├── script_picker.py
│       ├── docs_picker.py
│       ├── github_actions.py
│       └── plan_conflict.py  # PLAN.md external edit resolution
└── widgets/
    ├── __init__.py
    ├── session_list.py   # Session rows with status indicators
    ├── task_list.py      # PLAN.md task display with dependencies
    ├── workflow_bar.py   # Planning → Execute → Review → PR → Done
    ├── health_status.py  # Health check indicators
    └── github_panel.py   # PR/branch status with degradation
```

## Constraints

### Platform Requirements
- **macOS only** - iTerm2 is macOS-specific
- **iTerm2 3.5+** - Required for Python scripting API
- **Python 3.11+** - For modern async features and typing

### iTerm2 API Limitations
- **No push notifications for output** - Must poll for session content
- **Cannot move tabs between existing windows** - Can only move to new window
- **Session IDs are stable** - Safe to store and reference later

### Performance Targets
- **Polling interval**: 500ms default (configurable)
- **Notification latency**: <5 seconds from session entering WAITING state
- **Health check interval**: 10 seconds default (configurable)
- **GitHub refresh**: 60 seconds default (configurable)

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `textual` | ~2.x | TUI framework |
| `iterm2` | ~2.x | iTerm2 Python API |
| `dacite` | ~1.8 | JSON to dataclass conversion |
| `watchfiles` | ~0.21 | File watching for PLAN.md changes |
| `httpx` | ~0.27 | Health check HTTP requests |

### Optional Dependencies
| Package | Purpose | Fallback |
|---------|---------|----------|
| `terminal-notifier` (CLI) | macOS notifications | Silent degradation |
| `gh` (CLI) | GitHub integration | GitHub panel hidden |

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| Global config | `~/.config/iterm-controller/config.json` | App settings, project list, templates |
| Project config | `{project}/.iterm-controller.json` | Project-local overrides (optional) |
| Plan file | `{project}/PLAN.md` or configured path | Task tracking |

## Open Questions

### Resolved in This Spec

- [x] **Claude thinking detection**: Use pattern matching with confidence levels. See [Session Attention Detection](#session-attention-detection).
- [x] **PLAN.md conflict handling**: Detect-and-prompt strategy with reload modal. See [PLAN.md Conflict Resolution](#planmd-conflict-resolution).
- [x] **Spec file validation**: Validate on load, show warning indicator for missing files. See [Spec File Validation](#spec-file-validation).
- [x] **Task dependency visualization**: Inline with dimming and "blocked by" suffix. See [Task Dependency Visualization](#task-dependency-visualization).
- [x] **Auto mode triggers**: Stage-specific completion criteria defined. See [Auto Mode Workflow](#auto-mode-workflow).

### Still Open

- [ ] **Multi-window support**: Should projects span multiple iTerm2 windows? Current spec assumes single window per project.

## Security Considerations

- **No secrets in config**: Sensitive env vars are masked in UI display
- **gh CLI auth**: Leverages existing `gh auth` - no token storage
- **Local only**: No network access except health checks and GitHub API via `gh`

---
*Generated from PRD.md on 2026-01-31*
*Updated with feature specifications on 2026-01-31*
