"""Session spawning for iTerm2.

This module provides session creation functionality for spawning new tabs
and split panes in iTerm2.
"""

from __future__ import annotations

import logging
import re
import shlex
from dataclasses import dataclass

import iterm2

from iterm_controller.iterm.connection import ItermController
from iterm_controller.models import (
    ManagedSession,
    Project,
    SessionTemplate,
)

logger = logging.getLogger(__name__)

# Valid environment variable key pattern: starts with letter or underscore,
# followed by letters, digits, or underscores
_ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class SpawnResult:
    """Result of spawning a session."""

    session_id: str
    tab_id: str
    success: bool
    error: str | None = None


class SessionSpawner:
    """Spawns and manages terminal sessions."""

    def __init__(self, controller: ItermController) -> None:
        self.controller = controller
        self.managed_sessions: dict[str, ManagedSession] = {}

    def _validate_env_key(self, key: str) -> bool:
        """Validate that an environment variable key is safe.

        Valid keys must start with a letter or underscore, followed by
        letters, digits, or underscores. This prevents injection attacks
        via malicious key names.

        Args:
            key: The environment variable key to validate.

        Returns:
            True if the key is valid, False otherwise.
        """
        return bool(_ENV_KEY_PATTERN.match(key))

    def _build_command(
        self,
        template: SessionTemplate,
        project: Project,
    ) -> str:
        """Build the full command string for a session.

        Includes cd to working directory, environment exports, and the template command.

        Raises:
            ValueError: If any environment variable key is invalid.
        """
        working_dir = template.working_dir or project.path
        parts = [f"cd {self._quote_path(working_dir)}"]

        # Add environment exports if any
        if template.env:
            env_pairs = []
            for key, value in template.env.items():
                # Validate the key to prevent injection via key names
                if not self._validate_env_key(key):
                    raise ValueError(
                        f"Invalid environment variable key: {key!r}. "
                        "Keys must match ^[A-Za-z_][A-Za-z0-9_]*$"
                    )
                # Use shlex.quote for the value (returns single-quoted string)
                env_pairs.append(f"{key}={self._escape_value(value)}")
            parts.append(f"export {' '.join(env_pairs)}")

        # Add the main command if specified
        if template.command:
            parts.append(template.command)

        return " && ".join(parts)

    def _quote_path(self, path: str) -> str:
        """Quote a path for safe shell usage.

        Uses shlex.quote() to properly escape all shell metacharacters,
        preventing command injection attacks via malicious path names.
        """
        return shlex.quote(path)

    def _escape_value(self, value: str) -> str:
        """Escape special characters in environment variable values.

        Uses shlex.quote() to properly escape all shell metacharacters,
        preventing command injection attacks.
        """
        return shlex.quote(value)

    async def spawn_session(
        self,
        template: SessionTemplate,
        project: Project,
        window: iterm2.Window | None = None,
    ) -> SpawnResult:
        """Spawn a new session from template.

        Creates a new tab in the specified window (or current window) and
        sends the initial command from the template.

        Args:
            template: Session template defining the command and environment.
            project: Project context for working directory.
            window: Target window, or None to use current window (creating one if needed).

        Returns:
            SpawnResult with session_id, tab_id, and success status.
        """
        self.controller.require_connection()

        try:
            app = self.controller.app
            assert app is not None  # require_connection ensures this

            # Use provided window, current window, or create new
            if window is None:
                window = app.current_terminal_window
                if window is None:
                    window = await iterm2.Window.async_create(self.controller.connection)
                    logger.info("Created new iTerm2 window")

            # Create new tab
            tab = await window.async_create_tab()
            session = tab.current_session
            assert session is not None

            # Build and send command
            full_command = self._build_command(template, project)
            await session.async_send_text(full_command + "\n")

            # Track session
            managed = ManagedSession(
                id=session.session_id,
                template_id=template.id,
                project_id=project.id,
                tab_id=tab.tab_id,
            )
            self.managed_sessions[session.session_id] = managed

            logger.info(
                f"Spawned session {session.session_id} from template '{template.name}' "
                f"in tab {tab.tab_id}"
            )

            return SpawnResult(
                session_id=session.session_id,
                tab_id=tab.tab_id,
                success=True,
            )

        except Exception as e:
            logger.error(f"Failed to spawn session from template '{template.id}': {e}")
            return SpawnResult(
                session_id="",
                tab_id="",
                success=False,
                error=str(e),
            )

    async def spawn_split(
        self,
        template: SessionTemplate,
        project: Project,
        parent_session: iterm2.Session,
        vertical: bool = True,
    ) -> SpawnResult:
        """Spawn session as split pane.

        Creates a new pane by splitting an existing session and sends the
        initial command from the template.

        Args:
            template: Session template defining the command and environment.
            project: Project context for working directory.
            parent_session: Existing session to split.
            vertical: If True, split vertically (side by side); if False, horizontally.

        Returns:
            SpawnResult with session_id, tab_id, and success status.
        """
        self.controller.require_connection()

        try:
            # Split the parent session
            session = await parent_session.async_split_pane(vertical=vertical)

            # Build and send command
            full_command = self._build_command(template, project)
            await session.async_send_text(full_command + "\n")

            # Get tab_id from parent session's tab
            # Note: session.tab is available after split
            tab_id = parent_session.tab.tab_id if parent_session.tab else ""

            # Track session
            managed = ManagedSession(
                id=session.session_id,
                template_id=template.id,
                project_id=project.id,
                tab_id=tab_id,
            )
            self.managed_sessions[session.session_id] = managed

            logger.info(
                f"Spawned split session {session.session_id} from template '{template.name}' "
                f"(vertical={vertical})"
            )

            return SpawnResult(
                session_id=session.session_id,
                tab_id=tab_id,
                success=True,
            )

        except Exception as e:
            logger.error(f"Failed to spawn split session from template '{template.id}': {e}")
            return SpawnResult(
                session_id="",
                tab_id="",
                success=False,
                error=str(e),
            )

    def get_session(self, session_id: str) -> ManagedSession | None:
        """Get a managed session by ID."""
        return self.managed_sessions.get(session_id)

    def get_sessions_for_project(self, project_id: str) -> list[ManagedSession]:
        """Get all managed sessions for a project."""
        return [s for s in self.managed_sessions.values() if s.project_id == project_id]

    def untrack_session(self, session_id: str) -> None:
        """Remove a session from tracking."""
        if session_id in self.managed_sessions:
            del self.managed_sessions[session_id]
            logger.debug(f"Untracked session {session_id}")
