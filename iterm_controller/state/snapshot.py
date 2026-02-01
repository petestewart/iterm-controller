"""Immutable state snapshot for external observation.

This module provides a read-only view of the application state suitable
for agents, CLI tools, and external integrations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from iterm_controller.models import (
        AppConfig,
        HealthStatus,
        ManagedSession,
        Plan,
        Project,
        TestPlan,
    )


@dataclass
class StateSnapshot:
    """Immutable snapshot of application state for external observation.

    This dataclass provides a read-only view of the current application state
    suitable for agents, CLI tools, and external integrations that need to
    query state without interacting with the TUI.

    Example:
        from iterm_controller.state import AppState

        state = AppState()
        await state.load_config()
        snapshot = state.to_snapshot()

        # Query state
        print(f"Projects: {len(snapshot.projects)}")
        print(f"Active project: {snapshot.active_project_id}")
        print(f"Sessions: {len(snapshot.sessions)}")
    """

    # Projects and their state
    projects: dict[str, Project]
    active_project_id: str | None

    # Active sessions
    sessions: dict[str, ManagedSession]

    # Plans (PLAN.md content)
    plans: dict[str, Plan]

    # Test plans (TEST_PLAN.md content)
    test_plans: dict[str, TestPlan]

    # Health check statuses: project_id -> {check_name -> status}
    health_statuses: dict[str, dict[str, HealthStatus]]

    # Configuration (if loaded)
    config: AppConfig | None

    @property
    def active_project(self) -> Project | None:
        """Get the currently active project."""
        if self.active_project_id:
            return self.projects.get(self.active_project_id)
        return None

    @property
    def has_active_sessions(self) -> bool:
        """Check if any sessions are currently active."""
        return any(s.is_active for s in self.sessions.values())

    @property
    def open_projects(self) -> list[Project]:
        """Get all open projects."""
        return [p for p in self.projects.values() if p.is_open]

    def get_sessions_for_project(self, project_id: str) -> list[ManagedSession]:
        """Get all sessions for a specific project."""
        return [s for s in self.sessions.values() if s.project_id == project_id]

    def get_plan(self, project_id: str) -> Plan | None:
        """Get the plan for a project."""
        return self.plans.get(project_id)

    def get_test_plan(self, project_id: str) -> TestPlan | None:
        """Get the test plan for a project."""
        return self.test_plans.get(project_id)

    def get_health_statuses(self, project_id: str) -> dict[str, HealthStatus]:
        """Get health check statuses for a project."""
        return self.health_statuses.get(project_id, {}).copy()
