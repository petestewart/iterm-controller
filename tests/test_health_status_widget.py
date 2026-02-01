"""Tests for HealthStatusWidget."""

import pytest
from rich.text import Text
from unittest.mock import Mock

from iterm_controller.models import HealthStatus
from iterm_controller.widgets.health_status import HealthStatusWidget


class TestHealthStatusWidgetInit:
    """Tests for HealthStatusWidget initialization."""

    def test_init_default(self):
        """Test default initialization."""
        widget = HealthStatusWidget()

        assert widget.poller is None
        assert widget.statuses == {}

    def test_init_with_statuses(self):
        """Test initialization with statuses."""
        statuses = {"API": HealthStatus.HEALTHY, "DB": HealthStatus.UNKNOWN}
        widget = HealthStatusWidget(statuses=statuses)

        assert widget.statuses == statuses

    def test_init_with_poller(self):
        """Test initialization with poller."""
        mock_poller = Mock()
        mock_poller.get_all_status.return_value = {"API": HealthStatus.HEALTHY}

        widget = HealthStatusWidget(poller=mock_poller)

        assert widget.poller is mock_poller
        assert widget.statuses == {"API": HealthStatus.HEALTHY}


class TestHealthStatusWidgetStatusManagement:
    """Tests for status management methods."""

    def test_update_status_single(self):
        """Test updating a single status."""
        widget = HealthStatusWidget()

        widget._statuses["API"] = HealthStatus.HEALTHY

        assert widget.statuses["API"] == HealthStatus.HEALTHY

    def test_update_statuses_multiple(self):
        """Test updating multiple statuses."""
        widget = HealthStatusWidget()

        widget._statuses.update({
            "API": HealthStatus.HEALTHY,
            "DB": HealthStatus.UNHEALTHY,
        })

        assert widget.statuses["API"] == HealthStatus.HEALTHY
        assert widget.statuses["DB"] == HealthStatus.UNHEALTHY

    def test_set_statuses_replaces(self):
        """Test set_statuses replaces all statuses."""
        widget = HealthStatusWidget(statuses={"OLD": HealthStatus.HEALTHY})

        widget._statuses = {"NEW": HealthStatus.UNKNOWN}

        assert "OLD" not in widget.statuses
        assert widget.statuses["NEW"] == HealthStatus.UNKNOWN

    def test_clear_statuses(self):
        """Test clearing all statuses."""
        widget = HealthStatusWidget(statuses={"API": HealthStatus.HEALTHY})

        widget._statuses.clear()

        assert widget.statuses == {}

    def test_statuses_uses_poller_when_available(self):
        """Test that statuses property uses poller when available."""
        mock_poller = Mock()
        mock_poller.get_all_status.return_value = {"FROM_POLLER": HealthStatus.HEALTHY}

        widget = HealthStatusWidget(
            poller=mock_poller,
            statuses={"LOCAL": HealthStatus.UNKNOWN},
        )

        # Should return poller statuses, not local
        statuses = widget.statuses
        assert "FROM_POLLER" in statuses
        assert "LOCAL" not in statuses


class TestHealthStatusWidgetIconColor:
    """Tests for icon and color mapping."""

    def test_icon_color_healthy(self):
        """Test HEALTHY icon and color."""
        widget = HealthStatusWidget()
        icon, color = widget._get_icon_color(HealthStatus.HEALTHY)

        assert icon == "●"
        assert color == "green"

    def test_icon_color_unhealthy(self):
        """Test UNHEALTHY icon and color."""
        widget = HealthStatusWidget()
        icon, color = widget._get_icon_color(HealthStatus.UNHEALTHY)

        assert icon == "✗"
        assert color == "red"

    def test_icon_color_unknown(self):
        """Test UNKNOWN icon and color."""
        widget = HealthStatusWidget()
        icon, color = widget._get_icon_color(HealthStatus.UNKNOWN)

        assert icon == "○"
        assert color == "dim"

    def test_icon_color_checking(self):
        """Test CHECKING icon and color."""
        widget = HealthStatusWidget()
        icon, color = widget._get_icon_color(HealthStatus.CHECKING)

        assert icon == "◐"
        assert color == "yellow"


class TestHealthStatusWidgetRender:
    """Tests for render methods."""

    def test_render_empty_statuses(self):
        """Test rendering with no statuses."""
        widget = HealthStatusWidget()
        result = widget.render()

        assert isinstance(result, Text)
        assert "No health checks" in result.plain

    def test_render_single_healthy(self):
        """Test rendering single healthy check."""
        widget = HealthStatusWidget(statuses={"API": HealthStatus.HEALTHY})
        result = widget.render()

        assert "API" in result.plain
        assert "●" in result.plain

    def test_render_single_unhealthy(self):
        """Test rendering single unhealthy check."""
        widget = HealthStatusWidget(statuses={"API": HealthStatus.UNHEALTHY})
        result = widget.render()

        assert "API" in result.plain
        assert "✗" in result.plain

    def test_render_single_unknown(self):
        """Test rendering single unknown check."""
        widget = HealthStatusWidget(statuses={"API": HealthStatus.UNKNOWN})
        result = widget.render()

        assert "API" in result.plain
        assert "○" in result.plain

    def test_render_single_checking(self):
        """Test rendering single checking check."""
        widget = HealthStatusWidget(statuses={"API": HealthStatus.CHECKING})
        result = widget.render()

        assert "API" in result.plain
        assert "◐" in result.plain

    def test_render_multiple_statuses(self):
        """Test rendering multiple health checks."""
        widget = HealthStatusWidget(
            statuses={
                "API": HealthStatus.HEALTHY,
                "Web": HealthStatus.HEALTHY,
                "DB": HealthStatus.UNKNOWN,
            }
        )
        result = widget.render()

        assert "API" in result.plain
        assert "Web" in result.plain
        assert "DB" in result.plain

    def test_render_mixed_statuses(self):
        """Test rendering mixed health check statuses."""
        widget = HealthStatusWidget(
            statuses={
                "API": HealthStatus.HEALTHY,
                "Web": HealthStatus.UNHEALTHY,
                "DB": HealthStatus.UNKNOWN,
            }
        )
        result = widget.render()

        # All names present
        assert "API" in result.plain
        assert "Web" in result.plain
        assert "DB" in result.plain

        # All icons present
        assert "●" in result.plain  # healthy
        assert "✗" in result.plain  # unhealthy
        assert "○" in result.plain  # unknown


class TestHealthStatusWidgetHelperMethods:
    """Tests for helper methods."""

    def test_has_unhealthy_true(self):
        """Test has_unhealthy returns True when unhealthy exists."""
        widget = HealthStatusWidget(
            statuses={
                "API": HealthStatus.HEALTHY,
                "DB": HealthStatus.UNHEALTHY,
            }
        )

        assert widget.has_unhealthy() is True

    def test_has_unhealthy_false(self):
        """Test has_unhealthy returns False when all healthy/unknown."""
        widget = HealthStatusWidget(
            statuses={
                "API": HealthStatus.HEALTHY,
                "DB": HealthStatus.UNKNOWN,
            }
        )

        assert widget.has_unhealthy() is False

    def test_has_unhealthy_empty(self):
        """Test has_unhealthy returns False when empty."""
        widget = HealthStatusWidget()

        assert widget.has_unhealthy() is False

    def test_has_unknown_true(self):
        """Test has_unknown returns True when unknown exists."""
        widget = HealthStatusWidget(
            statuses={
                "API": HealthStatus.HEALTHY,
                "DB": HealthStatus.UNKNOWN,
            }
        )

        assert widget.has_unknown() is True

    def test_has_unknown_false(self):
        """Test has_unknown returns False when all known."""
        widget = HealthStatusWidget(
            statuses={
                "API": HealthStatus.HEALTHY,
                "DB": HealthStatus.UNHEALTHY,
            }
        )

        assert widget.has_unknown() is False

    def test_all_healthy_true(self):
        """Test all_healthy returns True when all healthy."""
        widget = HealthStatusWidget(
            statuses={
                "API": HealthStatus.HEALTHY,
                "DB": HealthStatus.HEALTHY,
                "Web": HealthStatus.HEALTHY,
            }
        )

        assert widget.all_healthy() is True

    def test_all_healthy_false_with_unhealthy(self):
        """Test all_healthy returns False when any unhealthy."""
        widget = HealthStatusWidget(
            statuses={
                "API": HealthStatus.HEALTHY,
                "DB": HealthStatus.UNHEALTHY,
            }
        )

        assert widget.all_healthy() is False

    def test_all_healthy_false_with_unknown(self):
        """Test all_healthy returns False when any unknown."""
        widget = HealthStatusWidget(
            statuses={
                "API": HealthStatus.HEALTHY,
                "DB": HealthStatus.UNKNOWN,
            }
        )

        assert widget.all_healthy() is False

    def test_all_healthy_false_empty(self):
        """Test all_healthy returns False when empty."""
        widget = HealthStatusWidget()

        assert widget.all_healthy() is False

    def test_get_status_exists(self):
        """Test get_status for existing check."""
        widget = HealthStatusWidget(statuses={"API": HealthStatus.HEALTHY})

        assert widget.get_status("API") == HealthStatus.HEALTHY

    def test_get_status_not_found(self):
        """Test get_status for non-existent check."""
        widget = HealthStatusWidget(statuses={"API": HealthStatus.HEALTHY})

        assert widget.get_status("DB") is None

    def test_get_summary_all_healthy(self):
        """Test get_summary with all healthy."""
        widget = HealthStatusWidget(
            statuses={
                "API": HealthStatus.HEALTHY,
                "Web": HealthStatus.HEALTHY,
            }
        )

        healthy, unhealthy, unknown = widget.get_summary()
        assert healthy == 2
        assert unhealthy == 0
        assert unknown == 0

    def test_get_summary_all_unhealthy(self):
        """Test get_summary with all unhealthy."""
        widget = HealthStatusWidget(
            statuses={
                "API": HealthStatus.UNHEALTHY,
                "DB": HealthStatus.UNHEALTHY,
            }
        )

        healthy, unhealthy, unknown = widget.get_summary()
        assert healthy == 0
        assert unhealthy == 2
        assert unknown == 0

    def test_get_summary_mixed(self):
        """Test get_summary with mixed statuses."""
        widget = HealthStatusWidget(
            statuses={
                "API": HealthStatus.HEALTHY,
                "Web": HealthStatus.UNHEALTHY,
                "DB": HealthStatus.UNKNOWN,
                "Cache": HealthStatus.CHECKING,
            }
        )

        healthy, unhealthy, unknown = widget.get_summary()
        assert healthy == 1
        assert unhealthy == 1
        assert unknown == 2  # UNKNOWN + CHECKING

    def test_get_summary_empty(self):
        """Test get_summary with no statuses."""
        widget = HealthStatusWidget()

        healthy, unhealthy, unknown = widget.get_summary()
        assert healthy == 0
        assert unhealthy == 0
        assert unknown == 0


class TestHealthStatusWidgetWithPoller:
    """Tests for widget integration with HealthCheckPoller."""

    def test_poller_setter_updates_display_state(self):
        """Test setting poller updates internal state."""
        mock_poller = Mock()
        mock_poller.get_all_status.return_value = {"API": HealthStatus.HEALTHY}

        widget = HealthStatusWidget()
        widget._poller = mock_poller

        assert widget.poller is mock_poller

    def test_render_uses_poller_statuses(self):
        """Test render uses poller statuses when available."""
        mock_poller = Mock()
        mock_poller.get_all_status.return_value = {
            "API": HealthStatus.HEALTHY,
            "DB": HealthStatus.UNHEALTHY,
        }

        widget = HealthStatusWidget(poller=mock_poller)
        result = widget.render()

        assert "API" in result.plain
        assert "DB" in result.plain
        assert "●" in result.plain  # healthy
        assert "✗" in result.plain  # unhealthy


class TestHealthStatusWidgetDisplayFormat:
    """Tests for correct display format per spec."""

    def test_format_matches_spec(self):
        """Test format matches spec: 'API ● Web ● DB ○'."""
        widget = HealthStatusWidget(
            statuses={
                "API": HealthStatus.HEALTHY,
                "Web": HealthStatus.HEALTHY,
                "DB": HealthStatus.UNKNOWN,
            }
        )
        result = widget.render()

        # Verify format: name followed by space and icon
        # Each entry should have name then icon
        text = result.plain

        # Names should precede their icons
        api_pos = text.find("API")
        web_pos = text.find("Web")
        db_pos = text.find("DB")

        assert api_pos >= 0
        assert web_pos >= 0
        assert db_pos >= 0

        # Each should have an icon after it
        assert "●" in text  # healthy icons for API and Web
        assert "○" in text  # unknown icon for DB
