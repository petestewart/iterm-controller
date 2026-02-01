"""Tests for template management."""

import pytest

from iterm_controller.models import AppConfig, ProjectTemplate, SessionTemplate
from iterm_controller.templates import (
    TemplateManager,
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
