"""GitHub Actions modal.

Modal dialog for viewing GitHub Actions workflow runs and their status.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from iterm_controller.models import WorkflowRun

if TYPE_CHECKING:
    from iterm_controller.app import ItermControllerApp


class GitHubActionsModal(ModalScreen[None]):
    """Modal for viewing GitHub Actions workflow runs.

    Displays recent workflow runs with status indicators.
    Supports refresh and graceful error handling.

    Example display:
        ┌────────────────────────────────────────────────┐
        │  GitHub Actions                                │
        ├────────────────────────────────────────────────┤
        │  Workflow          Branch     Status    Time   │
        │  ─────────────────────────────────────────────│
        │  CI                main       ✓         2m ago │
        │  Tests             feature    ●         running│
        │  Deploy            main       ✗         5m ago │
        ├────────────────────────────────────────────────┤
        │  [R] Refresh                    [Esc] Close    │
        └────────────────────────────────────────────────┘
    """

    BINDINGS = [
        Binding("r", "refresh", "Refresh"),
        Binding("escape", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    GitHubActionsModal {
        align: center middle;
    }

    GitHubActionsModal > Container {
        width: 80;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }

    GitHubActionsModal #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: $text;
    }

    GitHubActionsModal #loading {
        text-align: center;
        color: $text-muted;
    }

    GitHubActionsModal #error {
        text-align: center;
        color: $error;
        margin-bottom: 1;
    }

    GitHubActionsModal #runs-table {
        height: auto;
        max-height: 20;
        margin-bottom: 1;
    }

    GitHubActionsModal #button-row {
        width: 100%;
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    GitHubActionsModal #button-row Button {
        margin: 0 1;
    }
    """

    def __init__(self, project_path: str) -> None:
        """Initialize the GitHub Actions modal.

        Args:
            project_path: Path to the project directory.
        """
        super().__init__()
        self._project_path = project_path
        self._runs: list[WorkflowRun] = []
        self._loading = True
        self._error: str | None = None

    def compose(self) -> ComposeResult:
        """Compose the modal layout."""
        yield Container(
            Static("GitHub Actions", id="title"),
            Static("[dim]Loading workflow runs...[/dim]", id="loading"),
            Static("", id="error"),
            DataTable(id="runs-table"),
            Horizontal(
                Button("Refresh [R]", id="refresh-button", variant="primary"),
                Button("Close [Esc]", id="close-button", variant="default"),
                id="button-row",
            ),
            id="dialog",
        )

    async def on_mount(self) -> None:
        """Load workflow runs on mount."""
        # Set up the table columns
        table = self.query_one("#runs-table", DataTable)
        table.add_columns("Workflow", "Branch", "Status", "Time")

        # Hide error initially
        error_widget = self.query_one("#error", Static)
        error_widget.display = False

        await self._load_runs()

    async def _load_runs(self) -> None:
        """Load workflow runs from GitHub."""
        self._loading = True
        self._error = None

        # Show loading indicator
        loading = self.query_one("#loading", Static)
        loading.display = True

        # Hide error
        error_widget = self.query_one("#error", Static)
        error_widget.display = False

        app: ItermControllerApp = self.app  # type: ignore[assignment]

        if not app.github.available:
            self._error = app.github.error_message or "GitHub integration unavailable"
            self._loading = False
            self._update_display()
            return

        try:
            runs_data = await app.github.get_workflow_runs(self._project_path)
            self._runs = [
                WorkflowRun(
                    id=r["id"],
                    name=r["name"],
                    status=r["status"],
                    conclusion=r.get("conclusion"),
                    created_at=r["created_at"],
                    branch=r["branch"],
                )
                for r in runs_data
            ]
            self._error = None
        except Exception as e:
            self._error = f"Failed to load runs: {e}"
            self._runs = []

        self._loading = False
        self._update_display()

    def _update_display(self) -> None:
        """Update the display after loading."""
        loading = self.query_one("#loading", Static)
        loading.display = False

        error_widget = self.query_one("#error", Static)

        if self._error:
            error_widget.update(f"[red]{self._error}[/red]")
            error_widget.display = True
            return

        error_widget.display = False

        # Clear and repopulate table
        table = self.query_one("#runs-table", DataTable)
        table.clear()

        if not self._runs:
            table.add_row("No workflow runs found", "", "", "")
            return

        for run in self._runs:
            status_icon = self._get_status_icon(run)
            time_str = self._format_time(run.created_at)

            table.add_row(
                run.name,
                run.branch,
                status_icon,
                time_str,
            )

    def _get_status_icon(self, run: WorkflowRun) -> str:
        """Get a status icon for a workflow run.

        Args:
            run: The workflow run.

        Returns:
            Rich-formatted status icon.
        """
        # If completed, show conclusion
        if run.status == "completed":
            if run.conclusion == "success":
                return "[green]✓[/green]"
            elif run.conclusion == "failure":
                return "[red]✗[/red]"
            elif run.conclusion == "cancelled":
                return "[yellow]○[/yellow]"
            elif run.conclusion == "skipped":
                return "[dim]⊘[/dim]"
            else:
                return "[dim]?[/dim]"

        # In progress or queued
        if run.status == "in_progress":
            return "[yellow]●[/yellow]"
        elif run.status == "queued":
            return "[dim]◌[/dim]"

        return "[dim]○[/dim]"

    def _format_time(self, timestamp: str) -> str:
        """Format a timestamp as relative time.

        Args:
            timestamp: ISO format timestamp.

        Returns:
            Human-readable relative time string.
        """
        try:
            # Parse ISO format timestamp
            # Handle formats like "2024-01-15T10:30:00Z" or "2024-01-15T10:30:00+00:00"
            if timestamp.endswith("Z"):
                timestamp = timestamp[:-1] + "+00:00"
            dt = datetime.fromisoformat(timestamp)

            now = datetime.now(dt.tzinfo)
            diff = now - dt

            seconds = diff.total_seconds()

            if seconds < 60:
                return "just now"
            elif seconds < 3600:
                mins = int(seconds / 60)
                return f"{mins}m ago"
            elif seconds < 86400:
                hours = int(seconds / 3600)
                return f"{hours}h ago"
            else:
                days = int(seconds / 86400)
                return f"{days}d ago"
        except (ValueError, TypeError):
            return timestamp

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id

        if button_id == "close-button":
            self.dismiss(None)
        elif button_id == "refresh-button":
            await self._load_runs()

    async def action_refresh(self) -> None:
        """Refresh workflow runs."""
        await self._load_runs()

    def action_dismiss(self) -> None:
        """Close the modal."""
        self.dismiss(None)
