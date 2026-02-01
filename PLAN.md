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

- [ ] **Implement keyboard shortcuts** `[pending]`
  - Scope: Add shortcuts for common actions (spawn, kill, navigate)
  - Acceptance: Shortcuts work and are documented in help

- [ ] **Add error handling and logging** `[pending]`
  - Scope: Graceful error handling, structured logging for debugging
  - Acceptance: Errors don't crash app, can diagnose issues from logs

- [ ] **Write integration tests** `[pending]`
  - Scope: Test full workflows with mocked iTerm2 API
  - Acceptance: CI passes, core paths covered

- [ ] **Create installation script** `[pending]`
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

## Open Questions

- [ ] **Multi-window support**: Should projects span multiple iTerm2 windows? Current design assumes single window per project.

---
*Generated from PRD.md and specs/README.md on 2026-01-31*
