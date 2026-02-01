"""Test Mode screen.

QA testing via TEST_PLAN.md checklist and unit test runner.

See specs/test-mode.md for full specification.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from iterm_controller.models import (
    ManagedSession,
    SessionTemplate,
    TestPlan,
    TestStatus,
    TestStep,
    WorkflowMode,
)
from iterm_controller.screens.mode_screen import ModeScreen
from iterm_controller.state import (
    SessionClosed,
    SessionSpawned,
    SessionStatusChanged,
)
from iterm_controller.widgets.session_list import SessionListWidget
from iterm_controller.widgets.test_plan import TestPlanWidget
from iterm_controller.widgets.unit_tests import UnitTestWidget

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp
    from iterm_controller.models import Project
    from iterm_controller.test_plan_watcher import TestPlanWatcher

logger = logging.getLogger(__name__)


class TestModeScreen(ModeScreen):
    """Test Mode screen for QA testing and unit tests.

    This screen displays:
    - TEST_PLAN.md steps with status indicators
    - Unit test runner results
    - QA session status

    Users can toggle test steps, run unit tests, and spawn QA sessions.

    Layout:
        ┌─────────────────────────────┬──────────────────────────────┐
        │ TEST_PLAN.md        Progress│ Unit Tests                   │
        │                             │                              │
        │ ▼ Functional Tests    3/5   │ Last run: 2 min ago          │
        │   [x] User login works      │ Status: ✓ 42 passed          │
        │   [x] Error on bad password │         ✗ 2 failed           │
        │   [~] Session persistence   │         ○ 1 skipped          │
        │   [ ] Password reset flow   │                              │
        │   [ ] OAuth integration     │ Failed:                      │
        │                             │   test_auth.py::test_timeout │
        │ ▼ UI Tests            0/3   │   test_api.py::test_rate_lim │
        │   [ ] Button colors match   │                              │
        │   [ ] Responsive on mobile  │                              │
        │   [ ] Accessibility check   │                              │
        └─────────────────────────────┴──────────────────────────────┘
        │ QA Session                                                   │
        │ ⧖ qa-agent    Verifying step 3    Waiting                   │
        └──────────────────────────────────────────────────────────────┘
    """

    CURRENT_MODE = WorkflowMode.TEST

    BINDINGS = [
        *ModeScreen.BINDINGS,
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("tab", "switch_panel", "Switch Panel"),
        Binding("enter", "toggle_step", "Toggle"),
        Binding("g", "generate_plan", "Generate"),
        Binding("s", "spawn_qa", "Spawn QA"),
        Binding("r", "run_tests", "Run"),
        Binding("w", "watch_tests", "Watch"),
        Binding("f", "run_failed", "Failed"),
        Binding("x", "refresh", "Refresh"),
    ]

    DEFAULT_CSS = """
    TestModeScreen {
        layout: vertical;
    }

    TestModeScreen #main {
        height: 1fr;
        padding: 1;
    }

    TestModeScreen #panels {
        height: 1fr;
    }

    TestModeScreen #left-panel {
        width: 1fr;
        height: 1fr;
        padding-right: 1;
    }

    TestModeScreen #right-panel {
        width: 1fr;
        height: 1fr;
    }

    TestModeScreen #test-plan {
        height: 1fr;
    }

    TestModeScreen #unit-tests {
        height: 1fr;
    }

    TestModeScreen #sessions-container {
        dock: bottom;
        height: auto;
        min-height: 5;
        max-height: 10;
        padding-top: 1;
    }

    TestModeScreen #sessions-title {
        text-style: bold;
        padding-bottom: 0;
    }

    TestModeScreen #progress-bar {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $surface;
    }

    TestModeScreen SessionListWidget {
        height: auto;
        min-height: 3;
    }
    """

    # Track which panel is focused: "plan" or "tests"
    _active_panel: str = "plan"

    def __init__(self, project: Project) -> None:
        """Initialize the Test Mode screen.

        Args:
            project: The project to display.
        """
        super().__init__(project)
        self._test_plan: TestPlan | None = None
        self._test_plan_watcher: TestPlanWatcher | None = None
        self._sessions: dict[str, ManagedSession] = {}
        self._test_command: str = ""

    def compose(self) -> ComposeResult:
        """Compose the screen layout."""
        yield Header()
        yield Container(
            Horizontal(
                Vertical(
                    TestPlanWidget(id="test-plan"),
                    id="left-panel",
                ),
                Vertical(
                    UnitTestWidget(id="unit-tests"),
                    id="right-panel",
                ),
                id="panels",
            ),
            Vertical(
                Static("QA Session", id="sessions-title"),
                SessionListWidget(show_project=False, id="sessions"),
                id="sessions-container",
            ),
            Static(id="progress-bar"),
            id="main",
        )
        yield Footer()

    async def on_mount(self) -> None:
        """Load data when screen mounts."""
        await super().on_mount()
        await self._load_data()
        self._update_progress_bar()
        # Focus the test plan by default
        self.query_one("#test-plan", TestPlanWidget).focus()

    async def _load_data(self) -> None:
        """Load test plan and session data."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Load test plan from project
        test_plan_path = self.project.full_test_plan_path

        if test_plan_path.exists():
            from iterm_controller.test_plan_parser import TestPlanParser

            parser = TestPlanParser()
            self._test_plan = parser.parse_file(test_plan_path)
        else:
            self._test_plan = TestPlan(path=str(test_plan_path))

        # Set up watcher for test plan changes
        await self._setup_watcher()

        # Build session lookup
        self._sessions = {}
        for session in app.state.sessions.values():
            self._sessions[session.id] = session

        # Filter sessions for this project that are QA-related
        project_sessions = [
            s
            for s in app.state.sessions.values()
            if s.project_id == self.project.id
            and ("qa" in s.template_id.lower() or "test" in s.template_id.lower())
        ]

        # Detect test command
        self._test_command = self._detect_test_command()

        # Update widgets
        self._refresh_widgets(project_sessions)

    async def _setup_watcher(self) -> None:
        """Set up the test plan file watcher."""
        from iterm_controller.test_plan_watcher import TestPlanWatcher

        test_plan_path = self.project.full_test_plan_path

        self._test_plan_watcher = TestPlanWatcher(
            test_plan=self._test_plan,
            plan_path=test_plan_path,
        )

        # Set up callbacks
        self._test_plan_watcher.on_plan_reloaded = self._on_plan_reloaded
        self._test_plan_watcher.on_conflict_detected = self._on_conflict_detected
        self._test_plan_watcher.on_plan_deleted = self._on_plan_deleted

        # Start watching if file exists
        if test_plan_path.exists():
            await self._test_plan_watcher.start_watching(
                test_plan_path, self._test_plan
            )

    def _on_plan_reloaded(self, plan: TestPlan) -> None:
        """Handle test plan reload.

        Args:
            plan: The reloaded test plan.
        """
        self._test_plan = plan
        self._refresh_widgets()
        self._update_progress_bar()

    def _on_conflict_detected(
        self, new_plan: TestPlan, changes: list
    ) -> None:
        """Handle test plan conflict detection.

        Args:
            new_plan: The new test plan from disk.
            changes: List of detected changes.
        """
        # For now, auto-accept external changes
        # TODO: Show conflict resolution modal
        self._test_plan = new_plan
        self._refresh_widgets()
        self._update_progress_bar()
        self.notify("TEST_PLAN.md updated externally")

    def _on_plan_deleted(self) -> None:
        """Handle test plan deletion."""
        self._test_plan = TestPlan()
        self._refresh_widgets()
        self._update_progress_bar()
        self.notify("TEST_PLAN.md was deleted", severity="warning")

    def _refresh_widgets(self, sessions: list[ManagedSession] | None = None) -> None:
        """Refresh all widgets with current data.

        Args:
            sessions: Optional list of sessions to display.
        """
        if self._test_plan:
            # Update test plan widget
            plan_widget = self.query_one("#test-plan", TestPlanWidget)
            plan_widget.refresh_plan(self._test_plan)

        # Update unit test widget
        unit_tests = self.query_one("#unit-tests", UnitTestWidget)
        unit_tests.set_test_command(self._test_command)

        # Update session list
        if sessions is not None:
            session_widget = self.query_one("#sessions", SessionListWidget)
            session_widget.refresh_sessions(sessions)

        self._update_progress_bar()

    def _update_progress_bar(self) -> None:
        """Update the progress bar text."""
        if not self._test_plan:
            return

        summary = self._test_plan.summary
        total = len(self._test_plan.all_steps)
        if total == 0:
            progress_bar = self.query_one("#progress-bar", Static)
            progress_bar.update("No test steps defined")
            return

        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        in_progress = summary.get("in_progress", 0)
        pending = summary.get("pending", 0)

        percent = (passed / total) * 100

        progress_text = (
            f"TEST_PLAN: {passed}/{total} passed ({percent:.0f}%)  |  "
            f"{in_progress} in progress  |  {failed} failed  |  {pending} pending"
        )

        progress_bar = self.query_one("#progress-bar", Static)
        progress_bar.update(progress_text)

    def _detect_test_command(self) -> str:
        """Detect the test command for this project.

        Returns:
            The detected test command, or empty string if none found.
        """
        from pathlib import Path

        project_path = Path(self.project.path)

        # Detection order from spec
        detection_order = [
            ("pytest.ini", "pytest"),
            ("pyproject.toml", "pytest"),  # Check for [tool.pytest]
            ("package.json", "npm test"),  # Check for "test" script
            ("Makefile", "make test"),  # Check for test target
            ("Cargo.toml", "cargo test"),
            ("go.mod", "go test ./..."),
        ]

        for filename, command in detection_order:
            if (project_path / filename).exists():
                return command

        return ""

    # =========================================================================
    # Panel Navigation
    # =========================================================================

    def action_switch_panel(self) -> None:
        """Switch focus between test plan and unit tests panels."""
        if self._active_panel == "plan":
            self._active_panel = "tests"
            self.query_one("#unit-tests", UnitTestWidget).focus()
        else:
            self._active_panel = "plan"
            self.query_one("#test-plan", TestPlanWidget).focus()

    def action_cursor_down(self) -> None:
        """Move cursor down in test plan."""
        if self._active_panel == "plan":
            plan_widget = self.query_one("#test-plan", TestPlanWidget)
            plan_widget.select_next()

    def action_cursor_up(self) -> None:
        """Move cursor up in test plan."""
        if self._active_panel == "plan":
            plan_widget = self.query_one("#test-plan", TestPlanWidget)
            plan_widget.select_previous()

    # =========================================================================
    # Test Step Actions
    # =========================================================================

    async def action_toggle_step(self) -> None:
        """Toggle the selected test step status."""
        plan_widget = self.query_one("#test-plan", TestPlanWidget)
        step = plan_widget.selected_step

        if not step:
            self.notify("No step selected", severity="warning")
            return

        # Get next status
        next_status = plan_widget.get_next_status(step.status)

        # Update in watcher (which writes to file)
        if self._test_plan_watcher:
            step.status = next_status
            await self._test_plan_watcher.update_step(step)
            self.notify(f"Step → {next_status.value}")

            # Reload and refresh
            await self._load_data()

    def action_generate_plan(self) -> None:
        """Generate TEST_PLAN.md from PRD/specs."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Check if connected to iTerm2
        if not app.iterm.is_connected:
            self.notify("Not connected to iTerm2", severity="error")
            return

        # Spawn a session to generate the test plan
        command = "claude /qa --generate"
        self._spawn_qa_session("qa-generator", command)
        self.notify("Generating TEST_PLAN.md...")

    def action_spawn_qa(self) -> None:
        """Spawn a QA agent session to execute the test plan."""
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Check if connected to iTerm2
        if not app.iterm.is_connected:
            self.notify("Not connected to iTerm2", severity="error")
            return

        # Check if test plan exists
        test_plan_path = self.project.full_test_plan_path
        if not test_plan_path.exists():
            self.notify("No TEST_PLAN.md found. Press 'g' to generate.", severity="warning")
            return

        # Spawn QA session
        command = f"claude /qa --execute {test_plan_path}"
        self._spawn_qa_session("qa-agent", command)
        self.notify("Spawning QA agent session...")

    def _spawn_qa_session(self, template_id: str, command: str) -> None:
        """Spawn a QA session with the given command.

        Args:
            template_id: The template ID for the session.
            command: The command to run.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        async def _do_spawn() -> None:
            try:
                from iterm_controller.iterm_api import SessionSpawner

                # Create a temporary template for the QA session
                template = SessionTemplate(
                    id=template_id,
                    name=template_id.replace("-", " ").title(),
                    command=command,
                    env={},
                )

                spawner = SessionSpawner(app.iterm)
                result = await spawner.spawn_session(template, self.project)

                if result.success:
                    # Get the managed session
                    managed = spawner.get_session(result.session_id)
                    if managed:
                        managed.metadata["test_plan_path"] = str(
                            self.project.full_test_plan_path
                        )
                        app.state.add_session(managed)

                    await self._load_data()
                else:
                    self.notify(f"Failed to spawn session: {result.error}", severity="error")

            except Exception as e:
                logger.exception("Error spawning QA session")
                self.notify(f"Error spawning session: {e}", severity="error")

        self.call_later(_do_spawn)

    # =========================================================================
    # Unit Test Actions
    # =========================================================================

    def action_run_tests(self) -> None:
        """Run unit tests."""
        if not self._test_command:
            self.notify("No test command detected", severity="warning")
            return

        self._run_test_command(self._test_command)

    def action_watch_tests(self) -> None:
        """Start test watch mode."""
        # Try to detect watch command
        watch_cmd = self._detect_watch_command()
        if not watch_cmd:
            self.notify("No watch command available", severity="warning")
            return

        self._run_test_command(watch_cmd)

    def action_run_failed(self) -> None:
        """Run only failed tests."""
        if not self._test_command:
            self.notify("No test command detected", severity="warning")
            return

        # Modify command to run only failed tests
        if "pytest" in self._test_command:
            cmd = f"{self._test_command} --lf"
        elif "npm" in self._test_command:
            cmd = f"{self._test_command} -- --onlyChanged"
        else:
            cmd = self._test_command

        self._run_test_command(cmd)

    def _detect_watch_command(self) -> str:
        """Detect the test watch command.

        Returns:
            Watch command, or empty string if none detected.
        """
        if "pytest" in self._test_command:
            return "pytest-watch"
        elif "npm" in self._test_command:
            return "npm test -- --watch"
        elif "cargo" in self._test_command:
            return "cargo watch -x test"
        return ""

    def _run_test_command(self, command: str) -> None:
        """Run a test command in a new session.

        Args:
            command: The test command to run.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Check if connected to iTerm2
        if not app.iterm.is_connected:
            self.notify("Not connected to iTerm2", severity="error")
            return

        # Set running state
        unit_tests = self.query_one("#unit-tests", UnitTestWidget)
        unit_tests.set_running(True)

        # Spawn session with test command
        self._spawn_qa_session("test-runner", command)
        self.notify(f"Running: {command}")

    def action_refresh(self) -> None:
        """Refresh all data."""

        async def _do_refresh() -> None:
            await self._load_data()
            self.notify("Refreshed")

        self.call_later(_do_refresh)

    # =========================================================================
    # Session Event Handlers
    # =========================================================================

    def on_session_spawned(self, event: SessionSpawned) -> None:
        """Handle session spawned event.

        Args:
            event: The session spawned event.
        """
        # Only refresh if this session is for our project
        if event.session.project_id == self.project.id:
            self._on_session_changed(event.session)

    def on_session_closed(self, event: SessionClosed) -> None:
        """Handle session closed event.

        Args:
            event: The session closed event.
        """
        # Only refresh if this session was for our project
        if event.session.project_id == self.project.id:
            self._on_session_changed(event.session)

    def on_session_status_changed(self, event: SessionStatusChanged) -> None:
        """Handle session status changed event.

        Args:
            event: The session status changed event.
        """
        # Only refresh if this session is for our project
        if event.session.project_id == self.project.id:
            self._on_session_changed(event.session)

    def _on_session_changed(self, session: ManagedSession) -> None:
        """Update display when a session changes.

        Args:
            session: The session that changed.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        # Rebuild session lookup with current state
        self._sessions = {}
        for s in app.state.sessions.values():
            self._sessions[s.id] = s

        # Get QA-related project sessions
        project_sessions = [
            s
            for s in app.state.sessions.values()
            if s.project_id == self.project.id
            and ("qa" in s.template_id.lower() or "test" in s.template_id.lower())
        ]

        # Update widgets
        self._refresh_widgets(project_sessions)

    async def on_unmount(self) -> None:
        """Clean up when screen unmounts."""
        if self._test_plan_watcher:
            await self._test_plan_watcher.stop_watching()
