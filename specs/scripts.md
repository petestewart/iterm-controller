# Project Scripts

## Overview

Project scripts are named commands that can be launched from the Project Screen with keybindings. They provide quick access to common development tasks like starting servers, running tests, or launching orchestrator loops.

## ProjectScript Model

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

@dataclass
class ProjectScript:
    """A named script that can be run from the project screen."""
    id: str                                # Unique identifier
    name: str                              # Display name ("Server", "Tests")
    command: str                           # The actual command to run
    keybinding: str | None = None          # Keybinding ("s", "t", "l")
    working_dir: str | None = None         # Override project dir
    env: dict[str, str] | None = None      # Additional env vars
    session_type: SessionType = SessionType.SCRIPT
    show_in_toolbar: bool = True           # Show as button on project screen
```

## Common Script Types

| Type | SessionType | Example Command |
|------|-------------|-----------------|
| Server | SERVER | `bin/dev`, `npm run dev` |
| Tests | TEST_RUNNER | `bin/rails test`, `pytest` |
| Lint | SCRIPT | `bin/rubocop -A`, `npm run lint` |
| Build | SCRIPT | `npm run build` |
| Orchestrator | ORCHESTRATOR | `bin/run-tasks --phase=current` |

## Configuration Example

```json
{
  "projects": [{
    "id": "my-app",
    "name": "My App",
    "path": "/Users/me/src/my-app",
    "scripts": [
      {
        "id": "server",
        "name": "Server",
        "command": "bin/dev",
        "keybinding": "s",
        "session_type": "server"
      },
      {
        "id": "tests",
        "name": "Tests",
        "command": "bin/rails test",
        "keybinding": "t",
        "session_type": "test_runner"
      },
      {
        "id": "lint",
        "name": "Lint",
        "command": "bin/rubocop -A",
        "keybinding": "l",
        "session_type": "script"
      },
      {
        "id": "orchestrator",
        "name": "Run Tasks",
        "command": "bin/run-tasks --phase=current",
        "keybinding": "o",
        "session_type": "orchestrator"
      }
    ]
  }]
}
```

## ScriptService Class

```python
class ScriptService:
    """Manages running project scripts."""

    def __init__(
        self,
        session_spawner: "SessionSpawner",
        session_monitor: "SessionMonitor"
    ):
        self.session_spawner = session_spawner
        self.session_monitor = session_monitor
        self._running_scripts: dict[str, RunningScript] = {}

    async def run_script(
        self,
        project: "Project",
        script: ProjectScript,
        on_complete: Callable[[int], None] | None = None
    ) -> "ManagedSession":
        """Run a project script in a new session.

        Args:
            project: The project context
            script: The script configuration to run
            on_complete: Optional callback when script exits

        Returns:
            The spawned session
        """
        # Convert script to session template
        template = self._script_to_template(script, project)

        # Spawn the session
        session = await self.session_spawner.spawn(
            template=template,
            project=project,
            session_type=script.session_type
        )

        # Track the running script
        running = RunningScript(
            script=script,
            session_id=session.id,
            started_at=datetime.now(),
            on_complete=on_complete
        )
        self._running_scripts[script.id] = running

        return session

    async def get_running_scripts(
        self,
        project_id: str | None = None
    ) -> list["RunningScript"]:
        """Get all running scripts, optionally filtered by project."""
        scripts = list(self._running_scripts.values())

        if project_id:
            # Filter by project (requires session lookup)
            filtered = []
            for rs in scripts:
                session = self.session_monitor.get_session(rs.session_id)
                if session and session.project_id == project_id:
                    filtered.append(rs)
            return filtered

        return scripts

    def _script_to_template(
        self,
        script: ProjectScript,
        project: "Project"
    ) -> "SessionTemplate":
        """Convert a script to a session template for spawning."""
        return SessionTemplate(
            id=f"script-{script.id}",
            name=script.name,
            command=script.command,
            working_dir=script.working_dir or project.path,
            env=script.env or {}
        )

    async def stop_script(self, script_id: str) -> bool:
        """Stop a running script.

        Returns:
            True if script was running and stopped
        """
        running = self._running_scripts.get(script_id)
        if not running:
            return False

        session = self.session_monitor.get_session(running.session_id)
        if session:
            await self.session_spawner.terminate(session.id)

        del self._running_scripts[script_id]
        return True

    def on_session_exit(self, session_id: str, exit_code: int):
        """Handle session exit to trigger callbacks."""
        # Find the running script for this session
        for script_id, running in list(self._running_scripts.items()):
            if running.session_id == session_id:
                # Call completion callback
                if running.on_complete:
                    running.on_complete(exit_code)

                # Remove from tracking
                del self._running_scripts[script_id]
                break
```

## RunningScript Model

```python
@dataclass
class RunningScript:
    """A script currently executing in a session."""
    script: ProjectScript
    session_id: str
    started_at: datetime
    on_complete: Callable[[int], None] | None = None
```

## TUI Integration

### ScriptToolbar Widget

Displays script buttons in the Project Screen:

```
+-- Scripts ------------------------------------------------------------+
| [s] Server  [t] Tests  [l] Lint  [b] Build  [o] Orchestrator          |
+-----------------------------------------------------------------------+
```

Only scripts with `show_in_toolbar: true` appear here.

```python
from textual.widget import Widget
from textual.widgets import Button, Static

class ScriptToolbar(Widget):
    """Toolbar displaying project script buttons."""

    def __init__(self, project: "Project"):
        super().__init__()
        self.project = project
        self._running_ids: set[str] = set()

    def compose(self):
        """Create script buttons."""
        scripts = self.project.scripts or []
        toolbar_scripts = [s for s in scripts if s.show_in_toolbar]

        for script in toolbar_scripts:
            yield ScriptButton(script, running=script.id in self._running_ids)

    def update_running(self, running_ids: set[str]):
        """Update which scripts show as running."""
        self._running_ids = running_ids
        self.refresh()


class ScriptButton(Static):
    """A single script button in the toolbar."""

    def __init__(self, script: ProjectScript, running: bool = False):
        self.script = script
        self.running = running
        super().__init__(self._render())

    def _render(self) -> str:
        """Render button text."""
        key = f"[{self.script.keybinding}]" if self.script.keybinding else ""
        indicator = " *" if self.running else ""
        return f"{key} {self.script.name}{indicator}"
```

### Dynamic Keybindings

When ProjectScreen loads, it registers keybindings from the project's scripts:

```python
class ProjectScreen(Screen):
    """Project detail screen with script keybindings."""

    def __init__(self, project: "Project", script_service: ScriptService):
        super().__init__()
        self.project = project
        self.script_service = script_service

    def on_mount(self):
        """Register script keybindings on mount."""
        for script in self.project.scripts or []:
            if script.keybinding:
                self.bind(
                    script.keybinding,
                    f"run_script_{script.id}",
                    description=f"Run {script.name}"
                )

    async def action_run_script(self, script_id: str):
        """Handle script keybinding press."""
        script = self._get_script(script_id)
        if not script:
            return

        # Check if already running
        running = await self.script_service.get_running_scripts(self.project.id)
        running_ids = {r.script.id for r in running}

        if script.id in running_ids:
            # Script already running - handle based on type
            if script.session_type == SessionType.SERVER:
                # Restart server
                await self.script_service.stop_script(script.id)
                await self.script_service.run_script(self.project, script)
            else:
                # Focus existing session
                self._focus_script_session(script.id)
        else:
            # Start new script
            await self.script_service.run_script(self.project, script)

    def _get_script(self, script_id: str) -> ProjectScript | None:
        """Get script by ID."""
        for script in self.project.scripts or []:
            if script.id == script_id:
                return script
        return None
```

### Running Indicator

Scripts that are currently running show a visual indicator:

```
| [s] Server *  [t] Tests  [l] Lint  [b] Build  [o] Orchestrator        |
```

## Session Type Behavior

Different session types may have different behaviors:

| SessionType | Behavior |
|-------------|----------|
| SERVER | Long-running, restart on re-press |
| TEST_RUNNER | Run to completion, show results |
| SCRIPT | Run to completion |
| ORCHESTRATOR | Show progress, integrate with review |

```python
class ScriptBehavior:
    """Session type-specific script behaviors."""

    @staticmethod
    def on_repress(session_type: SessionType) -> str:
        """What to do when script keybinding is pressed while running.

        Returns:
            "restart" - Stop and restart the script
            "focus" - Focus the existing session
            "ignore" - Do nothing
        """
        behaviors = {
            SessionType.SERVER: "restart",
            SessionType.TEST_RUNNER: "focus",
            SessionType.SCRIPT: "focus",
            SessionType.ORCHESTRATOR: "focus",
        }
        return behaviors.get(session_type, "focus")

    @staticmethod
    def on_complete(session_type: SessionType, exit_code: int) -> str:
        """What to do when script completes.

        Returns:
            "close" - Close the session
            "keep" - Keep session open for review
            "notify" - Keep open and notify user
        """
        if exit_code != 0:
            return "notify"

        behaviors = {
            SessionType.SERVER: "notify",
            SessionType.TEST_RUNNER: "keep",
            SessionType.SCRIPT: "close",
            SessionType.ORCHESTRATOR: "notify",
        }
        return behaviors.get(session_type, "keep")
```

## Events

```python
from textual.message import Message

class ScriptStarted(Message):
    """Emitted when a script starts running."""

    def __init__(self, project_id: str, script_id: str, session_id: str):
        self.project_id = project_id
        self.script_id = script_id
        self.session_id = session_id
        super().__init__()


class ScriptCompleted(Message):
    """Emitted when a script finishes."""

    def __init__(self, project_id: str, script_id: str, exit_code: int):
        self.project_id = project_id
        self.script_id = script_id
        self.exit_code = exit_code
        super().__init__()
```

## Environment Variables

Scripts inherit environment variables in this order (later values override earlier):

1. System environment
2. Project env vars (from project config)
3. Script-specific env vars (from script config)

```python
import os

class ScriptEnvironment:
    """Builds environment for script execution."""

    def __init__(self, project: "Project"):
        self.project = project

    def build_env(self, script: ProjectScript) -> dict[str, str]:
        """Build complete environment for script execution.

        Args:
            script: The script to build environment for

        Returns:
            Complete environment dict
        """
        # Start with system environment
        env = dict(os.environ)

        # Add project-level env vars
        # (loaded from project config or .env file)
        project_env = self._load_project_env()
        env.update(project_env)

        # Add script-specific env vars
        if script.env:
            env.update(script.env)

        return env

    def _load_project_env(self) -> dict[str, str]:
        """Load project-level environment variables."""
        env = {}

        # Load from project config
        if hasattr(self.project, 'env') and self.project.env:
            env.update(self.project.env)

        # Load from .env file if exists
        env_path = Path(self.project.path) / ".env"
        if env_path.exists():
            parser = EnvParser()
            env.update(parser.load_file(env_path))

        return env
```

## Validation

```python
class ScriptValidator:
    """Validates script configuration."""

    def validate(self, script: ProjectScript) -> list[str]:
        """Validate script configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not script.id:
            errors.append("Script ID is required")

        if not script.name:
            errors.append("Script name is required")

        if not script.command:
            errors.append("Script command is required")

        if script.keybinding:
            if len(script.keybinding) != 1:
                errors.append("Keybinding must be a single character")
            if not script.keybinding.isalnum():
                errors.append("Keybinding must be alphanumeric")

        return errors

    def check_keybinding_conflicts(
        self,
        scripts: list[ProjectScript]
    ) -> list[str]:
        """Check for keybinding conflicts.

        Returns:
            List of conflict descriptions
        """
        conflicts = []
        seen: dict[str, str] = {}

        for script in scripts:
            if script.keybinding:
                key = script.keybinding.lower()
                if key in seen:
                    conflicts.append(
                        f"Keybinding '{key}' used by both "
                        f"'{seen[key]}' and '{script.name}'"
                    )
                else:
                    seen[key] = script.name

        return conflicts
```
