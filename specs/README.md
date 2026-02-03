# Technical Specification: iTerm2 Project Orchestrator

## Overview

A Python-based TUI application that serves as a "mission control" for development projects. It manages terminal sessions through iTerm2's Python API, streams live output from all active sessions, and provides unified visibility across multiple projects with integrated git operations, auto-review pipelines, and project scripts.

**Core value proposition:** One command to open a project and have all dev environment tabs spawn, configured, monitored, and reviewable from a single unified interface.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Textual TUI App                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐     │
│  │ Mission Control │  │  Project Screen │  │  Settings   │     │
│  │   (main)        │  │  (unified view) │  │   Screen    │     │
│  └────────┬────────┘  └────────┬────────┘  └─────────────┘     │
│           │                    │                                │
│           └────────┬───────────┘                                │
│                    ▼                                            │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                     App State Manager                        ││
│  │  - Projects, Sessions, Plans, Git, Reviews                   ││
│  │  - Event dispatch, Output streaming                          ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  iTerm2     │  │    Git      │  │   Review    │  │   Script    │
│  Controller │  │   Service   │  │   Service   │  │   Service   │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Plan       │  │  GitHub     │  │  Notifier   │  │  Session    │
│  Parser     │  │  (gh CLI)   │  │  (macOS)    │  │  Monitor    │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
```

## Components

| Component | Spec | Description |
|-----------|------|-------------|
| App Entry & State | [app.md](./app.md) | Main app, state management, event system |
| Data Models | [models.md](./models.md) | Core dataclasses including Review, Git, Script models |
| iTerm2 Integration | [iterm.md](./iterm.md) | Session spawning, output monitoring |
| TUI Screens | [ui.md](./ui.md) | Mission Control, Project Screen, Settings |
| Mission Control | [mission-control.md](./mission-control.md) | Main screen with live session output |
| Git Service | [git-service.md](./git-service.md) | Git operations (status, commit, push) |
| Review Service | [review-service.md](./review-service.md) | Auto-review pipeline for tasks |
| Project Scripts | [scripts.md](./scripts.md) | Named scripts with keybindings |
| PLAN.md Parser | [plan-parser.md](./plan-parser.md) | Parsing with review tracking |
| Session Monitor | [session-monitor.md](./session-monitor.md) | Output polling AND streaming |
| Notifications | [notifications.md](./notifications.md) | macOS notifications with sound |
| Configuration | [config.md](./config.md) | JSON config with scripts, review, git sections |
| Health Checks | [health-checks.md](./health-checks.md) | HTTP endpoint polling |

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **TUI Framework** | Textual 2.x | Rich widget library, async-native, reactive state, active development |
| **Code Structure** | Single package | Simpler imports, easy navigation, refactor to modular if needed |
| **Persistence** | JSON files | Human-readable, easy to debug, sufficient for config data |
| **Task Tracking** | PLAN.md | Source of truth stays in repo, editable by humans/Claude |
| **Session Monitoring** | Polling (500ms) | iTerm2 API design—no push for output, polling is responsive enough |
| **Output Streaming** | Push to subscribers | Polling loop pushes new output to registered subscribers for live display |
| **GitHub Integration** | `gh` CLI | Already installed/authenticated, avoids token management |
| **Git Operations** | Direct git CLI | GitService wraps git commands for status, commit, push operations |
| **Review Pipeline** | Configurable command + parser | Runs review command, parses output with subagent for structured feedback |
| **Notifications** | `terminal-notifier` | Reliable macOS integration, simple CLI interface |
| **Serialization** | `dataclasses` + `dacite` | Standard library dataclasses, dacite for JSON→dataclass |
| **Async** | Native `asyncio` | Required by iTerm2 API, works well with Textual |
| **Testing** | `pytest` + `pytest-asyncio` | Industry standard, good async support |

## Key Features Specification

### Live Output Streaming

Mission Control displays live output from all active sessions across projects.

**Streaming Architecture:**
```python
@dataclass
class OutputSubscriber:
    session_id: str
    callback: Callable[[str], None]  # Called with new output chunks

class SessionMonitor:
    subscribers: dict[str, list[OutputSubscriber]]

    async def poll_loop(self):
        while True:
            for session_id, session in self.sessions.items():
                new_output = await self.get_new_output(session)
                if new_output:
                    for subscriber in self.subscribers.get(session_id, []):
                        subscriber.callback(new_output)
            await asyncio.sleep(0.5)

    def subscribe(self, session_id: str, callback: Callable[[str], None]) -> str:
        """Returns subscription ID for later unsubscribe"""
        ...

    def unsubscribe(self, subscription_id: str):
        ...
```

**Display in Mission Control:**
- Split view showing all active sessions
- Scrollable output pane per session
- Visual indicators for attention state (waiting/working/idle)
- Click session to focus and expand

---

### Auto-Review Workflow

Completed tasks trigger automatic LLM review for quality assurance.

**Review Pipeline:**
```
Task Complete → Trigger Review → Run Command → Parse Output → Store Review
```

**Configuration:**
```python
@dataclass
class ReviewConfig:
    enabled: bool = True
    command: str = "claude /review"           # Command to run in session
    trigger: str = "on_complete"              # When to trigger: "on_complete", "manual"
    auto_advance: bool = False                # Auto-advance task status based on review

@dataclass
class Review:
    task_id: str
    status: ReviewStatus                      # PENDING, PASSED, NEEDS_CHANGES, FAILED
    summary: str                              # One-line summary
    issues: list[ReviewIssue]                 # Detailed issues found
    timestamp: datetime
    reviewer: str = "llm"                     # "llm" or "human"
```

**Review Status Flow:**
```
Task COMPLETE → Review PENDING → Run review command → Parse output → PASSED/NEEDS_CHANGES
```

**Implementation:**
```python
class ReviewService:
    async def trigger_review(self, task: Task, session: ManagedSession):
        """Run review command and parse output"""
        review = Review(task_id=task.id, status=ReviewStatus.PENDING, ...)
        self.state.reviews[task.id] = review

        # Send review command to session
        await session.send_text(self.config.command + "\n")

        # Monitor output for review completion
        await self.await_review_complete(session, review)

    async def await_review_complete(self, session: ManagedSession, review: Review):
        """Parse session output for review results"""
        # Uses pattern matching to detect review completion
        # Parses structured output or uses subagent to interpret
        ...
```

---

### Project Scripts

Named scripts with keybindings for common project operations.

**Configuration:**
```python
@dataclass
class ProjectScript:
    name: str                      # Display name
    command: str                   # Command to execute
    keybinding: str | None         # e.g., "ctrl+t" for tests
    session: str = "default"       # Which session to run in
    description: str = ""          # Shown in script picker

# In project config:
scripts:
  - name: "Run Tests"
    command: "npm test"
    keybinding: "ctrl+t"
    session: "tests"
  - name: "Build"
    command: "npm run build"
    keybinding: "ctrl+b"
```

**Script Picker UI:**
```
┌────────────────────────────────────────┐
│  Project Scripts                       │
├────────────────────────────────────────┤
│  > Run Tests          [ctrl+t]         │
│    Build              [ctrl+b]         │
│    Lint               [ctrl+l]         │
│    Deploy Staging                      │
│    Deploy Production                   │
└────────────────────────────────────────┘
```

**Implementation:**
```python
class ScriptService:
    def __init__(self, project: Project, session_manager: SessionManager):
        self.scripts = project.config.scripts

    async def run_script(self, script_name: str):
        script = self.get_script(script_name)
        session = self.get_or_create_session(script.session)
        await session.send_text(script.command + "\n")

    def get_keybindings(self) -> dict[str, str]:
        """Returns {keybinding: script_name} for registration"""
        return {s.keybinding: s.name for s in self.scripts if s.keybinding}
```

---

### Git Operations

Full git integration for status, commit, and push from the TUI.

**Git Service:**
```python
@dataclass
class GitStatus:
    branch: str
    ahead: int = 0
    behind: int = 0
    staged: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    has_conflicts: bool = False

class GitService:
    async def status(self, project_path: str) -> GitStatus:
        """Run git status and parse output"""
        result = await run_command("git", "-C", project_path, "status", "--porcelain", "-b")
        return self.parse_status(result.stdout)

    async def commit(self, project_path: str, message: str, files: list[str] | None = None):
        """Stage and commit files"""
        if files:
            await run_command("git", "-C", project_path, "add", *files)
        else:
            await run_command("git", "-C", project_path, "add", "-A")
        await run_command("git", "-C", project_path, "commit", "-m", message)

    async def push(self, project_path: str, force: bool = False):
        """Push to remote"""
        args = ["git", "-C", project_path, "push"]
        if force:
            args.append("--force-with-lease")
        await run_command(*args)
```

**Git Panel in Project Screen:**
```
┌─────────────────────────────────────┐
│  Git: main ↑2 ↓0                    │
├─────────────────────────────────────┤
│  Staged (2):                        │
│    M src/app.py                     │
│    A src/new_file.py                │
│  Modified (1):                      │
│    M README.md                      │
│                                     │
│  [c] Commit  [p] Push  [r] Refresh  │
└─────────────────────────────────────┘
```

---

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

## Package Structure

```
iterm_controller/
├── __init__.py
├── __main__.py           # Entry point: python -m iterm_controller
├── app.py                # Main Textual app class
├── state.py              # AppState, event system
├── models.py             # All dataclasses (Project, Session, Task, Review, Script, etc.)
├── config.py             # Config loading/saving, merging, paths
├── iterm_api.py          # iTerm2 connection, session management
├── session_monitor.py    # Output polling, streaming, attention detection
├── plan_parser.py        # PLAN.md parsing with review tracking
├── plan_watcher.py       # File watching for PLAN.md changes
├── git_service.py        # Git operations (status, commit, push)
├── review_service.py     # Auto-review pipeline
├── script_service.py     # Named scripts execution
├── github.py             # gh CLI wrapper with graceful degradation
├── notifications.py      # macOS notification sender
├── env_parser.py         # .env file parsing
├── health_checker.py     # HTTP health check polling
├── window_layouts.py     # Predefined window/tab layout management
├── screens/
│   ├── __init__.py
│   ├── mission_control.py   # Main screen with live session output
│   ├── project_screen.py    # Unified project view (plan/docs/work/test sections)
│   ├── project_list.py      # Project browser
│   ├── new_project.py       # Project creation form
│   ├── settings.py          # App settings
│   └── modals/
│       ├── __init__.py
│       ├── quit_confirm.py      # Quit options: close all/managed/leave
│       ├── script_picker.py     # Script selection
│       ├── docs_picker.py
│       ├── github_actions.py
│       ├── commit_modal.py      # Git commit message entry
│       └── plan_conflict.py     # PLAN.md external edit resolution
└── widgets/
    ├── __init__.py
    ├── session_output.py    # Live session output display
    ├── session_list.py      # Session rows with status indicators
    ├── task_list.py         # PLAN.md task display with review status
    ├── git_panel.py         # Git status and operations
    ├── review_panel.py      # Review status display
    ├── script_buttons.py    # Quick-access script buttons
    ├── health_status.py     # Health check indicators
    └── github_panel.py      # PR/branch status with degradation
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
- **Live output streaming**: Near real-time display of session output

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
- [x] **Output streaming architecture**: Push model with subscribers. See [Live Output Streaming](#live-output-streaming).
- [x] **Review automation**: Configurable command with parsing. See [Auto-Review Workflow](#auto-review-workflow).

### Still Open

- [ ] **Multi-window support**: Should projects span multiple iTerm2 windows? Current spec assumes single window per project.
- [ ] **Review parser strategy**: Use structured output format vs. subagent interpretation?

## Security Considerations

- **No secrets in config**: Sensitive env vars are masked in UI display
- **gh CLI auth**: Leverages existing `gh auth` - no token storage
- **git credentials**: Uses system git credential helper
- **Local only**: No network access except health checks and GitHub API via `gh`

---
*Updated with Mission Control architecture on 2026-02-02*
