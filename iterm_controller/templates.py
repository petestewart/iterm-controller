"""Template management for project creation.

Provides CRUD operations and validation for project templates.
"""

from __future__ import annotations

from .models import AppConfig, ProjectTemplate


class TemplateValidationError(Exception):
    """Raised when template validation fails."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Template validation failed: {', '.join(errors)}")


class TemplateManager:
    """Manages project templates.

    Provides list, get, add, update, delete operations for templates,
    along with validation of template configuration.
    """

    def __init__(self, config: AppConfig):
        """Initialize with application config.

        Args:
            config: The application configuration containing templates
        """
        self.config = config

    def list_templates(self) -> list[ProjectTemplate]:
        """List all available templates.

        Returns:
            A copy of the templates list to prevent external modification.
        """
        return self.config.templates.copy()

    def get_template(self, template_id: str) -> ProjectTemplate | None:
        """Get template by ID.

        Args:
            template_id: The unique template identifier

        Returns:
            The matching template, or None if not found
        """
        for template in self.config.templates:
            if template.id == template_id:
                return template
        return None

    def add_template(self, template: ProjectTemplate) -> None:
        """Add a new template.

        Args:
            template: The template to add

        Raises:
            ValueError: If a template with the same ID already exists
        """
        if self.get_template(template.id):
            raise ValueError(f"Template '{template.id}' already exists")
        self.config.templates.append(template)

    def update_template(self, template: ProjectTemplate) -> None:
        """Update an existing template.

        Args:
            template: The template with updated values (matched by ID)

        Raises:
            ValueError: If no template with the given ID exists
        """
        for i, t in enumerate(self.config.templates):
            if t.id == template.id:
                self.config.templates[i] = template
                return
        raise ValueError(f"Template '{template.id}' not found")

    def delete_template(self, template_id: str) -> bool:
        """Delete a template.

        Args:
            template_id: The ID of the template to delete

        Returns:
            True if a template was deleted, False if not found
        """
        original_count = len(self.config.templates)
        self.config.templates = [
            t for t in self.config.templates if t.id != template_id
        ]
        return len(self.config.templates) < original_count

    def validate_template(self, template: ProjectTemplate) -> list[str]:
        """Validate template configuration.

        Checks for:
        - Required fields (id, name)
        - Valid session template references

        Args:
            template: The template to validate

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check required fields
        if not template.id:
            errors.append("Template ID is required")
        elif not template.id.strip():
            errors.append("Template ID cannot be empty or whitespace")

        if not template.name:
            errors.append("Template name is required")
        elif not template.name.strip():
            errors.append("Template name cannot be empty or whitespace")

        # Validate session template references
        session_ids = {s.id for s in self.config.session_templates}
        for session_id in template.initial_sessions:
            if session_id not in session_ids:
                errors.append(f"Unknown session template: {session_id}")

        return errors

    def add_template_validated(self, template: ProjectTemplate) -> None:
        """Add a new template with validation.

        Args:
            template: The template to add

        Raises:
            TemplateValidationError: If validation fails
            ValueError: If a template with the same ID already exists
        """
        errors = self.validate_template(template)
        if errors:
            raise TemplateValidationError(errors)
        self.add_template(template)

    def update_template_validated(self, template: ProjectTemplate) -> None:
        """Update a template with validation.

        Args:
            template: The template with updated values

        Raises:
            TemplateValidationError: If validation fails
            ValueError: If no template with the given ID exists
        """
        errors = self.validate_template(template)
        if errors:
            raise TemplateValidationError(errors)
        self.update_template(template)
