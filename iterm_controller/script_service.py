"""Script service for running project scripts in iTerm2 sessions.

Provides functionality to run project scripts (server, tests, build, etc.)
in iTerm2 sessions with proper tracking and completion callbacks.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Callable

from iterm_controller.models import (
    ManagedSession,
    Project,
    ProjectScript,
    RunningScript,
    SessionTemplate,
    SessionType,
)

if TYPE_CHECKING:
    from iterm_controller.iterm.spawner import SessionSpawner


logger = logging.getLogger(__name__)


class ScriptService:
    """Manages running project scripts.

    This service handles:
    - Converting ProjectScript configs to SessionTemplate for spawning
    - Running scripts in sessions via SessionSpawner
    - Tracking running scripts and their associated sessions
    - Handling completion callbacks and cleanup
    - Stopping running scripts

    Attributes:
        session_spawner: The session spawner for creating terminal sessions.
    """

    def __init__(self, session_spawner: "SessionSpawner") -> None:
        """Initialize the script service.

        Args:
            session_spawner: The session spawner for creating terminal sessions.
        """
        self.session_spawner = session_spawner
        self._running_scripts: dict[str, RunningScript] = {}

    async def run_script(
        self,
        project: Project,
        script: ProjectScript,
        on_complete: Callable[[int], None] | None = None,
    ) -> ManagedSession:
        """Run a project script in a new session.

        Converts the script configuration to a SessionTemplate and spawns
        a new session. The session is tracked along with any completion
        callback.

        Args:
            project: The project context.
            script: The script configuration to run.
            on_complete: Optional callback when script exits (receives exit code).

        Returns:
            The spawned ManagedSession.

        Raises:
            RuntimeError: If session spawning fails.
        """
        # Convert script to session template
        template = self._script_to_template(script, project)

        # Get the window for the project's sessions (spawn in same window)
        window = await self._get_project_window(project)

        # Spawn the session
        result = await self.session_spawner.spawn_session(
            template=template,
            project=project,
            window=window,
        )

        if not result.success:
            raise RuntimeError(
                f"Failed to spawn session for script '{script.name}': {result.error}"
            )

        # Get the managed session
        session = self.session_spawner.get_session(result.session_id)
        if session is None:
            raise RuntimeError(
                f"Session {result.session_id} not found after spawn"
            )

        # Update session with script-specific info
        session.session_type = script.session_type
        session.display_name = script.name

        # Track the running script
        running = RunningScript(
            script=script,
            session_id=result.session_id,
            started_at=datetime.now(),
            on_complete=on_complete,
        )
        self._running_scripts[script.id] = running

        logger.info(
            f"Started script '{script.name}' (id={script.id}) in session {result.session_id}"
        )

        return session

    async def _get_project_window(self, project: Project) -> "iterm2.Window | None":
        """Get the iTerm2 window for a project's sessions.

        Looks for an existing session for the project and uses its window.
        This ensures new scripts spawn as tabs in the same window.

        Args:
            project: The project to find a window for.

        Returns:
            The iTerm2 window if found, None otherwise.
        """
        # Import here to avoid circular imports
        import iterm2

        # Look for existing sessions in this project
        project_sessions = self.session_spawner.get_sessions_for_project(project.id)

        if not project_sessions:
            return None

        # Get the window ID from an existing session
        for session in project_sessions:
            if session.window_id:
                # Try to get the window from iTerm2
                app = self.session_spawner.controller.app
                if app:
                    for window in app.windows:
                        if window.window_id == session.window_id:
                            return window
                break

        return None

    def _script_to_template(
        self,
        script: ProjectScript,
        project: Project,
    ) -> SessionTemplate:
        """Convert a ProjectScript to a SessionTemplate for spawning.

        Args:
            script: The script configuration.
            project: The project context.

        Returns:
            A SessionTemplate ready for spawning.
        """
        return SessionTemplate(
            id=f"script-{script.id}",
            name=script.name,
            command=script.command,
            working_dir=script.working_dir or project.path,
            env=script.env or {},
        )

    def get_running_scripts(
        self,
        project_id: str | None = None,
    ) -> list[RunningScript]:
        """Get all running scripts, optionally filtered by project.

        Args:
            project_id: If provided, only return scripts for this project.

        Returns:
            List of running scripts.
        """
        scripts = list(self._running_scripts.values())

        if project_id is None:
            return scripts

        # Filter by project
        filtered = []
        for rs in scripts:
            session = self.session_spawner.get_session(rs.session_id)
            if session and session.project_id == project_id:
                filtered.append(rs)

        return filtered

    def get_running_script(self, script_id: str) -> RunningScript | None:
        """Get a running script by its script ID.

        Args:
            script_id: The script ID to look up.

        Returns:
            The RunningScript if found, None otherwise.
        """
        return self._running_scripts.get(script_id)

    def get_running_script_for_session(
        self, session_id: str
    ) -> RunningScript | None:
        """Get the running script for a session.

        Args:
            session_id: The session ID to look up.

        Returns:
            The RunningScript if found, None otherwise.
        """
        for running in self._running_scripts.values():
            if running.session_id == session_id:
                return running
        return None

    def is_script_running(self, script_id: str) -> bool:
        """Check if a script is currently running.

        Args:
            script_id: The script ID to check.

        Returns:
            True if the script is running.
        """
        return script_id in self._running_scripts

    async def stop_script(self, script_id: str) -> bool:
        """Stop a running script.

        Terminates the session associated with the script and removes it
        from tracking.

        Args:
            script_id: The script ID to stop.

        Returns:
            True if the script was running and stopped.
        """
        running = self._running_scripts.get(script_id)
        if not running:
            logger.debug(f"Script '{script_id}' not running, cannot stop")
            return False

        # Get the session
        session = self.session_spawner.get_session(running.session_id)
        if session:
            # Use the terminator from the controller to close the session
            # Import terminator here to avoid circular imports
            from iterm_controller.iterm.terminator import SessionTerminator

            terminator = SessionTerminator(self.session_spawner.controller)

            # Get the iTerm2 session
            app = self.session_spawner.controller.app
            if app:
                iterm_session = app.get_session_by_id(running.session_id)
                if iterm_session:
                    result = await terminator.close_session(iterm_session, force=False)
                    if result.success:
                        self.session_spawner.untrack_session(running.session_id)
                        logger.info(f"Stopped script '{script_id}'")
                    else:
                        logger.warning(
                            f"Failed to stop script '{script_id}': {result.error}"
                        )

        # Remove from tracking regardless
        del self._running_scripts[script_id]
        return True

    def on_session_exit(self, session_id: str, exit_code: int) -> None:
        """Handle session exit to trigger callbacks and cleanup.

        This should be called when a session terminates to invoke any
        registered completion callback and remove the script from tracking.

        Args:
            session_id: The ID of the exited session.
            exit_code: The exit code of the process.
        """
        # Find the running script for this session
        script_id_to_remove: str | None = None

        for script_id, running in self._running_scripts.items():
            if running.session_id == session_id:
                script_id_to_remove = script_id

                # Call completion callback
                if running.on_complete:
                    try:
                        running.on_complete(exit_code)
                    except Exception as e:
                        logger.error(
                            f"Error in completion callback for script "
                            f"'{running.script.name}': {e}"
                        )

                logger.info(
                    f"Script '{running.script.name}' exited with code {exit_code}"
                )
                break

        # Remove from tracking
        if script_id_to_remove:
            del self._running_scripts[script_id_to_remove]

    def clear(self) -> None:
        """Clear all tracked running scripts.

        This does not stop the sessions, just removes tracking.
        """
        self._running_scripts.clear()

    def get_keybindings(
        self, project: Project
    ) -> dict[str, ProjectScript]:
        """Get keybinding-to-script mapping for a project.

        Args:
            project: The project to get keybindings for.

        Returns:
            Dictionary mapping keybinding strings to scripts.
        """
        bindings: dict[str, ProjectScript] = {}

        if not project.scripts:
            return bindings

        for script in project.scripts:
            if script.keybinding:
                bindings[script.keybinding] = script

        return bindings


class ScriptBehavior:
    """Session type-specific script behaviors.

    Provides static methods to determine behavior based on session type
    for common operations like what to do when a script keybinding is
    pressed while the script is already running.
    """

    @staticmethod
    def on_repress(session_type: SessionType) -> str:
        """Determine what to do when script keybinding is pressed while running.

        Args:
            session_type: The type of session.

        Returns:
            Action string:
            - "restart": Stop and restart the script
            - "focus": Focus the existing session
            - "ignore": Do nothing
        """
        behaviors = {
            SessionType.SERVER: "restart",
            SessionType.TEST_RUNNER: "focus",
            SessionType.SCRIPT: "focus",
            SessionType.ORCHESTRATOR: "focus",
            SessionType.SHELL: "focus",
            SessionType.CLAUDE_TASK: "focus",
            SessionType.REVIEW: "focus",
        }
        return behaviors.get(session_type, "focus")

    @staticmethod
    def on_complete(session_type: SessionType, exit_code: int) -> str:
        """Determine what to do when script completes.

        Args:
            session_type: The type of session.
            exit_code: The exit code of the process.

        Returns:
            Action string:
            - "close": Close the session
            - "keep": Keep session open for review
            - "notify": Keep open and notify user
        """
        # Always notify on failure
        if exit_code != 0:
            return "notify"

        behaviors = {
            SessionType.SERVER: "notify",  # Server stopped unexpectedly
            SessionType.TEST_RUNNER: "keep",  # Keep for reviewing results
            SessionType.SCRIPT: "close",  # One-off script done
            SessionType.ORCHESTRATOR: "notify",  # Orchestrator finished
            SessionType.SHELL: "keep",  # Shell exited
            SessionType.CLAUDE_TASK: "notify",  # Task completed
            SessionType.REVIEW: "keep",  # Review finished
        }
        return behaviors.get(session_type, "keep")


@dataclass
class ScriptValidationError:
    """A validation error for a script configuration."""

    script_id: str
    message: str


class ScriptValidator:
    """Validates script configuration.

    Checks for required fields, keybinding format, and conflicts.
    """

    def validate(self, script: ProjectScript) -> list[str]:
        """Validate a single script configuration.

        Args:
            script: The script to validate.

        Returns:
            List of validation error messages (empty if valid).
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
            elif not script.keybinding.isalnum():
                errors.append("Keybinding must be alphanumeric")

        return errors

    def check_keybinding_conflicts(
        self,
        scripts: list[ProjectScript],
    ) -> list[str]:
        """Check for keybinding conflicts between scripts.

        Args:
            scripts: List of scripts to check.

        Returns:
            List of conflict descriptions.
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

    def validate_all(
        self,
        scripts: list[ProjectScript],
    ) -> list[ScriptValidationError]:
        """Validate all scripts and check for conflicts.

        Args:
            scripts: List of scripts to validate.

        Returns:
            List of validation errors.
        """
        errors: list[ScriptValidationError] = []

        for script in scripts:
            for message in self.validate(script):
                errors.append(
                    ScriptValidationError(
                        script_id=script.id,
                        message=message,
                    )
                )

        for conflict in self.check_keybinding_conflicts(scripts):
            errors.append(
                ScriptValidationError(
                    script_id="",
                    message=conflict,
                )
            )

        return errors
