"""Tests for template management."""

from pathlib import Path

import pytest

from iterm_controller.models import AppConfig, Project, ProjectTemplate, SessionTemplate
from iterm_controller.templates import (
    SetupScriptError,
    TemplateManager,
    TemplateRunner,
    TemplateValidationError,
)


@pytest.fixture
def session_templates() -> list[SessionTemplate]:
    """Create sample session templates for testing."""
    return [
        SessionTemplate(id="shell", name="Shell", command=""),
        SessionTemplate(id="dev", name="Dev Server", command="npm run dev"),
        SessionTemplate(id="claude", name="Claude", command="claude"),
    ]


@pytest.fixture
def config(session_templates: list[SessionTemplate]) -> AppConfig:
    """Create a config with session templates."""
    return AppConfig(session_templates=session_templates)


@pytest.fixture
def manager(config: AppConfig) -> TemplateManager:
    """Create a template manager with sample config."""
    return TemplateManager(config)


@pytest.fixture
def sample_template() -> ProjectTemplate:
    """Create a sample project template."""
    return ProjectTemplate(
        id="web-project",
        name="Web Project",
        description="A web development project template",
        initial_sessions=["shell", "dev"],
        default_plan="# PLAN\n\n## Tasks\n\n- [ ] Setup project",
    )


class TestListTemplates:
    """Test listing templates."""

    def test_list_empty(self, manager: TemplateManager):
        """List returns empty list when no templates exist."""
        templates = manager.list_templates()
        assert templates == []

    def test_list_returns_copy(self, manager: TemplateManager, sample_template: ProjectTemplate):
        """List returns a copy to prevent external modification."""
        manager.add_template(sample_template)
        templates = manager.list_templates()

        # Modify the returned list
        templates.clear()

        # Original should be unaffected
        assert len(manager.list_templates()) == 1

    def test_list_after_add(self, manager: TemplateManager, sample_template: ProjectTemplate):
        """List returns added templates."""
        manager.add_template(sample_template)
        templates = manager.list_templates()

        assert len(templates) == 1
        assert templates[0].id == "web-project"
        assert templates[0].name == "Web Project"


class TestGetTemplate:
    """Test getting templates by ID."""

    def test_get_nonexistent(self, manager: TemplateManager):
        """Get returns None for nonexistent template."""
        result = manager.get_template("nonexistent")
        assert result is None

    def test_get_existing(self, manager: TemplateManager, sample_template: ProjectTemplate):
        """Get returns existing template."""
        manager.add_template(sample_template)
        result = manager.get_template("web-project")

        assert result is not None
        assert result.id == "web-project"
        assert result.name == "Web Project"

    def test_get_with_multiple_templates(self, manager: TemplateManager):
        """Get returns correct template when multiple exist."""
        template1 = ProjectTemplate(id="t1", name="Template 1")
        template2 = ProjectTemplate(id="t2", name="Template 2")
        template3 = ProjectTemplate(id="t3", name="Template 3")

        manager.add_template(template1)
        manager.add_template(template2)
        manager.add_template(template3)

        result = manager.get_template("t2")
        assert result is not None
        assert result.name == "Template 2"


class TestAddTemplate:
    """Test adding templates."""

    def test_add_new_template(self, manager: TemplateManager, sample_template: ProjectTemplate):
        """Add creates new template."""
        manager.add_template(sample_template)

        assert len(manager.list_templates()) == 1
        assert manager.get_template("web-project") is not None

    def test_add_duplicate_raises(self, manager: TemplateManager, sample_template: ProjectTemplate):
        """Add raises ValueError for duplicate ID."""
        manager.add_template(sample_template)

        with pytest.raises(ValueError, match="already exists"):
            manager.add_template(sample_template)

    def test_add_multiple_templates(self, manager: TemplateManager):
        """Can add multiple different templates."""
        template1 = ProjectTemplate(id="t1", name="Template 1")
        template2 = ProjectTemplate(id="t2", name="Template 2")

        manager.add_template(template1)
        manager.add_template(template2)

        assert len(manager.list_templates()) == 2


class TestUpdateTemplate:
    """Test updating templates."""

    def test_update_existing(self, manager: TemplateManager, sample_template: ProjectTemplate):
        """Update modifies existing template."""
        manager.add_template(sample_template)

        updated = ProjectTemplate(
            id="web-project",
            name="Updated Web Project",
            description="Updated description",
        )
        manager.update_template(updated)

        result = manager.get_template("web-project")
        assert result is not None
        assert result.name == "Updated Web Project"
        assert result.description == "Updated description"

    def test_update_nonexistent_raises(self, manager: TemplateManager):
        """Update raises ValueError for nonexistent template."""
        template = ProjectTemplate(id="nonexistent", name="Test")

        with pytest.raises(ValueError, match="not found"):
            manager.update_template(template)

    def test_update_preserves_other_templates(self, manager: TemplateManager):
        """Update only affects the target template."""
        template1 = ProjectTemplate(id="t1", name="Template 1")
        template2 = ProjectTemplate(id="t2", name="Template 2")
        manager.add_template(template1)
        manager.add_template(template2)

        updated1 = ProjectTemplate(id="t1", name="Updated Template 1")
        manager.update_template(updated1)

        assert manager.get_template("t1").name == "Updated Template 1"
        assert manager.get_template("t2").name == "Template 2"


class TestDeleteTemplate:
    """Test deleting templates."""

    def test_delete_existing(self, manager: TemplateManager, sample_template: ProjectTemplate):
        """Delete removes existing template and returns True."""
        manager.add_template(sample_template)

        result = manager.delete_template("web-project")

        assert result is True
        assert manager.get_template("web-project") is None
        assert len(manager.list_templates()) == 0

    def test_delete_nonexistent(self, manager: TemplateManager):
        """Delete returns False for nonexistent template."""
        result = manager.delete_template("nonexistent")
        assert result is False

    def test_delete_preserves_other_templates(self, manager: TemplateManager):
        """Delete only removes the target template."""
        template1 = ProjectTemplate(id="t1", name="Template 1")
        template2 = ProjectTemplate(id="t2", name="Template 2")
        template3 = ProjectTemplate(id="t3", name="Template 3")
        manager.add_template(template1)
        manager.add_template(template2)
        manager.add_template(template3)

        manager.delete_template("t2")

        assert manager.get_template("t1") is not None
        assert manager.get_template("t2") is None
        assert manager.get_template("t3") is not None
        assert len(manager.list_templates()) == 2


class TestValidateTemplate:
    """Test template validation."""

    def test_valid_template(self, manager: TemplateManager, sample_template: ProjectTemplate):
        """Valid template returns no errors."""
        errors = manager.validate_template(sample_template)
        assert errors == []

    def test_missing_id(self, manager: TemplateManager):
        """Missing ID returns error."""
        template = ProjectTemplate(id="", name="Test")
        errors = manager.validate_template(template)
        assert any("ID" in e for e in errors)

    def test_whitespace_id(self, manager: TemplateManager):
        """Whitespace-only ID returns error."""
        template = ProjectTemplate(id="   ", name="Test")
        errors = manager.validate_template(template)
        assert any("ID" in e and "empty" in e for e in errors)

    def test_missing_name(self, manager: TemplateManager):
        """Missing name returns error."""
        template = ProjectTemplate(id="test", name="")
        errors = manager.validate_template(template)
        assert any("name" in e for e in errors)

    def test_whitespace_name(self, manager: TemplateManager):
        """Whitespace-only name returns error."""
        template = ProjectTemplate(id="test", name="   ")
        errors = manager.validate_template(template)
        assert any("name" in e and "empty" in e for e in errors)

    def test_unknown_session_template(self, manager: TemplateManager):
        """Unknown session template reference returns error."""
        template = ProjectTemplate(
            id="test",
            name="Test",
            initial_sessions=["shell", "unknown-session"],
        )
        errors = manager.validate_template(template)
        assert any("unknown-session" in e for e in errors)

    def test_multiple_unknown_sessions(self, manager: TemplateManager):
        """Multiple unknown session references return multiple errors."""
        template = ProjectTemplate(
            id="test",
            name="Test",
            initial_sessions=["unknown1", "unknown2"],
        )
        errors = manager.validate_template(template)
        assert any("unknown1" in e for e in errors)
        assert any("unknown2" in e for e in errors)

    def test_valid_session_references(self, manager: TemplateManager):
        """Valid session template references pass validation."""
        template = ProjectTemplate(
            id="test",
            name="Test",
            initial_sessions=["shell", "dev", "claude"],
        )
        errors = manager.validate_template(template)
        assert errors == []

    def test_multiple_errors(self, manager: TemplateManager):
        """Multiple validation errors are all reported."""
        template = ProjectTemplate(
            id="",
            name="",
            initial_sessions=["unknown"],
        )
        errors = manager.validate_template(template)
        assert len(errors) >= 3  # ID, name, and session errors


class TestAddTemplateValidated:
    """Test validated template addition."""

    def test_add_valid_template(self, manager: TemplateManager, sample_template: ProjectTemplate):
        """Valid template is added successfully."""
        manager.add_template_validated(sample_template)
        assert manager.get_template("web-project") is not None

    def test_add_invalid_template_raises(self, manager: TemplateManager):
        """Invalid template raises TemplateValidationError."""
        template = ProjectTemplate(id="", name="")

        with pytest.raises(TemplateValidationError) as exc_info:
            manager.add_template_validated(template)

        assert len(exc_info.value.errors) > 0

    def test_validation_error_contains_all_errors(self, manager: TemplateManager):
        """TemplateValidationError contains all validation errors."""
        template = ProjectTemplate(
            id="",
            name="",
            initial_sessions=["unknown"],
        )

        with pytest.raises(TemplateValidationError) as exc_info:
            manager.add_template_validated(template)

        assert len(exc_info.value.errors) >= 3


class TestUpdateTemplateValidated:
    """Test validated template updates."""

    def test_update_valid_template(self, manager: TemplateManager, sample_template: ProjectTemplate):
        """Valid update succeeds."""
        manager.add_template(sample_template)

        updated = ProjectTemplate(
            id="web-project",
            name="Updated Name",
            initial_sessions=["shell"],
        )
        manager.update_template_validated(updated)

        result = manager.get_template("web-project")
        assert result.name == "Updated Name"

    def test_update_invalid_template_raises(
        self, manager: TemplateManager, sample_template: ProjectTemplate
    ):
        """Invalid update raises TemplateValidationError."""
        manager.add_template(sample_template)

        updated = ProjectTemplate(
            id="web-project",
            name="",  # Invalid
        )

        with pytest.raises(TemplateValidationError):
            manager.update_template_validated(updated)

        # Original should be unchanged
        result = manager.get_template("web-project")
        assert result.name == "Web Project"


class TestTemplateWithOptionalFields:
    """Test templates with all optional fields."""

    def test_minimal_template(self, manager: TemplateManager):
        """Template with only required fields is valid."""
        template = ProjectTemplate(id="minimal", name="Minimal Template")
        errors = manager.validate_template(template)
        assert errors == []

        manager.add_template(template)
        result = manager.get_template("minimal")
        assert result is not None
        assert result.description == ""
        assert result.setup_script is None
        assert result.initial_sessions == []
        assert result.default_plan is None
        assert result.files == {}
        assert result.required_fields == []

    def test_full_template(self, manager: TemplateManager):
        """Template with all fields is valid."""
        template = ProjectTemplate(
            id="full",
            name="Full Template",
            description="A fully-configured template",
            setup_script="npm install && npm run setup",
            initial_sessions=["shell", "dev"],
            default_plan="# PLAN\n\n- [ ] Setup",
            files={
                ".env": "PORT=3000",
                "README.md": "# Project\n\nCreated from template.",
            },
            required_fields=["name", "description"],
        )
        errors = manager.validate_template(template)
        assert errors == []

        manager.add_template(template)
        result = manager.get_template("full")
        assert result is not None
        assert result.setup_script == "npm install && npm run setup"
        assert len(result.files) == 2
        assert result.required_fields == ["name", "description"]


# =============================================================================
# TemplateRunner Tests
# =============================================================================


@pytest.fixture
def runner() -> TemplateRunner:
    """Create a template runner instance."""
    return TemplateRunner()


class TestSubstituteVars:
    """Test variable substitution in content."""

    def test_substitute_simple_var(self, runner: TemplateRunner):
        """Simple variable substitution works."""
        content = "Hello, {{name}}!"
        result = runner._substitute_vars(content, {"name": "World"})
        assert result == "Hello, World!"

    def test_substitute_multiple_vars(self, runner: TemplateRunner):
        """Multiple variables are substituted."""
        content = "Project: {{name}}, Author: {{author}}"
        result = runner._substitute_vars(
            content, {"name": "MyProject", "author": "Alice"}
        )
        assert result == "Project: MyProject, Author: Alice"

    def test_substitute_same_var_multiple_times(self, runner: TemplateRunner):
        """Same variable appearing multiple times is substituted."""
        content = "{{name}}: Hello {{name}}, goodbye {{name}}"
        result = runner._substitute_vars(content, {"name": "Bob"})
        assert result == "Bob: Hello Bob, goodbye Bob"

    def test_substitute_preserves_unknown_vars(self, runner: TemplateRunner):
        """Unknown variables are preserved as-is."""
        content = "Known: {{known}}, Unknown: {{unknown}}"
        result = runner._substitute_vars(content, {"known": "value"})
        assert result == "Known: value, Unknown: {{unknown}}"

    def test_substitute_empty_values(self, runner: TemplateRunner):
        """Empty values are substituted correctly."""
        content = "Value: {{empty}}"
        result = runner._substitute_vars(content, {"empty": ""})
        assert result == "Value: "

    def test_substitute_in_multiline(self, runner: TemplateRunner):
        """Substitution works in multiline content."""
        content = """# {{title}}

By {{author}}

## Description
This project is named {{title}}.
"""
        result = runner._substitute_vars(
            content, {"title": "MyApp", "author": "Dev Team"}
        )
        assert "# MyApp" in result
        assert "By Dev Team" in result
        assert "named MyApp" in result


class TestCreateFromTemplate:
    """Test project creation from templates."""

    @pytest.mark.asyncio
    async def test_creates_project_directory(self, runner: TemplateRunner, tmp_path: Path):
        """Creates project directory if it doesn't exist."""
        template = ProjectTemplate(id="test", name="Test")
        project_path = tmp_path / "new-project"

        project = await runner.create_from_template(
            template, str(project_path), {"name": "new-project"}
        )

        assert project_path.exists()
        assert project_path.is_dir()

    @pytest.mark.asyncio
    async def test_creates_nested_project_directory(
        self, runner: TemplateRunner, tmp_path: Path
    ):
        """Creates nested directories for project path."""
        template = ProjectTemplate(id="test", name="Test")
        project_path = tmp_path / "a" / "b" / "c" / "project"

        await runner.create_from_template(
            template, str(project_path), {"name": "project"}
        )

        assert project_path.exists()

    @pytest.mark.asyncio
    async def test_creates_files_from_template(
        self, runner: TemplateRunner, tmp_path: Path
    ):
        """Creates files specified in template."""
        template = ProjectTemplate(
            id="test",
            name="Test",
            files={
                "README.md": "# Project",
                ".env": "PORT=3000",
            },
        )
        project_path = tmp_path / "project"

        await runner.create_from_template(template, str(project_path), {})

        assert (project_path / "README.md").read_text() == "# Project"
        assert (project_path / ".env").read_text() == "PORT=3000"

    @pytest.mark.asyncio
    async def test_creates_nested_files(self, runner: TemplateRunner, tmp_path: Path):
        """Creates files in nested directories."""
        template = ProjectTemplate(
            id="test",
            name="Test",
            files={
                "src/index.py": "# Entry point",
                "config/settings.json": '{"debug": true}',
            },
        )
        project_path = tmp_path / "project"

        await runner.create_from_template(template, str(project_path), {})

        assert (project_path / "src" / "index.py").read_text() == "# Entry point"
        assert (project_path / "config" / "settings.json").read_text() == '{"debug": true}'

    @pytest.mark.asyncio
    async def test_substitutes_vars_in_files(
        self, runner: TemplateRunner, tmp_path: Path
    ):
        """Substitutes variables in file content."""
        template = ProjectTemplate(
            id="test",
            name="Test",
            files={
                "README.md": "# {{name}}\n\nBy {{author}}",
            },
        )
        project_path = tmp_path / "project"

        await runner.create_from_template(
            template, str(project_path), {"name": "MyProject", "author": "Alice"}
        )

        content = (project_path / "README.md").read_text()
        assert "# MyProject" in content
        assert "By Alice" in content

    @pytest.mark.asyncio
    async def test_creates_plan_md(self, runner: TemplateRunner, tmp_path: Path):
        """Creates PLAN.md from default_plan."""
        template = ProjectTemplate(
            id="test",
            name="Test",
            default_plan="# Plan for {{name}}\n\n- [ ] Setup",
        )
        project_path = tmp_path / "project"

        await runner.create_from_template(
            template, str(project_path), {"name": "MyProject"}
        )

        plan_content = (project_path / "PLAN.md").read_text()
        assert "# Plan for MyProject" in plan_content
        assert "- [ ] Setup" in plan_content

    @pytest.mark.asyncio
    async def test_returns_project_object(self, runner: TemplateRunner, tmp_path: Path):
        """Returns a properly configured Project object."""
        template = ProjectTemplate(id="test-template", name="Test")
        project_path = tmp_path / "my-project"

        project = await runner.create_from_template(
            template, str(project_path), {"name": "MyProject"}
        )

        assert isinstance(project, Project)
        assert project.id == "MyProject"
        assert project.name == "MyProject"
        assert project.template_id == "test-template"
        assert str(project_path.resolve()) in project.path

    @pytest.mark.asyncio
    async def test_uses_dir_name_when_no_name_provided(
        self, runner: TemplateRunner, tmp_path: Path
    ):
        """Uses directory name as project name when not provided."""
        template = ProjectTemplate(id="test", name="Test")
        project_path = tmp_path / "fallback-name"

        project = await runner.create_from_template(template, str(project_path), {})

        assert project.id == "fallback-name"
        assert project.name == "fallback-name"

    @pytest.mark.asyncio
    async def test_passes_jira_ticket_to_project(
        self, runner: TemplateRunner, tmp_path: Path
    ):
        """Passes jira_ticket from form_values to the created Project."""
        template = ProjectTemplate(id="test", name="Test")
        project_path = tmp_path / "jira-project"

        project = await runner.create_from_template(
            template, str(project_path), {"name": "jira-project", "jira_ticket": "PROJ-456"}
        )

        assert project.jira_ticket == "PROJ-456"

    @pytest.mark.asyncio
    async def test_jira_ticket_none_when_not_provided(
        self, runner: TemplateRunner, tmp_path: Path
    ):
        """jira_ticket is None when not provided in form_values."""
        template = ProjectTemplate(id="test", name="Test")
        project_path = tmp_path / "no-jira-project"

        project = await runner.create_from_template(
            template, str(project_path), {"name": "no-jira-project"}
        )

        assert project.jira_ticket is None


class TestSetupScriptExecution:
    """Test setup script execution during project creation."""

    @pytest.mark.asyncio
    async def test_runs_setup_script(self, runner: TemplateRunner, tmp_path: Path):
        """Setup script is executed in project directory."""
        template = ProjectTemplate(
            id="test",
            name="Test",
            setup_script="echo 'hello' > setup_ran.txt",
        )
        project_path = tmp_path / "project"

        await runner.create_from_template(template, str(project_path), {})

        assert (project_path / "setup_ran.txt").exists()
        assert "hello" in (project_path / "setup_ran.txt").read_text()

    @pytest.mark.asyncio
    async def test_substitutes_vars_in_script(
        self, runner: TemplateRunner, tmp_path: Path
    ):
        """Variables are substituted in setup script."""
        template = ProjectTemplate(
            id="test",
            name="Test",
            setup_script="echo '{{project_name}}' > name.txt",
        )
        project_path = tmp_path / "project"

        await runner.create_from_template(
            template, str(project_path), {"project_name": "MyProject"}
        )

        content = (project_path / "name.txt").read_text().strip()
        assert content == "MyProject"

    @pytest.mark.asyncio
    async def test_script_error_raises(self, runner: TemplateRunner, tmp_path: Path):
        """Failed setup script raises SetupScriptError."""
        template = ProjectTemplate(
            id="test",
            name="Test",
            setup_script="exit 1",
        )
        project_path = tmp_path / "project"

        with pytest.raises(SetupScriptError) as exc_info:
            await runner.create_from_template(template, str(project_path), {})

        assert exc_info.value.returncode == 1

    @pytest.mark.asyncio
    async def test_script_error_contains_stderr(
        self, runner: TemplateRunner, tmp_path: Path
    ):
        """SetupScriptError contains stderr output."""
        template = ProjectTemplate(
            id="test",
            name="Test",
            setup_script="echo 'error message' >&2 && exit 1",
        )
        project_path = tmp_path / "project"

        with pytest.raises(SetupScriptError) as exc_info:
            await runner.create_from_template(template, str(project_path), {})

        assert "error message" in exc_info.value.stderr

    @pytest.mark.asyncio
    async def test_script_runs_in_project_dir(
        self, runner: TemplateRunner, tmp_path: Path
    ):
        """Setup script runs in the project directory."""
        template = ProjectTemplate(
            id="test",
            name="Test",
            setup_script="pwd > current_dir.txt",
        )
        project_path = tmp_path / "project"

        await runner.create_from_template(template, str(project_path), {})

        cwd_content = (project_path / "current_dir.txt").read_text().strip()
        assert cwd_content == str(project_path.resolve())

    @pytest.mark.asyncio
    async def test_multiline_script(self, runner: TemplateRunner, tmp_path: Path):
        """Multiline setup scripts work correctly."""
        template = ProjectTemplate(
            id="test",
            name="Test",
            setup_script="""echo 'line1' > output.txt
echo 'line2' >> output.txt
echo 'line3' >> output.txt""",
        )
        project_path = tmp_path / "project"

        await runner.create_from_template(template, str(project_path), {})

        content = (project_path / "output.txt").read_text()
        assert "line1" in content
        assert "line2" in content
        assert "line3" in content

    @pytest.mark.asyncio
    async def test_no_script_no_error(self, runner: TemplateRunner, tmp_path: Path):
        """Template without setup script works fine."""
        template = ProjectTemplate(
            id="test",
            name="Test",
            setup_script=None,
        )
        project_path = tmp_path / "project"

        # Should not raise
        project = await runner.create_from_template(template, str(project_path), {})
        assert project is not None
