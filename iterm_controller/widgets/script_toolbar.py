"""Script toolbar widget for Project Screen.

Displays a toolbar with script buttons from project configuration.
Each button shows its keybinding and can launch the script in a new session.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Static

if TYPE_CHECKING:
    from iterm_controller.models import Project, ProjectScript

logger = logging.getLogger(__name__)


# Default scripts when project has none configured
DEFAULT_SCRIPTS: list[tuple[str, str, str]] = [
    ("s", "server", "Server"),
    ("t", "tests", "Tests"),
    ("l", "lint", "Lint"),
    ("b", "build", "Build"),
    ("o", "orchestrator", "Orchestrator"),
]


class ScriptToolbar(Static):
    """Toolbar with script buttons from project config.

    Displays a collapsible toolbar showing available project scripts.
    Scripts can be defined in project configuration or use defaults.

    Example display:
        -- Scripts ----------------------------------------
        [s] Server  [t] Tests  [l] Lint  [b] Build  [o] Orchestrator

    Each button posts a ScriptRunRequested message when clicked.
    """

    DEFAULT_CSS = """
    ScriptToolbar {
        height: auto;
        min-height: 3;
        padding: 0 1;
        border: solid $surface-lighten-1;
        margin-bottom: 1;
    }

    ScriptToolbar .section-header {
        color: $text;
        text-style: bold;
        margin-bottom: 1;
    }

    ScriptToolbar .section-header-collapsed {
        color: $text-muted;
        text-style: bold;
        margin-bottom: 0;
    }

    ScriptToolbar #script-container {
        height: auto;
    }

    ScriptToolbar #script-buttons {
        height: auto;
        width: 100%;
    }

    ScriptToolbar #script-buttons Button {
        margin-right: 1;
        width: auto;
        min-width: 10;
    }

    ScriptToolbar .no-scripts {
        color: $text-muted;
        padding-left: 1;
    }
    """

    class ScriptRunRequested(Message):
        """Posted when user requests to run a script."""

        def __init__(
            self,
            script_id: str,
            script_name: str,
            keybinding: str | None = None,
        ) -> None:
            super().__init__()
            self.script_id = script_id
            self.script_name = script_name
            self.keybinding = keybinding

    class ScriptSelected(Message):
        """Posted when a script button is selected/focused."""

        def __init__(self, script_id: str) -> None:
            super().__init__()
            self.script_id = script_id

    def __init__(
        self,
        project: Project | None = None,
        collapsed: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initialize the script toolbar widget.

        Args:
            project: Project to show scripts for.
            collapsed: Whether to start collapsed.
            **kwargs: Additional arguments passed to Static.
        """
        self._project = project
        self._collapsed = collapsed
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
    def scripts(self) -> list[tuple[str | None, str, str]]:
        """Get scripts as list of (keybinding, id, name) tuples.

        Returns:
            List of (keybinding, script_id, script_name) tuples.
            Uses project scripts if available, otherwise defaults.
        """
        if self._project and self._project.scripts:
            return [
                (s.keybinding, s.id, s.name)
                for s in self._project.scripts
                if s.show_in_toolbar
            ]
        # Return defaults with keybinding as first element
        return [(key, script_id, name) for key, script_id, name in DEFAULT_SCRIPTS]

    @property
    def selected_script(self) -> tuple[str | None, str, str] | None:
        """Get the currently selected script.

        Returns:
            Tuple of (keybinding, id, name) or None if no selection.
        """
        if self._collapsed:
            return None
        scripts = self.scripts
        if 0 <= self._selected_index < len(scripts):
            return scripts[self._selected_index]
        return None

    @property
    def has_scripts(self) -> bool:
        """Check if there are any scripts available."""
        return len(self.scripts) > 0

    def set_project(self, project: Project) -> None:
        """Set the project and refresh display.

        Args:
            project: Project to show scripts for.
        """
        self._project = project
        self._selected_index = 0
        self.refresh()

    def toggle_collapsed(self) -> None:
        """Toggle section collapsed state."""
        self._collapsed = not self._collapsed
        self.refresh()

    def select_next(self) -> None:
        """Select the next script."""
        if self._collapsed:
            return
        scripts = self.scripts
        if scripts:
            self._selected_index = min(self._selected_index + 1, len(scripts) - 1)
            self.refresh()
            # Post selection message
            if self.selected_script:
                self.post_message(self.ScriptSelected(self.selected_script[1]))

    def select_previous(self) -> None:
        """Select the previous script."""
        if self._collapsed:
            return
        if self._selected_index > 0:
            self._selected_index -= 1
            self.refresh()
            # Post selection message
            if self.selected_script:
                self.post_message(self.ScriptSelected(self.selected_script[1]))

    def run_selected_script(self) -> None:
        """Run the currently selected script."""
        selected = self.selected_script
        if selected:
            keybinding, script_id, script_name = selected
            self.post_message(
                self.ScriptRunRequested(script_id, script_name, keybinding)
            )

    def run_script_by_id(self, script_id: str) -> None:
        """Run a script by its ID.

        Args:
            script_id: ID of the script to run.
        """
        for keybinding, sid, name in self.scripts:
            if sid == script_id:
                self.post_message(self.ScriptRunRequested(sid, name, keybinding))
                return
        logger.warning(f"Script not found: {script_id}")

    def run_script_by_keybinding(self, keybinding: str) -> bool:
        """Run a script by its keybinding.

        Args:
            keybinding: Keybinding to match (e.g., "s", "t").

        Returns:
            True if a script was found and run request posted, False otherwise.
        """
        for key, script_id, name in self.scripts:
            if key == keybinding:
                self.post_message(self.ScriptRunRequested(script_id, name, key))
                return True
        return False

    def get_keybindings_map(self) -> dict[str, str]:
        """Get mapping of keybindings to script IDs.

        Returns:
            Dictionary mapping keybinding to script_id.
        """
        return {key: script_id for key, script_id, _ in self.scripts if key}

    def compose(self) -> "ComposeResult":  # type: ignore[name-defined]
        """Compose the widget content."""
        from textual.app import ComposeResult

        # Section header
        collapse_icon = ">" if self._collapsed else "v"
        header_class = (
            "section-header-collapsed" if self._collapsed else "section-header"
        )
        yield Static(
            f"{collapse_icon} Scripts", classes=header_class, id="section-header"
        )

        if not self._collapsed:
            yield Vertical(id="script-container")

    def on_mount(self) -> None:
        """Initialize when mounted."""
        self.refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        if button_id and button_id.startswith("script-"):
            script_id = button_id[7:]  # Remove "script-" prefix
            self.run_script_by_id(script_id)

    def _render_script_button(
        self,
        keybinding: str | None,
        script_id: str,
        name: str,
        is_selected: bool,
    ) -> Text:
        """Render a script button label.

        Args:
            keybinding: Optional keybinding for the script.
            script_id: Script identifier.
            name: Display name.
            is_selected: Whether this script is selected.

        Returns:
            Rich Text object for the button.
        """
        text = Text()
        if keybinding:
            text.append(f"[{keybinding}] ", style="bold cyan")
        text.append(name)
        return text

    def _update_scripts_display(self, container: Vertical) -> None:
        """Update the script container with current scripts."""
        container.remove_children()

        scripts = self.scripts
        if not scripts:
            container.mount(Static("[dim]No scripts configured[/dim]", classes="no-scripts"))
            return

        # Create button row
        buttons: list[Button] = []
        for i, (keybinding, script_id, name) in enumerate(scripts):
            # Format button label
            if keybinding:
                label = f"[{keybinding}] {name}"
            else:
                label = name

            button = Button(label, id=f"script-{script_id}")
            buttons.append(button)

        container.mount(Horizontal(*buttons, id="script-buttons"))

    def refresh(self, *args: Any, **kwargs: Any) -> None:
        """Override refresh to update scripts display."""
        # Update section header
        try:
            header = self.query_one("#section-header", Static)
            collapse_icon = ">" if self._collapsed else "v"
            header.update(f"{collapse_icon} Scripts")
            header.set_class(self._collapsed, "section-header-collapsed")
            header.set_class(not self._collapsed, "section-header")
        except Exception:
            pass

        # Update scripts if not collapsed
        if not self._collapsed:
            try:
                container = self.query_one("#script-container", Vertical)
                self._update_scripts_display(container)
            except Exception:
                pass

        super().refresh(*args, **kwargs)

    def get_script_by_id(self, script_id: str) -> ProjectScript | None:
        """Get a ProjectScript by its ID.

        Args:
            script_id: Script identifier.

        Returns:
            ProjectScript if found, None otherwise.
        """
        if not self._project or not self._project.scripts:
            return None
        for script in self._project.scripts:
            if script.id == script_id:
                return script
        return None

    def get_script_count(self) -> int:
        """Get the number of available scripts.

        Returns:
            Number of scripts available.
        """
        return len(self.scripts)
