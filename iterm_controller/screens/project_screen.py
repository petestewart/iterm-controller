"""Unified Project Screen.

Replaces the old Project Dashboard + Mode Screens with a single unified view.
All sections (Planning, Tasks, Docs, Git, Env, Scripts, Sessions) are visible
and collapsible in a two-column layout.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from iterm_controller.models import ManagedSession, Plan, Project
from iterm_controller.state import (
    GitStatusChanged,
    PlanReloaded,
    SessionClosed,
    SessionOutputUpdated,
    SessionSpawned,
    SessionStatusChanged,
    TaskStatusChanged,
)
from iterm_controller.widgets import (
    DocsSection,
    EnvSection,
    GitSection,
    PlanningSection,
    ScriptToolbar,
    SessionsPanel,
    TasksSection,
)

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp
    from iterm_controller.models import GitStatus

logger = logging.getLogger(__name__)


class ProjectScreen(Screen):
    """Unified project view with collapsible sections.

    Displays all project information in a two-column layout:
    - Left column: Planning artifacts, Tasks
    - Right column: Docs, Git Status, Env Variables
    - Bottom: Scripts toolbar, Active Sessions panel

    Features:
    - All sections visible and collapsible
    - Git actions (stage, commit, push)
    - Scripts launchable via keybindings
    - Sessions clickable to focus in iTerm2
    """

    DEFAULT_CSS = """
    ProjectScreen {
        layout: vertical;
    }

    ProjectScreen #project-header {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        dock: top;
    }

    ProjectScreen #project-name {
        text-style: bold;
        color: $primary;
    }

    ProjectScreen #branch-info {
        margin-left: 2;
        color: $text-muted;
    }

    ProjectScreen #content-grid {
        height: 1fr;
        min-height: 10;
    }

    ProjectScreen #left-column {
        width: 1fr;
        height: 100%;
        padding: 0 1;
        overflow-y: auto;
    }

    ProjectScreen #right-column {
        width: 1fr;
        height: 100%;
        padding: 0 1;
        overflow-y: auto;
    }

    ProjectScreen #bottom-section {
        height: auto;
        max-height: 15;
        dock: bottom;
    }

    ProjectScreen #main-container {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("e", "edit_artifact", "Edit"),
        Binding("c", "commit", "Commit"),
        Binding("p", "push", "Push"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "run_server", "Server", show=False),
        Binding("t", "run_tests", "Tests", show=False),
        Binding("l", "run_lint", "Lint", show=False),
        Binding("b", "run_build", "Build", show=False),
        Binding("o", "run_orchestrator", "Orchestrator", show=False),
        Binding("tab", "next_section", "Next Section", show=False),
        Binding("shift+tab", "prev_section", "Prev Section", show=False),
        Binding("1", "focus_session_1", "Focus 1", show=False),
        Binding("2", "focus_session_2", "Focus 2", show=False),
        Binding("3", "focus_session_3", "Focus 3", show=False),
        Binding("4", "focus_session_4", "Focus 4", show=False),
        Binding("5", "focus_session_5", "Focus 5", show=False),
        Binding("6", "focus_session_6", "Focus 6", show=False),
        Binding("7", "focus_session_7", "Focus 7", show=False),
        Binding("8", "focus_session_8", "Focus 8", show=False),
        Binding("9", "focus_session_9", "Focus 9", show=False),
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, project_id: str, **kwargs: Any) -> None:
        """Initialize the project screen.

        Args:
            project_id: ID of the project to display.
            **kwargs: Additional arguments passed to Screen.
        """
        super().__init__(**kwargs)
        self.project_id = project_id
        self._project: Project | None = None
        self._plan: Plan | None = None
        self._git_status: GitStatus | None = None
        self._sessions: list[ManagedSession] = []
        self._section_index = 0
        self._sections: list[str] = [
            "planning",
            "tasks",
            "docs",
            "git",
            "env",
            "scripts",
            "sessions",
        ]

    @property
    def app(self) -> "ItermControllerApp":
        """Get the app instance with proper typing."""
        return super().app  # type: ignore[return-value]

    @property
    def project(self) -> Project | None:
        """Get the current project."""
        return self._project

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()

        # Project header with name and branch
        yield Horizontal(
            Static("PROJECT: Loading...", id="project-name"),
            Static("", id="branch-info"),
            id="project-header",
        )

        # Main content with two columns
        yield Container(
            Horizontal(
                # Left column: Planning, Tasks
                Vertical(
                    PlanningSection(id="planning"),
                    TasksSection(id="tasks"),
                    id="left-column",
                ),
                # Right column: Docs, Git, Env
                Vertical(
                    DocsSection(id="docs"),
                    GitSection(id="git"),
                    EnvSection(id="env"),
                    id="right-column",
                ),
                id="content-grid",
            ),
            id="main-container",
        )

        # Bottom section: Scripts and Sessions
        yield Container(
            ScriptToolbar(id="scripts"),
            SessionsPanel(project_id=self.project_id, id="sessions"),
            id="bottom-section",
        )

        yield Footer()

    async def on_mount(self) -> None:
        """Load project data when screen mounts."""
        await self._load_project()
        await self._load_git_status()
        await self._load_sessions()
        await self._load_plan()

    async def _load_project(self) -> None:
        """Load project from state."""
        self._project = self.app.state.projects.get(self.project_id)

        if self._project:
            # Update header
            self.query_one("#project-name", Static).update(
                f"PROJECT: {self._project.name}"
            )

            # Update branch info (will be set by git status)
            jira_suffix = f"  [{self._project.jira_ticket}]" if self._project.jira_ticket else ""
            self.query_one("#branch-info", Static).update(jira_suffix)

            # Set project on all section widgets
            self.query_one("#planning", PlanningSection).set_project(self._project)
            self.query_one("#docs", DocsSection).set_project(self._project)
            self.query_one("#git", GitSection).set_project(self._project)
            self.query_one("#env", EnvSection).set_project(self._project)
            self.query_one("#scripts", ScriptToolbar).set_project(self._project)
            self.query_one("#sessions", SessionsPanel).set_project(self.project_id)
        else:
            self.query_one("#project-name", Static).update("PROJECT: Not found")

    async def _load_git_status(self) -> None:
        """Load git status for the project."""
        if not self._project:
            return

        # Fetch git status via state manager
        self._git_status = await self.app.state.git.refresh(self.project_id)

        if self._git_status:
            # Update branch info in header
            branch_text = f"[{self._git_status.branch}]"
            if self._git_status.ahead > 0:
                branch_text += f" ↑{self._git_status.ahead}"
            if self._git_status.behind > 0:
                branch_text += f" ↓{self._git_status.behind}"

            jira_suffix = f"  ({self._project.jira_ticket})" if self._project.jira_ticket else ""
            self.query_one("#branch-info", Static).update(f"{branch_text}{jira_suffix}")

            # Update git section widget
            self.query_one("#git", GitSection).set_git_status(self._git_status)

    async def _load_sessions(self) -> None:
        """Load sessions for the project."""
        self._sessions = [
            s for s in self.app.state.sessions.values()
            if s.project_id == self.project_id and s.is_active
        ]

        # Update sessions panel
        await self.query_one("#sessions", SessionsPanel).refresh_sessions(self._sessions)

    async def _load_plan(self) -> None:
        """Load plan for the project."""
        if not self._project:
            return

        # Get plan from state manager
        self._plan = self.app.state.get_plan(self.project_id)

        if self._plan:
            self.query_one("#tasks", TasksSection).set_plan(self._plan)

    # =========================================================================
    # Event handlers for state changes
    # =========================================================================

    async def on_git_status_changed(self, message: GitStatusChanged) -> None:
        """Handle git status change event.

        Args:
            message: The git status changed message.
        """
        if message.project_id == self.project_id:
            self._git_status = message.status
            if self._git_status:
                self.query_one("#git", GitSection).set_git_status(self._git_status)

                # Update branch info
                if self._project:
                    branch_text = f"[{self._git_status.branch}]"
                    if self._git_status.ahead > 0:
                        branch_text += f" ↑{self._git_status.ahead}"
                    if self._git_status.behind > 0:
                        branch_text += f" ↓{self._git_status.behind}"
                    jira_suffix = f"  ({self._project.jira_ticket})" if self._project.jira_ticket else ""
                    self.query_one("#branch-info", Static).update(f"{branch_text}{jira_suffix}")

    async def on_plan_reloaded(self, message: PlanReloaded) -> None:
        """Handle plan reloaded event.

        Args:
            message: The plan reloaded message.
        """
        if hasattr(message, "plan"):
            self._plan = message.plan
            self.query_one("#tasks", TasksSection).set_plan(message.plan)

    async def on_task_status_changed(self, message: TaskStatusChanged) -> None:
        """Handle task status changed event.

        Args:
            message: The task status changed message.
        """
        # Refresh the tasks section
        self.query_one("#tasks", TasksSection).refresh()

    async def on_session_spawned(self, message: SessionSpawned) -> None:
        """Handle session spawned event.

        Args:
            message: The session spawned message.
        """
        if message.session.project_id == self.project_id:
            self._sessions.append(message.session)
            await self.query_one("#sessions", SessionsPanel).refresh_sessions(self._sessions)

    async def on_session_closed(self, message: SessionClosed) -> None:
        """Handle session closed event.

        Args:
            message: The session closed message.
        """
        self._sessions = [s for s in self._sessions if s.id != message.session.id]
        await self.query_one("#sessions", SessionsPanel).refresh_sessions(self._sessions)

    async def on_session_status_changed(self, message: SessionStatusChanged) -> None:
        """Handle session status changed event.

        Args:
            message: The session status changed message.
        """
        # Update session in list
        for i, session in enumerate(self._sessions):
            if session.id == message.session.id:
                self._sessions[i] = message.session
                break
        # Refresh sessions panel (it handles this event internally too)

    async def on_session_output_updated(self, message: SessionOutputUpdated) -> None:
        """Handle session output updated event.

        Args:
            message: The session output updated message.
        """
        # Sessions panel handles this internally
        pass

    # =========================================================================
    # Widget message handlers
    # =========================================================================

    async def on_git_section_commit_requested(
        self, message: GitSection.CommitRequested
    ) -> None:
        """Handle commit request from git section.

        Args:
            message: The commit requested message.
        """
        await self._show_commit_modal()

    async def on_git_section_push_requested(
        self, message: GitSection.PushRequested
    ) -> None:
        """Handle push request from git section.

        Args:
            message: The push requested message.
        """
        await self._do_push()

    async def on_git_section_refresh_requested(
        self, message: GitSection.RefreshRequested
    ) -> None:
        """Handle refresh request from git section.

        Args:
            message: The refresh requested message.
        """
        await self._load_git_status()

    async def on_git_section_stage_file_requested(
        self, message: GitSection.StageFileRequested
    ) -> None:
        """Handle stage file request from git section.

        Args:
            message: The stage file requested message.
        """
        await self.app.state.git.stage_files(self.project_id, [message.file_path])

    async def on_git_section_unstage_file_requested(
        self, message: GitSection.UnstageFileRequested
    ) -> None:
        """Handle unstage file request from git section.

        Args:
            message: The unstage file requested message.
        """
        await self.app.state.git.unstage_files(self.project_id, [message.file_path])

    async def on_script_toolbar_script_run_requested(
        self, message: ScriptToolbar.ScriptRunRequested
    ) -> None:
        """Handle script run request from toolbar.

        Args:
            message: The script run requested message.
        """
        await self._run_script(message.script_id)

    async def on_sessions_panel_session_selected(
        self, message: SessionsPanel.SessionSelected
    ) -> None:
        """Handle session selection from sessions panel.

        Args:
            message: The session selected message.
        """
        await self._focus_session(message.session)

    async def on_planning_section_artifact_selected(
        self, message: PlanningSection.ArtifactSelected
    ) -> None:
        """Handle artifact selection from planning section.

        Args:
            message: The artifact selected message.
        """
        if message.exists:
            await self._open_in_editor(message.artifact_path)
        else:
            self.notify(f"Artifact {message.artifact_name} does not exist yet")

    async def on_planning_section_create_missing_requested(
        self, message: PlanningSection.CreateMissingRequested
    ) -> None:
        """Handle create missing request from planning section.

        Args:
            message: The create missing requested message.
        """
        self.notify(f"Would create: {', '.join(message.missing_artifacts)}")
        # Future: Launch Claude session to create artifacts

    async def on_docs_section_doc_selected(
        self, message: DocsSection.DocSelected
    ) -> None:
        """Handle doc selection from docs section.

        Args:
            message: The doc selected message.
        """
        if message.is_url:
            # Open URL in browser
            import webbrowser
            webbrowser.open(message.url)
        elif message.doc_path:
            await self._open_in_editor(message.doc_path)

    async def on_tasks_section_task_selected(
        self, message: TasksSection.TaskSelected
    ) -> None:
        """Handle task selection from tasks section.

        Args:
            message: The task selected message.
        """
        # Future: Show task detail modal
        self.notify(f"Task: {message.task.id} - {message.task.title}")

    async def on_env_section_edit_env_requested(
        self, message: EnvSection.EditEnvRequested
    ) -> None:
        """Handle edit env request from env section.

        Args:
            message: The edit env requested message.
        """
        env_section = self.query_one("#env", EnvSection)
        env_path = env_section.get_env_file_path()
        if env_path:
            await self._open_in_editor(env_path)

    # =========================================================================
    # Actions
    # =========================================================================

    async def action_edit_artifact(self) -> None:
        """Edit the selected artifact."""
        planning = self.query_one("#planning", PlanningSection)
        selected_path = planning.get_selected_path()
        if selected_path and selected_path.exists():
            await self._open_in_editor(selected_path)
        else:
            self.notify("No artifact selected or file doesn't exist")

    async def action_commit(self) -> None:
        """Show commit modal."""
        await self._show_commit_modal()

    async def action_push(self) -> None:
        """Push changes to remote."""
        await self._do_push()

    async def action_refresh(self) -> None:
        """Refresh all data."""
        await self._load_git_status()
        await self._load_sessions()
        await self._load_plan()
        self.query_one("#planning", PlanningSection).refresh_artifacts()
        self.query_one("#docs", DocsSection).refresh_docs()
        self.query_one("#env", EnvSection).refresh_env()
        self.notify("Refreshed")

    def action_next_section(self) -> None:
        """Focus the next section."""
        self._section_index = (self._section_index + 1) % len(self._sections)
        self._highlight_section()

    def action_prev_section(self) -> None:
        """Focus the previous section."""
        self._section_index = (self._section_index - 1) % len(self._sections)
        self._highlight_section()

    def _highlight_section(self) -> None:
        """Highlight the current section."""
        section_id = self._sections[self._section_index]
        try:
            widget = self.query_one(f"#{section_id}")
            widget.focus()
        except Exception:
            pass

    async def action_run_server(self) -> None:
        """Run the server script."""
        await self._run_script_by_keybinding("s")

    async def action_run_tests(self) -> None:
        """Run the tests script."""
        await self._run_script_by_keybinding("t")

    async def action_run_lint(self) -> None:
        """Run the lint script."""
        await self._run_script_by_keybinding("l")

    async def action_run_build(self) -> None:
        """Run the build script."""
        await self._run_script_by_keybinding("b")

    async def action_run_orchestrator(self) -> None:
        """Run the orchestrator script."""
        await self._run_script_by_keybinding("o")

    async def action_focus_session_1(self) -> None:
        """Focus session 1 in iTerm2."""
        await self._focus_session_by_index(1)

    async def action_focus_session_2(self) -> None:
        """Focus session 2 in iTerm2."""
        await self._focus_session_by_index(2)

    async def action_focus_session_3(self) -> None:
        """Focus session 3 in iTerm2."""
        await self._focus_session_by_index(3)

    async def action_focus_session_4(self) -> None:
        """Focus session 4 in iTerm2."""
        await self._focus_session_by_index(4)

    async def action_focus_session_5(self) -> None:
        """Focus session 5 in iTerm2."""
        await self._focus_session_by_index(5)

    async def action_focus_session_6(self) -> None:
        """Focus session 6 in iTerm2."""
        await self._focus_session_by_index(6)

    async def action_focus_session_7(self) -> None:
        """Focus session 7 in iTerm2."""
        await self._focus_session_by_index(7)

    async def action_focus_session_8(self) -> None:
        """Focus session 8 in iTerm2."""
        await self._focus_session_by_index(8)

    async def action_focus_session_9(self) -> None:
        """Focus session 9 in iTerm2."""
        await self._focus_session_by_index(9)

    # =========================================================================
    # Helper methods
    # =========================================================================

    async def _show_commit_modal(self) -> None:
        """Show the commit modal."""
        git_section = self.query_one("#git", GitSection)
        if not git_section.has_staged_changes:
            self.notify("No staged changes to commit", severity="warning")
            return

        from iterm_controller.screens.modals.commit_modal import CommitModal

        def on_commit(message: str | None) -> None:
            if message:
                self.call_later(self._do_commit, message)

        self.app.push_screen(CommitModal(), on_commit)

    async def _do_commit(self, message: str) -> None:
        """Execute the commit.

        Args:
            message: Commit message.
        """
        sha = await self.app.state.git.commit(self.project_id, message)
        if sha:
            self.notify(f"Committed: {sha[:8]}")
        else:
            self.notify("Commit failed", severity="error")

    async def _do_push(self) -> None:
        """Push changes to remote."""
        git_section = self.query_one("#git", GitSection)
        if not git_section.can_push:
            self.notify("Nothing to push", severity="warning")
            return

        success = await self.app.state.git.push(self.project_id)
        if success:
            self.notify("Pushed successfully")
        else:
            self.notify("Push failed", severity="error")

    async def _run_script(self, script_id: str) -> None:
        """Run a project script.

        Args:
            script_id: ID of the script to run.
        """
        if not self._project:
            return

        # Find script in project config
        toolbar = self.query_one("#scripts", ScriptToolbar)
        script = toolbar.get_script_by_id(script_id)

        if script:
            # Spawn a session for the script using ScriptService
            try:
                session = await self.app.services.scripts.run_script(
                    self._project,
                    script,
                )
                # Add to state
                self.app.state.add_session(session)
                self.notify(f"Started: {script.name}")
            except Exception as e:
                logger.error("Failed to run script %s: %s", script_id, e)
                self.notify(f"Failed to start {script.name}", severity="error")
        else:
            self.notify(f"Script not found: {script_id}", severity="warning")

    async def _run_script_by_keybinding(self, keybinding: str) -> None:
        """Run a script by its keybinding.

        Args:
            keybinding: The keybinding to match.
        """
        toolbar = self.query_one("#scripts", ScriptToolbar)
        if toolbar.run_script_by_keybinding(keybinding):
            return  # The toolbar will post ScriptRunRequested

        self.notify(f"No script bound to '{keybinding}'", severity="warning")

    async def _focus_session(self, session: ManagedSession) -> None:
        """Focus a session in iTerm2.

        Args:
            session: The session to focus.
        """
        try:
            await self.app.services.iterm.focus_session(session.id)
            self.notify(f"Focused: {session.template_id}")
        except Exception as e:
            logger.error("Failed to focus session %s: %s", session.id, e)
            self.notify("Failed to focus session", severity="error")

    async def _focus_session_by_index(self, index: int) -> None:
        """Focus a session by its 1-based index.

        Args:
            index: 1-based session index.
        """
        sessions_panel = self.query_one("#sessions", SessionsPanel)
        session = sessions_panel.select_by_index(index)
        if session:
            await self._focus_session(session)
        else:
            self.notify(f"No session at index {index}", severity="warning")

    async def _open_in_editor(self, path: Path) -> None:
        """Open a file in the configured editor.

        Args:
            path: Path to the file to open.
        """
        from iterm_controller.editors import EDITOR_COMMANDS, get_editor

        editor = get_editor()
        if editor not in EDITOR_COMMANDS:
            self.notify(f"Unknown editor: {editor}", severity="error")
            return

        import asyncio

        cmd = EDITOR_COMMANDS[editor]
        try:
            await asyncio.create_subprocess_exec(cmd, str(path))
            self.notify(f"Opening in {editor}")
        except Exception as e:
            logger.error("Failed to open editor: %s", e)
            self.notify(f"Failed to open editor: {e}", severity="error")
