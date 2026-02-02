"""Project header widget displaying project name and Jira ticket.

Shows project identification at the top of mode screens.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Static

if TYPE_CHECKING:
    from iterm_controller.models import Project


class ProjectHeaderWidget(Widget):
    """Widget displaying project name and optional Jira ticket.

    Shows project identification at the top of mode screens in the format:
        my-project [PROJ-123]

    If no Jira ticket is configured, only shows the project name:
        my-project
    """

    DEFAULT_CSS = """
    ProjectHeaderWidget {
        width: 100%;
        height: 1;
        background: $surface;
        padding: 0 1;
    }

    ProjectHeaderWidget .project-name {
        text-style: bold;
        color: $text;
    }

    ProjectHeaderWidget .jira-ticket {
        color: $text-muted;
        margin-left: 1;
    }
    """

    def __init__(
        self,
        project: Project,
        *,
        name: str | None = None,
        id: str | None = None,
    ) -> None:
        """Initialize the project header widget.

        Args:
            project: The project to display.
            name: Optional widget name.
            id: Optional widget ID.
        """
        super().__init__(name=name, id=id)
        self._project = project

    def compose(self) -> ComposeResult:
        """Compose the widget layout."""
        with Horizontal():
            yield Static(self._project.name, classes="project-name")
            if self._project.jira_ticket:
                yield Static(f"[{self._project.jira_ticket}]", classes="jira-ticket")

    def update_project(self, project: Project) -> None:
        """Update the displayed project.

        Args:
            project: The new project to display.

        Note:
            This method requires the widget to be mounted in a Textual app.
            Use recompose() to re-render after updating.
        """
        self._project = project
        # Trigger recompose to update the display
        self.recompose()
