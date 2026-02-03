"""Planning section widget for Project Screen.

Displays collapsible section showing planning artifacts with existence status.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Button, Static

from iterm_controller.models import ArtifactStatus
from iterm_controller.widgets.artifact_list import (
    check_artifact_status,
    get_spec_files,
)

if TYPE_CHECKING:
    from iterm_controller.models import Project


class PlanningSection(Static):
    """Planning artifacts section with collapsible content.

    Displays a section showing planning artifacts:
    - PROBLEM.md - Problem statement
    - PRD.md - Product requirements document
    - specs/ - Technical specifications directory
    - PLAN.md - Implementation task list

    Example display:
        -- Planning ----------------------------------------
        > ● PROBLEM.md          Problem statement
          ● PRD.md              Product requirements
          ● specs/              4 spec files
          ○ PLAN.md             Not created yet
        [c] Create missing
    """

    DEFAULT_CSS = """
    PlanningSection {
        height: auto;
        min-height: 6;
        padding: 0 1;
        border: solid $surface-lighten-1;
        margin-bottom: 1;
    }

    PlanningSection .section-header {
        color: $text;
        text-style: bold;
        margin-bottom: 1;
    }

    PlanningSection .section-header-collapsed {
        color: $text-muted;
        text-style: bold;
        margin-bottom: 0;
    }

    PlanningSection #artifacts-container {
        height: auto;
        padding-left: 1;
    }

    PlanningSection #create-missing-btn {
        margin-top: 1;
        width: auto;
        min-width: 20;
    }

    PlanningSection .edit-hint {
        color: $text-muted;
    }
    """

    ARTIFACTS = [
        ("PROBLEM.md", "problem", "Problem statement"),
        ("PRD.md", "prd", "Product requirements"),
        ("specs/", "specs", "Technical specifications"),
        ("PLAN.md", "plan", "Implementation task list"),
    ]

    class ArtifactSelected(Message):
        """Posted when an artifact is selected."""

        def __init__(self, artifact_name: str, artifact_path: Path, exists: bool) -> None:
            super().__init__()
            self.artifact_name = artifact_name
            self.artifact_path = artifact_path
            self.exists = exists

    class CreateMissingRequested(Message):
        """Posted when user requests to create missing artifacts."""

        def __init__(self, missing_artifacts: list[str]) -> None:
            super().__init__()
            self.missing_artifacts = missing_artifacts

    def __init__(
        self,
        project: Project | None = None,
        collapsed: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the planning section widget.

        Args:
            project: Project to check artifacts for.
            collapsed: Whether to start collapsed.
            **kwargs: Additional arguments passed to Static.
        """
        # Initialize instance attributes before calling super().__init__
        # because Textual's Static may call refresh() during initialization
        self._project = project
        self._collapsed = collapsed
        self._artifact_status: dict[str, ArtifactStatus] = {}
        self._spec_files: list[str] = []
        self._selected_index = 0
        self._expanded_specs = True
        super().__init__(**kwargs)

    @property
    def project(self) -> Project | None:
        """Get the current project."""
        return self._project

    @property
    def collapsed(self) -> bool:
        """Get collapsed state."""
        return self._collapsed

    @property
    def selected_artifact(self) -> str | None:
        """Get the currently selected artifact name."""
        if not self._project or self._collapsed:
            return None
        items = self._get_selectable_items()
        if 0 <= self._selected_index < len(items):
            return items[self._selected_index]
        return None

    @property
    def missing_artifacts(self) -> list[str]:
        """Get list of missing artifact names."""
        return [
            name
            for name, _, _ in self.ARTIFACTS
            if not self._artifact_status.get(name, ArtifactStatus(exists=False)).exists
        ]

    def _get_selectable_items(self) -> list[str]:
        """Get list of selectable item names."""
        items = []
        for artifact_name, _, _ in self.ARTIFACTS:
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
        self.refresh_artifacts()

    def toggle_collapsed(self) -> None:
        """Toggle section collapsed state."""
        self._collapsed = not self._collapsed
        self.refresh()

    def refresh_artifacts(self) -> None:
        """Check artifact status and refresh display."""
        if not self._project:
            self._artifact_status = {}
            self._spec_files = []
        else:
            project_path = Path(self._project.path)
            self._artifact_status = check_artifact_status(project_path)
            self._spec_files = get_spec_files(project_path)
        self.refresh()

    def select_next(self) -> None:
        """Select the next artifact."""
        if self._collapsed:
            return
        items = self._get_selectable_items()
        if items:
            self._selected_index = min(self._selected_index + 1, len(items) - 1)
            self.refresh()

    def select_previous(self) -> None:
        """Select the previous artifact."""
        if self._collapsed:
            return
        if self._selected_index > 0:
            self._selected_index -= 1
            self.refresh()

    def toggle_specs_expanded(self) -> None:
        """Toggle expansion of specs directory."""
        self._expanded_specs = not self._expanded_specs
        # Adjust selection if we collapsed and were on a spec file
        selected = self.selected_artifact
        if selected and selected.startswith("specs/") and selected != "specs/":
            # Find specs/ index
            for i, (name, _, _) in enumerate(self.ARTIFACTS):
                if name == "specs/":
                    self._selected_index = i
                    break
        self.refresh()

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

    def action_select_artifact(self) -> None:
        """Handle selection of current artifact."""
        if not self._project:
            return
        selected = self.selected_artifact
        if not selected:
            return
        path = self.get_selected_path()
        if path:
            status = self._artifact_status.get(
                selected.split("/")[0] + "/" if "/" in selected else selected,
                ArtifactStatus(exists=False),
            )
            self.post_message(self.ArtifactSelected(selected, path, status.exists))

    def action_create_missing(self) -> None:
        """Handle request to create missing artifacts."""
        missing = self.missing_artifacts
        if missing:
            self.post_message(self.CreateMissingRequested(missing))

    def compose(self) -> "ComposeResult":  # type: ignore[name-defined]
        """Compose the widget content."""
        from textual.app import ComposeResult

        # Section header
        collapse_icon = ">" if self._collapsed else "v"
        header_class = "section-header-collapsed" if self._collapsed else "section-header"
        yield Static(f"{collapse_icon} Planning", classes=header_class, id="section-header")

        if not self._collapsed:
            yield Vertical(id="artifacts-container")
            yield Button("[c] Create missing", id="create-missing-btn")

    def on_mount(self) -> None:
        """Initialize when mounted."""
        if self._project:
            self.refresh_artifacts()
        else:
            self.refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "create-missing-btn":
            self.action_create_missing()

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
            text.append("● ", style="green")
        else:
            text.append("○ ", style="dim")

        # Name
        name_style = "bold" if is_selected else ""
        text.append(name.ljust(20), style=name_style)

        # Description (use status description if available, otherwise default)
        desc = status.description if status.description else description
        if status.exists:
            text.append(desc)
            # Add edit hint for existing artifacts
            if is_selected:
                text.append(" [e]", style="dim cyan")
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

    def _update_artifacts_display(self, container: Vertical) -> None:
        """Update the artifacts container with current status."""
        container.remove_children()

        if not self._project:
            container.mount(Static("[dim]No project selected[/dim]"))
            return

        # Build content
        lines: list[Text] = []
        selectable_items = self._get_selectable_items()
        item_index = 0

        for artifact_name, _, description in self.ARTIFACTS:
            status = self._artifact_status.get(
                artifact_name,
                ArtifactStatus(exists=False, description="Not created yet"),
            )
            is_selected = item_index == self._selected_index
            lines.append(
                self._render_artifact(artifact_name, description, status, is_selected)
            )
            item_index += 1

            # Add spec files as sub-items
            if artifact_name == "specs/" and self._expanded_specs:
                for spec_file in self._spec_files:
                    is_spec_selected = item_index == self._selected_index
                    lines.append(self._render_spec_file(spec_file, is_spec_selected))
                    item_index += 1

        # Combine into single content
        content = Text()
        for i, line in enumerate(lines):
            if i > 0:
                content.append("\n")
            content.append_text(line)

        container.mount(Static(content, id="artifacts-content"))

        # Update button visibility based on missing artifacts
        try:
            button = self.query_one("#create-missing-btn", Button)
            has_missing = bool(self.missing_artifacts)
            button.display = has_missing
        except Exception:
            pass

    def refresh(self, *args: Any, **kwargs: Any) -> None:
        """Override refresh to update artifacts display."""
        # Update section header
        try:
            header = self.query_one("#section-header", Static)
            collapse_icon = ">" if self._collapsed else "v"
            header.update(f"{collapse_icon} Planning")
            header.set_class(self._collapsed, "section-header-collapsed")
            header.set_class(not self._collapsed, "section-header")
        except Exception:
            pass

        # Update artifacts if not collapsed
        if not self._collapsed:
            try:
                container = self.query_one("#artifacts-container", Vertical)
                self._update_artifacts_display(container)
            except Exception:
                pass

        super().refresh(*args, **kwargs)
