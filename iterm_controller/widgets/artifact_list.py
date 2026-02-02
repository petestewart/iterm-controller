"""Artifact list widget for Plan Mode.

Displays planning artifacts with status indicators showing
which artifacts exist and their current state.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.message import Message
from textual.widgets import Static

from iterm_controller.models import ArtifactStatus

if TYPE_CHECKING:
    from iterm_controller.models import Project


class ArtifactListWidget(Static):
    """Displays planning artifacts with status indicators.

    This widget shows the status of planning artifacts:
    - PROBLEM.md - Problem statement
    - PRD.md - Product requirements document
    - specs/ - Technical specifications directory
    - PLAN.md - Implementation task list

    Status icons:
    - ✓ Artifact exists
    - ○ Artifact missing

    Example display:
        ✓ PROBLEM.md          Problem statement
        ✓ PRD.md              Product requirements
        ✓ specs/              4 spec files
          └─ README.md        Technical overview
          └─ models.md        Data models
        ○ PLAN.md             Not created yet
    """

    DEFAULT_CSS = """
    ArtifactListWidget {
        height: auto;
        min-height: 8;
        padding: 1;
        border: solid $surface-lighten-1;
    }
    """

    ARTIFACT_DEFINITIONS = [
        ("PROBLEM.md", "Problem statement"),
        ("PRD.md", "Product requirements"),
        ("specs/", "Technical specifications"),
        ("PLAN.md", "Implementation task list"),
    ]

    class ArtifactSelected(Message):
        """Posted when an artifact is selected."""

        def __init__(self, artifact_name: str, artifact_path: Path) -> None:
            super().__init__()
            self.artifact_name = artifact_name
            self.artifact_path = artifact_path

    def __init__(
        self,
        project: Project | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the artifact list widget.

        Args:
            project: Project to check artifacts for.
            **kwargs: Additional arguments passed to Static.
        """
        self._project = project
        self._artifact_status: dict[str, ArtifactStatus] = {}
        self._spec_files: list[str] = []
        self._selected_index = 0
        self._expanded_specs = True
        # Pass initial content to Static constructor
        super().__init__("Loading artifacts...", **kwargs)

    @property
    def project(self) -> Project | None:
        """Get the current project."""
        return self._project

    @property
    def artifact_status(self) -> dict[str, ArtifactStatus]:
        """Get artifact status dictionary."""
        return self._artifact_status

    @property
    def selected_artifact(self) -> str | None:
        """Get the currently selected artifact name."""
        if not self._project:
            return None
        items = self._get_selectable_items()
        if 0 <= self._selected_index < len(items):
            return items[self._selected_index]
        return None

    def _get_selectable_items(self) -> list[str]:
        """Get list of selectable item names."""
        items = []
        for artifact_name, _ in self.ARTIFACT_DEFINITIONS:
            items.append(artifact_name)
            # Add spec files as sub-items when specs/ is expanded
            if artifact_name == "specs/" and self._expanded_specs:
                for spec_file in self._spec_files:
                    items.append(f"specs/{spec_file}")
        return items

    def set_project(self, project: Project) -> None:
        """Set the project and refresh artifact status.

        Args:
            project: Project to check artifacts for.
        """
        self._project = project
        self.refresh_status()

    def refresh_status(self) -> None:
        """Check artifact status and refresh display."""
        if not self._project:
            self._artifact_status = {}
            self._spec_files = []
            self.update(self._build_content_text())
            return

        project_path = Path(self._project.path)
        self._artifact_status = check_artifact_status(project_path)
        self._spec_files = get_spec_files(project_path)
        self.update(self._build_content_text())

    def select_next(self) -> None:
        """Select the next artifact."""
        items = self._get_selectable_items()
        if items:
            self._selected_index = min(self._selected_index + 1, len(items) - 1)
            self.update(self._build_content_text())

    def select_previous(self) -> None:
        """Select the previous artifact."""
        if self._selected_index > 0:
            self._selected_index -= 1
            self.update(self._build_content_text())

    def toggle_specs_expanded(self) -> None:
        """Toggle expansion of specs directory."""
        self._expanded_specs = not self._expanded_specs
        # Adjust selection if we collapsed and were on a spec file
        selected = self.selected_artifact
        if selected and selected.startswith("specs/") and selected != "specs/":
            # Find specs/ index
            for i, (name, _) in enumerate(self.ARTIFACT_DEFINITIONS):
                if name == "specs/":
                    self._selected_index = i
                    break
        self.update(self._build_content_text())

    def get_selected_path(self) -> Path | None:
        """Get the full path to the selected artifact.

        Returns:
            Path to the artifact, or None if no project or selection.
        """
        if not self._project:
            return None
        selected = self.selected_artifact
        if not selected:
            return None
        return Path(self._project.path) / selected

    def _render_artifact(
        self,
        name: str,
        description: str,
        status: ArtifactStatus,
        is_selected: bool,
    ) -> Text:
        """Render a single artifact row.

        Args:
            name: Artifact name.
            description: Artifact description.
            status: Artifact status.
            is_selected: Whether this artifact is selected.

        Returns:
            Rich Text object for the row.
        """
        text = Text()

        # Selection indicator
        if is_selected:
            text.append("> ", style="bold cyan")
        else:
            text.append("  ")

        # Status icon
        if status.exists:
            text.append("✓ ", style="green")
        else:
            text.append("○ ", style="dim")

        # Name
        name_style = "bold" if is_selected else ""
        text.append(name.ljust(20), style=name_style)

        # Description (use status description if available, otherwise default)
        desc = status.description if status.description else description
        if status.exists:
            text.append(desc)
        else:
            text.append(desc, style="dim")

        return text

    def _render_spec_file(self, filename: str, is_selected: bool) -> Text:
        """Render a spec file sub-item.

        Args:
            filename: The spec filename.
            is_selected: Whether this item is selected.

        Returns:
            Rich Text object for the row.
        """
        text = Text()

        # Selection indicator
        if is_selected:
            text.append("> ", style="bold cyan")
        else:
            text.append("  ")

        # Tree connector
        text.append("  └─ ", style="dim")

        # Filename
        name_style = "bold" if is_selected else ""
        text.append(filename, style=name_style)

        return text

    def _build_content_text(self) -> Text:
        """Render the artifact list as a Text object.

        Returns:
            Rich Text object containing the list.
        """
        if not self._project:
            return Text("No project selected", style="dim italic")

        lines: list[Text] = []
        selectable_items = self._get_selectable_items()
        item_index = 0

        for artifact_name, description in self.ARTIFACT_DEFINITIONS:
            status = self._artifact_status.get(
                artifact_name,
                ArtifactStatus(exists=False),
            )
            is_selected = item_index == self._selected_index
            lines.append(self._render_artifact(
                artifact_name, description, status, is_selected
            ))
            item_index += 1

            # Add spec files as sub-items
            if artifact_name == "specs/" and self._expanded_specs:
                for spec_file in self._spec_files:
                    is_spec_selected = item_index == self._selected_index
                    lines.append(self._render_spec_file(spec_file, is_spec_selected))
                    item_index += 1

        result = Text()
        for i, line in enumerate(lines):
            if i > 0:
                result.append("\n")
            result.append_text(line)

        return result

    def on_mount(self) -> None:
        """Update content when mounted."""
        # If we have a project, do a full refresh to check file status
        if self._project:
            self.refresh_status()
        else:
            self.update("No project selected")



def check_artifact_status(project_path: Path) -> dict[str, ArtifactStatus]:
    """Check existence and status of planning artifacts.

    Args:
        project_path: Path to the project root.

    Returns:
        Dictionary mapping artifact names to their status.
    """
    status: dict[str, ArtifactStatus] = {}

    # Check PROBLEM.md
    problem_path = project_path / "PROBLEM.md"
    status["PROBLEM.md"] = ArtifactStatus(
        exists=problem_path.exists(),
        description="Problem statement" if problem_path.exists() else "Not created yet",
    )

    # Check PRD.md
    prd_path = project_path / "PRD.md"
    status["PRD.md"] = ArtifactStatus(
        exists=prd_path.exists(),
        description="Product requirements" if prd_path.exists() else "Not created yet",
    )

    # Check specs/ directory
    specs_path = project_path / "specs"
    if specs_path.is_dir():
        spec_files = list(specs_path.glob("*.md"))
        count = len(spec_files)
        status["specs/"] = ArtifactStatus(
            exists=True,
            description=f"{count} spec file{'s' if count != 1 else ''}",
        )
    else:
        status["specs/"] = ArtifactStatus(
            exists=False,
            description="Not created yet",
        )

    # Check PLAN.md
    plan_path = project_path / "PLAN.md"
    if plan_path.exists():
        # Count tasks by looking for checkbox patterns
        content = plan_path.read_text()
        task_count = content.count("- [ ]") + content.count("- [x]")
        if task_count > 0:
            status["PLAN.md"] = ArtifactStatus(
                exists=True,
                description=f"{task_count} task{'s' if task_count != 1 else ''}",
            )
        else:
            status["PLAN.md"] = ArtifactStatus(
                exists=True,
                description="No tasks yet",
            )
    else:
        status["PLAN.md"] = ArtifactStatus(
            exists=False,
            description="Not created yet",
        )

    return status


def get_spec_files(project_path: Path) -> list[str]:
    """Get list of spec files in the specs/ directory.

    Args:
        project_path: Path to the project root.

    Returns:
        List of spec filenames (without path).
    """
    specs_path = project_path / "specs"
    if not specs_path.is_dir():
        return []

    spec_files = sorted(specs_path.glob("*.md"))
    return [f.name for f in spec_files]
