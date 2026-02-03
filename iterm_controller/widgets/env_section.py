"""Environment variables section widget for Project Screen.

Displays collapsible section showing environment variables from .env file.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Button, Static

from iterm_controller.env_parser import load_env_file

if TYPE_CHECKING:
    from iterm_controller.models import Project

logger = logging.getLogger(__name__)

# Patterns that indicate sensitive values that should be masked
SENSITIVE_PATTERNS = ["KEY", "SECRET", "PASSWORD", "TOKEN", "CREDENTIAL", "AUTH"]

# Maximum display length for truncated values
MAX_VALUE_DISPLAY_LENGTH = 30


class EnvSection(Static):
    """Environment variables section with collapsible content.

    Displays a collapsible section showing environment variables:
    - Loaded from the project's .env file
    - Sensitive values are masked (keys containing KEY, SECRET, etc.)
    - Values are truncated if too long

    Example display:
        -- Env Variables -------------------------------
        > DATABASE_URL: postgresql://localhost:5432/...
          API_KEY: ****
          DEBUG: true
        [e] Edit
    """

    DEFAULT_CSS = """
    EnvSection {
        height: auto;
        min-height: 5;
        padding: 0 1;
        border: solid $surface-lighten-1;
        margin-bottom: 1;
    }

    EnvSection .section-header {
        color: $text;
        text-style: bold;
        margin-bottom: 1;
    }

    EnvSection .section-header-collapsed {
        color: $text-muted;
        text-style: bold;
        margin-bottom: 0;
    }

    EnvSection #env-container {
        height: auto;
        padding-left: 1;
    }

    EnvSection #edit-env-btn {
        margin-top: 1;
        width: auto;
        min-width: 12;
    }
    """

    class EnvSelected(Message):
        """Posted when an environment variable is selected."""

        def __init__(self, key: str, value: str) -> None:
            super().__init__()
            self.key = key
            self.value = value

    class EditEnvRequested(Message):
        """Posted when user requests to edit environment variables."""

        pass

    def __init__(
        self,
        project: Project | None = None,
        collapsed: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the env section widget.

        Args:
            project: Project to show env vars for.
            collapsed: Whether to start collapsed.
            **kwargs: Additional arguments passed to Static.
        """
        self._project = project
        self._collapsed = collapsed
        self._env_vars: dict[str, str] = {}
        self._selected_index = 0
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
    def selected_item(self) -> tuple[str, str] | None:
        """Get the currently selected item.

        Returns:
            Tuple of (key, value) or None if no selection.
        """
        if not self._project or self._collapsed:
            return None
        keys = list(self._env_vars.keys())
        if 0 <= self._selected_index < len(keys):
            key = keys[self._selected_index]
            return (key, self._env_vars[key])
        return None

    def set_project(self, project: Project) -> None:
        """Set the project and refresh env vars.

        Args:
            project: Project to show env vars for.
        """
        self._project = project
        self.refresh_env()

    def toggle_collapsed(self) -> None:
        """Toggle section collapsed state."""
        self._collapsed = not self._collapsed
        self.refresh()

    def refresh_env(self) -> None:
        """Load environment variables from .env file and refresh display."""
        self._env_vars = {}

        if not self._project:
            self.refresh()
            return

        project_path = Path(self._project.path)
        env_file = project_path / ".env"

        if env_file.exists():
            try:
                self._env_vars = load_env_file(env_file)
            except Exception as e:
                logger.warning("Failed to load .env file for '%s': %s", self._project.name, e)

        # Reset selection if out of bounds
        if self._selected_index >= len(self._env_vars):
            self._selected_index = max(0, len(self._env_vars) - 1)

        self.refresh()

    def select_next(self) -> None:
        """Select the next item."""
        if self._collapsed:
            return
        keys = list(self._env_vars.keys())
        if keys:
            self._selected_index = min(self._selected_index + 1, len(keys) - 1)
            self.refresh()

    def select_previous(self) -> None:
        """Select the previous item."""
        if self._collapsed:
            return
        if self._selected_index > 0:
            self._selected_index -= 1
            self.refresh()

    def action_select_env(self) -> None:
        """Handle selection of current env var."""
        selected = self.selected_item
        if selected:
            key, value = selected
            self.post_message(self.EnvSelected(key, value))

    def action_edit_env(self) -> None:
        """Handle request to edit environment variables."""
        self.post_message(self.EditEnvRequested())

    def compose(self) -> "ComposeResult":  # type: ignore[name-defined]
        """Compose the widget content."""
        from textual.app import ComposeResult

        # Section header
        collapse_icon = ">" if self._collapsed else "v"
        header_class = "section-header-collapsed" if self._collapsed else "section-header"
        yield Static(f"{collapse_icon} Env Variables", classes=header_class, id="section-header")

        if not self._collapsed:
            yield Vertical(id="env-container")
            yield Button("[e] Edit", id="edit-env-btn")

    def on_mount(self) -> None:
        """Initialize when mounted."""
        if self._project:
            self.refresh_env()
        else:
            self.refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "edit-env-btn":
            self.action_edit_env()

    def _is_sensitive(self, key: str) -> bool:
        """Check if key is sensitive and should be masked.

        Args:
            key: Environment variable key.

        Returns:
            True if the key contains sensitive patterns.
        """
        key_upper = key.upper()
        return any(pattern in key_upper for pattern in SENSITIVE_PATTERNS)

    def _format_value(self, key: str, value: str) -> str:
        """Format a value for display.

        Args:
            key: Environment variable key.
            value: Environment variable value.

        Returns:
            Formatted value (masked or truncated).
        """
        if self._is_sensitive(key):
            return "****"

        if len(value) > MAX_VALUE_DISPLAY_LENGTH:
            return value[:MAX_VALUE_DISPLAY_LENGTH] + "..."

        return value

    def _render_env_item(
        self,
        key: str,
        value: str,
        is_selected: bool,
    ) -> Text:
        """Render a single env var row.

        Args:
            key: Environment variable key.
            value: Environment variable value.
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

        # Key
        key_style = "bold" if is_selected else ""
        text.append(key, style=key_style)
        text.append(": ", style="dim")

        # Value (formatted)
        display_value = self._format_value(key, value)
        value_style = "dim italic" if self._is_sensitive(key) else ""
        text.append(display_value, style=value_style)

        return text

    def _update_env_display(self, container: Vertical) -> None:
        """Update the env container with current items."""
        container.remove_children()

        if not self._project:
            container.mount(Static("[dim]No project selected[/dim]"))
            return

        if not self._env_vars:
            container.mount(Static("[dim]No .env file found[/dim]"))
            return

        # Build content
        lines: list[Text] = []
        keys = list(self._env_vars.keys())
        for idx, key in enumerate(keys):
            value = self._env_vars[key]
            is_selected = idx == self._selected_index
            lines.append(self._render_env_item(key, value, is_selected))

        # Combine into single content
        content = Text()
        for i, line in enumerate(lines):
            if i > 0:
                content.append("\n")
            content.append_text(line)

        container.mount(Static(content, id="env-content"))

    def refresh(self, *args: Any, **kwargs: Any) -> None:
        """Override refresh to update env display."""
        # Update section header
        try:
            header = self.query_one("#section-header", Static)
            collapse_icon = ">" if self._collapsed else "v"
            header.update(f"{collapse_icon} Env Variables")
            header.set_class(self._collapsed, "section-header-collapsed")
            header.set_class(not self._collapsed, "section-header")
        except Exception:
            pass

        # Update env vars if not collapsed
        if not self._collapsed:
            try:
                container = self.query_one("#env-container", Vertical)
                self._update_env_display(container)
            except Exception:
                pass

        super().refresh(*args, **kwargs)

    def get_env_count(self) -> int:
        """Get total number of environment variables.

        Returns:
            Count of environment variables.
        """
        return len(self._env_vars)

    def get_env_file_path(self) -> Path | None:
        """Get the path to the .env file.

        Returns:
            Path to .env file or None if no project.
        """
        if not self._project:
            return None
        return Path(self._project.path) / ".env"
