# iTerm2 Project Orchestrator - Quickstart Walkthrough

This guide walks you through setting up and using the iTerm2 Project Orchestrator from scratch. By the end, you'll have a fully configured project with automated session management.

## Prerequisites

Before starting, ensure you have:

- **macOS** with iTerm2 installed
- **Python 3.11+** installed
- **Git** (for project tracking)
- **Optional**: `gh` CLI for GitHub integration

## Step 1: Enable iTerm2 Python API

The orchestrator communicates with iTerm2 through its Python API. Enable it:

1. Open **iTerm2**
2. Go to **Preferences** → **General** → **Magic**
3. Check **"Enable Python API"**
4. Restart iTerm2

## Step 2: Install the Orchestrator

```bash
# Clone or navigate to the project directory
cd /path/to/iterm-controller

# Install in development mode
pip install -e .

# Or install dependencies directly
pip install textual iterm2 dacite watchfiles httpx
```

**Optional dependencies:**

```bash
# For macOS notifications
brew install terminal-notifier

# For GitHub integration
brew install gh
gh auth login
```

## Step 3: Create Your First Configuration

Create the global configuration directory and file:

```bash
mkdir -p ~/.config/iterm-controller
```

Create `~/.config/iterm-controller/config.json`:

```json
{
  "projects": [
    {
      "name": "my-project",
      "path": "/path/to/my-project",
      "plan_file": "PLAN.md"
    }
  ],
  "session_templates": [
    {
      "name": "dev-server",
      "command": "npm run dev",
      "working_dir": ".",
      "auto_restart": false
    },
    {
      "name": "claude",
      "command": "claude",
      "working_dir": "."
    },
    {
      "name": "shell",
      "command": null,
      "working_dir": "."
    }
  ],
  "window_layouts": [
    {
      "name": "standard",
      "sessions": ["shell", "dev-server"]
    },
    {
      "name": "ai-assisted",
      "sessions": ["claude", "shell", "dev-server"]
    }
  ],
  "settings": {
    "poll_interval_ms": 500,
    "notification_enabled": true
  }
}
```

## Step 4: Create a PLAN.md for Your Project

In your project directory, create a `PLAN.md` file:

```markdown
# Project Plan

## Phase 1: Setup

### 1.1 Initialize project structure
- [x] Create directory layout
- [x] Add configuration files

### 1.2 Install dependencies
- [ ] Run npm install
- [ ] Verify all packages

## Phase 2: Implementation

### 2.1 Build core feature
- [ ] Create main module
- [ ] Add error handling
- [ ] Write tests

### 2.2 Add documentation
- [ ] Write README
- [ ] Add code comments
```

The orchestrator parses this format and tracks task progress.

## Step 5: Launch the TUI

Start the orchestrator:

```bash
python -m iterm_controller
```

You'll see the **Project List** screen showing your configured projects.

## Step 6: Navigate the Interface

### Keyboard Navigation

| Key | Action |
|-----|--------|
| `↑/↓` or `j/k` | Navigate lists |
| `Enter` | Select/Open |
| `Escape` | Go back |
| `q` | Quit |
| `?` | Show help |

### Main Screens

1. **Project List** - Browse and select projects
2. **Project Dashboard** - Overview of a single project
3. **Control Room** - Monitor all active sessions across projects

## Step 7: Open a Project

From the Project List:

1. Use arrow keys to highlight your project
2. Press **Enter** to open the Project Dashboard
3. You'll see:
   - Project status
   - Task progress from PLAN.md
   - Available session templates
   - GitHub branch info (if configured)

## Step 8: Spawn Sessions

### Spawn a Single Session

1. From the Project Dashboard, press `s` to open session spawner
2. Select a template (e.g., "dev-server")
3. The session opens in a new iTerm2 tab

### Spawn a Window Layout

1. Press `l` to open layout spawner
2. Select a layout (e.g., "ai-assisted")
3. All configured sessions spawn together

## Step 9: Monitor Sessions

### Session States

The orchestrator monitors your sessions and detects:

| State | Meaning | Visual |
|-------|---------|--------|
| **WORKING** | Command is running | Green indicator |
| **IDLE** | Waiting at prompt | Yellow indicator |
| **WAITING** | Needs your input | Red indicator + notification |

### Control Room View

Press `c` from any screen to open the Control Room, which shows:

- All active sessions across all projects
- Current state of each session
- Quick actions (focus, kill)

## Step 10: Work with Tasks

### View Tasks

From the Project Dashboard, press `t` to see the task list parsed from PLAN.md.

### Claim a Task

1. Navigate to a pending task
2. Press `Enter` or `c` to claim it
3. Status changes to "in_progress"
4. PLAN.md is automatically updated

### Complete a Task

1. Navigate to an in-progress task
2. Press `d` to mark done
3. Status changes to "complete"
4. Checkbox in PLAN.md becomes `[x]`

## Step 11: Use Workflow Modes

The orchestrator provides focused workflow modes:

### Plan Mode (`p`)

View and edit planning artifacts:
- PLAN.md
- PRD.md
- PROBLEM.md
  - specs/


### Docs Mode (`o`)

Browse project documentation:
- README files
- Documentation directories
- Inline help

### Work Mode (`w`)

Focused task execution:
- Active task display
- Session output
- Quick task transitions

### Test Mode (`e`)

QA workflow:
- TEST_PLAN.md parsing
- Test case tracking
- Bug recording

## Step 12: Use the CLI (Headless Operations)

For scripting or agent integration, use CLI commands:

```bash
# List all projects
python -m iterm_controller list-projects

# List sessions for a project
python -m iterm_controller list-sessions --project my-project

# Spawn a session
python -m iterm_controller spawn --project my-project --template dev-server

# Kill a session
python -m iterm_controller kill --session SESSION_ID

# Task operations
python -m iterm_controller task list --project my-project
python -m iterm_controller task claim --project my-project --task 2.1
python -m iterm_controller task done --project my-project --task 2.1
```

## Step 13: Programmatic API

For integration with other tools:

```python
from iterm_controller import ItermControllerAPI

async def main():
    api = ItermControllerAPI()
    await api.initialize()

    # List projects
    projects = await api.list_projects()

    # Spawn a session
    result = await api.spawn_session("my-project", "dev-server")

    # Get session status
    sessions = await api.list_sessions("my-project")

    # Update task status
    await api.claim_task("my-project", "2.1")
    await api.complete_task("my-project", "2.1")

import asyncio
asyncio.run(main())
```

## Common Workflows

### Starting a New Work Session

1. Launch: `python -m iterm_controller`
2. Select your project
3. Press `l` → Select "ai-assisted" layout
4. Press `t` → Claim your first task
5. Work in the spawned sessions

### Checking on Running Sessions

1. Press `c` for Control Room
2. See all sessions with their states
3. Click a WAITING session to focus it
4. Handle the prompt/question
5. Return to your work

### Ending a Work Session

1. Complete your current task (`d`)
2. Press `k` to open session killer
3. Select sessions to terminate (or "Kill All")
4. Press `q` to quit

## Project-Specific Configuration

Override global settings per-project by creating `.iterm-controller.json` in your project root:

```json
{
  "session_templates": [
    {
      "name": "dev-server",
      "command": "rails server",
      "working_dir": "."
    }
  ],
  "plan_file": "docs/PLAN.md",
  "settings": {
    "notification_enabled": false
  }
}
```

## Troubleshooting

### "Cannot connect to iTerm2"

1. Ensure iTerm2 is running
2. Verify Python API is enabled (Preferences → General → Magic)
3. Restart iTerm2

### Sessions not spawning

1. Check your template commands are valid
2. Verify working directories exist
3. Check iTerm2 console for errors

### PLAN.md not updating

1. Ensure the file path is correct in config
2. Check file permissions
3. Look for parse errors in the TUI status bar

### Notifications not working

1. Install: `brew install terminal-notifier`
2. Grant notification permissions in System Preferences
3. Verify `notification_enabled: true` in settings

## Next Steps

- Explore the [README.md](README.md) for detailed feature documentation
- Check [specs/](specs/) for technical specifications
- Customize attention patterns in config for your workflow
- Set up GitHub integration for PR status tracking

---

Happy orchestrating!
