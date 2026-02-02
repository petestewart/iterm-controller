"""Health check status indicators widget.

Displays health check status in the project dashboard with color-coded
indicators for each configured health check endpoint.

Display format:
    Health: API ● Web ● DB ○

Status icons:
- ● (green) - Healthy
- ✗ (red) - Unhealthy
- ○ (dim) - Unknown/Not checked
- ◐ (yellow) - Checking
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.text import Text
from textual.widgets import Static

from iterm_controller.models import HealthStatus

if TYPE_CHECKING:
    from iterm_controller.health_checker import HealthCheckPoller


class HealthStatusWidget(Static):
    """Displays health check status indicators.

    This widget shows the status of configured health check endpoints
    with color-coded icons. It can be updated either via direct status
    dictionary updates or through an associated HealthCheckPoller.

    Example display:
        API ● Web ● DB ○

    Where:
    - ● (green) = Healthy
    - ✗ (red) = Unhealthy
    - ○ (dim) = Unknown
    - ◐ (yellow) = Checking

    Attributes:
        DEFAULT_CSS: Widget styling.
    """

    DEFAULT_CSS = """
    HealthStatusWidget {
        height: auto;
        min-height: 1;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        poller: HealthCheckPoller | None = None,
        statuses: dict[str, HealthStatus] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the health status widget.

        Args:
            poller: Optional HealthCheckPoller to get status from.
            statuses: Optional initial status dictionary.
            **kwargs: Additional arguments passed to Static.
        """
        super().__init__(**kwargs)
        self._poller = poller
        self._statuses: dict[str, HealthStatus] = statuses or {}

    def on_mount(self) -> None:
        """Initialize the health status content when mounted."""
        self.update(self._render_status())

    @property
    def poller(self) -> HealthCheckPoller | None:
        """Get the associated poller."""
        return self._poller

    @poller.setter
    def poller(self, value: HealthCheckPoller | None) -> None:
        """Set the associated poller and refresh display."""
        self._poller = value
        self.refresh_display()

    @property
    def statuses(self) -> dict[str, HealthStatus]:
        """Get current health statuses.

        Returns the statuses from the poller if available,
        otherwise returns the local status dictionary.
        """
        if self._poller:
            return self._poller.get_all_status()
        return self._statuses.copy()

    def update_status(self, name: str, status: HealthStatus) -> None:
        """Update status for a single health check.

        Args:
            name: Health check name.
            status: New status value.
        """
        self._statuses[name] = status
        self.refresh_display()

    def update_statuses(self, statuses: dict[str, HealthStatus]) -> None:
        """Update multiple health check statuses.

        Args:
            statuses: Dictionary mapping check names to statuses.
        """
        self._statuses.update(statuses)
        self.refresh_display()

    def set_statuses(self, statuses: dict[str, HealthStatus]) -> None:
        """Replace all health check statuses.

        Args:
            statuses: New status dictionary.
        """
        self._statuses = statuses.copy()
        self.refresh_display()

    def clear_statuses(self) -> None:
        """Clear all health check statuses."""
        self._statuses.clear()
        self.refresh_display()

    def refresh_display(self) -> None:
        """Refresh the widget display."""
        self.update(self._render_status())

    def _get_icon_color(self, status: HealthStatus) -> tuple[str, str]:
        """Get icon and color for a status.

        Args:
            status: Health check status.

        Returns:
            Tuple of (icon, color) for Rich styling.
        """
        status_map = {
            HealthStatus.UNKNOWN: ("○", "dim"),
            HealthStatus.CHECKING: ("◐", "yellow"),
            HealthStatus.HEALTHY: ("●", "green"),
            HealthStatus.UNHEALTHY: ("✗", "red"),
        }
        return status_map.get(status, ("?", "dim"))

    def _render_status(self) -> Text:
        """Render the health status display.

        Returns:
            Text object with formatted health status indicators.
        """
        statuses = self.statuses

        if not statuses:
            return Text("No health checks", style="dim")

        text = Text()
        items = list(statuses.items())

        for i, (name, status) in enumerate(items):
            if i > 0:
                text.append(" ")

            icon, color = self._get_icon_color(status)
            text.append(name, style="bold")
            text.append(" ")
            text.append(icon, style=color)

        return text

    def render(self) -> Text:
        """Render the widget content.

        Returns:
            Text object to display.
        """
        return self._render_status()

    def has_unhealthy(self) -> bool:
        """Check if any health check is unhealthy.

        Returns:
            True if any check has UNHEALTHY status.
        """
        return any(s == HealthStatus.UNHEALTHY for s in self.statuses.values())

    def has_unknown(self) -> bool:
        """Check if any health check is unknown.

        Returns:
            True if any check has UNKNOWN status.
        """
        return any(s == HealthStatus.UNKNOWN for s in self.statuses.values())

    def all_healthy(self) -> bool:
        """Check if all health checks are healthy.

        Returns:
            True if all checks have HEALTHY status.
        """
        statuses = self.statuses
        if not statuses:
            return False
        return all(s == HealthStatus.HEALTHY for s in statuses.values())

    def get_status(self, name: str) -> HealthStatus | None:
        """Get status for a specific health check.

        Args:
            name: Health check name.

        Returns:
            Status if found, None otherwise.
        """
        return self.statuses.get(name)

    def get_summary(self) -> tuple[int, int, int]:
        """Get summary counts of health statuses.

        Returns:
            Tuple of (healthy_count, unhealthy_count, unknown_count).
        """
        statuses = self.statuses
        healthy = sum(1 for s in statuses.values() if s == HealthStatus.HEALTHY)
        unhealthy = sum(1 for s in statuses.values() if s == HealthStatus.UNHEALTHY)
        unknown = sum(
            1 for s in statuses.values()
            if s in (HealthStatus.UNKNOWN, HealthStatus.CHECKING)
        )
        return (healthy, unhealthy, unknown)
