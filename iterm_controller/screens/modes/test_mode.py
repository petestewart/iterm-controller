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
    AttentionState,
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
from iterm_controller.test_output_parser import UnitTestResults, parse_test_output
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
        # Track test runner sessions to capture their output
        self._test_runner_session_id: str | None = None
        self._test_runner_output: str = ""
        self._unit_test_results: UnitTestResults | None = None

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

        # Also update with any stored results
        if self._unit_test_results:
            unit_tests.refresh_results(self._unit_test_results)

        # Update session list
        if sessions is not None:
            session_widget = self.query_one("#sessions", SessionListWidget)
            session_widget.refresh_sessions(sessions)

        self._update_progress_bar()

    def _update_progress_bar(self) -> None:
        """Update the progress bar text."""
        progress_parts = []

        # TEST_PLAN.md progress
        if self._test_plan:
            summary = self._test_plan.summary
            total = len(self._test_plan.all_steps)
            if total > 0:
                passed = summary.get("passed", 0)
                failed = summary.get("failed", 0)
                percent = (passed / total) * 100
                progress_parts.append(
                    f"TEST_PLAN: {passed}/{total} ({percent:.0f}%)"
                )

        # Unit test results
        if self._unit_test_results and self._unit_test_results.last_run:
            results = self._unit_test_results
            unit_total = results.passed + results.failed + results.skipped
            if unit_total > 0:
                progress_parts.append(
                    f"Unit: {results.passed}/{unit_total} passed"
                )
                if results.failed > 0:
                    progress_parts.append(f"{results.failed} failed")
        elif self._test_runner_session_id:
            progress_parts.append("Unit: Running...")

        # Join parts
        if progress_parts:
            progress_text = "  |  ".join(progress_parts)
        else:
            progress_text = "No test data"

        progress_bar = self.query_one("#progress-bar", Static)
        progress_bar.update(progress_text)

    def _detect_test_command(self) -> str:
        """Detect the test command for this project.

        Uses content-aware detection to check if project files actually
        indicate test support (e.g., [tool.pytest] in pyproject.toml,
        "test" script in package.json, test target in Makefile).

        Respects project config override via test_command in
        .iterm-controller.json.

        Returns:
            The detected test command, or empty string if none found.
        """
        from iterm_controller.config import load_project_config
        from iterm_controller.test_command_detector import TestCommandDetector

        # Load project-local config for potential overrides
        project_config = load_project_config(self.project.path)

        detector = TestCommandDetector(self.project.path)
        result = detector.detect(project_config)
        return result.test_command

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

        Uses content-aware detection and respects project config override
        via test_watch_command in .iterm-controller.json.

        Returns:
            Watch command, or empty string if none detected.
        """
        from iterm_controller.config import load_project_config
        from iterm_controller.test_command_detector import TestCommandDetector

        # Load project-local config for potential overrides
        project_config = load_project_config(self.project.path)

        detector = TestCommandDetector(self.project.path)
        result = detector.detect(project_config)
        return result.watch_command

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

        # Set running state and reset output tracking
        unit_tests = self.query_one("#unit-tests", UnitTestWidget)
        unit_tests.set_running(True)
        self._test_runner_output = ""

        # Spawn session with test command and track it
        self._spawn_test_runner_session(command)
        self.notify(f"Running: {command}")

    def _spawn_test_runner_session(self, command: str) -> None:
        """Spawn a test runner session and track it for output capture.

        Args:
            command: The test command to run.
        """
        app: ItermControllerApp = self.app  # type: ignore[assignment]

        async def _do_spawn() -> None:
            try:
                from iterm_controller.iterm_api import SessionSpawner

                # Create a temporary template for the test runner session
                template = SessionTemplate(
                    id="test-runner",
                    name="Test Runner",
                    command=command,
                    env={},
                )

                spawner = SessionSpawner(app.iterm)
                result = await spawner.spawn_session(template, self.project)

                if result.success:
                    # Track this as our test runner session
                    self._test_runner_session_id = result.session_id

                    # Get the managed session
                    managed = spawner.get_session(result.session_id)
                    if managed:
                        managed.metadata["test_runner"] = "true"
                        managed.metadata["test_command"] = command
                        app.state.add_session(managed)

                    await self._load_data()
                else:
                    self.notify(f"Failed to spawn session: {result.error}", severity="error")
                    self._reset_test_runner_state()

            except Exception as e:
                logger.exception("Error spawning test runner session")
                self.notify(f"Error spawning session: {e}", severity="error")
                self._reset_test_runner_state()

        self.call_later(_do_spawn)

    def _reset_test_runner_state(self) -> None:
        """Reset test runner tracking state."""
        self._test_runner_session_id = None
        self._test_runner_output = ""
        unit_tests = self.query_one("#unit-tests", UnitTestWidget)
        unit_tests.set_running(False)

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
            # Check if this was the test runner session
            if event.session.id == self._test_runner_session_id:
                self._on_test_runner_completed(event.session)
            self._on_session_changed(event.session)

    def on_session_status_changed(self, event: SessionStatusChanged) -> None:
        """Handle session status changed event.

        Args:
            event: The session status changed event.
        """
        # Only refresh if this session is for our project
        if event.session.project_id == self.project.id:
            # Check if this is the test runner session and capture its output
            if event.session.id == self._test_runner_session_id:
                self._capture_test_runner_output(event.session)

                # If session becomes IDLE, tests may have completed
                if event.session.attention_state == AttentionState.IDLE:
                    self._on_test_runner_completed(event.session)

            self._on_session_changed(event.session)

    def _capture_test_runner_output(self, session: ManagedSession) -> None:
        """Capture output from the test runner session.

        Args:
            session: The test runner session.
        """
        if session.last_output:
            # Accumulate output
            if session.last_output not in self._test_runner_output:
                self._test_runner_output += session.last_output

    def _on_test_runner_completed(self, session: ManagedSession) -> None:
        """Handle test runner completion - parse output and update UI.

        Args:
            session: The completed test runner session.
        """
        # Get full output from the session
        if session.last_output:
            self._test_runner_output = session.last_output

        # Parse the test output
        test_command = session.metadata.get("test_command", self._test_command)
        results = parse_test_output(self._test_runner_output, test_command)
        self._unit_test_results = results

        # Update the widget
        unit_tests = self.query_one("#unit-tests", UnitTestWidget)
        unit_tests.refresh_results(results)

        # Clear tracking state
        self._test_runner_session_id = None

        # Notify user of results
        if results.failed > 0:
            self.notify(
                f"Tests complete: {results.passed} passed, {results.failed} failed",
                severity="warning"
            )
        else:
            self.notify(
                f"Tests complete: {results.passed} passed",
                severity="information"
            )

        logger.info(
            f"Test run complete: {results.passed} passed, {results.failed} failed, "
            f"{results.skipped} skipped in {results.duration_seconds:.2f}s"
        )

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
