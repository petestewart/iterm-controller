"""Plan state manager.

Handles PLAN.md and TEST_PLAN.md state operations including loading,
updating, and conflict notification.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from iterm_controller.models import Plan, TestPlan
from iterm_controller.state.events import (
    PlanConflict,
    PlanReloaded,
    StateEvent,
    TaskStatusChanged,
    TestPlanConflict,
    TestPlanDeleted,
    TestPlanReloaded,
    TestStepUpdated,
    WorkflowStageChanged,
)

if TYPE_CHECKING:
    from textual.app import App


class PlanStateManager:
    """Manages PLAN.md and TEST_PLAN.md state.

    Handles:
    - Storing plans by project ID
    - Notifying about plan reloads and conflicts
    - Task status change notifications
    - Workflow stage changes
    - Test plan management
    """

    def __init__(self) -> None:
        """Initialize the plan state manager."""
        self.plans: dict[str, Plan] = {}
        self.test_plans: dict[str, TestPlan] = {}
        self._app: App | None = None
        self._emit_callback: Callable[[StateEvent, dict[str, Any]], None] | None = None

    def connect_app(self, app: App) -> None:
        """Connect to a Textual App for message posting.

        Args:
            app: The Textual App instance.
        """
        self._app = app

    def set_emit_callback(
        self, callback: Callable[[StateEvent, dict[str, Any]], None]
    ) -> None:
        """Set callback for emitting events to legacy subscribers.

        Args:
            callback: Function to call with (event, kwargs) when emitting.
        """
        self._emit_callback = callback

    def _post_message(self, message: Any) -> None:
        """Post a message to the connected Textual app."""
        if self._app is not None:
            self._app.post_message(message)

    def _emit(self, event: StateEvent, **kwargs: Any) -> None:
        """Emit event to legacy subscribers."""
        if self._emit_callback:
            self._emit_callback(event, kwargs)

    # =========================================================================
    # PLAN.md Management
    # =========================================================================

    def set_plan(self, project_id: str, plan: Plan) -> None:
        """Set or update the plan for a project.

        Args:
            project_id: The project ID.
            plan: The parsed plan.
        """
        self.plans[project_id] = plan
        self._emit(StateEvent.PLAN_RELOADED, project_id=project_id, plan=plan)
        self._post_message(PlanReloaded(project_id, plan))

    def get_plan(self, project_id: str) -> Plan | None:
        """Get the plan for a project.

        Args:
            project_id: The project ID.

        Returns:
            The plan if one exists, None otherwise.
        """
        return self.plans.get(project_id)

    def notify_plan_conflict(self, project_id: str, new_plan: Plan) -> None:
        """Notify about a PLAN.md conflict.

        Args:
            project_id: The project ID.
            new_plan: The new plan from the external change.
        """
        self._emit(StateEvent.PLAN_CONFLICT, project_id=project_id, new_plan=new_plan)
        self._post_message(PlanConflict(project_id, new_plan))

    def update_task_status(self, project_id: str, task_id: str) -> None:
        """Notify about a task status change.

        Args:
            project_id: The project ID.
            task_id: The task that changed.
        """
        self._emit(StateEvent.TASK_STATUS_CHANGED, project_id=project_id, task_id=task_id)
        self._post_message(TaskStatusChanged(task_id, project_id))

    def update_workflow_stage(self, project_id: str, stage: str) -> None:
        """Notify about a workflow stage change.

        Args:
            project_id: The project ID.
            stage: The new workflow stage.
        """
        self._emit(
            StateEvent.WORKFLOW_STAGE_CHANGED,
            project_id=project_id,
            stage=stage,
        )
        self._post_message(WorkflowStageChanged(project_id, stage))

    # =========================================================================
    # TEST_PLAN.md Management
    # =========================================================================

    def set_test_plan(self, project_id: str, test_plan: TestPlan) -> None:
        """Set or update the test plan for a project.

        Args:
            project_id: The project ID.
            test_plan: The parsed test plan.
        """
        self.test_plans[project_id] = test_plan
        self._emit(StateEvent.TEST_PLAN_RELOADED, project_id=project_id, test_plan=test_plan)
        self._post_message(TestPlanReloaded(project_id, test_plan))

    def get_test_plan(self, project_id: str) -> TestPlan | None:
        """Get the test plan for a project.

        Args:
            project_id: The project ID.

        Returns:
            The test plan if one exists, None otherwise.
        """
        return self.test_plans.get(project_id)

    def clear_test_plan(self, project_id: str) -> None:
        """Clear the test plan for a project (e.g., when file is deleted).

        Args:
            project_id: The project ID.
        """
        self.test_plans.pop(project_id, None)
        self._emit(StateEvent.TEST_PLAN_DELETED, project_id=project_id)
        self._post_message(TestPlanDeleted(project_id))

    def notify_test_plan_conflict(self, project_id: str, new_plan: TestPlan) -> None:
        """Notify about a TEST_PLAN.md conflict.

        Args:
            project_id: The project ID.
            new_plan: The new plan from the external change.
        """
        self._emit(StateEvent.TEST_PLAN_CONFLICT, project_id=project_id, new_plan=new_plan)
        self._post_message(TestPlanConflict(project_id, new_plan))

    def update_test_step_status(self, project_id: str, step_id: str) -> None:
        """Notify about a test step status change.

        Args:
            project_id: The project ID.
            step_id: The step that changed.
        """
        self._emit(StateEvent.TEST_STEP_UPDATED, project_id=project_id, step_id=step_id)
        self._post_message(TestStepUpdated(project_id, step_id))
