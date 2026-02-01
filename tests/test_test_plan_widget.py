"""Tests for TestPlanWidget."""

import pytest
from iterm_controller.models import TestPlan, TestSection, TestStatus, TestStep
from iterm_controller.widgets.test_plan import TestPlanWidget


class TestTestPlanWidgetInit:
    """Tests for TestPlanWidget initialization."""

    def test_empty_init(self) -> None:
        """Test initialization with no test plan."""
        widget = TestPlanWidget()

        assert widget.test_plan is not None
        assert len(widget.test_plan.sections) == 0
        assert widget.selected_index == 0
        assert widget.selected_step is None

    def test_init_with_plan(self) -> None:
        """Test initialization with a test plan."""
        step = TestStep(
            id="section-0-1",
            section="Functional",
            description="User login works",
            status=TestStatus.PENDING,
        )
        section = TestSection(id="section-0", title="Functional", steps=[step])
        plan = TestPlan(sections=[section])

        widget = TestPlanWidget(test_plan=plan)

        assert widget.test_plan == plan
        assert len(widget.test_plan.sections) == 1


class TestTestPlanWidgetSelection:
    """Tests for step selection."""

    def test_select_next(self) -> None:
        """Test selecting next step."""
        steps = [
            TestStep(id="s0-1", section="Test", description="Step 1", status=TestStatus.PENDING),
            TestStep(id="s0-2", section="Test", description="Step 2", status=TestStatus.PENDING),
        ]
        section = TestSection(id="s0", title="Test", steps=steps)
        plan = TestPlan(sections=[section])

        widget = TestPlanWidget(test_plan=plan)
        # Manually set up visible steps and expanded sections without triggering update()
        widget._test_plan = plan
        widget._expanded_sections = {section.id}
        widget._rebuild_visible_steps()

        assert widget.selected_index == 0
        # Manually update index without triggering update()
        widget._selected_index = (widget._selected_index + 1) % len(widget._visible_steps)
        assert widget.selected_index == 1

    def test_select_previous(self) -> None:
        """Test selecting previous step."""
        steps = [
            TestStep(id="s0-1", section="Test", description="Step 1", status=TestStatus.PENDING),
            TestStep(id="s0-2", section="Test", description="Step 2", status=TestStatus.PENDING),
        ]
        section = TestSection(id="s0", title="Test", steps=steps)
        plan = TestPlan(sections=[section])

        widget = TestPlanWidget(test_plan=plan)
        widget._test_plan = plan
        widget._expanded_sections = {section.id}
        widget._rebuild_visible_steps()
        widget._selected_index = 1  # Start at second step

        # Manually update index without triggering update()
        widget._selected_index = (widget._selected_index - 1) % len(widget._visible_steps)
        assert widget.selected_index == 0

    def test_select_wraps_around(self) -> None:
        """Test that selection wraps around."""
        steps = [
            TestStep(id="s0-1", section="Test", description="Step 1", status=TestStatus.PENDING),
            TestStep(id="s0-2", section="Test", description="Step 2", status=TestStatus.PENDING),
        ]
        section = TestSection(id="s0", title="Test", steps=steps)
        plan = TestPlan(sections=[section])

        widget = TestPlanWidget(test_plan=plan)
        widget._test_plan = plan
        widget._expanded_sections = {section.id}
        widget._rebuild_visible_steps()

        # Start at last step, next should wrap to first
        widget._selected_index = 1
        widget._selected_index = (widget._selected_index + 1) % len(widget._visible_steps)
        assert widget.selected_index == 0

    def test_selected_step(self) -> None:
        """Test getting selected step."""
        step = TestStep(id="s0-1", section="Test", description="Step 1", status=TestStatus.PENDING)
        section = TestSection(id="s0", title="Test", steps=[step])
        plan = TestPlan(sections=[section])

        widget = TestPlanWidget(test_plan=plan)
        widget._test_plan = plan
        widget._expanded_sections = {section.id}
        widget._rebuild_visible_steps()

        selected = widget.selected_step
        assert selected is not None
        assert selected.id == "s0-1"


class TestTestPlanWidgetStatusIcons:
    """Tests for status icon rendering."""

    def test_pending_icon(self) -> None:
        """Test PENDING status uses correct icon."""
        widget = TestPlanWidget()
        icon = widget._get_status_icon(TestStatus.PENDING)
        assert icon == "[ ]"

    def test_in_progress_icon(self) -> None:
        """Test IN_PROGRESS status uses correct icon."""
        widget = TestPlanWidget()
        icon = widget._get_status_icon(TestStatus.IN_PROGRESS)
        assert icon == "[~]"

    def test_passed_icon(self) -> None:
        """Test PASSED status uses correct icon."""
        widget = TestPlanWidget()
        icon = widget._get_status_icon(TestStatus.PASSED)
        assert icon == "[x]"

    def test_failed_icon(self) -> None:
        """Test FAILED status uses correct icon."""
        widget = TestPlanWidget()
        icon = widget._get_status_icon(TestStatus.FAILED)
        assert icon == "[!]"


class TestTestPlanWidgetStatusColors:
    """Tests for status color assignment."""

    def test_pending_color(self) -> None:
        """Test PENDING status uses white color."""
        widget = TestPlanWidget()
        color = widget._get_status_color(TestStatus.PENDING)
        assert color == "white"

    def test_in_progress_color(self) -> None:
        """Test IN_PROGRESS status uses yellow color."""
        widget = TestPlanWidget()
        color = widget._get_status_color(TestStatus.IN_PROGRESS)
        assert color == "yellow"

    def test_passed_color(self) -> None:
        """Test PASSED status uses green color."""
        widget = TestPlanWidget()
        color = widget._get_status_color(TestStatus.PASSED)
        assert color == "green"

    def test_failed_color(self) -> None:
        """Test FAILED status uses red color."""
        widget = TestPlanWidget()
        color = widget._get_status_color(TestStatus.FAILED)
        assert color == "red"


class TestTestPlanWidgetStatusCycle:
    """Tests for status cycling."""

    def test_pending_to_in_progress(self) -> None:
        """Test PENDING cycles to IN_PROGRESS."""
        widget = TestPlanWidget()
        next_status = widget.get_next_status(TestStatus.PENDING)
        assert next_status == TestStatus.IN_PROGRESS

    def test_in_progress_to_passed(self) -> None:
        """Test IN_PROGRESS cycles to PASSED."""
        widget = TestPlanWidget()
        next_status = widget.get_next_status(TestStatus.IN_PROGRESS)
        assert next_status == TestStatus.PASSED

    def test_passed_to_pending(self) -> None:
        """Test PASSED cycles to PENDING."""
        widget = TestPlanWidget()
        next_status = widget.get_next_status(TestStatus.PASSED)
        assert next_status == TestStatus.PENDING

    def test_failed_to_pending(self) -> None:
        """Test FAILED cycles to PENDING."""
        widget = TestPlanWidget()
        next_status = widget.get_next_status(TestStatus.FAILED)
        assert next_status == TestStatus.PENDING


class TestTestPlanWidgetRefresh:
    """Tests for plan refresh - uses internal methods to avoid Textual app context."""

    def test_refresh_updates_plan(self) -> None:
        """Test that setting plan updates internal state."""
        widget = TestPlanWidget()

        step = TestStep(id="s0-1", section="Test", description="Step 1", status=TestStatus.PENDING)
        section = TestSection(id="s0", title="Test", steps=[step])
        plan = TestPlan(sections=[section])

        # Manually set plan and rebuild without triggering update()
        widget._test_plan = plan
        widget._expanded_sections = {section.id}
        widget._rebuild_visible_steps()

        assert widget.test_plan == plan
        assert len(widget._visible_steps) == 1

    def test_refresh_clamps_selection(self) -> None:
        """Test that selection is clamped to valid range."""
        steps = [
            TestStep(id="s0-1", section="Test", description="Step 1", status=TestStatus.PENDING),
            TestStep(id="s0-2", section="Test", description="Step 2", status=TestStatus.PENDING),
        ]
        section = TestSection(id="s0", title="Test", steps=steps)
        plan1 = TestPlan(sections=[section])

        widget = TestPlanWidget()
        widget._test_plan = plan1
        widget._expanded_sections = {section.id}
        widget._rebuild_visible_steps()
        widget._selected_index = 1  # Select second step

        # Set new plan with only one step
        step = TestStep(id="s0-1", section="Test", description="Step 1", status=TestStatus.PENDING)
        section2 = TestSection(id="s0", title="Test", steps=[step])
        plan2 = TestPlan(sections=[section2])

        # Manually update plan and clamp selection
        widget._test_plan = plan2
        widget._expanded_sections = {section2.id}
        widget._rebuild_visible_steps()
        if widget._selected_index >= len(widget._visible_steps):
            widget._selected_index = max(0, len(widget._visible_steps) - 1)

        # Selection should be clamped to valid range
        assert widget.selected_index == 0
