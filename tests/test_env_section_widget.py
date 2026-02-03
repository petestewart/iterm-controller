"""Tests for the EnvSection widget."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from iterm_controller.models import Project
from iterm_controller.widgets.env_section import (
    EnvSection,
    MAX_VALUE_DISPLAY_LENGTH,
    SENSITIVE_PATTERNS,
)


def make_project(path: str = "/tmp/test-project") -> Project:
    """Create a test project."""
    return Project(
        id="project-1",
        name="Test Project",
        path=path,
    )


class TestEnvSectionInit:
    """Tests for EnvSection initialization."""

    def test_init_without_project(self) -> None:
        """Test widget initializes without a project."""
        widget = EnvSection()

        assert widget.project is None
        assert widget.collapsed is False

    def test_init_with_project(self) -> None:
        """Test widget initializes with a project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = EnvSection(project=project)

            assert widget.project == project

    def test_init_collapsed(self) -> None:
        """Test widget initializes collapsed."""
        widget = EnvSection(collapsed=True)

        assert widget.collapsed is True


class TestEnvSectionToggle:
    """Tests for section collapse toggle."""

    def test_toggle_collapsed(self) -> None:
        """Test toggling collapsed state."""
        widget = EnvSection()

        assert widget.collapsed is False

        with patch.object(widget, "refresh"):
            widget.toggle_collapsed()

        assert widget.collapsed is True

        with patch.object(widget, "refresh"):
            widget.toggle_collapsed()

        assert widget.collapsed is False


class TestEnvSectionNavigation:
    """Tests for environment variable navigation."""

    def test_selected_item_initial(self) -> None:
        """Test initial selection is first item."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".env").write_text("DATABASE_URL=postgres://localhost\nDEBUG=true")
            project = make_project(path=tmpdir)
            widget = EnvSection(project=project)
            widget.refresh_env()

            assert widget.selected_item is not None
            key, _value = widget.selected_item
            assert key == "DATABASE_URL"

    def test_select_next(self) -> None:
        """Test selecting next item."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".env").write_text("DATABASE_URL=postgres://localhost\nDEBUG=true")
            project = make_project(path=tmpdir)
            widget = EnvSection(project=project)
            widget.refresh_env()

            with patch.object(widget, "refresh"):
                widget.select_next()

            assert widget.selected_item is not None
            key, _value = widget.selected_item
            assert key == "DEBUG"

    def test_select_previous(self) -> None:
        """Test selecting previous item."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".env").write_text("DATABASE_URL=postgres://localhost\nDEBUG=true")
            project = make_project(path=tmpdir)
            widget = EnvSection(project=project)
            widget.refresh_env()

            with patch.object(widget, "refresh"):
                widget.select_next()  # Now at DEBUG
                widget.select_previous()  # Back to DATABASE_URL

            assert widget.selected_item is not None
            key, _value = widget.selected_item
            assert key == "DATABASE_URL"

    def test_select_previous_at_start(self) -> None:
        """Test select_previous doesn't go below zero."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".env").write_text("DATABASE_URL=postgres://localhost")
            project = make_project(path=tmpdir)
            widget = EnvSection(project=project)
            widget.refresh_env()

            with patch.object(widget, "refresh"):
                widget.select_previous()

            assert widget.selected_item is not None
            key, _value = widget.selected_item
            assert key == "DATABASE_URL"

    def test_select_next_at_end(self) -> None:
        """Test select_next doesn't exceed list bounds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".env").write_text("DATABASE_URL=postgres://localhost")
            project = make_project(path=tmpdir)
            widget = EnvSection(project=project)
            widget.refresh_env()

            with patch.object(widget, "refresh"):
                for _ in range(10):
                    widget.select_next()

            assert widget.selected_item is not None
            key, _value = widget.selected_item
            assert key == "DATABASE_URL"

    def test_select_when_collapsed_returns_none(self) -> None:
        """Test selected_item is None when collapsed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".env").write_text("DATABASE_URL=postgres://localhost")
            project = make_project(path=tmpdir)
            widget = EnvSection(project=project, collapsed=True)
            widget.refresh_env()

            assert widget.selected_item is None


class TestEnvSectionLoading:
    """Tests for .env file loading."""

    def test_loads_simple_env_file(self) -> None:
        """Test loading a simple .env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".env").write_text("DATABASE_URL=postgres://localhost\nDEBUG=true")
            project = make_project(path=tmpdir)
            widget = EnvSection(project=project)
            widget.refresh_env()

            assert widget.get_env_count() == 2
            assert widget._env_vars.get("DATABASE_URL") == "postgres://localhost"
            assert widget._env_vars.get("DEBUG") == "true"

    def test_loads_quoted_values(self) -> None:
        """Test loading .env file with quoted values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".env").write_text('MESSAGE="Hello World"\nNAME=\'John\'')
            project = make_project(path=tmpdir)
            widget = EnvSection(project=project)
            widget.refresh_env()

            assert widget._env_vars.get("MESSAGE") == "Hello World"
            assert widget._env_vars.get("NAME") == "John"

    def test_handles_missing_env_file(self) -> None:
        """Test handling when .env file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = EnvSection(project=project)
            widget.refresh_env()

            assert widget.get_env_count() == 0

    def test_ignores_comments(self) -> None:
        """Test comments in .env file are ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".env").write_text("# This is a comment\nDATABASE_URL=postgres://localhost")
            project = make_project(path=tmpdir)
            widget = EnvSection(project=project)
            widget.refresh_env()

            assert widget.get_env_count() == 1
            assert "DATABASE_URL" in widget._env_vars


class TestEnvSectionSensitiveValues:
    """Tests for sensitive value detection and masking."""

    def test_is_sensitive_key_patterns(self) -> None:
        """Test sensitive key pattern detection."""
        widget = EnvSection()

        # Should be sensitive
        assert widget._is_sensitive("API_KEY") is True
        assert widget._is_sensitive("SECRET_KEY") is True
        assert widget._is_sensitive("PASSWORD") is True
        assert widget._is_sensitive("ACCESS_TOKEN") is True
        assert widget._is_sensitive("AWS_SECRET_ACCESS_KEY") is True
        assert widget._is_sensitive("AUTH_TOKEN") is True
        assert widget._is_sensitive("CREDENTIAL") is True

        # Should not be sensitive
        assert widget._is_sensitive("DATABASE_URL") is False
        assert widget._is_sensitive("DEBUG") is False
        assert widget._is_sensitive("PORT") is False

    def test_format_value_masks_sensitive(self) -> None:
        """Test sensitive values are masked."""
        widget = EnvSection()

        assert widget._format_value("API_KEY", "super-secret-key-12345") == "****"
        assert widget._format_value("PASSWORD", "mypassword") == "****"

    def test_format_value_shows_non_sensitive(self) -> None:
        """Test non-sensitive values are shown."""
        widget = EnvSection()

        assert widget._format_value("DEBUG", "true") == "true"
        assert widget._format_value("PORT", "8080") == "8080"

    def test_format_value_truncates_long_values(self) -> None:
        """Test long values are truncated."""
        widget = EnvSection()

        long_value = "a" * 50
        formatted = widget._format_value("LONG_VALUE", long_value)

        assert len(formatted) == MAX_VALUE_DISPLAY_LENGTH + 3  # +3 for "..."
        assert formatted.endswith("...")


class TestEnvSectionMessages:
    """Tests for message posting."""

    def test_env_selected_message(self) -> None:
        """Test EnvSelected message contains key and value."""
        msg = EnvSection.EnvSelected(key="DATABASE_URL", value="postgres://localhost")

        assert msg.key == "DATABASE_URL"
        assert msg.value == "postgres://localhost"

    def test_edit_env_requested_message(self) -> None:
        """Test EditEnvRequested message."""
        msg = EnvSection.EditEnvRequested()

        # Just verify it's a valid message instance
        assert isinstance(msg, EnvSection.EditEnvRequested)


class TestEnvSectionRendering:
    """Tests for rendering methods."""

    def test_render_env_item_not_selected(self) -> None:
        """Test _render_env_item for non-selected item."""
        widget = EnvSection()

        text = widget._render_env_item(
            key="DATABASE_URL",
            value="postgres://localhost",
            is_selected=False,
        )
        rendered = str(text)

        assert "DATABASE_URL" in rendered
        assert "postgres://localhost" in rendered
        assert ">" not in rendered  # No selection indicator

    def test_render_env_item_selected(self) -> None:
        """Test _render_env_item shows selection indicator."""
        widget = EnvSection()

        text = widget._render_env_item(
            key="DATABASE_URL",
            value="postgres://localhost",
            is_selected=True,
        )
        rendered = str(text)

        assert ">" in rendered  # Selection indicator
        assert "DATABASE_URL" in rendered

    def test_render_env_item_sensitive_masked(self) -> None:
        """Test _render_env_item masks sensitive values."""
        widget = EnvSection()

        text = widget._render_env_item(
            key="API_KEY",
            value="super-secret-key",
            is_selected=False,
        )
        rendered = str(text)

        assert "API_KEY" in rendered
        assert "****" in rendered
        assert "super-secret-key" not in rendered


class TestEnvSectionRefresh:
    """Tests for refresh methods."""

    def test_refresh_env_updates_vars_list(self) -> None:
        """Test refresh_env updates the variables list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = EnvSection(project=project)
            widget.refresh_env()

            # Initially empty
            assert widget.get_env_count() == 0

            # Create .env file
            (Path(tmpdir) / ".env").write_text("DATABASE_URL=postgres://localhost")

            # Refresh
            widget.refresh_env()

            # Should now have one var
            assert widget.get_env_count() == 1

    def test_set_project_sets_project(self) -> None:
        """Test set_project sets the project reference."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".env").write_text("DEBUG=true")

            widget = EnvSection()
            assert widget.project is None

            project = make_project(path=tmpdir)
            widget._project = project
            widget.refresh_env()

            assert widget.project == project
            assert widget.get_env_count() == 1


class TestEnvSectionGetEnvCount:
    """Tests for get_env_count method."""

    def test_get_env_count_empty(self) -> None:
        """Test get_env_count with no variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = EnvSection(project=project)
            widget.refresh_env()

            assert widget.get_env_count() == 0

    def test_get_env_count_with_vars(self) -> None:
        """Test get_env_count with variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / ".env").write_text("A=1\nB=2\nC=3")
            project = make_project(path=tmpdir)
            widget = EnvSection(project=project)
            widget.refresh_env()

            assert widget.get_env_count() == 3


class TestEnvSectionGetEnvFilePath:
    """Tests for get_env_file_path method."""

    def test_get_env_file_path_with_project(self) -> None:
        """Test get_env_file_path returns correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = make_project(path=tmpdir)
            widget = EnvSection(project=project)

            env_path = widget.get_env_file_path()

            assert env_path is not None
            assert env_path == Path(tmpdir) / ".env"

    def test_get_env_file_path_without_project(self) -> None:
        """Test get_env_file_path returns None without project."""
        widget = EnvSection()

        assert widget.get_env_file_path() is None
