"""Environment edit modal for editing environment variables.

Provides a text area for editing KEY=value pairs.
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea


class EnvEditModal(ModalScreen[dict[str, str] | None]):
    """Modal for editing environment variables.

    Displays a text area with KEY=value pairs for editing.
    Returns a dict of environment variables on save, or None on cancel.
    """

    DEFAULT_CSS = """
    EnvEditModal {
        align: center middle;
    }

    EnvEditModal > Container {
        width: 70;
        height: 30;
        border: thick $background 80%;
        background: $surface;
        padding: 1 2;
    }

    EnvEditModal .modal-title {
        text-style: bold;
        color: $primary;
        text-align: center;
        margin-bottom: 1;
    }

    EnvEditModal .hint {
        color: $text-muted;
        margin-bottom: 1;
    }

    EnvEditModal #env-editor {
        height: 18;
        border: solid $surface-lighten-1;
        margin-bottom: 1;
    }

    EnvEditModal .error {
        color: $error;
        margin-bottom: 1;
    }

    EnvEditModal #button-row {
        height: auto;
        align: center middle;
    }

    EnvEditModal #button-row Button {
        margin: 0 1;
        min-width: 12;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
    ]

    def __init__(
        self,
        env_vars: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the environment edit modal.

        Args:
            env_vars: Initial environment variables to edit.
            **kwargs: Additional arguments passed to ModalScreen.
        """
        super().__init__(**kwargs)
        self._env_vars = env_vars or {}

    @property
    def env_vars(self) -> dict[str, str]:
        """Get the initial environment variables."""
        return self._env_vars

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        yield Container(
            Static("Edit Environment Variables", classes="modal-title"),
            Static("Enter one KEY=value pair per line", classes="hint"),
            TextArea(id="env-editor"),
            Static("", id="error-message", classes="error"),
            Horizontal(
                Button("Cancel", variant="default", id="cancel-btn"),
                Button("Save", variant="primary", id="save-btn"),
                id="button-row",
            ),
        )

    def on_mount(self) -> None:
        """Initialize the modal content."""
        self._load_env_vars()
        # Focus the editor
        self.query_one("#env-editor", TextArea).focus()

    def _load_env_vars(self) -> None:
        """Load environment variables into the editor."""
        editor = self.query_one("#env-editor", TextArea)
        env_content = "\n".join(
            f"{key}={value}"
            for key, value in sorted(self._env_vars.items())
        )
        editor.load_text(env_content)

    def _parse_env_vars(self) -> dict[str, str] | None:
        """Parse environment variables from editor content.

        Returns:
            Dict of environment variables, or None if parsing fails.
        """
        editor = self.query_one("#env-editor", TextArea)
        content = editor.text
        error_message = self.query_one("#error-message", Static)

        result: dict[str, str] = {}
        lines = content.strip().split("\n")

        for i, line in enumerate(lines, 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Parse KEY=value
            if "=" not in line:
                error_message.update(f"Line {i}: Missing '=' in '{line}'")
                return None

            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()

            # Validate key
            if not key:
                error_message.update(f"Line {i}: Empty key")
                return None

            if not self._is_valid_env_key(key):
                error_message.update(
                    f"Line {i}: Invalid key '{key}' (use letters, numbers, underscores)"
                )
                return None

            # Remove quotes from value if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]

            result[key] = value

        error_message.update("")
        return result

    def _is_valid_env_key(self, key: str) -> bool:
        """Check if a string is a valid environment variable key.

        Valid keys start with a letter or underscore and contain only
        letters, numbers, and underscores.
        """
        if not key:
            return False
        if not (key[0].isalpha() or key[0] == "_"):
            return False
        return all(c.isalnum() or c == "_" for c in key)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button pressed event.
        """
        if event.button.id == "cancel-btn":
            self.dismiss(None)
        elif event.button.id == "save-btn":
            self._do_save()

    def action_cancel(self) -> None:
        """Cancel and close the modal."""
        self.dismiss(None)

    def action_save(self) -> None:
        """Save the environment variables."""
        self._do_save()

    def _do_save(self) -> None:
        """Validate and save the environment variables."""
        result = self._parse_env_vars()
        if result is not None:
            self.dismiss(result)
        else:
            # Error message already set by _parse_env_vars
            pass
