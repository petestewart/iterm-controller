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

- [ ] **Add blocked task visualization**
  - Spec: specs/work-mode.md#blocked-task-view
  - Scope: Show dependency chain, `v` key for detailed view
  - Acceptance: Blocked tasks dimmed with "blocked by" suffix

### Phase 15: Test Mode

- [ ] **Create TestStep and TestPlan models**
  - Spec: specs/test-plan-parser.md#parsing
  - Scope: TestStatus enum, TestStep, TestSection, TestPlan dataclasses
  - Acceptance: Models serialize to/from JSON

- [ ] **Implement TEST_PLAN.md parser**
  - Spec: specs/test-plan-parser.md
  - Scope: Parse markdown checkboxes with [ ]/[~]/[x]/[!] markers
  - Acceptance: Parses sections, steps, statuses, notes

- [ ] **Create TestPlanWatcher for file changes**
  - Spec: specs/test-plan-parser.md#file-watching
  - Scope: Watch TEST_PLAN.md, emit events on change, handle conflicts
  - Acceptance: External edits detected within 1 second

- [ ] **Create TestModeScreen with step list**
  - Spec: specs/test-mode.md
  - Scope: Two-panel layout: TEST_PLAN.md steps and unit test results
  - Acceptance: Test steps displayed with status indicators

- [ ] **Add unit test runner integration**
  - Spec: specs/test-mode.md#secondary-unit-test-runner
  - Scope: Detect test command, `r` runs tests, display results
  - Acceptance: Can run pytest/npm test and see results

- [ ] **Implement test command detection**
  - Spec: specs/test-mode.md#test-command-detection
  - Scope: Auto-detect from pytest.ini, package.json, Makefile, etc.
  - Acceptance: Correct test command detected for project type

- [ ] **Add TEST_PLAN.md generation**
  - Spec: specs/test-mode.md#generate-test_planmd
  - Scope: `g` key launches Claude to generate test plan from PRD/specs
  - Acceptance: Can generate TEST_PLAN.md with verification steps

### Phase 16: Docs Mode

- [ ] **Create DocsModeScreen with tree widget**
  - Spec: specs/docs-mode.md
  - Scope: Tree view of docs/, specs/, README.md, CHANGELOG.md
  - Acceptance: Documentation tree displays with folders collapsible

- [ ] **Implement folder/file tree navigation**
  - Spec: specs/docs-mode.md#actions
  - Scope: Arrow keys navigate, Enter opens/expands, Left/Right collapse/expand
  - Acceptance: Can navigate entire doc tree with keyboard

- [ ] **Add document CRUD operations**
  - Spec: specs/docs-mode.md#add-document-modal
  - Scope: `a` adds, `d` deletes (with confirm), `r` renames
  - Acceptance: Can create docs/new-file.md and delete it

- [ ] **Add inline preview for markdown**
  - Spec: specs/docs-mode.md#inline-preview
  - Scope: `p` key shows markdown preview modal
  - Acceptance: Can preview README.md content inline

### Phase 17: Mode Integration

- [ ] **Extend Auto Mode for mode-specific commands**
  - Spec: specs/auto-mode.md#mode-specific-automation
  - Scope: Add mode_commands config, trigger on mode entry
  - Acceptance: Entering Plan Mode can auto-run "claude /prd"

- [ ] **Add mode indicator to header**
  - Spec: specs/workflow-modes.md#mode-indicator
  - Scope: Show current mode and 1-4 shortcuts in header
  - Acceptance: Header shows "[Plan] 1 2 3 4" with current highlighted

- [ ] **Implement mode persistence (restore on reopen)**
  - Spec: specs/workflow-modes.md#mode-persistence
  - Scope: Save last_mode to project, restore on project open
  - Acceptance: Closing and reopening project returns to last mode

- [ ] **Update help screen with mode shortcuts**
  - Scope: Add workflow modes section to help modal
  - Acceptance: Help shows 1-4 key descriptions for modes

## Open Questions

- [~] **Multi-window support**: Should projects span multiple iTerm2 windows? Current design assumes single window per project.

---
*Generated from PRD.md and specs/README.md on 2026-01-31*
