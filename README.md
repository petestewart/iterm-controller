# iTerm2 Controller Prototype

A demonstration of programmatically controlling iTerm2 from Python.

## Features

- **Create tabs/panes** - Spawn new terminal sessions programmatically
- **Monitor output** - Watch session output in real-time
- **Event notifications** - Get notified when sessions start, end, or change
- **Send commands** - Execute commands in any managed session

## Setup

1. **Enable iTerm2 Python API**:
   - Open iTerm2 Preferences (⌘,)
   - Go to General → Magic
   - Check "Enable Python API"

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Full TUI Controller

```bash
python controller.py
```

This opens an interactive TUI with:
- Buttons to spawn different process types
- Real-time status cards for each session
- Output preview from each session
- Keyboard shortcuts (1-4 to spawn, q to quit)

Run in demo mode (no iTerm2 required):
```bash
python controller.py --demo
```

### Simple Interactive Demo

```bash
python simple_demo.py
```

A menu-driven demo showing:
- Creating tabs and split layouts
- Monitoring session output
- Listing all sessions
- Sending commands

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Controller TUI (Textual)                       │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ Spawn Buttons│  │ Session Cards            │ │
│  │              │  │ ┌────────┐ ┌────────┐   │ │
│  │ [Dev Server] │  │ │Server  │ │Watcher │   │ │
│  │ [Watcher   ] │  │ │Running │ │Running │   │ │
│  │ [Shell     ] │  │ └────────┘ └────────┘   │ │
│  └──────────────┘  └──────────────────────────┘ │
│  ┌──────────────────────────────────────────┐   │
│  │ Log: [12:00] Created session xyz...      │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
          │
          │ iterm2 Python API (websocket)
          ▼
┌─────────────────────────────────────────────────┐
│  iTerm2                                          │
│  ┌──────────────────────────────────────────┐   │
│  │ Tab 1: Controller                         │   │
│  └──────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────┐   │
│  │ Tab 2: Dev Server (spawned & monitored)   │   │
│  └──────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────┐   │
│  │ Tab 3: Watcher (spawned & monitored)      │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

## Key API Methods Used

| Method | Purpose |
|--------|---------|
| `window.async_create_tab()` | Create new tab |
| `session.async_split_pane()` | Create split pane |
| `session.async_send_text()` | Send command |
| `session.get_screen_streamer()` | Real-time output monitoring |
| `session.async_get_screen_contents()` | Get current screen |
| `async_subscribe_to_terminate_session_notification()` | Watch for exit |
| `async_subscribe_to_new_session_notification()` | Watch for new sessions |

## Extending

You could extend this to:
- Save/restore session layouts
- Auto-restart crashed processes
- Aggregate logs from multiple sessions
- Build a process supervisor
- Create keyboard shortcuts for complex workflows
