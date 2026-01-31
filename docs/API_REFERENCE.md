# iTerm2 Python API Reference

This document covers the iTerm2 Python API methods relevant to the controller application.

## Setup

```python
import iterm2
from iterm2 import notifications as iterm2_notifications

# Entry point - runs async main with iTerm2 connection
iterm2.run_until_complete(main)

async def main(connection):
    app = await iterm2.async_get_app(connection)
    # connection is passed to all API calls
```

## Core Objects

### App
The singleton application object.

```python
app = await iterm2.async_get_app(connection)

# Properties
app.windows              # List of all windows
app.current_terminal_window  # Currently focused window
```

### Window
Represents an iTerm2 window.

```python
window = app.current_terminal_window

# Properties
window.window_id         # Unique identifier
window.tabs              # List of Tab objects
window.current_tab       # Currently selected tab

# Methods
tab = await window.async_create_tab()           # Create new tab
tab = await window.async_create_tab(command="ls")  # With command
await window.async_activate()                   # Focus this window
await window.async_set_title("My Window")       # Set window title
await window.async_close()                      # Close window
```

### Creating New Windows

```python
# Create a new empty window
new_window = await iterm2.Window.async_create(connection)

# Create window with a command running
new_window = await iterm2.Window.async_create(connection, command="htop")

# Create window with specific profile
new_window = await iterm2.Window.async_create(connection, profile="Default")
```

### Multi-Window Management

```python
app = await iterm2.async_get_app(connection)

# Access all windows
all_windows = app.windows
terminal_windows = app.terminal_windows

# Get specific window by ID
window = app.get_window_by_id(window_id)

# Find which window contains a session
window, tab = app.get_window_and_tab_for_session(session)

# Window positioning
frame = await window.async_get_frame()  # Returns Frame(x, y, width, height)
await window.async_set_frame(iterm2.Frame(
    origin=iterm2.Point(x, y),
    size=iterm2.Size(width, height)
))

# Fullscreen
is_fullscreen = await window.async_get_fullscreen()
await window.async_set_fullscreen(True)
```

### Tab
Represents a tab within a window.

```python
tab = window.current_tab

# Properties
tab.tab_id               # Unique identifier
tab.sessions             # List of Session objects (panes)
tab.current_session      # Currently focused session/pane

# Methods
await tab.async_activate()    # Focus this tab
await tab.async_close()       # Close the tab
await tab.async_set_title("My Tab")  # Set tab title
```

### Session
Represents a terminal session (a pane within a tab).

```python
session = tab.current_session

# Properties
session.session_id       # Unique identifier
session.grid_size        # Visible dimensions (width, height in cells)
session.preferred_size   # Preferred dimensions
```

## Session Methods

### Creating Sessions

```python
# Create new tab with session
tab = await window.async_create_tab()
session = tab.current_session

# Split pane vertically (side by side)
right_pane = await session.async_split_pane(vertical=True)

# Split pane horizontally (top/bottom)
bottom_pane = await session.async_split_pane(vertical=False)

# Split with command
pane = await session.async_split_pane(vertical=True, command="npm run dev")
```

### Sending Input

```python
# Send text as if typed
await session.async_send_text("echo hello\n")

# Send without newline (user must press enter)
await session.async_send_text("partial command")

# Inject data as if it came from the program
await session.async_inject(b"fake output")
```

### Reading Output

```python
# Get visible screen contents
contents = await session.async_get_screen_contents()
for i in range(contents.number_of_lines):
    line = contents.line(i)
    print(line.string)  # Text content
    # line also has color/style info

# Get scrollback history
contents = await session.async_get_contents(first_line=0, number_of_lines=100)

# Get line info (dimensions, history size)
info = await session.async_get_line_info()
print(info.scrollback_buffer_height)
print(info.overflow)  # Lines lost due to scrollback limit
```

### Session Metadata

```python
# Set session name (appears in tab)
await session.async_set_name("Dev Server")

# Custom variables (must start with "user.")
await session.async_set_variable("user.project_id", "proj-123")
await session.async_set_variable("user.status", "running")

# Read variables
value = await session.async_get_variable("user.project_id")
```

### Session Lifecycle

```python
# Activate (focus) the session
await session.async_activate()

# Close the session
await session.async_close()

# Restart the session
await session.async_restart()

# Bury (hide without closing)
await session.async_set_buried(True)
```

## Notifications (Event Subscriptions)

### Subscribe to Events

```python
from iterm2 import notifications as iterm2_notifications

# When a new session is created
async def on_new_session(connection, notification):
    print(f"New session: {notification.session_id}")

await iterm2_notifications.async_subscribe_to_new_session_notification(
    connection, on_new_session
)

# When a session terminates
async def on_terminate(connection, notification):
    print(f"Session ended: {notification.session_id}")

await iterm2_notifications.async_subscribe_to_terminate_session_notification(
    connection, on_terminate
)

# When shell prompt appears (command finished)
async def on_prompt(connection, notification):
    print(f"Prompt ready in: {notification.session_id}")

await iterm2_notifications.async_subscribe_to_prompt_notification(
    connection, on_prompt, session=session.session_id  # Optional: specific session
)

# When screen content changes
async def on_screen_update(connection, notification):
    print(f"Screen updated: {notification.session_id}")

await iterm2_notifications.async_subscribe_to_screen_update_notification(
    connection, on_screen_update
)

# When layout changes (tabs/panes rearranged)
async def on_layout_change(connection, notification):
    print("Layout changed")

await iterm2_notifications.async_subscribe_to_layout_change_notification(
    connection, on_layout_change
)

# When focus changes
async def on_focus_change(connection, notification):
    print(f"Focus changed")

await iterm2_notifications.async_subscribe_to_focus_change_notification(
    connection, on_focus_change
)

# When a variable changes
async def on_var_change(connection, notification):
    print(f"Variable {notification.name} = {notification.value}")

await iterm2_notifications.async_subscribe_to_variable_change_notification(
    connection, on_var_change,
    name="user.status",  # Variable to watch
    session=session.session_id
)
```

### Unsubscribe

```python
# Subscribe returns a token
token = await iterm2_notifications.async_subscribe_to_new_session_notification(
    connection, callback
)

# Use token to unsubscribe
await iterm2_notifications.async_unsubscribe(connection, token)
```

## Screen Streaming

For real-time output monitoring:

```python
# Event-based streaming (waits for changes)
async with session.get_screen_streamer() as streamer:
    while True:
        contents = await streamer.async_get()
        if contents:
            # Process screen contents
            pass

# Note: Some TUI apps may not trigger screen update events properly.
# In those cases, polling with async_get_screen_contents() may work better.
```

## Window Arrangements

Save and restore window layouts:

```python
# Save current arrangement
# (Done via iTerm2 menu or AppleScript, not directly via Python API)

# Restore arrangement by name
await iterm2.async_restore_window_arrangement(connection, "MyArrangement")
```

## Profile Management

```python
# Get session's profile
profile = await session.async_get_profile()

# Modify profile properties
await session.async_set_profile_properties({
    "Background Color": {"Red": 0.1, "Green": 0.1, "Blue": 0.1}
})
```

## Error Handling

```python
try:
    await session.async_send_text("command\n")
except iterm2.RPCException as e:
    # Session may have closed
    print(f"RPC error: {e}")
```

## Known Limitations

### Tab Movement Between Windows

The API has limited support for moving tabs between windows:

| Operation | Supported | Method |
|-----------|-----------|--------|
| Move tab to NEW window | ✅ Yes | `tab.async_move_to_window()` |
| Move tab to EXISTING window | ❌ No | Not in API |
| Reorder tabs within same window | ✅ Yes | `window.async_set_tabs([...])` |

**Impact**: Cannot programmatically consolidate tabs from multiple windows into one, or split tabs from one window into specific existing windows.

**Workarounds to explore**:
1. **AppleScript** - iTerm2's AppleScript interface might support cross-window tab moves
2. **Close & recreate** - Close tabs and recreate in target window (loses scrollback history)
3. **Window arrangements** - Use `async_save_window_as_arrangement()` / `async_restore_window_arrangement()` for predefined layouts
4. **Design around it** - Create windows with correct tabs from the start, rather than reorganizing later

**TODO**: Investigate AppleScript `tell application "iTerm2"` for more flexible tab management.

## Best Practices

1. **Always check for None**: `window = app.current_terminal_window` can be None
2. **Use try/except**: Sessions can close at any time
3. **Poll vs Stream**: Use polling for TUI apps, streaming for simple output
4. **Session IDs are stable**: Store session_id to reference sessions later
5. **Variables for metadata**: Use `user.*` variables to attach custom data to sessions
