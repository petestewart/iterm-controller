# Mission Control Screen

## Overview

Mission Control is the main screen of the application, showing live output streaming from all active sessions across all projects. It replaces the previous "Control Room" which only showed session status indicators.

## Key Difference from Old Control Room

| Aspect | Old Control Room | New Mission Control |
|--------|------------------|---------------------|
| Display | Session list with status indicators (Working/Waiting/Idle) | Live terminal output from each session in real-time |
| Focus | Status overview | Active monitoring and interaction |

## Layout

### Default View

```
+-----------------------------------------------------------------------------+
|  MISSION CONTROL                                           4 active sessions|
|  ===========================================================================|
|                                                                             |
|  +- 1. Project A --------------------------------------------- WORKING ----+|
|  |  Claude: Creating PLAN.md                                    00:03:42   ||
|  |  -----------------------------------------------------------------------||
|  |  > Analyzing the PRD structure...                                       ||
|  |  > Creating Phase 1: Project Setup                                      ||
|  |  > Adding task 1.1: Initialize repository_                              ||
|  +---------------------------------------------------------------------------+|
|                                                                             |
|  +- 2. Project B --------------------------------------------- WORKING ----+|
|  |  Orchestrator: Phase 2 (Task 2.3 of 6)                       00:12:07   ||
|  |  Progress: ########........ 3/6 tasks                                   ||
|  |  -----------------------------------------------------------------------||
|  |  [2.3] Adding user authentication                                       ||
|  |  > Creating app/models/user.rb                                          ||
|  |  > Running rails db:migrate_                                            ||
|  +---------------------------------------------------------------------------+|
|                                                                             |
|  +- 3. Project C --------------------------------------------- WORKING ----+|
|  |  Tests: pytest                                               00:01:23   ||
|  |  -----------------------------------------------------------------------||
|  |  tests/test_auth.py::test_login PASSED                                  ||
|  |  tests/test_auth.py::test_logout PASSED                                 ||
|  |  tests/test_users.py::test_create ..._                                  ||
|  +---------------------------------------------------------------------------+|
|                                                                             |
|  +- 4. Project D --------------------------------------------- WAITING ----+|
|  |  Claude: Task 3.1 - Fix pagination bug                       00:08:15   ||
|  |  -----------------------------------------------------------------------||
|  |  I've identified the issue. The offset calculation is wrong.            ||
|  |                                                                         ||
|  |  Should I proceed with the fix? [y/n]_                                  ||
|  +---------------------------------------------------------------------------+|
|                                                                             |
|  [1-9] Focus  [Enter] Open project  [n] New session  [?] Help  [p] Projects |
+-----------------------------------------------------------------------------+
```

### Expanded View

Pressing `x` or `Enter` on a session expands it:

```
+-----------------------------------------------------------------------------+
|  MISSION CONTROL                                           4 active sessions|
|  ===========================================================================|
|                                                                             |
|  +- 2. Project B --------------------------------------------- WORKING ----+|
|  |  Orchestrator: Phase 2 (Task 2.3 of 6)                       00:12:07   ||
|  |  -----------------------------------------------------------------------||
|  |                                                                         ||
|  |  [2.2] Done: Set up database schema                                     ||
|  |  ---------------------------------------------------------------------- ||
|  |  [2.3] Adding user authentication                                       ||
|  |  > Reading existing codebase structure...                               ||
|  |  > Found app/controllers/application_controller.rb                      ||
|  |  > Creating app/models/user.rb                                          ||
|  |  > Adding has_secure_password                                           ||
|  |  > Creating migration: 20240115_create_users.rb                         ||
|  |  > Running rails db:migrate                                             ||
|  |  > Migration successful                                                 ||
|  |  > Creating app/controllers/sessions_controller.rb                      ||
|  |  > Adding routes for login/logout_                                      ||
|  |                                                                         ||
|  +---------------------------------------------------------------------------+|
|   1. Project A [WORKING]  3. Project C [WORKING]  4. Project D [WAITING]    |
|                                                                             |
|  [1-4] Switch  [Esc] Collapse  [f] Focus iTerm  [k] Kill  [p] Open project  |
+-----------------------------------------------------------------------------+
```

## Keybindings

| Key | Action |
|-----|--------|
| `1-9` | Focus session N in iTerm2 |
| `Enter` | Open project for selected session |
| `x` | Expand/collapse selected session |
| `n` | New session (shows session picker) |
| `k` | Kill selected session |
| `f` | Focus selected session in iTerm2 |
| `p` | Go to project list |
| `j/k` or Up/Down | Navigate session list |
| `?` | Help |
| `q` | Quit |

## Widgets

### SessionList

Vertical scrollable container of SessionCards.

```python
from textual.widgets import Static
from textual.containers import ScrollableContainer
from textual.app import ComposeResult

class SessionList(ScrollableContainer):
    """Scrollable container for session cards."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.expanded_session: str | None = None  # ID of expanded session

    def compose(self) -> ComposeResult:
        for session in self.app.state.sessions.get_active_sessions():
            yield SessionCard(
                session,
                expanded=(session.id == self.expanded_session)
            )

    def expand_session(self, session_id: str):
        """Expand a session and collapse others."""
        self.expanded_session = session_id
        self.refresh()

    def collapse_session(self):
        """Collapse the expanded session."""
        self.expanded_session = None
        self.refresh()
```

### SessionCard

A single session with header and output log.

```python
from collections import deque
from textual.widgets import Static
from textual.containers import Vertical
from textual.app import ComposeResult

class SessionCard(Static):
    """Card displaying a session with header and live output."""

    def __init__(self, session: "ManagedSession", expanded: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.session = session
        self.expanded = expanded
        self._output_lines: deque[str] = deque(maxlen=100)

    def compose(self) -> ComposeResult:
        yield SessionCardHeader(self.session)
        if self.session.session_type == SessionType.ORCHESTRATOR:
            yield OrchestratorProgress(self.session.progress)
        yield Static("-" * 70, classes="separator")
        yield OutputLog(session=self.session, expanded=self.expanded)

    def update_output(self, output: str):
        """Update the output log with new content."""
        log = self.query_one(OutputLog)
        log.append_output(output)
```

### SessionCardHeader

Shows: project name, session type/name, status, duration.

Format: `Project A | Claude: Creating PLAN.md | WORKING | 00:03:42`

```python
from textual.widgets import Static
from textual.containers import Horizontal
from textual.app import ComposeResult

class SessionCardHeader(Static):
    """Header row for a session card."""

    def __init__(self, session: "ManagedSession", **kwargs):
        super().__init__(**kwargs)
        self.session = session

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Static(f"{self.session.project_name}", classes="project-name"),
            Static(self.get_session_info(), classes="session-info"),
            Static(self.session.attention_state.value.upper(), classes="status"),
            Static(self.format_duration(), classes="duration"),
            classes="header-row"
        )

    def get_session_info(self) -> str:
        """Get session type and current activity."""
        return f"{self.session.template_id}: {self.session.current_activity}"

    def format_duration(self) -> str:
        """Format elapsed time as HH:MM:SS."""
        elapsed = self.session.elapsed_seconds
        hours, remainder = divmod(int(elapsed), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
```

### OutputLog

Scrollable output display with ANSI color support.

```python
from textual.widgets import Static

class OutputLog(Static):
    """Displays scrollable output with ANSI color support."""

    DEFAULT_CSS = """
    OutputLog {
        height: 4;
    }
    OutputLog.expanded {
        height: 20;
    }
    """

    def __init__(self, session: "ManagedSession", expanded: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.session = session
        self.max_lines = 20 if expanded else 4
        self._lines: deque[str] = deque(maxlen=100)

        if expanded:
            self.add_class("expanded")

    def render(self) -> str:
        """Render the last N lines of output."""
        output_lines = list(self._lines)[-self.max_lines:]
        return "\n".join(f"> {line}" for line in output_lines)

    def append_output(self, output: str):
        """Append new output and refresh."""
        for line in output.split("\n"):
            if line.strip():
                self._lines.append(line)
        self.refresh()

    async def on_mount(self):
        """Subscribe to output updates."""
        # Initial load from session buffer
        for line in self.session.output_buffer.get_last_lines(self.max_lines):
            self._lines.append(line)
```

### OrchestratorProgress

Progress bar for orchestrator sessions.

```python
from textual.widgets import Static

class OrchestratorProgress(Static):
    """Progress bar for orchestrator sessions."""

    def __init__(self, progress: "OrchestratorState", **kwargs):
        super().__init__(**kwargs)
        self.progress = progress

    def render(self) -> str:
        """Render progress bar with task counts."""
        completed = self.progress.completed_tasks
        total = self.progress.total_tasks
        current_task = self.progress.current_task

        # Calculate progress bar (16 chars wide)
        if total > 0:
            filled = int((completed / total) * 16)
            bar = "#" * filled + "." * (16 - filled)
        else:
            bar = "." * 16

        lines = [f"Progress: {bar} {completed}/{total} tasks"]
        if current_task:
            lines.append(f"[{current_task.id}] {current_task.title}")

        return "\n".join(lines)
```

## Output Streaming

Mission Control subscribes to output updates from SessionMonitor:

```python
from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import Header, Footer, Static
from textual.containers import Container, Vertical

class MissionControlScreen(Screen):
    """Main mission control showing all active sessions across projects."""

    BINDINGS = [
        ("n", "new_session", "New Session"),
        ("k", "kill_session", "Kill Session"),
        ("enter", "open_project", "Open Project"),
        ("x", "expand_collapse", "Expand/Collapse"),
        ("f", "focus_iterm", "Focus iTerm"),
        ("p", "app.push_screen('project_list')", "Projects"),
        ("j", "move_down", "Down"),
        ("k", "move_up", "Up"),
        ("1", "focus_session_1", "Focus 1"),
        ("2", "focus_session_2", "Focus 2"),
        ("3", "focus_session_3", "Focus 3"),
        ("4", "focus_session_4", "Focus 4"),
        ("5", "focus_session_5", "Focus 5"),
        ("6", "focus_session_6", "Focus 6"),
        ("7", "focus_session_7", "Focus 7"),
        ("8", "focus_session_8", "Focus 8"),
        ("9", "focus_session_9", "Focus 9"),
        ("?", "show_help", "Help"),
        ("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("MISSION CONTROL", id="title"),
            Static(id="session-count"),
            SessionList(id="session-list"),
            id="main"
        )
        yield Footer()

    async def on_mount(self):
        """Subscribe to session output updates."""
        self.app.state.on_event(
            StateEvent.SESSION_OUTPUT_UPDATED,
            self.on_session_output_updated
        )
        await self.refresh_sessions()

    def on_session_output_updated(self, event: "SessionOutputUpdated") -> None:
        """Handle live output updates."""
        try:
            card = self.query_one(f"#session-{event.session_id}", SessionCard)
            card.update_output(event.output)
        except Exception:
            pass  # Session card may not exist yet

    async def refresh_sessions(self):
        """Refresh session list from state."""
        session_list = self.query_one("#session-list", SessionList)
        session_list.refresh()

        active_count = len(self.app.state.sessions.get_active_sessions())
        self.query_one("#session-count").update(f"{active_count} active sessions")
```

## Session Ordering

Sessions are ordered by:
1. Attention state (WAITING first, then WORKING, then IDLE)
2. Last activity (most recent first within same state)

```python
def sort_sessions(sessions: list["ManagedSession"]) -> list["ManagedSession"]:
    """Sort sessions by attention state and activity."""
    state_priority = {
        AttentionState.WAITING: 0,
        AttentionState.WORKING: 1,
        AttentionState.IDLE: 2,
    }

    return sorted(
        sessions,
        key=lambda s: (
            state_priority.get(s.attention_state, 3),
            -(s.last_activity.timestamp() if s.last_activity else 0)
        )
    )
```

## Empty State

When no sessions are active:

```
+-----------------------------------------------------------------------------+
|  MISSION CONTROL                                           0 active sessions|
|  ===========================================================================|
|                                                                             |
|                                                                             |
|                         No active sessions                                  |
|                                                                             |
|                    Press [n] to start a new session                         |
|                    Press [p] to open a project                              |
|                                                                             |
|                                                                             |
+-----------------------------------------------------------------------------+
```

```python
class EmptyState(Static):
    """Empty state display when no sessions are active."""

    def render(self) -> str:
        return """
                    No active sessions

               Press [n] to start a new session
               Press [p] to open a project
        """
```

## CSS Styling

```css
MissionControlScreen {
    background: $surface;
}

#title {
    text-style: bold;
    color: $primary;
    padding: 1;
}

#session-count {
    text-align: right;
    color: $text-muted;
}

SessionCard {
    border: solid $primary;
    margin: 1;
    padding: 1;
}

SessionCard.waiting {
    border: solid $warning;
}

SessionCard.working {
    border: solid $success;
}

SessionCard.idle {
    border: solid $surface-lighten-2;
}

.header-row {
    layout: horizontal;
}

.project-name {
    width: auto;
    text-style: bold;
}

.status {
    width: 10;
    text-align: right;
}

.status.waiting {
    color: $warning;
}

.status.working {
    color: $success;
}

.duration {
    width: 10;
    text-align: right;
    color: $text-muted;
}

.separator {
    color: $surface-lighten-2;
}

OutputLog {
    height: 4;
    overflow-y: auto;
}

OutputLog.expanded {
    height: 20;
}

EmptyState {
    width: 100%;
    height: 100%;
    content-align: center middle;
    color: $text-muted;
}
```

## Integration with Session Monitor

The screen integrates with SessionMonitor to receive live output updates:

```python
@dataclass
class SessionOutputUpdated:
    """Event emitted when session output changes."""
    session_id: str
    output: str
    timestamp: datetime

class SessionMonitor:
    """Extended to emit output events."""

    async def _process_output(
        self,
        session: "ManagedSession",
        new_output: str
    ):
        """Process new output and emit event."""
        # Update session buffer
        session.output_buffer.append(new_output)

        # Emit event for UI updates
        self.state.emit(
            StateEvent.SESSION_OUTPUT_UPDATED,
            SessionOutputUpdated(
                session_id=session.id,
                output=new_output,
                timestamp=datetime.now()
            )
        )

        # Continue with attention detection...
        await super()._process_output(session, new_output)
```
