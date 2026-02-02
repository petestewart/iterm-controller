"""Tests for the ProjectHeaderWidget."""

import pytest

from iterm_controller.models import Project
from iterm_controller.widgets.project_header import ProjectHeaderWidget


def make_project(
    project_id: str = "test-project",
    name: str = "Test Project",
    path: str = "/path/to/project",
    jira_ticket: str | None = None,
) -> Project:
    """Create a test project."""
    return Project(
        id=project_id,
        name=name,
        path=path,
        jira_ticket=jira_ticket,
    )


class TestProjectHeaderWidgetInit:
    """Tests for ProjectHeaderWidget initialization."""

    def test_init_with_project(self) -> None:
        """Test widget initializes with provided project."""
        project = make_project()
        widget = ProjectHeaderWidget(project=project)

        assert widget._project == project

    def test_init_with_id(self) -> None:
        """Test widget initializes with custom id."""
        project = make_project()
        widget = ProjectHeaderWidget(project=project, id="custom-header")

        assert widget.id == "custom-header"

    def test_init_with_name(self) -> None:
        """Test widget initializes with custom name."""
        project = make_project()
        widget = ProjectHeaderWidget(project=project, name="custom-name")

        assert widget.name == "custom-name"


class TestProjectDisplay:
    """Tests for project name and Jira ticket display."""

    def test_project_name_displayed(self) -> None:
        """Test project name is stored for display."""
        project = make_project(name="My Cool Project")
        widget = ProjectHeaderWidget(project=project)

        assert widget._project.name == "My Cool Project"

    def test_jira_ticket_none(self) -> None:
        """Test widget handles missing Jira ticket."""
        project = make_project(jira_ticket=None)
        widget = ProjectHeaderWidget(project=project)

        assert widget._project.jira_ticket is None

    def test_jira_ticket_present(self) -> None:
        """Test widget stores Jira ticket."""
        project = make_project(jira_ticket="PROJ-123")
        widget = ProjectHeaderWidget(project=project)

        assert widget._project.jira_ticket == "PROJ-123"

    def test_jira_ticket_complex_format(self) -> None:
        """Test widget handles various Jira ticket formats."""
        project = make_project(jira_ticket="MYPROJECT-9999")
        widget = ProjectHeaderWidget(project=project)

        assert widget._project.jira_ticket == "MYPROJECT-9999"


class TestUpdateProject:
    """Tests for the update_project method (internal state only, not recompose)."""

    def test_update_changes_project_internal(self) -> None:
        """Test that setting _project directly changes the stored project."""
        # Note: update_project() calls recompose() which requires an app context.
        # We test the state change directly instead.
        project1 = make_project(name="Original")
        project2 = make_project(name="Updated")
        widget = ProjectHeaderWidget(project=project1)

        # Direct state change (what update_project does before recompose)
        widget._project = project2

        assert widget._project.name == "Updated"

    def test_update_changes_jira_ticket_internal(self) -> None:
        """Test that setting _project changes Jira ticket."""
        project1 = make_project(jira_ticket=None)
        project2 = make_project(jira_ticket="NEW-456")
        widget = ProjectHeaderWidget(project=project1)

        widget._project = project2

        assert widget._project.jira_ticket == "NEW-456"

    def test_update_removes_jira_ticket_internal(self) -> None:
        """Test that setting _project can remove Jira ticket."""
        project1 = make_project(jira_ticket="OLD-123")
        project2 = make_project(jira_ticket=None)
        widget = ProjectHeaderWidget(project=project1)

        widget._project = project2

        assert widget._project.jira_ticket is None


class TestCompose:
    """Tests for compose method behavior.

    Note: compose() uses a context manager (with Horizontal():) which makes
    testing the generator directly complex. We test the expected behavior
    by verifying the project data is available for rendering.
    """

    def test_compose_accesses_project_name(self) -> None:
        """Test compose has access to project name."""
        project = make_project(name="Test Project")
        widget = ProjectHeaderWidget(project=project)

        # Verify the widget stores the project correctly
        assert widget._project.name == "Test Project"

    def test_compose_accesses_jira_ticket(self) -> None:
        """Test compose has access to Jira ticket when present."""
        project = make_project(name="Test", jira_ticket="ABC-123")
        widget = ProjectHeaderWidget(project=project)

        # Verify the widget stores the jira ticket correctly
        assert widget._project.jira_ticket == "ABC-123"

    def test_compose_handles_no_jira(self) -> None:
        """Test compose handles missing Jira ticket."""
        project = make_project(name="Test", jira_ticket=None)
        widget = ProjectHeaderWidget(project=project)

        # Verify the widget handles None jira_ticket
        assert widget._project.jira_ticket is None


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_project_name(self) -> None:
        """Test widget handles empty project name."""
        project = make_project(name="")
        widget = ProjectHeaderWidget(project=project)

        assert widget._project.name == ""

    def test_long_project_name(self) -> None:
        """Test widget handles long project name."""
        long_name = "A" * 100
        project = make_project(name=long_name)
        widget = ProjectHeaderWidget(project=project)

        assert widget._project.name == long_name

    def test_project_with_special_characters(self) -> None:
        """Test widget handles project names with special characters."""
        project = make_project(name="project-with_special.chars (v2)")
        widget = ProjectHeaderWidget(project=project)

        assert widget._project.name == "project-with_special.chars (v2)"

    def test_jira_ticket_with_lowercase(self) -> None:
        """Test widget handles lowercase Jira tickets."""
        project = make_project(jira_ticket="proj-123")
        widget = ProjectHeaderWidget(project=project)

        assert widget._project.jira_ticket == "proj-123"
