# Plan: iTerm2 Project Orchestrator

## Overview

Build a Python-based TUI application that serves as a "control room" for development projects. One command opens a project with all dev environment tabs spawned, configured, and monitored.

**Success criteria:**
- Create projects from templates with setup scripts and spawned sessions
- Control Room displays all sessions with accurate status (Working/Waiting/Idle)
- System notifications within 5 seconds when sessions need attention
- Spawn/kill sessions from dashboard
- Task progress from PLAN.md
- Health checks for configured endpoints
- GitHub panel with branch sync and PR info
- Quit confirmation with close options
- Settings for defaults (IDE, shell, notifications)
- Auto mode with stage-specific commands
- Window launch with predefined tab layouts

## Architecture Reference

See [specs/README.md](./specs/README.md) for full technical specification including:
- Component architecture diagram
- Data models and configuration schemas
- iTerm2 API integration patterns
- Feature specifications (health checks, auto mode, quit confirmation, etc.)

## Tasks

### Phase 1: Project Foundation

- [x] **Set up Python package structure** `[complete]`
  - Spec: specs/README.md#package-structure
  - Scope: Create iterm_controller package with __init__.py, __main__.py, empty module files
  - Acceptance: `python -m iterm_controller` runs without import errors

- [x] **Create core data models** `[complete]`
  - Spec: specs/models.md
  - Scope: Implement dataclasses for Project, Session, Task, Config, HealthCheck, etc.
  - Acceptance: All models serializable to/from JSON with dacite

- [x] **Implement configuration loading** `[complete]`
  - Spec: specs/config.md#configuration-merging
  - Scope: Load global config from ~/.config/iterm-controller/config.json, merge with project-local overrides
  - Acceptance: Config merging works per spec (scalars override, lists replace, dicts merge, null removes)

- [x] **Add environment file parser** `[complete]`
  - Spec: specs/config.md#environment-file-parsing
  - Scope: Parse .env files for session environment variables and placeholder resolution
  - Acceptance: Parses KEY=value, handles quotes, expands ${VAR} references

- [x] **Implement template management** `[complete]`
  - Spec: specs/config.md#project-templates
  - Scope: Template CRUD operations, schema validation, required field checking
  - Acceptance: Can list/add/update/delete templates, validation catches errors

- [x] **Add template setup script runner** `[complete]`
  - Spec: specs/config.md#running-setup-scripts
  - Scope: Execute template setup scripts during project creation with variable substitution
  - Acceptance: Scripts run in project directory, variables substituted, errors handled

### Phase 2: iTerm2 Integration

- [x] **Establish iTerm2 connection** `[complete]`
  - Spec: specs/iterm.md#connection-management
  - Scope: Connect to iTerm2 Python API, handle connection lifecycle
  - Acceptance: Can connect, verify iTerm2 version, gracefully handle disconnection

- [x] **Implement session spawning** `[complete]`
  - Spec: specs/iterm.md#session-spawning
  - Scope: Create tabs/panes in iTerm2 windows, send initial commands from SessionTemplate
  - Acceptance: Can spawn tabs and split panes per configuration

- [x] **Build output polling system** `[complete]`
  - Spec: specs/session-monitor.md#polling-architecture
  - Scope: Poll session output at configurable interval (default 500ms)
  - Acceptance: Captures session output reliably without performance degradation

- [x] **Implement attention state detection** `[complete]`
  - Spec: specs/session-monitor.md#attention-state-detection
  - Scope: Apply pattern matching for WAITING/WORKING/IDLE states
  - Acceptance: Detects Claude prompts, shell prompts, and activity correctly

- [x] **Add window layout spawning** `[complete]`
  - Spec: specs/iterm.md#window-layout-spawning
  - Scope: Launch new iTerm2 windows with predefined tab/session layouts
  - Acceptance: WindowLayout configurations spawn correct structure

- [x] **Implement session termination** `[complete]`
  - Spec: specs/iterm.md#session-termination
  - Scope: Graceful session shutdown with SIGTERM, timeout, and SIGKILL fallback
  - Acceptance: Sessions close cleanly, forced close works after timeout

- [x] **Add adaptive polling** `[complete]`
  - Spec: specs/session-monitor.md#adaptive-polling
  - Scope: Adjust polling rate based on session activity (faster when active, slower when idle)
  - Acceptance: Polling interval adapts dynamically, no performance degradation

- [x] **Implement window layout persistence** `[complete]`
  - Spec: specs/config.md#window-layout-configuration
  - Scope: Save/load/reuse window layouts to configuration
  - Acceptance: Layouts persist across sessions, can save current layout

### Phase 3: PLAN.md Integration

- [x] **Build PLAN.md parser** `[complete]`
  - Spec: specs/plan-parser.md#parsing
  - Scope: Parse markdown task lists with metadata (Status, Spec, Session, Depends)
  - Acceptance: Extracts phases, tasks, statuses, and dependencies

- [x] **Implement PLAN.md updater** `[complete]`
  - Spec: specs/plan-parser.md#updating
  - Scope: Update task status in PLAN.md while preserving formatting
  - Acceptance: Status changes written back correctly without corrupting file

- [x] **Add file watcher for PLAN.md** `[complete]`
  - Spec: specs/plan-parser.md#file-watching
  - Scope: Use watchfiles to detect external changes, trigger reload/conflict resolution
  - Acceptance: External edits detected within 1 second

- [x] **Implement conflict resolution UI** `[complete]`
  - Spec: specs/plan-parser.md#conflict-resolution
  - Scope: Show diff and prompt for reload/keep decision
  - Acceptance: Modal displays changes, user can choose action

- [x] **Add write queue for PLAN.md** `[complete]`
  - Spec: specs/plan-parser.md#write-queue-management
  - Scope: Queue pending writes, handle external changes during write operations
  - Acceptance: Writes don't conflict with external edits, queue processes correctly

### Phase 4: Core TUI Framework

- [x] **Create main Textual app** `[complete]`
  - Spec: specs/app.md#main-application-class
  - Scope: Set up Textual app with screen navigation, CSS styling
  - Acceptance: App launches, can navigate between placeholder screens

- [x] **Implement app state manager** `[complete]`
  - Spec: specs/app.md#app-state-manager
  - Scope: Reactive state for projects, sessions, settings with event dispatch
  - Acceptance: State changes trigger UI updates automatically

- [x] **Build session list widget** `[complete]`
  - Spec: specs/ui.md#session-list-widget
  - Scope: Display sessions with status indicators (Working/Waiting/Idle icons)
  - Acceptance: Session status updates reflected in real-time

- [x] **Build task list widget** `[complete]`
  - Spec: specs/ui.md#task-list-widget
  - Scope: Display tasks with phases, dependencies, blocked state dimming
  - Acceptance: Blocked tasks show "blocked by X" and are dimmed

- [x] **Build workflow bar widget** `[complete]`
  - Spec: specs/auto-mode.md#workflow-bar-widget
  - Scope: Display Planning → Execute → Review → PR → Done stages
  - Acceptance: Current stage highlighted, progress visible

- [x] **Implement task progress aggregation** `[complete]`
  - Spec: specs/models.md#task-models
  - Scope: Calculate task completion percentages per phase and overall
  - Acceptance: Dashboard shows accurate progress stats (e.g., "3/5 tasks complete")

### Phase 5: Screens

- [x] **Build Control Room screen** `[complete]`
  - Spec: specs/ui.md#control-room-screen
  - Scope: Main dashboard showing all sessions across all projects
  - Acceptance: Lists all active sessions, shows status, supports spawn/kill

- [x] **Build Project Dashboard screen** `[complete]`
  - Spec: specs/ui.md#project-dashboard-screen
  - Scope: Single project view with tasks, sessions, workflow bar
  - Acceptance: Shows project-specific sessions, PLAN.md tasks, health status

- [x] **Build Project List screen** `[complete]`
  - Spec: specs/ui.md#project-list-screen
  - Scope: Browse and select projects from config
  - Acceptance: Lists projects, can open project dashboard

- [x] **Build New Project screen** `[complete]`
  - Spec: specs/ui.md#new-project-screen
  - Scope: Create project from template, run setup script, create branch
  - Acceptance: Template selection, form inputs, spawns initial sessions

- [x] **Build Settings screen** `[complete]`
  - Spec: specs/ui.md#settings-screen
  - Scope: Configure defaults (IDE, shell, polling interval, notifications)
  - Acceptance: Settings persist to global config

### Phase 6: Modals & Dialogs

- [x] **Implement quit confirmation modal** `[complete]`
  - Spec: specs/app.md#lifecycle-management
  - Scope: Offer Close All / Close Managed / Leave Running options
  - Acceptance: Each option behaves correctly per spec

- [x] **Implement script picker modal** `[complete]`
  - Scope: Select and run project scripts in new sessions
  - Acceptance: Lists scripts, spawns session with selected command

- [x] **Implement docs picker modal** `[complete]`
  - Scope: Quick access to project documentation files
  - Acceptance: Lists docs, opens selected file in editor

### Phase 7: GitHub Integration

- [x] **Implement gh CLI wrapper** `[complete]`
  - Spec: specs/github.md
  - Scope: Check availability, fetch branch sync status, PR info
  - Acceptance: Graceful degradation when gh unavailable or unauthenticated

- [x] **Build GitHub panel widget** `[complete]`
  - Spec: specs/github.md#github-status-widget
  - Scope: Display branch status, PR info, comments
  - Acceptance: Shows data when available, hides/degrades gracefully

- [x] **Add GitHub actions modal** `[complete]`
  - Spec: specs/github.md#github-actions-modal
  - Scope: View workflow runs and status
  - Acceptance: Lists recent runs, shows pass/fail status

### Phase 8: Notifications & Health

- [x] **Implement macOS notifications** `[complete]`
  - Spec: specs/notifications.md
  - Scope: Send notifications via terminal-notifier when session enters WAITING
  - Acceptance: Notification fires within 5 seconds of state change

- [x] **Build health check poller** `[complete]`
  - Spec: specs/health-checks.md
  - Scope: Poll HTTP endpoints, resolve env placeholders, update status
  - Acceptance: Health indicators update correctly, handle timeouts/errors

- [x] **Build health status widget** `[complete]`
  - Spec: specs/health-checks.md#health-status-widget
  - Scope: Display health check status in project dashboard
  - Acceptance: Shows green/red indicators per service

- [x] **Add notification latency tracking** `[complete]`
  - Spec: specs/notifications.md#notification-latency-verification
  - Scope: Track and verify notification latency meets 5-second SLA
  - Acceptance: Latency measured, SLA violations logged, stats available

### Phase 9: Auto Mode

- [x] **Implement workflow stage inference** `[complete]`
  - Spec: specs/auto-mode.md#stage-inference
  - Scope: Detect current stage from PLAN.md and project state
  - Acceptance: Stage correctly identified based on completion criteria

- [x] **Implement auto advance logic** `[complete]`
  - Spec: specs/auto-mode.md#auto-mode-controller
  - Scope: Trigger stage commands when phase completes
  - Acceptance: Commands execute (with confirmation if configured)

- [x] **Build auto mode configuration UI** `[complete]`
  - Spec: specs/auto-mode.md#configuration
  - Scope: Configure stage commands and auto-advance settings
  - Acceptance: Settings persist and affect behavior

### Phase 10: Polish & Validation

- [x] **Add spec file validation** `[complete]`
  - Spec: specs/README.md#spec-file-validation
  - Scope: Validate spec references in tasks, show warnings for missing files
  - Acceptance: Invalid refs show warning indicator in task list

- [x] **Implement keyboard shortcuts** `[complete]`
  - Scope: Add shortcuts for common actions (spawn, kill, navigate)
  - Acceptance: Shortcuts work and are documented in help

- [x] **Add error handling and logging** `[complete]`
  - Scope: Graceful error handling, structured logging for debugging
  - Acceptance: Errors don't crash app, can diagnose issues from logs

- [x] **Write integration tests** `[complete]`
  - Scope: Test full workflows with mocked iTerm2 API
  - Acceptance: CI passes, core paths covered

- [x] **Create installation script** `[complete]`
  - Scope: Script to install dependencies, configure iTerm2 settings
  - Acceptance: New user can get running with single command

## Dependencies

| Dependency | Purpose | Install |
|------------|---------|---------|
| iTerm2 3.5+ | Terminal control | Required |
| Python 3.11+ | Runtime | `brew install python@3.11` |
| textual ~2.x | TUI framework | `pip install textual` |
| iterm2 ~2.x | iTerm2 API | `pip install iterm2` |
| dacite ~1.8 | JSON→dataclass | `pip install dacite` |
| watchfiles ~0.21 | File watching | `pip install watchfiles` |
| httpx ~0.27 | Health checks | `pip install httpx` |
| gh CLI | GitHub integration | `brew install gh` (optional) |
| terminal-notifier | macOS notifications | `brew install terminal-notifier` (optional) |

### Phase 11: Bug Fixes & Improvements

- [x] **Add Jira ticket field to New Project screen** `[complete]`
  - Scope: Add optional Jira ticket # field to the Create New Project form
  - Acceptance: Field appears in form, value saved to project configuration

- [x] **Auto-refresh project list after creating project** `[complete]`
  - Scope: Project list screen should automatically refresh after a new project is created
  - Acceptance: New project appears in list without manual navigation

- [x] **Fix project selection with Enter key** `[complete]`
  - Scope: Pressing Enter on a selected project in the project list should open it
  - Affects: Direct project list access AND Control Room "Select a project first" flow when spawning sessions
  - Root cause: Screen binding `Binding("enter", "open_project")` is intercepted by DataTable, which emits `DataTable.RowSelected` instead
  - Fix: Add `on_data_table_row_selected` handler instead of relying on the binding
  - Acceptance: Enter key opens the selected project's dashboard

- [x] **Fix keyboard shortcuts for Settings and Sessions screens** `[complete]`
  - Scope: Settings uses `s`/`ctrl+s` but should use `,`/`ctrl+,` (standard convention). Sessions/Control Room should use `s`/`ctrl+s`
  - Fix: Update bindings in app.py - change settings to comma, add sessions shortcut with `s`
  - Acceptance: `,` or `ctrl+,` opens Settings, `s` or `ctrl+s` opens Sessions/Control Room

- [x] **Fix all push_screen_wait crashes (NoActiveWorker errors)** `[complete]`
  - Scope: Multiple actions crash with `NoActiveWorker: push_screen must be run from a worker when wait_for_dismiss is True`
  - Root cause: `push_screen_wait()` requires a worker context but action handlers run in the main event loop
  - Affected locations:
    - `app.py:86` - `action_quit` → QuitConfirmModal
    - `app.py:178` - `action_show_help` → HelpModal
    - `control_room.py:151` - `action_spawn_session` → ScriptPickerModal
    - `project_dashboard.py:200` - action handler → ScriptPickerModal
    - `project_dashboard.py:245` - action handler → ScriptPickerModal
    - `project_dashboard.py:279` - `action_open_docs` → DocsPickerModal
    - `settings.py:156` - action handler → modal
    - `auto_mode.py:443` - may need review
  - Fix: Use `self.app.push_screen()` with callback instead, or use `@work` decorator
  - Acceptance: All modal-triggering shortcuts work without crashing

### Phase 12: Workflow Mode Infrastructure

- [x] **Add WorkflowMode enum to models** `[complete]`
  - Spec: specs/models.md#workflow-mode-models
  - Scope: Add WorkflowMode enum (PLAN, DOCS, WORK, TEST) and last_mode field to Project
  - Acceptance: Enum importable, Project.last_mode persists to JSON

- [x] **Add mode navigation bindings to ProjectDashboard** `[complete]`
  - Spec: specs/ui.md#workflow-modes
  - Scope: Add 1-4 keybindings to navigate to mode screens from Project Dashboard
  - Acceptance: Pressing 1-4 pushes appropriate mode screen

- [x] **Create ModeScreen base class** `[complete]`
  - Spec: specs/workflow-modes.md#screen-base-class
  - Scope: Shared base with common bindings (1-4 mode switch, Esc back)
  - Acceptance: All mode screens inherit common navigation

- [x] **Add mode persistence to Project model** `[complete]`
  - Spec: specs/workflow-modes.md#mode-persistence
  - Scope: Save/restore last_mode, update on mode change
  - Acceptance: Reopening project restores last mode

- [x] **Register mode screens in app.py** `[complete]`
  - Scope: Register PlanModeScreen, DocsModeScreen, WorkModeScreen, TestModeScreen
  - Acceptance: All mode screens accessible via navigation

### Phase 13: Plan Mode

- [x] **Create PlanModeScreen with artifact list** `[complete]`
  - Spec: specs/plan-mode.md
  - Scope: Show PROBLEM.md, PRD.md, specs/, PLAN.md with status indicators
  - Acceptance: Artifact list displays with correct exists/missing status

- [x] **Implement artifact existence checking** `[complete]`
  - Spec: specs/plan-mode.md#artifact-existence-check
  - Scope: Check file/directory existence, count specs, count tasks
  - Acceptance: Status indicators accurate for all artifacts

- [x] **Add create/edit actions for artifacts** `[complete]`
  - Spec: specs/plan-mode.md#actions
  - Scope: `c` creates missing artifact via Claude, `e` opens in editor
  - Acceptance: Can create PRD.md and open it for editing

- [x] **Add inline artifact preview** `[complete]`
  - Spec: specs/plan-mode.md#inline-preview
  - Scope: Enter key shows markdown preview modal
  - Acceptance: Can preview PRD.md content inline

- [x] **Integrate with Auto Mode planning commands** `[complete]`
  - Spec: specs/auto-mode.md#mode-specific-automation
  - Scope: Trigger mode_commands.plan when entering Plan Mode
  - Acceptance: Configured command runs on mode entry

### Phase 14: Work Mode

- [x] **Create WorkModeScreen with task queue** `[complete]`
  - Spec: specs/work-mode.md
  - Scope: Two-panel layout: task queue (pending) and active work (in_progress)
  - Acceptance: Tasks displayed in correct panels by status

- [x] **Implement task claiming (claim/unclaim)** `[complete]`
  - Spec: specs/work-mode.md#claim-workflow
  - Scope: `c` claims task (sets in_progress), `u` unclaims (back to pending)
  - Acceptance: Task status changes persist to PLAN.md

- [x] **Add task-session linking** `[complete]`
  - Spec: specs/work-mode.md#task-session-linking
  - Scope: When spawning for task, link session to task, show in active work
  - Acceptance: Session shows which task it's working on

- [x] **Show active work with session status** `[complete]`
  - Spec: specs/work-mode.md#active-work-panel
  - Scope: Display task with assigned session, started time, attention state
  - Acceptance: Active tasks show linked session status

- [x] **Add blocked task visualization** `[complete]`
  - Spec: specs/work-mode.md#blocked-task-view
  - Scope: Show dependency chain, `v` key for detailed view
  - Acceptance: Blocked tasks dimmed with "blocked by" suffix

### Phase 15: Test Mode

- [x] **Create TestStep and TestPlan models** `[complete]`
  - Spec: specs/test-plan-parser.md#parsing
  - Scope: TestStatus enum, TestStep, TestSection, TestPlan dataclasses
  - Acceptance: Models serialize to/from JSON

- [x] **Implement TEST_PLAN.md parser** `[complete]`
  - Spec: specs/test-plan-parser.md
  - Scope: Parse markdown checkboxes with [ ]/[~]/[x]/[!] markers
  - Acceptance: Parses sections, steps, statuses, notes

- [x] **Create TestPlanWatcher for file changes** `[complete]`
  - Spec: specs/test-plan-parser.md#file-watching
  - Scope: Watch TEST_PLAN.md, emit events on change, handle conflicts
  - Acceptance: External edits detected within 1 second

- [x] **Create TestModeScreen with step list** `[complete]`
  - Spec: specs/test-mode.md
  - Scope: Two-panel layout: TEST_PLAN.md steps and unit test results
  - Acceptance: Test steps displayed with status indicators

- [x] **Add unit test runner integration** `[complete]`
  - Spec: specs/test-mode.md#secondary-unit-test-runner
  - Scope: Detect test command, `r` runs tests, display results
  - Acceptance: Can run pytest/npm test and see results

- [x] **Implement test command detection** `[complete]`
  - Spec: specs/test-mode.md#test-command-detection
  - Scope: Auto-detect from pytest.ini, package.json, Makefile, etc.
  - Acceptance: Correct test command detected for project type

- [x] **Add TEST_PLAN.md generation** `[complete]`
  - Spec: specs/test-mode.md#generate-test_planmd
  - Scope: `g` key launches Claude to generate test plan from PRD/specs
  - Acceptance: Can generate TEST_PLAN.md with verification steps

### Phase 16: Docs Mode

- [x] **Create DocsModeScreen with tree widget** `[complete]`
  - Spec: specs/docs-mode.md
  - Scope: Tree view of docs/, specs/, README.md, CHANGELOG.md
  - Acceptance: Documentation tree displays with folders collapsible

- [x] **Implement folder/file tree navigation** `[complete]`
  - Spec: specs/docs-mode.md#actions
  - Scope: Arrow keys navigate, Enter opens/expands, Left/Right collapse/expand
  - Acceptance: Can navigate entire doc tree with keyboard

- [x] **Add document CRUD operations** `[complete]`
  - Spec: specs/docs-mode.md#add-document-modal
  - Scope: `a` adds, `d` deletes (with confirm), `r` renames
  - Acceptance: Can create docs/new-file.md and delete it

- [x] **Add inline preview for markdown** `[complete]`
  - Spec: specs/docs-mode.md#inline-preview
  - Scope: `p` key shows markdown preview modal
  - Acceptance: Can preview README.md content inline

### Phase 17: Mode Integration

- [x] **Extend Auto Mode for mode-specific commands** `[complete]`
  - Spec: specs/auto-mode.md#mode-specific-automation
  - Scope: Add mode_commands config, trigger on mode entry
  - Acceptance: Entering Plan Mode can auto-run "claude /prd"

- [x] **Add mode indicator to header** `[complete]`
  - Spec: specs/workflow-modes.md#mode-indicator
  - Scope: Show current mode and 1-4 shortcuts in header
  - Acceptance: Header shows "[Plan] 1 2 3 4" with current highlighted

- [x] **Implement mode persistence (restore on reopen)** `[complete]`
  - Spec: specs/workflow-modes.md#mode-persistence
  - Scope: Save last_mode to project, restore on project open
  - Acceptance: Closing and reopening project returns to last mode

- [x] **Update help screen with mode shortcuts** `[complete]`
  - Scope: Add workflow modes section to help modal
  - Acceptance: Help shows 1-4 key descriptions for modes

### Phase 18: Security Fixes (Critical)

- [x] **Fix shell injection in template setup script** `[complete]`
  - Scope: Replace `asyncio.create_subprocess_shell()` with `create_subprocess_exec()` in templates.py
  - Location: iterm_controller/templates.py:280
  - Fix: Use `shlex.split()` and `create_subprocess_exec()`, validate all user inputs with `shlex.quote()`
  - Acceptance: Setup scripts run safely, malicious variable values cannot inject commands

- [x] **Fix command injection in session spawning** `[complete]`
  - Scope: Escape shell metacharacters in `_escape_value()` and validate environment variable keys
  - Location: iterm_controller/iterm_api.py:300-323
  - Fix: Use `shlex.quote()` for all values, validate env keys with regex `^[A-Za-z_][A-Za-z0-9_]*$`
  - Acceptance: Cannot inject commands via template.env values or keys

- [x] **Fix arbitrary command execution in auto mode** `[complete]`
  - Scope: Implement command allowlisting for auto mode commands
  - Location: iterm_controller/auto_mode.py:535-621
  - Fix: Add command validation against expected patterns or allowlist
  - Acceptance: Only approved commands can be executed via auto mode

### Phase 19: Type System & Code Quality (Critical)

- [x] **Rename ConnectionError to avoid shadowing built-in** `[complete]`
  - Scope: Rename `ConnectionError` class to `ItermControllerConnectionError`
  - Location: iterm_controller/exceptions.py:51
  - Fix: Find/replace all usages across codebase
  - Acceptance: No shadowing of Python's built-in `ConnectionError`

- [x] **Fix callable type hint to Callable** `[complete]`
  - Scope: Change `-> callable` to proper `-> Callable[[re.Match[str]], str]` return type
  - Location: iterm_controller/plan_parser.py:278
  - Fix: Import `Callable` from typing, use correct generic type
  - Acceptance: mypy passes without type errors

- [x] **Add type hints to **kwargs in widgets** `[complete]`
  - Scope: Add `**kwargs: Any` type hint to widget constructors
  - Locations: widgets/session_list.py:61, widgets/task_list.py:76
  - Fix: Import `Any` from typing, add annotation
  - Acceptance: All widget constructors have complete type hints

- [x] **Remove duplicate exception classes from iterm_api.py** `[complete]`
  - Scope: Remove local exception definitions, import from exceptions.py instead
  - Location: iterm_controller/iterm_api.py:40-55
  - Fix: Delete duplicate classes, add imports from `exceptions`
  - Acceptance: Single source of truth for exception classes

- [x] **Remove empty TYPE_CHECKING blocks** `[complete]`
  - Scope: Clean up empty `if TYPE_CHECKING: pass` blocks
  - Locations: models.py:17-18, widgets/task_list.py:19-20, widgets/task_queue.py:17-18, app.py:29-30, iterm_api.py:27-28
  - Fix: Remove empty blocks or add actual type imports
  - Acceptance: No empty TYPE_CHECKING blocks in codebase

- [x] **Remove unused import load_global_config from app.py** `[complete]`
  - Scope: Remove unused import
  - Location: iterm_controller/app.py:13
  - Acceptance: No unused imports in app.py

### Phase 20: Agent-Native Architecture (Critical)

- [x] **Create public API module for programmatic access** `[complete]`
  - Scope: Create iterm_controller/api.py exposing core operations as async functions
  - Functions: spawn_session, kill_session, open_project, claim_task, toggle_test_step, etc.
  - Acceptance: All 28 UI actions have programmatic equivalents

- [x] **Add CLI subcommands for headless operation** `[complete]`
  - Scope: Add argparse subparsers to __main__.py for command-line operations
  - Depends: Phase 20 task 1
  - Commands: spawn, kill, list-projects, list-sessions, task claim, task done
  - Acceptance: Can perform operations without launching TUI

- [x] **Add state query API for external observation** `[complete]`
  - Scope: Add methods to query state without TUI context
  - Location: iterm_controller/state.py
  - Functions: get_state(), get_sessions(), get_plan()
  - Acceptance: External tools can query current sessions, tasks, project state

- [x] **Extract core logic from action methods** `[complete]`
  - Scope: Separate business logic from TUI-specific code in action_* methods
  - Locations: All screen action handlers
  - Fix: Move core logic to api.py, have action methods call API
  - Acceptance: All keyboard shortcuts have callable API equivalents

- [x] **Export public API from __init__.py** `[complete]`
  - Scope: Export key classes and functions for external use
  - Exports: ItermController, SessionSpawner, AppState, Project, ManagedSession, Task, Plan, config functions
  - Acceptance: Can `from iterm_controller import Controller, Project` etc.

- [x] **Document agent integration patterns** `[complete]`
  - Scope: Create documentation showing programmatic usage
  - Acceptance: README includes example of API usage without TUI

### Phase 21: Path Traversal Security (High)

- [x] **Add centralized path validation utility** `[complete]`
  - Scope: Create utility function to validate paths stay within project directory
  - Location: New file iterm_controller/security.py
  - Function: `validate_path_in_project(path: Path, project_root: Path) -> bool`
  - Acceptance: Reusable validation across all file operations

- [x] **Fix path traversal in spec validator** `[complete]`
  - Scope: Validate spec references don't escape project directory
  - Location: iterm_controller/spec_validator.py:66-71
  - Depends: Phase 21 task 1
  - Fix: Use centralized path validation before accessing files
  - Acceptance: `../../../etc/passwd` spec refs are rejected

- [x] **Fix path traversal in document operations** `[complete]`
  - Scope: Validate all document paths in docs mode
  - Location: iterm_controller/screens/modes/docs_mode.py:477-544
  - Depends: Phase 21 task 1
  - Fix: Validate create/delete/rename paths stay in project
  - Acceptance: Cannot create/delete files outside project directory

- [x] **Fix path traversal in add document modal** `[complete]`
  - Scope: Validate filename doesn't contain traversal sequences
  - Location: iterm_controller/screens/modals/add_document.py:165-192
  - Depends: Phase 21 task 1
  - Fix: Reject filenames with `..` or `/` characters
  - Acceptance: Cannot create files outside intended directory

- [x] **Add editor command allowlist** `[complete]`
  - Scope: Validate editor commands against known-safe list
  - Locations: docs_mode.py, plan_mode.py, docs_picker.py subprocess calls
  - Fix: Only allow editors from EDITOR_COMMANDS dict
  - Acceptance: Cannot execute arbitrary commands via editor setting

### Phase 22: Code Duplication Cleanup (Important)

- [x] **Extract EDITOR_COMMANDS to shared module** `[complete]`
  - Scope: Create shared constants for editor command mapping
  - Location: New file iterm_controller/editors.py
  - Currently duplicated in: plan_mode.py:42-54, docs_mode.py:34-46
  - Acceptance: Single source of truth for editor commands

- [x] **Extract _open_in_editor to ModeScreen base class** `[complete]`
  - Scope: Move duplicated editor-opening logic to shared location
  - Depends: Phase 22 task 1
  - Currently duplicated in: plan_mode.py:319-353, docs_mode.py:442-475
  - Acceptance: Single implementation of editor opening logic

- [x] **Create TaskDependencyResolver utility** `[complete]`
  - Scope: Extract is_task_blocked() and get_blocking_tasks() to shared utility
  - Currently duplicated in: task_list.py:180-221, task_queue.py:122-161, blocked_tasks.py:88-125
  - Acceptance: Single implementation of dependency checking

- [x] **Create shared STATUS_ICONS and STATUS_COLORS constants** `[complete]`
  - Scope: Consolidate status display constants
  - Currently duplicated in: task_list.py:55-69, session_list.py:44-54, active_work.py:60-70
  - Acceptance: Consistent status display across all widgets

- [x] **Remove duplicate StateEvent enum** `[complete]`
  - Scope: Use single StateEvent definition from state.py
  - Location: Remove from iterm_controller/plan_watcher.py:28-32
  - Fix: Import StateEvent from state module instead
  - Acceptance: Single enum definition for state events

### Phase 23: Architecture Improvements (Important)

- [x] **Split iterm_api.py into focused modules** `[complete]`
  - Scope: Break 1207-line file into separate modules
  - New structure: iterm_controller/iterm/connection.py, spawner.py, terminator.py, tracker.py, layout_spawner.py, layout_manager.py
  - Acceptance: Each module < 300 lines with single responsibility

- [x] **Refactor AppState into focused state managers** `[complete]`
  - Scope: Split 571-line god class into smaller managers
  - Components: ProjectStateManager, SessionStateManager, PlanStateManager
  - Acceptance: Each manager has single responsibility

- [x] **Remove dual event system (callbacks)** `[complete]`
  - Scope: Remove unused callback event system, keep only Textual Messages
  - Location: iterm_controller/state.py:221-224, 245-281
  - Fix: Remove subscribe(), unsubscribe(), emit() and _listeners
  - Acceptance: Single event mechanism (Textual Messages only)

- [x] **Add dependency injection for services** `[complete]`
  - Scope: Inject dependencies via app instead of instantiating in screens
  - Fix: Create ServiceContainer, inject SessionSpawner etc via app
  - Acceptance: Screens don't directly instantiate infrastructure classes

- [x] **Create iTerm2 abstraction layer** `[complete]`
  - Scope: Add protocol/interface for terminal operations
  - Location: New file iterm_controller/ports.py with TerminalProvider protocol
  - Acceptance: Can mock iTerm2 operations for testing

- [x] **Fix circular import prevention patterns** `[complete]`
  - Scope: Refactor to eliminate delayed imports for circular dependency prevention
  - Locations: 8 instances across app.py, screens, etc.
  - Acceptance: No `from X import Y` inside functions for circular deps

### Phase 24: Performance Optimizations (Important)

- [x] **Add output buffer size limit** `[complete]`
  - Scope: Limit stored session output to prevent memory bloat
  - Location: iterm_controller/session_monitor.py:491-552
  - Fix: Add MAX_OUTPUT_BUFFER constant (100KB), truncate older output
  - Acceptance: Memory usage stable with long-running sessions

- [x] **Use async file I/O for plan parsing** `[complete]`
  - Scope: Replace synchronous file reads with asyncio.to_thread
  - Locations: plan_parser.py:62-101, plan_watcher.py:159-161, 481-486
  - Fix: Use `await asyncio.to_thread(path.read_text, encoding="utf-8")`
  - Acceptance: Event loop not blocked during file reads

- [x] **Reuse httpx client in health checker** `[complete]`
  - Scope: Create single httpx.AsyncClient instance for reuse
  - Location: iterm_controller/health_checker.py:117-135
  - Fix: Initialize client in __init__, close in stop_polling()
  - Acceptance: Connection pool reused, reduced SSL handshakes

- [x] **Add task lookup dictionary to Plan model** `[complete]`
  - Scope: Cache task by ID for O(1) lookups instead of O(n) linear search
  - Location: iterm_controller/plan_watcher.py:520-524
  - Fix: Add `_task_map_cache` property to Plan model
  - Acceptance: Task status updates are O(1)

- [x] **Cache sorted session list in widget** `[complete]`
  - Scope: Avoid re-sorting on every render
  - Location: iterm_controller/widgets/session_list.py:160-180
  - Fix: Cache sorted list, invalidate on session changes
  - Acceptance: Reduced sorting overhead on frequent renders

- [x] **Debounce UI refresh on state changes** `[complete]`
  - Scope: Prevent UI thrashing with rapid status updates
  - Location: iterm_controller/screens/control_room.py:293-303
  - Fix: Add 100ms debounce timer for refresh calls
  - Acceptance: UI updates batched during rapid changes

### Phase 25: Code Simplification (Nice-to-have)

- [x] **Flatten exception hierarchy** `[complete]`
  - Scope: Reduce 24 exception classes to ~5 essential ones
  - Location: iterm_controller/exceptions.py (531 lines)
  - Keep: ItermControllerError, ConnectionError, ConfigError, PlanError, TemplateNotFoundError
  - Remove: ~19 rarely-used exception classes
  - Acceptance: Exception module < 100 lines
  - Result: Reduced from 569 lines to 119 lines, removed unused classes (SessionError, TemplateError, NotificationError, AutoModeError, TestPlanError, ErrorStats, etc.), kept only actively-used exceptions

- [x] **Remove ErrorStats tracking** `[complete]`
  - Scope: Remove unused error statistics tracking
  - Location: iterm_controller/exceptions.py:500-531
  - Fix: Delete ErrorStats class and record_error function
  - Acceptance: No dead code for unused metrics
  - Result: Removed ErrorStats class, record_error is now a no-op for backward compatibility

- [x] **Remove unused window layout capture** `[complete]`
  - Scope: Delete capture_current_layout and related methods
  - Location: iterm_controller/iterm/layout_manager.py (was 273 lines, now 93 lines)
  - Reason: Never called from production code
  - Acceptance: Only spawn methods remain in layouts
  - Result: Removed capture_current_layout, capture_and_save, _capture_tab, _capture_session, _infer_split_direction and related tests (180 lines removed)

- [x] **Simplify auto_mode.py class structure** `[complete]`
  - Scope: Consolidate 4 classes into single AutoMode class
  - Remove: WorkflowStageInferrer (trivial wrapper), create_controller_for_project factory
  - Acceptance: Single cohesive class for auto mode
  - Result: Created unified AutoMode class (520 lines), kept backward compatibility wrappers for existing API (WorkflowStageInferrer, AutoModeController, AutoAdvanceHandler, AutoModeIntegration, create_controller_for_project) that delegate to AutoMode. All 63 tests pass.

- [ ] **Add logging to silent exception handlers** `[pending]`
  - Scope: Add logging to exception handlers that currently silently swallow errors
  - Location: iterm_controller/state.py:279-281 (comment says log but doesn't)
  - Fix: Add `logger.warning("Subscriber error for %s: %s", event.value, e)`
  - Acceptance: All exception handlers log their errors

- [ ] **Extract magic numbers to named constants** `[pending]`
  - Scope: Replace hardcoded numbers with named constants
  - Locations: task_list.py:264 (padding=40), session_list.py:134 (width=25)
  - Acceptance: No magic numbers in widget rendering code

- [ ] **Remove unused model fields** `[pending]`
  - Scope: Remove fields that are tracked but never meaningfully used
  - Fields: SessionTemplate.health_check, ManagedSession.metadata, TestStep.line_number, HealthCheck.service
  - Acceptance: All model fields have actual usage

- [ ] **Fix import organization** `[pending]`
  - Scope: Consolidate split imports into single lines
  - Location: iterm_controller/screens/project_list.py:15-16
  - Fix: `from textual.widgets import DataTable, Footer, Header, Static`
  - Acceptance: Consistent import style across codebase

- [ ] **Use singleton parsers in MakeTestParser** `[pending]`
  - Scope: Avoid creating parser instances on every parse call
  - Location: iterm_controller/test_output_parser.py:478-506
  - Fix: Use class-level singleton parsers or parser pool
  - Acceptance: Reduced object allocation overhead

- [ ] **Address TODO comments** `[pending]`
  - Scope: Implement or remove 2 remaining TODO comments
  - Locations: project_list.py:232 (delete confirmation), test_mode.py:309 (conflict modal)
  - Acceptance: No TODO comments in production code

## Open Questions

- [~] **Multi-window support**: Should projects span multiple iTerm2 windows? Current design assumes single window per project.

---
*Generated from PRD.md and specs/README.md on 2026-01-31*
*Code review findings added on 2026-02-01*
