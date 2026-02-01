# PRD: iTerm2 Project Orchestrator

## Problem Statement

**Problem:** Developers working on multiple projects simultaneously face constant context-switching friction. Each project requires multiple terminal tabs/panes (dev servers, test watchers, Claude sessions, linters), remembering which commands to run, manually monitoring session output for prompts requiring attention, and tearing down/rebuilding terminal layouts when switching projects. This is especially painful when running multiple Claude Code sessions—missing a clarifying question means wasted time and lost momentum.

**Context:** A POC exists demonstrating iTerm2's Python API capabilities (spawn tabs/panes, monitor output, detect termination, Textual TUI). Detailed specifications already exist in `docs/APP_SPEC.md` and `docs/DATA_MODEL.md`.

**Desired Outcome:** A terminal-based TUI application that serves as a "control room" for development projects. One command to open a project and have all dev environment tabs spawn, configured, and monitored.

**Success Criteria:**
- Create new projects from templates (runs setup script, creates branch, spawns configured sessions)
- Control Room displays all sessions across projects with accurate status (Working/Waiting/Idle)
- System notification fires within 5 seconds when any session enters Waiting state
- Spawn/kill individual sessions from the dashboard
- Project dashboard shows task progress parsed from PLAN.md
- Health checks poll configured endpoints and display status
- GitHub panel shows branch sync status and PR info (using `gh` CLI)
- Quit confirmation offers options: close all, close managed only, leave running
- Settings screen allows configuring defaults (IDE, shell, notification preferences)
- Auto mode can be configured with stage-specific commands that run when a phase completes
- Launch a new window with a predefined set of tabs/sessions

## Proposed Solution

### Technical Approach

Build a Python-based TUI application using:

1. **Textual framework** for the terminal UI—provides rich widgets, reactive state management, and async support that integrates well with iTerm2's async Python API.

2. **iTerm2 Python API** for terminal control—session creation, output monitoring, and window management. The existing POC validates this approach works.

3. **File-based persistence** (JSON) for project configurations stored at `~/.config/iterm-controller/config.json` with optional project-local overrides at `{project}/.iterm-controller.json`.

4. **Markdown-based task tracking** via PLAN.md with structured metadata (Status, Spec, Session, Depends fields) parsed and updated in real-time.

5. **`gh` CLI integration** for GitHub status—branch sync, PR info, and comments. Avoids OAuth complexity by leveraging existing auth.

6. **macOS notification center** for attention alerts via `terminal-notifier` or Python's `pync` library.

### Key Design Decisions

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| **Textual for TUI** | Rich widget library, async-native, active development, good for complex layouts | Rich (simpler but less capable), curses (too low-level) |
| **JSON persistence** | Human-readable, easy to debug, sufficient for config data | SQLite (overkill for config), YAML (parsing edge cases) |
| **PLAN.md for tasks** | Source of truth stays in repo, editable by humans/Claude, no external dependencies | External tracker (beads), embedded database |
| **Polling for output** | iTerm2 API design—no push notifications, but 500ms polling is responsive enough | WebSocket (not available), triggers (not supported) |
| **`gh` CLI for GitHub** | Already installed/authenticated for most developers, avoids token management | GitHub API directly (token complexity), no integration |

## Scope

### Affected Systems

- **iTerm2** - Target terminal emulator, controlled via Python scripting API
- **Local filesystem** - Config storage, PLAN.md parsing, env file reading
- **macOS notifications** - System notification center for attention alerts
- **GitHub** (via `gh` CLI) - Read-only access to branch/PR status

### Workflow Modes

Dedicated screens for focused project activities:

| Mode | Purpose |
|------|---------|
| Plan Mode | Planning artifacts (PROBLEM.md, PRD.md, specs/, PLAN.md) |
| Docs Mode | Tree-based documentation browser |
| Work Mode | Task execution and session tracking |
| Test Mode | QA testing (TEST_PLAN.md) and unit test runner |

Navigation via `1-4` keys from Project Dashboard. Mode persistence remembers last mode per project.

### Dependencies

| Dependency | Purpose | Notes |
|------------|---------|-------|
| iTerm2 | Terminal control | Requires iTerm2 3.5+ with Python scripting enabled |
| Python 3.11+ | Runtime | For modern async features and typing |
| Textual | TUI framework | ~2.x latest stable |
| `gh` CLI | GitHub integration | Optional, degrades gracefully if not installed |
| `terminal-notifier` | macOS notifications | Optional, degrades gracefully |

### Out of Scope

- **Remote/SSH projects** - Strictly local development
- **Session replay/history** - No persistent output storage beyond scrollback
- **Cross-machine sync** - No cloud sync of project configs
- **Plugin system** - No extensibility API in V1
- **Inter-session communication** - Sessions are independent

## Risks & Open Questions

### Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **iTerm2 API stability** | Medium - API could change between versions | Pin to known-working iTerm2 version range, document requirements |
| **Polling performance** | Low - Many sessions could strain resources | Implement adaptive polling, batch output reads |
| **PLAN.md sync conflicts** | Medium - External edits while dashboard open | File watcher with merge/reload strategy |
| **Claude output detection** | High - Heuristics may miss/false-positive prompts | Start with conservative patterns, iterate based on usage |

### Open Questions

- [ ] **Multi-window support**: Should we support projects spanning multiple iTerm2 windows? Current design assumes single window.
- [ ] **Claude thinking detection**: How to distinguish "thinking" (working) from "waiting for input"? May need Claude-specific output patterns.
- [ ] **PLAN.md conflict handling**: When PLAN.md is edited externally while dashboard is open—prompt to reload, auto-merge, or lock file?
- [ ] **Spec file validation**: Should we validate that referenced spec files exist? Show broken links?
- [ ] **Task dependency visualization**: How to display blocked tasks? Inline blocker, collapse, or separate graph view?
- [ ] **Auto mode triggers**: What signals that a workflow phase is complete and the next should start?

## Success Criteria

From PROBLEM.md:

- [ ] Can create a new project from a template (runs setup script, creates branch, spawns configured sessions)
- [ ] Control Room displays all sessions across projects with accurate status (Working/Waiting/Idle)
- [ ] System notification fires within 5 seconds when any session enters Waiting state
- [ ] Can spawn/kill individual sessions from the dashboard
- [ ] Project dashboard shows task progress parsed from PLAN.md
- [ ] Health checks poll configured endpoints and display status
- [ ] GitHub panel shows branch sync status and PR info (using `gh` CLI)
- [ ] Quit confirmation offers options: close all, close managed only, leave running
- [ ] Settings screen allows configuring defaults (IDE, shell, notification preferences)
- [ ] Auto mode can be configured with stage-specific commands that run when a phase completes
- [ ] Can launch a new window with a predefined set of tabs/sessions

### Workflow Mode Criteria

- [ ] Can navigate to Plan/Docs/Work/Test modes from Project Dashboard using `1-4` keys
- [ ] Plan Mode shows artifact status (PROBLEM.md, PRD.md, specs/, PLAN.md) and can launch planning sessions
- [ ] Docs Mode shows tree-based documentation browser with add/edit/delete operations
- [ ] Work Mode allows claiming tasks and tracking work sessions assigned to tasks
- [ ] Test Mode displays TEST_PLAN.md steps and can run unit tests
- [ ] Mode persistence - reopening project restores last active mode

---
*Generated from PROBLEM.md on 2026-01-31*
