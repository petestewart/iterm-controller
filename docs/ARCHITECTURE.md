# Architecture Overview

## System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        iTerm2 Application                        │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Window                                                     │  │
│  │  ┌─────────────┬─────────────┬─────────────┬───────────┐  │  │
│  │  │ Tab 1       │ Tab 2       │ Tab 3       │ Tab 4     │  │  │
│  │  │ Controller  │ Dev Server  │ Watcher 1   │ Claude    │  │  │
│  │  │ (TUI)       │ (spawned)   │ (spawned)   │ (spawned) │  │  │
│  │  └─────────────┴─────────────┴─────────────┴───────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                    Python API (WebSocket)                        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Controller Application                       │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Textual TUI                           │    │
│  │  ┌──────────────┐  ┌──────────────────────────────────┐ │    │
│  │  │   Sidebar    │  │         Main Panel               │ │    │
│  │  │  - Buttons   │  │  ┌────────────────────────────┐  │ │    │
│  │  │  - Actions   │  │  │     Session Cards          │  │ │    │
│  │  │              │  │  │  - Name, status, output    │  │ │    │
│  │  │              │  │  └────────────────────────────┘  │ │    │
│  │  │              │  │  ┌────────────────────────────┐  │ │    │
│  │  │              │  │  │     Log Panel              │  │ │    │
│  │  │              │  │  └────────────────────────────┘  │ │    │
│  │  └──────────────┘  └──────────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  Session Manager                         │    │
│  │  - managed_sessions: dict[session_id, SessionInfo]       │    │
│  │  - session_cards: dict[session_id, SessionCard]          │    │
│  │  - monitor tasks (asyncio)                               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  iTerm2 Connection                       │    │
│  │  - iterm_connection: Connection                          │    │
│  │  - notification subscriptions                            │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Code Structure

```
iterm-controller/
├── controller.py          # Main application (monolithic for POC)
├── simple_demo.py         # Simpler menu-driven demo
├── requirements.txt       # Dependencies
├── README.md              # Usage instructions
└── docs/
    ├── API_REFERENCE.md   # iTerm2 API documentation
    ├── ARCHITECTURE.md    # This file
    └── DATA_MODEL.md      # Data structures for future app
```

## Key Classes

### ControllerApp (Textual App)

The main TUI application. Inherits from `textual.app.App`.

**Responsibilities:**
- Render the UI (sidebar, main panel, log)
- Handle button clicks and keyboard shortcuts
- Manage the lifecycle of spawned sessions
- Coordinate between UI and iTerm2 API

**Key Attributes:**
```python
class ControllerApp(App):
    iterm_connection: Connection     # iTerm2 API connection
    managed_sessions: dict[str, dict]  # session_id -> session info
    session_cards: dict[str, SessionCard]  # session_id -> UI card
```

**Key Methods:**
```python
async def spawn_session(name, command)      # Create tab, run command, monitor
async def spawn_watcher_pair()              # Create split panes
async def spawn_dev_layout()                # Create 2x2 grid
async def monitor_session(session_id)       # Poll screen contents
async def watch_session_termination(id)     # Subscribe to exit events
async def refresh_all_sessions()            # Update all session outputs
async def kill_all_sessions()               # Close all managed sessions
```

### SessionCard (Textual Widget)

A UI card displaying session status and output preview.

**Attributes:**
```python
class SessionCard(Static):
    session_id: str          # iTerm2 session ID
    session_name: str        # Display name
    command: str             # Command being run
    status: reactive[str]    # "starting", "running", "exited"
    last_output: reactive[str]  # Most recent screen content
```

**Methods:**
```python
def update_status(status: str)    # Update status indicator
def update_output(text: str)      # Update output preview
```

## Data Flow

### Spawning a Session

```
1. User clicks button / presses key
   │
   ▼
2. on_button_pressed() called
   │
   ▼
3. spawn_session(name, command)
   │
   ├──► iTerm2: window.async_create_tab()
   │    └──► Returns: Tab with Session
   │
   ├──► iTerm2: session.async_set_name(name)
   │
   ├──► iTerm2: session.async_send_text(command)
   │
   ├──► Create SessionCard widget
   │    └──► Mount to sessions-container
   │
   ├──► Store in managed_sessions dict
   │
   └──► Start monitor_session() task
```

### Monitoring a Session

```
1. monitor_session(session_id) started as asyncio task
   │
   ▼
2. Loop every 1 second:
   │
   ├──► iTerm2: session.async_get_screen_contents()
   │    └──► Returns: ScreenContents
   │
   ├──► Extract text lines from contents
   │
   └──► session_cards[id].update_output(text)
        └──► TUI re-renders card
```

### Termination Detection

```
1. watch_session_termination() subscribes to notifications
   │
   ▼
2. When session exits, iTerm2 sends notification
   │
   ▼
3. on_terminate() callback fires
   │
   ├──► Update card status to "exited"
   │
   └──► Remove from managed_sessions
```

## Async Architecture

The application uses Python's `asyncio` for concurrency:

```python
# iTerm2 provides the event loop via run_until_complete
iterm2.run_until_complete(main_with_iterm)

async def main_with_iterm(connection):
    # Textual also uses asyncio
    app = ControllerApp(iterm_connection=connection)
    await app.run_async()
```

**Concurrent Tasks:**
- Main TUI event loop (Textual)
- One monitor task per managed session
- Notification callbacks (termination, etc.)

**Task Management:**
```python
# Spawning monitor tasks
asyncio.create_task(self.monitor_session(session_id))

# Tasks automatically cancelled when session removed from managed_sessions
while session_id in self.managed_sessions:
    # ... polling loop
```

## Extension Points

### Adding New Session Types

1. Add button to `compose()` method
2. Add keyboard binding to `BINDINGS`
3. Add handler in `on_button_pressed()`
4. Add action method `action_spawn_xxx()`

### Custom Session Layouts

The `async_split_pane()` method supports complex layouts:

```python
# 2x2 grid
top_left = tab.current_session
top_right = await top_left.async_split_pane(vertical=True)
bottom_left = await top_left.async_split_pane(vertical=False)
bottom_right = await top_right.async_split_pane(vertical=False)
```

### Persistent State

Currently all state is in-memory. To add persistence:

1. Define data models (see DATA_MODEL.md)
2. Serialize to JSON/SQLite on changes
3. Load on startup
4. Reconnect to existing sessions via session_id

## Limitations

1. **No persistence**: All state lost on restart
2. **Single window**: Assumes one iTerm2 window
3. **No error recovery**: If iTerm2 restarts, connection lost
4. **Limited output parsing**: Just shows raw text, no structure
5. **No inter-session communication**: Sessions are independent
