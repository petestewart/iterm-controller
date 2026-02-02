"""Window layout spawning for iTerm2.

This module provides functionality for spawning predefined window layouts
with tabs and sessions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import iterm2

from iterm_controller.iterm.connection import ItermController
from iterm_controller.iterm.spawner import SessionSpawner, SpawnResult
from iterm_controller.models import (
    ManagedSession,
    Project,
    SessionLayout,
    SessionTemplate,
    TabLayout,
    WindowLayout,
)

logger = logging.getLogger(__name__)


@dataclass
class LayoutSpawnResult:
    """Result of spawning an entire window layout."""

    window_id: str
    results: list[SpawnResult]
    success: bool
    error: str | None = None

    @property
    def all_successful(self) -> bool:
        """Check if all sessions spawned successfully."""
        return all(r.success for r in self.results)

    @property
    def spawned_session_ids(self) -> list[str]:
        """Get list of successfully spawned session IDs."""
        return [r.session_id for r in self.results if r.success]


class WindowLayoutSpawner:
    """Spawns window layouts with predefined tabs and sessions."""

    def __init__(self, controller: ItermController, spawner: SessionSpawner) -> None:
        self.controller = controller
        self.spawner = spawner

    async def spawn_layout(
        self,
        layout: WindowLayout,
        project: Project,
        session_templates: dict[str, SessionTemplate],
    ) -> LayoutSpawnResult:
        """Spawn a complete window layout.

        Creates a new iTerm2 window and populates it with tabs and sessions
        according to the WindowLayout configuration.

        Args:
            layout: The window layout configuration specifying tabs and sessions.
            project: Project context for working directories and environment.
            session_templates: Mapping of template IDs to SessionTemplate objects.

        Returns:
            LayoutSpawnResult containing the window ID, individual spawn results,
            and overall success status.
        """
        self.controller.require_connection()
        results: list[SpawnResult] = []

        try:
            # Create new window
            window = await iterm2.Window.async_create(self.controller.connection)
            window_id = window.window_id
            logger.info(f"Created new window {window_id} for layout '{layout.name}'")

            if not layout.tabs:
                logger.warning(f"Layout '{layout.name}' has no tabs defined")
                return LayoutSpawnResult(
                    window_id=window_id,
                    results=results,
                    success=True,
                )

            for tab_index, tab_layout in enumerate(layout.tabs):
                tab_results = await self._spawn_tab(
                    window=window,
                    tab_index=tab_index,
                    tab_layout=tab_layout,
                    project=project,
                    session_templates=session_templates,
                )
                results.extend(tab_results)

            success = all(r.success for r in results) if results else True
            logger.info(
                f"Layout '{layout.name}' spawned with {len(results)} sessions "
                f"({sum(1 for r in results if r.success)} successful)"
            )

            return LayoutSpawnResult(
                window_id=window_id,
                results=results,
                success=success,
            )

        except Exception as e:
            logger.error(f"Failed to spawn layout '{layout.name}': {e}")
            return LayoutSpawnResult(
                window_id="",
                results=results,
                success=False,
                error=str(e),
            )

    async def _spawn_tab(
        self,
        window: iterm2.Window,
        tab_index: int,
        tab_layout: TabLayout,
        project: Project,
        session_templates: dict[str, SessionTemplate],
    ) -> list[SpawnResult]:
        """Spawn a single tab with its sessions.

        Args:
            window: The iTerm2 window to create the tab in.
            tab_index: Index of this tab (0 = use window's default tab).
            tab_layout: Configuration for this tab's layout.
            project: Project context.
            session_templates: Available session templates.

        Returns:
            List of SpawnResult for each session in the tab.
        """
        results: list[SpawnResult] = []

        try:
            # First tab uses window's default tab, others create new tabs
            if tab_index == 0:
                tab = window.current_tab
                if tab is None:
                    logger.error("Window has no current tab")
                    return results
            else:
                tab = await window.async_create_tab()

            # Set tab title
            if tab_layout.name:
                await tab.async_set_title(tab_layout.name)
                logger.debug(f"Set tab title to '{tab_layout.name}'")

            if not tab_layout.sessions:
                logger.debug(f"Tab '{tab_layout.name}' has no sessions defined")
                return results

            # Get the tab's initial session as the parent for splits
            current_session = tab.current_session
            if current_session is None:
                logger.error(f"Tab '{tab_layout.name}' has no current session")
                return results

            for session_index, session_layout in enumerate(tab_layout.sessions):
                result = await self._spawn_session_in_tab(
                    tab=tab,
                    current_session=current_session,
                    session_index=session_index,
                    session_layout=session_layout,
                    project=project,
                    session_templates=session_templates,
                )
                if result:
                    results.append(result)
                    # Update current_session for the next split if successful
                    if result.success and session_index > 0:
                        # After a split, continue splitting from the new session
                        try:
                            new_session = self.controller.app.get_session_by_id(
                                result.session_id
                            )
                            if new_session:
                                current_session = new_session
                        except Exception:
                            pass  # Keep using the previous session

        except Exception as e:
            logger.error(f"Failed to spawn tab '{tab_layout.name}': {e}")

        return results

    async def _spawn_session_in_tab(
        self,
        tab: iterm2.Tab,
        current_session: iterm2.Session,
        session_index: int,
        session_layout: SessionLayout,
        project: Project,
        session_templates: dict[str, SessionTemplate],
    ) -> SpawnResult | None:
        """Spawn a single session within a tab.

        Args:
            tab: The tab to spawn the session in.
            current_session: The session to use or split from.
            session_index: Index of this session (0 = use tab's default session).
            session_layout: Configuration for this session.
            project: Project context.
            session_templates: Available session templates.

        Returns:
            SpawnResult for this session, or None if template not found.
        """
        template = session_templates.get(session_layout.template_id)
        if not template:
            logger.warning(
                f"Session template '{session_layout.template_id}' not found, skipping"
            )
            return SpawnResult(
                session_id="",
                tab_id=tab.tab_id,
                success=False,
                error=f"Template '{session_layout.template_id}' not found",
            )

        try:
            if session_index == 0:
                # First session uses the tab's default session
                # Send command directly to it
                full_command = self.spawner._build_command(template, project)
                await current_session.async_send_text(full_command + "\n")

                # Get window_id from the tab's window
                window_id = ""
                if tab.window:
                    window_id = tab.window.window_id

                # Track session
                managed = ManagedSession(
                    id=current_session.session_id,
                    template_id=template.id,
                    project_id=project.id,
                    tab_id=tab.tab_id,
                    window_id=window_id,
                )
                self.spawner.managed_sessions[current_session.session_id] = managed

                logger.info(
                    f"Initialized tab's default session with template '{template.name}' "
                    f"in window {window_id}"
                )

                return SpawnResult(
                    session_id=current_session.session_id,
                    tab_id=tab.tab_id,
                    success=True,
                    window_id=window_id,
                )
            else:
                # Subsequent sessions are splits
                vertical = session_layout.split == "vertical"
                return await self.spawner.spawn_split(
                    template=template,
                    project=project,
                    parent_session=current_session,
                    vertical=vertical,
                )

        except Exception as e:
            logger.error(
                f"Failed to spawn session from template '{template.id}': {e}"
            )
            return SpawnResult(
                session_id="",
                tab_id=tab.tab_id,
                success=False,
                error=str(e),
            )
