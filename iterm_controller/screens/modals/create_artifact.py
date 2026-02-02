"""Create artifact modal for missing planning artifacts.

Shows creation options when user presses Enter on a missing artifact:
- Create with Agent: Spawn a Claude session with the appropriate slash command
- Create Manually: Create an empty file and open in editor

See specs/plan-mode.md for specification.
"""

from __future__ import annotations

from typing import Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


# Result type for the modal
CreateArtifactResult = Literal["agent", "manual", "cancel"]


class CreateArtifactModal(ModalScreen[CreateArtifactResult]):
    """Modal for choosing how to create a missing artifact.

    Offers two creation paths:
    - Agent: Spawn a Claude session with the appropriate command
    - Manual: Create an empty file and open in the configured editor
    """

    BINDINGS = [
        Binding("a", "create_with_agent", "Agent"),
        Binding("m", "create_manually", "Manual"),
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    CreateArtifactModal {
        align: center middle;
    }

    CreateArtifactModal #dialog {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    CreateArtifactModal #title {
        text-style: bold;
        color: $primary;
        padding-bottom: 1;
    }

    CreateArtifactModal #message {
        padding-bottom: 1;
    }

    CreateArtifactModal #artifact-name {
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
    }

    CreateArtifactModal #options-title {
        padding-bottom: 1;
    }

    CreateArtifactModal #option-agent {
        padding-left: 2;
        padding-bottom: 0;
    }

    CreateArtifactModal #option-manual {
        padding-left: 2;
        padding-bottom: 1;
    }

    CreateArtifactModal #buttons {
        margin-top: 1;
        height: 3;
        align: center middle;
    }

    CreateArtifactModal Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        artifact_name: str,
        agent_command: str | None = None,
    ) -> None:
        """Initialize the modal.

        Args:
            artifact_name: Name of the artifact to create (e.g., "PRD.md").
            agent_command: The Claude command to use for agent creation (e.g., "claude /prd").
                           If None, the agent option will be disabled.
        """
        super().__init__()
        self._artifact_name = artifact_name
        self._agent_command = agent_command

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        agent_desc = ""
        if self._agent_command:
            # Extract the slash command part for display
            cmd_parts = self._agent_command.split()
            if len(cmd_parts) > 1:
                slash_cmd = cmd_parts[1]
                agent_desc = f" (runs {slash_cmd})"

        yield Vertical(
            Static("Create Artifact", id="title"),
            Static(f"The artifact does not exist:", id="message"),
            Static(f"  {self._artifact_name}", id="artifact-name"),
            Static("How would you like to create it?", id="options-title"),
            Static(f"[A] Agent: Spawn Claude session{agent_desc}", id="option-agent"),
            Static("[M] Manual: Create file and open in editor", id="option-manual"),
            Horizontal(
                Button("[A] Agent", variant="success", id="agent", disabled=not self._agent_command),
                Button("[M] Manual", variant="primary", id="manual"),
                Button("[Esc] Cancel", variant="default", id="cancel"),
                id="buttons",
            ),
            id="dialog",
        )

    def on_mount(self) -> None:
        """Focus the appropriate button when mounted."""
        # Focus agent button if available, otherwise manual
        if self._agent_command:
            self.query_one("#agent", Button).focus()
        else:
            self.query_one("#manual", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: The button pressed event.
        """
        if event.button.id == "agent":
            self.dismiss("agent")
        elif event.button.id == "manual":
            self.dismiss("manual")
        elif event.button.id == "cancel":
            self.dismiss("cancel")

    def action_create_with_agent(self) -> None:
        """Create the artifact with Claude agent."""
        if self._agent_command:
            self.dismiss("agent")

    def action_create_manually(self) -> None:
        """Create the artifact manually."""
        self.dismiss("manual")

    def action_cancel(self) -> None:
        """Cancel and dismiss."""
        self.dismiss("cancel")
