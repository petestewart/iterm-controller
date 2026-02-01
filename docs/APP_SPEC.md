# Application Specification

## Overview

A terminal-based project orchestrator that manages development environments through iTerm2. The app provides a unified interface for launching, monitoring, and coordinating terminal sessions across projects.

**Core value proposition:** One command to open a project and have all your dev environment tabs/panes spawn, configured, and monitored.

---

## Screens

### 1. Control Room

The default entry point when launching the app. Shows all active sessions across all projects, with emphasis on sessions that need attention.

**Sorted by Status (default):**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Control Room                                              3 need attention │
│                                                        Sort: [S]tatus ▼     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ⚠ WAITING ─────────────────────────────────────────────────────────────────│
│                                                                             │
│  > Claude [a]              My Web App         2.1 Add user auth middleware  │
│    "Should I use JWT or session cookies for auth?"                     2m   │
│                                                                             │
│    Claude [b]              API Dashboard      1.3 Fix rate limiting         │
│    "Ready for next task. What should I work on?"                       5m   │
│                                                                             │
│    Tests [c]               CLI Tool           ─                             │
│    "Press Enter to continue or q to quit"                             12s   │
│                                                                             │
│  ● WORKING ─────────────────────────────────────────────────────────────────│
│                                                                             │
│    Claude [d]              My Web App         2.2 Create login form         │
│    "Creating LoginForm component with validation..."                   30s  │
│                                                                             │
│    Dev Server [e]          My Web App         ─                             │
│    "Compiled successfully in 234ms"                                    45s  │
│                                                                             │
│  ○ IDLE ────────────────────────────────────────────────────────────────────│
│                                                                             │
│    Claude [f]              API Dashboard      ─                             │
│    (at prompt)                                                         8m   │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Enter] Jump to session  [P]rojects  [S]ort  [K]ill  [N]ew project  [Q]uit │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Sorted by Project:**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Control Room                                              3 need attention │
│                                                        Sort: [P]roject ▼    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ⚡ My Web App ─────────────────────────────────────────────────────────────│
│                                                                             │
│  > ⚠ Claude [a]            2.1 Add user auth middleware                2m   │
│      "Should I use JWT or session cookies for auth?"                        │
│                                                                             │
│    ● Claude [d]            2.2 Create login form                       30s  │
│      "Creating LoginForm component..."                                      │
│                                                                             │
│    ● Dev Server [e]        ─                                           45s  │
│      "Compiled successfully in 234ms"                                       │
│                                                                             │
│  🐛 API Dashboard ──────────────────────────────────────────────────────────│
│                                                                             │
│    ⚠ Claude [b]            1.3 Fix rate limiting                       5m   │
│      "Ready for next task. What should I work on?"                          │
│                                                                             │
│    ○ Claude [f]            ─                                           8m   │
│      (at prompt)                                                            │
│                                                                             │
│  🔧 CLI Tool ───────────────────────────────────────────────────────────────│
│                                                                             │
│    ⚠ Tests [c]             ─                                          12s   │
│      "Press Enter to continue or q to quit"                                 │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Enter] Jump to session  [P]rojects  [S]ort  [K]ill  [N]ew project  [Q]uit │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Sorted by Activity (most recent first):**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Control Room                                              3 need attention │
│                                                        Sort: [A]ctivity ▼   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  > ⚠ Tests [c]             CLI Tool           ─                       12s   │
│      "Press Enter to continue or q to quit"                                 │
│                                                                             │
│    ● Claude [d]            My Web App         2.2 Create login form    30s  │
│      "Creating LoginForm component..."                                      │
│                                                                             │
│    ● Dev Server [e]        My Web App         ─                        45s  │
│      "Compiled successfully in 234ms"                                       │
│                                                                             │
│    ⚠ Claude [a]            My Web App         2.1 Add user auth        2m   │
│      "Should I use JWT or session cookies?"                                 │
│                                                                             │
│    ⚠ Claude [b]            API Dashboard      1.3 Fix rate limiting    5m   │
│      "Ready for next task. What should I work on?"                          │
│                                                                             │
│    ○ Claude [f]            API Dashboard      ─                        8m   │
│      (at prompt)                                                            │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Enter] Jump to session  [P]rojects  [S]ort  [K]ill  [N]ew project  [Q]uit │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Empty state (no active sessions):**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Control Room                                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                                                                             │
│                         No active sessions                                  │
│                                                                             │
│                   [N] New project   [P] View projects                       │
│                                                                             │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  [P]rojects  [N]ew project  [Q]uit                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Session row elements:**

| Element | Description |
|---------|-------------|
| Status indicator | `⚠` waiting (needs attention), `●` working, `○` idle |
| Session name | e.g., `Claude`, `Dev Server`, `Tests` |
| Quick-select key | `[a]` through `[z]` for keyboard navigation |
| Project name | Which project this session belongs to |
| Task | Current task from PLAN.md (or `─` if not linked to a task) |
| Last output | Truncated preview of most recent output line |
| Time | Duration in current state |

**Session states:**

| State | Indicator | Description |
|-------|-----------|-------------|
| Waiting | `⚠` | Session needs user input (highest priority) |
| Working | `●` | Actively producing output |
| Idle | `○` | At prompt, not doing anything |

**"Waiting" detection heuristics:**
- Question mark at end of Claude output
- Known prompt patterns ("Press Enter", "y/n", "[Y/n]", "continue?")
- Interactive prompts detected in output
- Claude-specific: clarifying question patterns

**Sort/Group modes:**
- **Status** (default) - Waiting first, then Working, then Idle
- **Project** - Grouped by project with type emoji header
- **Activity** - Most recent activity first (flat list)

**Actions:**
- `Enter` - Jump to selected session (opens project dashboard, focuses session)
- `P` - Switch to Project List view
- `S` - Cycle sort mode (Status → Project → Activity → Status)
- `K` - Kill selected session (with confirmation)
- `N` - Create new project
- `,` - Open Settings
- `a-z` - Quick select session by assigned key
- `↑↓` - Navigate session list
- `Q` - Quit app

**Global shortcuts:**
- `Ctrl+R` - Return to Control Room from any screen
- `Ctrl+,` - Open Settings from any screen

**Notifications:**
When a session enters WAITING state:
- System notification with session name, project, and the prompt/question
- Optional sound (configurable in settings)
- "X need attention" counter updates in header

---

### 2. Project List

List of all configured projects. Accessible from Control Room via `[P]`.

```
┌─────────────────────────────────────────────────────────────┐
│  Projects                                        [N]ew  [Q]uit │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  > My Web App          feature   WEBAPP-456                   │
│    ~/projects/webapp   main → feature/user-auth               │
│                                                               │
│    API Dashboard       bug       API-789                      │
│    ~/projects/api      main → fix/login-redirect              │
│                                                               │
│    CLI Tool            chore                                  │
│    ~/projects/cli      main                                   │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│  [Enter] Open  [E]dit  [D]elete  [↑↓] Navigate               │
└─────────────────────────────────────────────────────────────┘
```

**Elements:**
- Project name and type badge
- External ticket ID (if linked)
- Path
- Git branch info (base → current)

**Actions:**
- `Enter` - Open selected project (goes to Project Dashboard)
- `N` - Create new project
- `E` - Edit project configuration
- `D` - Delete project (with confirmation)
- `R` - Return to Control Room
- `Q` - Quit app

---

### 3. New Project

Form for creating a new project, optionally from a template.

```
┌─────────────────────────────────────────────────────────────┐
│  New Project                                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Name:          [my-feature                          ]      │
│  Type:          [feature ▼]                                 │
│  Jira Ticket:   [PROJ-123                  ] (optional)     │
│                                                             │
│  ── Template ─────────────────────────────────────────────  │
│  > Trunk Tools Feature     Create worktree + database       │
│    Trunk Tools Bug Fix     Worktree from production tag     │
│    Standalone Project      New directory, no worktree       │
│    None                    Manual setup                     │
│                                                             │
│  ── Directory ────────────────────────────────────────────  │
│  (Set by template: ~/Projects/trunk-tools/my-feature)       │
│                                                             │
│  ── Git Branch ───────────────────────────────────────────  │
│  [x] Create branch: [feature/my-feature              ]      │
│      (derived from project name)                            │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  [Create]  [Cancel]                                         │
└─────────────────────────────────────────────────────────────┘
```

**With no template selected:**

```
┌─────────────────────────────────────────────────────────────┐
│  ── Directory ────────────────────────────────────────────  │
│  ○ Use existing    [                         ] [Browse]     │
│  ● Create new      Base: [~/Projects/        ]              │
│                    Name: [my-feature         ]              │
└─────────────────────────────────────────────────────────────┘
```

**Elements:**
- Name field (required)
- Type dropdown
- Jira ticket field (optional)
- Template selector with descriptions
- Directory config (auto-filled by template or manual)
- Git branch toggle with auto-derived name

**Actions:**
- `Enter` on template - Select it
- `Tab` - Move between fields
- `Create` - Execute project creation
- `Cancel` / `Esc` - Return to Project List

---

### 4. Project Dashboard

The main view when a project is open. Shows workflow status, documentation, tasks, sessions, and GitHub integration.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ⚡ My Web App                                           feature │ WEBAPP-456 │
│  ~/projects/webapp                              main → feature/user-auth    │
├─────────────────────────────────────────────────────────────────────────────┤
│  ○ Planning  ──→  ◐ Execute  ──→  ○ Review  ──→  ○ PR  ──→  ○ Done          │
│                                                                             │
├──────────────────────┬──────────────────────────────────────────────────────┤
│  Docs                │  Plan                                        2/7     │
│  ──────────────────  │  ────────────────────────────────────────────────────│
│    PRD               │  ▼ Phase 1: Setup                            2/2 ✓   │
│  ○ Problem Statement │    ✓ 1.1 Create project structure                    │
│  ▶ Specs (3)         │    ✓ 1.2 Set up database schema                      │
│                      │  ▼ Phase 2: Core Features                    0/3     │
│  ──────────────────  │    ⧖ 2.1 Add user auth middleware    ← Claude [a]    │
│  Sessions            │    ○ 2.2 Create login form                           │
│  ──────────────────  │    ○ 2.3 Add session persistence                     │
│  ● Claude       [a]  │  ▶ Phase 3: Testing                          0/2     │
│  ● Dev Server   [b]  │                                                      │
│  ○ Tests        [c]  │                                                      │
│                      │                                                      │
│  ──────────────────  ├──────────────────────────────────────────────────────┤
│  Scripts             │  GitHub                                              │
│  ──────────────────  │  ────────────────────────────────────────────────────│
│    dev               │  ✓ synced with origin                                │
│    test              │  PR #42 (draft) · 2 comments                         │
│    lint              │                                                      │
│                      │                                                      │
├──────────────────────┴──────────────────────────────────────────────────────┤
│  Health: API ● Web ●     Ports: 3000 3001 5432     ENV: .env .env.local     │
├─────────────────────────────────────────────────────────────────────────────┤
│  [P]lan  [D]ocs  [S]essions  [G]itHub  [O]pen IDE  [B]ack  [Q]uit           │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Layout:**
- **Header**: Project name (with type emoji), type badge, ticket, git branch info
- **Workflow bar**: Visual progress through project lifecycle stages
- **Left sidebar**: Docs, Sessions, Scripts
- **Main panel (top)**: Plan with collapsible phases and task list
- **Main panel (bottom)**: GitHub status
- **Status bar**: Health checks, ports, env files
- **Footer**: Available actions

**Project type indicators (emoji):**
- `⚡` Feature
- `🐛` Bug
- `🔧` Refactor
- `🔍` Spike
- `🧹` Chore

**Workflow stages:**
- `○` Not started
- `◐` In progress
- `●` Complete

**Doc status indicators:**
- *(no indicator)* - File exists
- `○` - File missing / not created yet
- `▶` - Collapsed folder (e.g., specs)
- `▼` - Expanded folder

**Task status indicators:**
- `○` Not Yet Implemented
- `⧖` In Progress (with session link: `← Claude [a]`)
- `✓` Complete
- `⊘` Blocked
- `–` Skipped

**Phase display:**
- `▼ Phase Name` - Expanded, shows all tasks
- `▶ Phase Name (0/3)` - Collapsed, shows progress count
- Phase header shows `✓` when all tasks complete

**Session status indicators:**
- `●` Running
- `○` Stopped/Exited
- `◐` Starting/Waiting
- `✗` Failed/Error

**Actions:**
- `P` - Focus Plan panel (navigate tasks)
- `D` - Open docs picker
- `S` - Focus Sessions panel / Spawn new session
- `G` - Open GitHub details / actions
- `O` - Open project in IDE
- `B` - Back to project list
- `Ctrl+R` - Return to Control Room
- `Q` - Quit (with cleanup options)
- `1-9` / `a-z` - Quick select session by key

---

### 5. Script Picker (Modal)

Shown when spawning a new session.

```
┌────────────────────────────────────────┐
│  Run Script                            │
├────────────────────────────────────────┤
│  dev                                   │
│  > start_api      Start API server     │
│    start_web      Start web client     │
│                                        │
│  test                                  │
│    test           Run all tests        │
│    test_watch     Run tests in watch   │
│                                        │
│  lint                                  │
│    lint           Run linter           │
│    typecheck      Run type checker     │
│                                        │
│  build                                 │
│    build          Production build     │
│                                        │
├────────────────────────────────────────┤
│  [Enter] Run  [Esc] Cancel             │
└────────────────────────────────────────┘
```

**Grouped by category**, shows description if available.

---

### 6. Docs Picker (Modal)

Quick access to project documentation with status management.

```
┌──────────────────────────────────────────────────┐
│  Project Docs                                    │
├──────────────────────────────────────────────────┤
│  Core Documents                                  │
│  > PRD                docs/PRD.md                │
│  ○ Problem Statement  (not created)      [C]reate│
│    PLAN              docs/PLAN.md                │
│  ○ QA Test Plan      (not created)       [C]reate│
│                                                  │
│  ▼ Specs (3 files)                               │
│      auth.spec.md                                │
│      api.spec.md                                 │
│      models.spec.md                              │
│                                                  │
│  References                                      │
│    Design Figma      figma.com/...               │
│    API Docs          docs/api/README             │
│                                                  │
├──────────────────────────────────────────────────┤
│  [Enter] Open  [C] Create  [M] Mark complete/unneeded │
│  [Esc] Cancel                                    │
└──────────────────────────────────────────────────┘
```

**Elements:**
- `○` indicates file doesn't exist yet
- `▼`/`▶` toggles for collapsible folders (Specs)
- `[C]reate` action for missing files (opens template in editor)

**Actions:**
- `Enter` - Open selected doc in configured IDE (or browser for URLs)
- `C` - Create missing document from template
- `M` - Toggle document state (mark as complete or unneeded)
- `Esc` - Close picker

**Document creation:**
When creating a missing doc, the app:
1. Creates the file from a template (if available)
2. Opens it in the configured IDE
3. Updates the dashboard to show the doc exists

---

### 7. Environment Viewer (Modal)

Shows parsed environment variables.

```
┌────────────────────────────────────────┐
│  Environment Variables                 │
├────────────────────────────────────────┤
│  From: .env                            │
│    DATABASE_URL     postgres://...     │
│    API_PORT         3001               │
│    NODE_ENV         development        │
│                                        │
│  From: .env.local                      │
│    API_KEY          ••••••••           │
│    DEBUG            true               │
│                                        │
│  Overrides                             │
│    (none)                              │
│                                        │
├────────────────────────────────────────┤
│  [Esc] Close                           │
└────────────────────────────────────────┘
```

**Respects `show_in_ui`, `hide_in_ui`, and `sensitive_patterns`.**

---

### 8. Quit Confirmation (Modal)

Shown when quitting with active sessions.

```
┌────────────────────────────────────────┐
│  Quit Application                      │
├────────────────────────────────────────┤
│  You have 4 active sessions:           │
│                                        │
│    ● API Server                        │
│    ● Web Client                        │
│    ● Tests                             │
│    ● Claude Plan                       │
│                                        │
│  What would you like to do?            │
│                                        │
│  > [C] Close all sessions and quit     │
│    [M] Close managed sessions only     │
│    [L] Leave sessions running          │
│    [Esc] Cancel                        │
│                                        │
└────────────────────────────────────────┘
```

---

### 9. Project Editor

Form for creating/editing project configuration.

```
┌─────────────────────────────────────────────────────────────┐
│  Edit Project: My Web App                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Name:        [My Web App                    ]              │
│  Path:        [~/projects/webapp             ] [Browse]     │
│  Type:        [feature ▼]                                   │
│  IDE:         [cursor ▼]                                    │
│                                                             │
│  ── Git ──────────────────────────────────────────────────  │
│  Branch:      [feature/user-auth             ]              │
│  Base:        [main                          ]              │
│  Remote:      [origin                        ]              │
│                                                             │
│  ── External Ticket ──────────────────────────────────────  │
│  System:      [jira ▼]                                      │
│  Ticket ID:   [WEBAPP-456                    ]              │
│  URL:         [https://mycompany.atlassian.net/...]         │
│                                                             │
│  ── Docs ─────────────────────────────────────────────────  │
│  PRD:         [docs/PRD.md                   ] [Browse]     │
│  Plan:        [docs/PLAN.md                  ] [Browse]     │
│  Specs Dir:   [docs/specs                    ] [Browse]     │
│                                                             │
│  [Scripts...]  [Env Files...]  [Ports...]  [Health...]      │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  [Save]  [Cancel]                                           │
└─────────────────────────────────────────────────────────────┘
```

**Sub-editors** for complex fields (scripts, ports, health checks).

---

### 10. Settings

Global application settings. Accessible via `Ctrl+,` from any screen, or `,` from Control Room.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Settings                                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  General                                                                    │
│  ─────────────────────────────────────────────────────────────────────────  │
│    Default IDE:              [Cursor ▼]                                     │
│    Default shell:            [/bin/zsh                          ]           │
│    Default project dir:      [~/Projects/                       ]           │
│    Confirm on quit:          [✓]                                            │
│                                                                             │
│  Notifications                                                              │
│  ─────────────────────────────────────────────────────────────────────────  │
│    Enable notifications:     [✓]                                            │
│    Play sound:               [✓]                                            │
│    Cooldown (seconds):       [30      ]                                     │
│    Monitor session types:    [All ▼]                                        │
│                                                                             │
│  Control Room                                                               │
│  ─────────────────────────────────────────────────────────────────────────  │
│    Default sort:             [Status ▼]                                     │
│    Polling interval (ms):    [500     ]                                     │
│                                                                             │
│  GitHub                                                                     │
│  ─────────────────────────────────────────────────────────────────────────  │
│    Auth method:              [gh CLI ▼]       Status: ✓ authenticated       │
│    Refresh interval (sec):   [60      ]                                     │
│                                                                             │
│  [Templates...]                                                             │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Save]  [Cancel]                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Sections:**

| Section | Settings |
|---------|----------|
| General | Default IDE, shell, project directory, quit confirmation |
| Notifications | Enable/disable, sound, cooldown, which sessions to monitor |
| Control Room | Default sort mode, polling interval |
| GitHub | Authentication method, refresh interval |

**Actions:**
- `Tab` / `Shift+Tab` - Move between fields
- `Enter` on dropdown - Open dropdown menu
- `Space` on checkbox - Toggle
- `T` or click `[Templates...]` - Open Templates sub-screen
- `Save` / `Ctrl+S` - Save and close
- `Cancel` / `Esc` - Discard changes and close

**Global shortcut:**
- `Ctrl+,` - Open Settings from any screen

---

### 11. Templates Manager

Sub-screen for managing project templates. Accessed from Settings via `[Templates...]`.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Project Templates                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  > Trunk Tools Feature                                                      │
│    Create a new feature branch with worktree and database                   │
│    Setup: ~/scripts/create-trunk-worktree.sh                                │
│                                                                             │
│    Trunk Tools Bug Fix                                                      │
│    Worktree from production tag for bug fixes                               │
│    Setup: ~/scripts/create-trunk-bugfix.sh                                  │
│                                                                             │
│    Standalone Project                                                       │
│    New directory with standard structure, no worktree                       │
│    Setup: (none)                                                            │
│                                                                             │
│    Rails API Project                                                        │
│    Rails API-only app with PostgreSQL and Redis                             │
│    Setup: ~/scripts/create-rails-api.sh                                     │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  [N]ew  [E]dit  [D]uplicate  [Delete]  [↑↓] Navigate  [Esc] Back            │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Template Editor:**
```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Edit Template: Trunk Tools Feature                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Name:            [Trunk Tools Feature                          ]           │
│  Description:     [Create a new feature branch with worktree... ]           │
│                                                                             │
│  ── Setup ──────────────────────────────────────────────────────────────    │
│  Setup script:    [~/scripts/create-trunk-worktree.sh   ] [Browse]          │
│                                                                             │
│  Parameters:                                                                │
│    branch_name       required   "Git branch name"                           │
│    project_path      required   "Where to create the worktree"              │
│    database_name     optional   "PostgreSQL database name"                  │
│    [Add parameter...]                                                       │
│                                                                             │
│  ── Defaults ───────────────────────────────────────────────────────────    │
│  Default IDE:     [Cursor ▼]                                                │
│  Default scripts: [Edit...]                                                 │
│  Default ports:   [Edit...]                                                 │
│  Startup sequence: [server, claude]                                         │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Save]  [Cancel]                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Elements:**
- Template list with name, description, setup script path
- Selected template highlighted with `>`

**Actions:**
- `Enter` - Edit selected template
- `N` - Create new template
- `E` - Edit selected template
- `D` - Duplicate selected template
- `Delete` - Delete template (with confirmation)
- `↑↓` - Navigate list
- `Esc` - Return to Settings

**Template fields:**
- Name and description
- Setup script path (optional)
- Setup parameters with name, required/optional, description
- Default config values (IDE, scripts, ports, startup sequence, etc.)

---

## Flows

### Flow 1: Create New Project

The primary flow for starting work on something new.

```
1. User on Project List → presses [N] for New Project

2. New Project Form (Step 1 - Basic Info):
   ┌────────────────────────────────────────────────────┐
   │  New Project                                       │
   ├────────────────────────────────────────────────────┤
   │  Name:        [                              ]     │
   │  Type:        [feature ▼]                          │
   │  Jira Ticket: [          ] (optional)              │
   │                                                    │
   │  Template:    [None ▼]                             │
   │               ☐ Trunk Tools Feature                │
   │               ☐ Trunk Tools Bug Fix                │
   │               ☐ Standalone Project                 │
   │               ☐ None (manual setup)                │
   └────────────────────────────────────────────────────┘

3. If template selected → pre-fills defaults, shows template params
   If no template → shows directory options:

   ┌────────────────────────────────────────────────────┐
   │  Directory:                                        │
   │  ○ Use existing   [~/projects/my-app    ] [Browse] │
   │  ● Create new     [~/Projects/] + [my-feature]     │
   └────────────────────────────────────────────────────┘

4. Git Branch Configuration:
   ┌────────────────────────────────────────────────────┐
   │  Git Branch:                                       │
   │  ☑ Create new branch                               │
   │    Branch name: [feature/my-feature        ]       │
   │    (auto-derived from project name)                │
   │                                                    │
   │  ☐ Use existing branch                             │
   │  ☐ No git branch management                        │
   └────────────────────────────────────────────────────┘

5. User confirms → App executes:
   a. If template selected:
      - Resolve template params (branch_name, project_path, etc.)
      - Run template's setup_script
      - Wait for script completion
      - Initialize ProjectConfig from template's default_config
      - Apply user's input as overrides
   b. If no template:
      - Create directory (if "Create new" selected)
      - Create git branch (if enabled)
      - Initialize empty ProjectConfig

6. Project saved to app config

7. User lands on Project Dashboard
   - If template has startup_sequence → sessions auto-spawn
   - Otherwise → empty dashboard, ready for manual setup
```

**Error Handling:**
- If setup script fails → show error, offer to retry or cancel
- If directory already exists → warn, offer to use existing or rename
- If git branch exists → warn, offer to use existing or rename

### Flow 2: Open Project

```
1. User selects project from Project List
2. App validates project path exists
3. App parses env files
4. App checks git status (current branch, dirty state)
5. App runs startup_sequence:
   a. For each template in sequence:
      - Create tab/pane in iTerm2
      - Send command
      - Wait for ready (if configured)
      - Start monitoring
6. App shows Project Dashboard
7. App begins health check polling (if configured)
```

### Flow 3: Spawn Session

```
1. User presses [S] on Project Dashboard
2. App shows Script Picker modal
3. User selects a script
4. App determines layout (new tab vs split pane)
5. App creates session in iTerm2:
   a. Create tab or split existing pane
   b. cd to working_dir (if specified)
   c. Apply script-specific env vars
   d. Send command
6. App adds session to managed_sessions
7. App starts output monitoring
8. App updates dashboard with new session
```

### Flow 4: Kill Session

```
1. User selects session and presses [K]
2. App shows confirmation (if session is running)
3. App sends SIGTERM to session
4. App waits for exit (with timeout)
5. If not exited, offer to force kill (SIGKILL)
6. App removes from managed_sessions
7. App updates dashboard
```

### Flow 5: Quit Application

```
1. User presses [Q]
2. If no active sessions:
   a. App exits immediately
3. If active sessions exist:
   a. Show Quit Confirmation modal
   b. User selects action:
      - Close all: Kill all sessions, then exit
      - Close managed: Kill only our sessions, leave others
      - Leave running: Just exit, sessions persist
      - Cancel: Return to dashboard
4. App performs selected action
5. App saves state (if needed)
6. App exits
```

### Flow 6: Health Check Loop

```
1. App starts background task on project open
2. Every interval_seconds for each health check:
   a. Resolve URL (replace {env.VAR} placeholders)
   b. Make HTTP request
   c. Compare status to expected_status
   d. Update health_status
   e. Update status bar display
3. If health check fails:
   a. Show indicator in status bar
   b. Optionally notify user (configurable)
4. Loop continues until project closed
```

### Flow 7: Task Workflow

The flow for working on tasks from the plan.

```
1. User opens project → Dashboard displays
2. App parses PLAN.md:
   a. Extract phases (H2 headings)
   b. Extract tasks (H3 headings) with metadata
   c. Build task dependency graph
   d. Display in Plan panel
3. User selects a task and presses Enter (or clicks):
   a. App checks if task has unmet dependencies → show warning if blocked
   b. App updates PLAN.md: Status → "In Progress"
   c. If task has associated session template → spawn session
   d. App updates PLAN.md: Session → session name
   e. Dashboard updates to show task in progress
4. Work proceeds in the session (Claude or manual)
5. When work is complete:
   a. User/Claude marks task complete (or app detects completion)
   b. App updates PLAN.md: Status → "Complete", removes Session field
   c. Dashboard updates
   d. If all tasks in a phase complete → phase shows ✓
   e. If all tasks complete → workflow stage advances to Review
6. App monitors for PLAN.md changes (file watcher):
   a. If external edit detected → re-parse and update dashboard
```

**Task selection actions:**
- `Enter` - Start working on task (updates status, spawns session if configured)
- `Space` - Toggle task complete/incomplete
- `s` - Skip task (mark as Skipped)
- `v` - View task details (show full description, spec link)

### Flow 8: GitHub Integration

Displaying and acting on GitHub PR status.

```
1. On project open (if git configured):
   a. App checks if branch is synced with remote
   b. App queries GitHub API for open PRs matching branch
   c. If PR exists:
      - Fetch PR status (draft/open/merged)
      - Fetch review status (pending/approved/changes requested)
      - Fetch unresolved comment count
   d. Display in GitHub panel
2. Periodic refresh (configurable interval, e.g., 60 seconds)
3. User presses [G] for GitHub actions:
   a. Show GitHub modal with options:
      - View PR in browser
      - Create PR (if none exists)
      - Sync branch (push/pull)
      - View comments
```

**GitHub panel display:**
```
│  GitHub                                              │
│  ────────────────────────────────────────────────────│
│  Branch: ✓ synced                    (or: ⚠ 2 behind)│
│  PR: #42 (draft)                     (or: No PR)     │
│  Reviews: ✓ approved                 (or: ⧖ pending) │
│  Comments: 2 unresolved              (or: ✓ none)    │
```

**GitHub modal:**
```
┌────────────────────────────────────────┐
│  GitHub Actions                        │
├────────────────────────────────────────┤
│  Branch: feature/user-auth             │
│  Status: 2 commits ahead of origin     │
│                                        │
│  > [P] Push to origin                  │
│    [L] Pull from origin                │
│    [V] View PR #42 in browser          │
│    [C] View 2 unresolved comments      │
│    [N] Create new PR                   │
│                                        │
├────────────────────────────────────────┤
│  [Esc] Cancel                          │
└────────────────────────────────────────┘
```

### Flow 9: Session State Monitoring & Notifications

Background process that monitors all active sessions and triggers notifications.

```
1. App maintains session state monitor (background task)
2. For each active session, every polling interval (e.g., 500ms):
   a. Read latest output from iTerm2 session
   b. Analyze output to determine state:
      - WORKING: New output within last N seconds
      - IDLE: At shell prompt, no recent output
      - WAITING: Detected input prompt (see heuristics below)
   c. If state changed:
      - Update session state in app state
      - Update Control Room display
      - If new state is WAITING → trigger notification
3. When WAITING state detected:
   a. Extract the prompt/question text (last line or relevant context)
   b. Send system notification:
      - Title: "{Session} needs attention"
      - Body: "{Project}: {prompt text}"
   c. Play notification sound (if enabled in settings)
   d. Update Control Room "X need attention" counter
```

**WAITING detection heuristics:**

| Pattern | Example | Confidence |
|---------|---------|------------|
| Question mark at line end | "Should I use JWT or cookies?" | High |
| Known confirmation prompts | "Continue? [y/N]", "Press Enter" | High |
| Claude clarification patterns | "I have a question:", "Before I proceed:" | High |
| Idle at non-shell prompt | Cursor after ">" but not bash/zsh | Medium |
| Long idle after partial output | Started typing, stopped mid-sentence | Low |

**Session state transitions:**
```
                    ┌──────────────────┐
                    │                  │
    ┌───────────────▼──────────────────┴───────────────┐
    │                                                   │
    │   WORKING ◄──────────► IDLE ◄──────────► WAITING │
    │      │                  │                    │    │
    │      │                  │                    │    │
    │      └──────────────────┴────────────────────┘    │
    │                         │                         │
    │                         ▼                         │
    │                      EXITED                       │
    │                                                   │
    └───────────────────────────────────────────────────┘
```

**Notification settings (configurable):**
- Enable/disable system notifications
- Enable/disable sound
- Notification cooldown (don't re-notify for same session within X seconds)
- Which session types to monitor (all, Claude only, etc.)

---

## Behaviors

### Session Monitoring

- Poll session output every 1 second (configurable?)
- Detect patterns (success_pattern, error_pattern)
- Update session status based on patterns
- Keep rolling buffer of output history
- Highlight errors in output view

### Git Integration

- On project open: detect current branch, compare to configured branch
- Show warning if on different branch than expected
- Show dirty state indicator if uncommitted changes
- (Future: quick actions for common git operations?)

### Port Conflict Detection

- On project open: check if configured ports are in use
- Show warning before spawning session if port conflict
- (Future: offer to kill conflicting process?)

### Auto-Restart (Optional)

- If session has `restart_on_exit: true`
- When session exits unexpectedly:
  - Wait brief cooldown (prevent crash loops)
  - Respawn the session
  - Log the restart

### Tab Naming

- Apply `tab_prefix` to all managed tabs
- Format: `{tab_prefix}{session_name}`
- Example: `[webapp] API Server`

---

## Workflow Stages

Projects follow a universal development lifecycle. The dashboard displays current stage and infers progression automatically.

### Stages

```
Planning  →  Execute  →  Review  →  PR  →  Done
```

| Stage | Description |
|-------|-------------|
| **Planning** | Defining the problem, creating PRD, writing specs, creating the implementation plan |
| **Execute** | Actively working on tasks from the plan |
| **Review** | Code review, self-review, or team review |
| **PR** | Pull request created, addressing feedback |
| **Done** | PR merged, work complete |

### Stage Inference

Stages are inferred automatically based on project state:

| Stage | Inferred when... |
|-------|------------------|
| Planning | Default starting state |
| Execute | Planning complete AND at least one task marked "In Progress" or "Complete" |
| Review | All tasks complete (or user manually advances) |
| PR | PR exists on GitHub for the project branch |
| Done | PR is merged |

**Planning is considered complete when:**
- PRD exists (or marked unneeded)
- At least one spec exists (or marked unneeded)
- PLAN.md exists with at least one task

### Document States

Documents (PRD, Problem Statement, Specs, PLAN, QA Plan) have the following states:

| State | Description | UI Indicator |
|-------|-------------|--------------|
| Missing | File doesn't exist yet | `○` before name |
| Exists | File is present | *(no indicator)* |
| Complete | Manually marked as finished | *(no indicator, shown in completed section)* |
| Unneeded | Explicitly skipped for this project | *(hidden or struck through)* |

Users can manually toggle between Exists/Complete/Unneeded via the Docs panel.

---

## PLAN.md Format

The implementation plan is stored as a markdown file with a specific structure that the app parses to display tasks in the dashboard.

### Structure

```markdown
# Implementation Plan

## Phase 1: Setup

### 1.1 Create project structure
**Status:** Complete
**Spec:** specs/project-structure.spec.md

Set up the initial directory structure with src/, tests/, docs/ folders.
Create package.json with required dependencies.

### 1.2 Set up database schema
**Status:** In Progress
**Session:** Claude [a]
**Spec:** specs/database.spec.md

Create PostgreSQL tables for users, sessions, and audit logs.
Run initial migrations.

---

## Phase 2: Core Features

### 2.1 Add user auth middleware
**Status:** Not Yet Implemented
**Spec:** specs/auth.spec.md
**Depends:** 1.2

Implement JWT-based authentication middleware that:
- Validates tokens on protected routes
- Refreshes tokens before expiry
- Handles token revocation

### 2.2 Create login form component
**Status:** Not Yet Implemented
**Spec:** specs/auth.spec.md#login-form
**Depends:** 2.1

Build React component with:
- Email/password fields
- Validation
- Error display
- Loading states

---

## Phase 3: Testing

### 3.1 Write unit tests
**Status:** Not Yet Implemented
**Depends:** 2.1, 2.2

Cover auth middleware and login form with unit tests.

### 3.2 Write integration tests
**Status:** Not Yet Implemented
**Depends:** 3.1

End-to-end tests for the full login flow.
```

### Task Metadata Fields

Each task (H3 heading) can have the following metadata fields:

| Field | Required | Description |
|-------|----------|-------------|
| **Status** | Yes | Current state of the task |
| **Spec** | No | Path to related spec file (can include anchor: `file.md#section`) |
| **Session** | No | Which session is working on this (auto-updated) |
| **Depends** | No | Comma-separated list of task IDs that must complete first |

### Task Statuses

| Status | Description | Dashboard Icon |
|--------|-------------|----------------|
| `Not Yet Implemented` | Work hasn't started | `○` |
| `In Progress` | Currently being worked on | `⧖` |
| `Complete` | Task is finished | `✓` |
| `Blocked` | Cannot proceed (see Depends or add reason) | `⊘` |
| `Skipped` | Decided not to implement | `–` |

### Status Updates

When a session (Claude or user) begins working on a task:
1. The PLAN.md file is updated with `**Status:** In Progress`
2. The `**Session:**` field is added/updated with the session name
3. Dashboard reflects the change immediately

When work is complete:
1. Status updated to `Complete`
2. Session field is removed
3. Dashboard updates and may trigger workflow stage advancement

### Phases

- Phases are H2 headings (`## Phase Name`)
- Tasks within a phase are H3 headings (`### Task ID Task Name`)
- Phases can be collapsed/expanded in the dashboard
- Phase progress shown as fraction: `(2/5)` or `✓` when complete

### Flat Task Lists

If PLAN.md contains no H2 phase headers, tasks are displayed as a flat list:

```markdown
# Implementation Plan

### Add user authentication
**Status:** In Progress

### Create login form
**Status:** Not Yet Implemented

### Write tests
**Status:** Not Yet Implemented
```

This displays without phase groupings in the dashboard.

---

## State Persistence

### Config File Location

```
~/.config/iterm-controller/config.json
```

Or project-local:
```
{project_path}/.iterm-controller.json
```

### What Gets Persisted

- Project definitions (full ProjectConfig)
- Document states (exists/complete/unneeded) - stored in ProjectDocs
- App settings (default shell, confirm on quit, etc.)
- Window arrangements? (TBD)

### What Doesn't Get Persisted

- Active session state (runtime only)
- Health check results (runtime only)
- Parsed env variables (re-parsed on open)
- Workflow stage (inferred from project state on open)
- Parsed Plan/tasks (re-parsed from PLAN.md on open)
- GitHub status (fetched from API on open)

### What Lives in Project Files (not app config)

- **PLAN.md** - Task list, phases, status updates
  - Task status is stored in the markdown file itself
  - Session assignments updated in real-time
- **Spec files** - Individual specification documents
- **PRD, Problem Statement, etc.** - Project documents

---

## Open Questions

### Resolved

1. ~~**Project discovery**: Should we auto-detect projects from a directory? Or always require explicit creation?~~
   - *Decision: Explicit creation for now*

2. ~~**Session templates vs scripts**: There's overlap here. Templates define "what tabs to create", scripts define "commands to run". Should they merge?~~
   - *Decision: Keep separate. Templates define session structure, scripts are commands that can be run in sessions.*

3. ~~**Task tracking**: Use external system (beads) or project-local?~~
   - *Decision: Project-local via PLAN.md with structured markdown format*

### Open

4. **Multi-window support**: Should we support projects that span multiple iTerm2 windows?

5. **Claude integration**: Special handling for Claude sessions? (detect prompts, show thinking state, etc.)
   - How to detect when Claude is "thinking" vs waiting for input?
   - Should we parse Claude's output to auto-update task status?

6. **Notifications**: How to notify user of events (health check failure, session crash)? System notifications? Sound? Just visual?

7. **Remote projects**: Any support for SSH-based projects? Or strictly local?

8. **Import/Export**: Share project configs between machines?

9. **PLAN.md sync**: How to handle conflicts if PLAN.md is edited externally while dashboard is open?
   - File watcher + merge?
   - Prompt user to reload?

10. **GitHub auth**: How to authenticate with GitHub API?
    - Use `gh` CLI credentials?
    - OAuth flow?
    - Personal access token?

11. **Spec file linking**: How detailed should spec references be?
    - Just file path?
    - Support anchors to specific sections (`spec.md#section`)?
    - Validate that referenced spec exists?

12. **Task dependencies**: How to visualize blocked tasks?
    - Show blocker inline?
    - Collapse blocked tasks?
    - Show dependency graph view?

---

## Future Considerations

- **Plugins**: Allow custom behaviors/integrations
- **Profiles**: Different session sets for different modes (dev vs test vs debug)
- **Macros**: Record and replay sequences of actions
- **Search**: Search across all session output
- **Sharing**: Share session output (for debugging, pair programming)
