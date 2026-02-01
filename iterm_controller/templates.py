"""Template management for project creation.

Provides CRUD operations, validation, and setup script execution for project templates.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from .models import AppConfig, Project, ProjectTemplate


class TemplateValidationError(Exception):
    """Raised when template validation fails."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Template validation failed: {', '.join(errors)}")


class SetupScriptError(Exception):
    """Raised when a template setup script fails."""

    def __init__(self, message: str, returncode: int | None = None, stderr: str = ""):
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(message)


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


class TemplateRunner:
    """Runs template setup during project creation.

    Handles:
    - Creating project directory and files
    - Variable substitution in file content and scripts
    - Executing setup scripts in the project directory
    """

    # Pattern for {{variable}} placeholders
    VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")

    async def create_from_template(
        self,
        template: ProjectTemplate,
        project_path: str,
        form_values: dict[str, str],
    ) -> Project:
        """Create a new project from a template.

        Args:
            template: The template to use
            project_path: Path where the project should be created
            form_values: User-provided values for variable substitution

        Returns:
            The created Project object

        Raises:
            SetupScriptError: If the setup script fails
            OSError: If file/directory operations fail
        """
        path = Path(project_path)

        # Create project directory
        path.mkdir(parents=True, exist_ok=True)

        # Create additional files from template
        for filename, content in template.files.items():
            file_path = path / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Substitute template variables
            content = self._substitute_vars(content, form_values)
            file_path.write_text(content)

        # Create default PLAN.md if specified
        if template.default_plan:
            plan_content = self._substitute_vars(template.default_plan, form_values)
            (path / "PLAN.md").write_text(plan_content)

        # Run setup script if specified
        if template.setup_script:
            await self._run_setup_script(template.setup_script, path, form_values)

        # Create project object
        project = Project(
            id=form_values.get("name", path.name),
            name=form_values.get("name", path.name),
            path=str(path.resolve()),
            template_id=template.id,
        )

        return project

    def _substitute_vars(self, content: str, values: dict[str, str]) -> str:
        """Substitute {{var}} placeholders in content.

        Args:
            content: String containing {{variable}} placeholders
            values: Dictionary of variable names to values

        Returns:
            Content with placeholders replaced
        """

        def replace(match: re.Match[str]) -> str:
            var_name = match.group(1)
            return values.get(var_name, match.group(0))

        return self.VAR_PATTERN.sub(replace, content)

    async def _run_setup_script(
        self,
        script: str,
        path: Path,
        values: dict[str, str],
    ) -> None:
        """Run template setup script in the project directory.

        Args:
            script: The script content to execute
            path: Working directory for the script
            values: Variable values for substitution

        Raises:
            SetupScriptError: If the script exits with non-zero status
        """
        # Substitute variables in script
        script = self._substitute_vars(script, values)

        # Run script
        process = await asyncio.create_subprocess_shell(
            script,
            cwd=path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise SetupScriptError(
                f"Setup script failed with exit code {process.returncode}: {stderr.decode()}",
                returncode=process.returncode,
                stderr=stderr.decode(),
            )
