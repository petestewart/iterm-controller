"""Test plan widget for Test Mode.

Displays TEST_PLAN.md steps with status indicators and selection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.binding import Binding
from textual.widgets import Static

from iterm_controller.models import TestPlan, TestSection, TestStatus, TestStep

if TYPE_CHECKING:
    pass


class TestPlanWidget(Static, can_focus=True):
    """Displays TEST_PLAN.md test steps with status indicators.

    Shows test sections with steps and their statuses:
    - [ ] Pending: Not yet tested
    - [~] In Progress: Currently being verified
    - [x] Passed: Verification succeeded
    - [!] Failed: Verification failed (with notes)

    Layout:
        ▼ Functional Tests    3/5
          [x] User login works
          [x] Error on bad password
          [~] Session persistence
          [ ] Password reset flow
          [!] OAuth integration
              Note: OAuth callback URL mismatch

        ▼ UI Tests            0/3
          [ ] Button colors match
          [ ] Responsive on mobile
          [ ] Accessibility check
    """

    DEFAULT_CSS = """
    TestPlanWidget {
        height: 1fr;
        padding: 0 1;
        border: solid $surface-lighten-2;
    }

    TestPlanWidget:focus {
        border: solid $accent;
    }
    """

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("up", "cursor_up", "Up", show=False),
    ]

    # Status icons matching TEST_PLAN.md markers
    STATUS_ICONS = {
        TestStatus.PENDING: "[ ]",
        TestStatus.IN_PROGRESS: "[~]",
        TestStatus.PASSED: "[x]",
        TestStatus.FAILED: "[!]",
    }

    # Status colors
    STATUS_COLORS = {
        TestStatus.PENDING: "white",
        TestStatus.IN_PROGRESS: "yellow",
        TestStatus.PASSED: "green",
        TestStatus.FAILED: "red",
    }

    def __init__(
        self,
        test_plan: TestPlan | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the test plan widget.

        Args:
            test_plan: Initial test plan to display.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self._test_plan = test_plan or TestPlan()
        self._selected_index: int = 0
        self._visible_steps: list[TestStep] = []
        self._expanded_sections: set[str] = set()
        self._rebuild_visible_steps()

    @property
    def test_plan(self) -> TestPlan:
        """Get the current test plan."""
        return self._test_plan

    @property
    def selected_step(self) -> TestStep | None:
        """Get the currently selected step."""
        if 0 <= self._selected_index < len(self._visible_steps):
            return self._visible_steps[self._selected_index]
        return None

    @property
    def selected_index(self) -> int:
        """Get the current selection index."""
        return self._selected_index

    def refresh_plan(self, test_plan: TestPlan) -> None:
        """Update the displayed test plan.

        Args:
            test_plan: New test plan to display.
        """
        self._test_plan = test_plan
        # Auto-expand all sections initially
        self._expanded_sections = {s.id for s in test_plan.sections}
        self._rebuild_visible_steps()
        # Ensure selected index is valid
        if self._selected_index >= len(self._visible_steps):
            self._selected_index = max(0, len(self._visible_steps) - 1)
        self.update(self._render_plan())

    def _rebuild_visible_steps(self) -> None:
        """Rebuild the list of visible steps from expanded sections."""
        self._visible_steps = []
        for section in self._test_plan.sections:
            if section.id in self._expanded_sections:
                self._visible_steps.extend(section.steps)

    def toggle_section(self, section_id: str) -> None:
        """Toggle section expansion.

        Args:
            section_id: The section ID to toggle.
        """
        if section_id in self._expanded_sections:
            self._expanded_sections.discard(section_id)
        else:
            self._expanded_sections.add(section_id)
        self._rebuild_visible_steps()
        self.update(self._render_plan())

    def select_next(self) -> None:
        """Select the next step."""
        if self._visible_steps:
            self._selected_index = (self._selected_index + 1) % len(self._visible_steps)
            self.update(self._render_plan())

    def select_previous(self) -> None:
        """Select the previous step."""
        if self._visible_steps:
            self._selected_index = (self._selected_index - 1) % len(self._visible_steps)
            self.update(self._render_plan())

    def action_cursor_down(self) -> None:
        """Handle down arrow key."""
        self.select_next()

    def action_cursor_up(self) -> None:
        """Handle up arrow key."""
        self.select_previous()

    def _get_status_icon(self, status: TestStatus) -> str:
        """Get the icon for a given test status.

        Args:
            status: The test status.

        Returns:
            String icon representing the status.
        """
        return self.STATUS_ICONS.get(status, "[ ]")

    def _get_status_color(self, status: TestStatus) -> str:
        """Get the color for a given test status.

        Args:
            status: The test status.

        Returns:
            Color name for Rich markup.
        """
        return self.STATUS_COLORS.get(status, "white")

    def _render_step(self, step: TestStep, is_selected: bool) -> Text:
        """Render a single test step row.

        Args:
            step: The step to render.
            is_selected: Whether this step is currently selected.

        Returns:
            Rich Text object for the step row.
        """
        icon = self._get_status_icon(step.status)
        color = self._get_status_color(step.status)

        text = Text()

        # Selection indicator
        if is_selected:
            text.append("  ▸ ", style="bold cyan")
        else:
            text.append("    ")

        # Status icon with color
        text.append(f"{icon} ", style=color)

        # Description with appropriate styling
        if step.status == TestStatus.FAILED:
            text.append(step.description, style="red")
        elif step.status == TestStatus.PASSED:
            text.append(step.description, style="green")
        elif step.status == TestStatus.IN_PROGRESS:
            text.append(step.description, style="yellow")
        else:
            text.append(step.description)

        return text

    def _render_section(self, section: TestSection) -> Text:
        """Render a section header.

        Args:
            section: The section to render.

        Returns:
            Rich Text object for the section header.
        """
        is_expanded = section.id in self._expanded_sections
        passed, total = section.completion_count

        text = Text()

        # Expansion indicator
        if is_expanded:
            text.append("▼ ", style="bold")
        else:
            text.append("▶ ", style="bold")

        # Section title
        text.append(section.title, style="bold")

        # Progress count
        text.append(f"  {passed}/{total}", style="dim")

        # Failed indicator
        if section.has_failures:
            text.append(" !", style="red bold")

        return text

    def _render_plan(self) -> Text:
        """Render the complete test plan.

        Returns:
            Rich Text object containing the plan header and steps.
        """
        text = Text()

        # Header with progress
        summary = self._test_plan.summary
        total = len(self._test_plan.all_steps)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        in_progress = summary.get("in_progress", 0)

        text.append("TEST_PLAN.md", style="bold")
        if total > 0:
            percent = (passed / total) * 100
            text.append(f"  {percent:.0f}%", style="dim")
        text.append("\n")

        # Progress summary
        text.append(f"{passed} passed", style="green")
        text.append("  |  ", style="dim")
        text.append(f"{in_progress} in progress", style="yellow")
        text.append("  |  ", style="dim")
        text.append(f"{failed} failed", style="red")
        text.append("\n\n")

        if not self._test_plan.sections:
            text.append("No test plan found", style="dim italic")
            return text

        # Render sections and steps
        step_index = 0
        for section in self._test_plan.sections:
            text.append_text(self._render_section(section))
            text.append("\n")

            if section.id in self._expanded_sections:
                for step in section.steps:
                    is_selected = step_index == self._selected_index
                    text.append_text(self._render_step(step, is_selected))
                    text.append("\n")

                    # Add notes if present (for failed steps)
                    if step.notes:
                        text.append(f"        Note: {step.notes}\n", style="dim italic")

                    step_index += 1

            text.append("\n")

        return text

    def render(self) -> Text:
        """Render the widget content.

        Returns:
            Rich Text object to display.
        """
        return self._render_plan()

    def get_next_status(self, current: TestStatus) -> TestStatus:
        """Get the next status in the cycle.

        Cycle: pending → in_progress → passed → pending
        For failed, cycles to pending.

        Args:
            current: The current status.

        Returns:
            The next status in the cycle.
        """
        cycle = {
            TestStatus.PENDING: TestStatus.IN_PROGRESS,
            TestStatus.IN_PROGRESS: TestStatus.PASSED,
            TestStatus.PASSED: TestStatus.PENDING,
            TestStatus.FAILED: TestStatus.PENDING,
        }
        return cycle.get(current, TestStatus.PENDING)
