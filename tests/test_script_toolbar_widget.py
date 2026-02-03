"""Tests for the ScriptToolbar widget."""

from unittest.mock import patch

import pytest

from iterm_controller.models import Project, ProjectScript, SessionType
from iterm_controller.widgets.script_toolbar import DEFAULT_SCRIPTS, ScriptToolbar


def make_project(
    path: str = "/tmp/test-project",
    scripts: list[ProjectScript] | None = None,
) -> Project:
    """Create a test project."""
    return Project(
        id="project-1",
        name="Test Project",
        path=path,
        scripts=scripts,
    )


def make_script(
    script_id: str,
    name: str,
    command: str = "echo hello",
    keybinding: str | None = None,
    show_in_toolbar: bool = True,
) -> ProjectScript:
    """Create a test script."""
    return ProjectScript(
        id=script_id,
        name=name,
        command=command,
        keybinding=keybinding,
        show_in_toolbar=show_in_toolbar,
    )


class TestScriptToolbarInit:
    """Tests for ScriptToolbar initialization."""

    def test_init_without_project(self) -> None:
        """Test widget initializes without a project."""
        widget = ScriptToolbar()

        assert widget.project is None
        assert widget.collapsed is False
        assert widget.has_scripts is True  # Has default scripts

    def test_init_with_project(self) -> None:
        """Test widget initializes with a project."""
        project = make_project()
        widget = ScriptToolbar(project=project)

        assert widget.project == project

    def test_init_collapsed(self) -> None:
        """Test widget initializes collapsed."""
        widget = ScriptToolbar(collapsed=True)

        assert widget.collapsed is True

    def test_init_with_project_scripts(self) -> None:
        """Test widget uses project scripts when available."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
            make_script("deploy", "Deploy", keybinding="d"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        assert widget.get_script_count() == 2


class TestScriptToolbarScripts:
    """Tests for scripts property and defaults."""

    def test_default_scripts_used_when_no_project(self) -> None:
        """Test default scripts are used when no project."""
        widget = ScriptToolbar()

        assert widget.scripts == [
            (key, script_id, name) for key, script_id, name in DEFAULT_SCRIPTS
        ]

    def test_default_scripts_used_when_project_has_no_scripts(self) -> None:
        """Test default scripts are used when project has no scripts."""
        project = make_project(scripts=None)
        widget = ScriptToolbar(project=project)

        assert widget.scripts == [
            (key, script_id, name) for key, script_id, name in DEFAULT_SCRIPTS
        ]

    def test_project_scripts_used_when_available(self) -> None:
        """Test project scripts are used when available."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
            make_script("deploy", "Deploy", keybinding="d"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        assert widget.scripts == [
            ("t", "test", "Test Suite"),
            ("d", "deploy", "Deploy"),
        ]

    def test_scripts_without_keybinding(self) -> None:
        """Test scripts without keybinding are included."""
        scripts = [
            make_script("manual", "Manual Script", keybinding=None),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        assert widget.scripts == [
            (None, "manual", "Manual Script"),
        ]

    def test_hidden_scripts_excluded(self) -> None:
        """Test scripts with show_in_toolbar=False are excluded."""
        scripts = [
            make_script("visible", "Visible", keybinding="v", show_in_toolbar=True),
            make_script("hidden", "Hidden", keybinding="h", show_in_toolbar=False),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        assert widget.scripts == [
            ("v", "visible", "Visible"),
        ]


class TestScriptToolbarToggle:
    """Tests for section collapse toggle."""

    def test_toggle_collapsed(self) -> None:
        """Test toggling collapsed state."""
        widget = ScriptToolbar()

        assert widget.collapsed is False

        with patch.object(widget, "refresh"):
            widget.toggle_collapsed()

        assert widget.collapsed is True

        with patch.object(widget, "refresh"):
            widget.toggle_collapsed()

        assert widget.collapsed is False


class TestScriptToolbarNavigation:
    """Tests for script navigation."""

    def test_selected_script_initial(self) -> None:
        """Test initial selection is first script."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
            make_script("deploy", "Deploy", keybinding="d"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        assert widget.selected_script is not None
        assert widget.selected_script[1] == "test"

    def test_select_next(self) -> None:
        """Test selecting next script."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
            make_script("deploy", "Deploy", keybinding="d"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        with patch.object(widget, "refresh"):
            with patch.object(widget, "post_message"):
                widget.select_next()

        assert widget.selected_script is not None
        assert widget.selected_script[1] == "deploy"

    def test_select_previous(self) -> None:
        """Test selecting previous script."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
            make_script("deploy", "Deploy", keybinding="d"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        with patch.object(widget, "refresh"):
            with patch.object(widget, "post_message"):
                widget.select_next()  # Now at deploy
                widget.select_previous()  # Back to test

        assert widget.selected_script is not None
        assert widget.selected_script[1] == "test"

    def test_select_previous_at_start(self) -> None:
        """Test select_previous doesn't go below zero."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        with patch.object(widget, "refresh"):
            with patch.object(widget, "post_message"):
                widget.select_previous()

        assert widget.selected_script is not None
        assert widget.selected_script[1] == "test"

    def test_select_next_at_end(self) -> None:
        """Test select_next doesn't exceed list bounds."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        with patch.object(widget, "refresh"):
            with patch.object(widget, "post_message"):
                for _ in range(10):
                    widget.select_next()

        assert widget.selected_script is not None
        assert widget.selected_script[1] == "test"

    def test_select_when_collapsed_returns_none(self) -> None:
        """Test selected_script is None when collapsed."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project, collapsed=True)

        assert widget.selected_script is None

    def test_select_next_ignored_when_collapsed(self) -> None:
        """Test select_next does nothing when collapsed."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
            make_script("deploy", "Deploy", keybinding="d"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project, collapsed=True)

        widget.select_next()

        # Index shouldn't change, and selected_script should be None
        assert widget._selected_index == 0
        assert widget.selected_script is None


class TestScriptToolbarRunScript:
    """Tests for running scripts."""

    def test_run_selected_script(self) -> None:
        """Test running the selected script."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        with patch.object(widget, "post_message") as mock_post:
            widget.run_selected_script()

        mock_post.assert_called_once()
        msg = mock_post.call_args[0][0]
        assert isinstance(msg, ScriptToolbar.ScriptRunRequested)
        assert msg.script_id == "test"
        assert msg.script_name == "Test Suite"
        assert msg.keybinding == "t"

    def test_run_selected_script_no_selection(self) -> None:
        """Test run_selected_script does nothing when collapsed."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project, collapsed=True)

        with patch.object(widget, "post_message") as mock_post:
            widget.run_selected_script()

        mock_post.assert_not_called()

    def test_run_script_by_id(self) -> None:
        """Test running a script by ID."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
            make_script("deploy", "Deploy", keybinding="d"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        with patch.object(widget, "post_message") as mock_post:
            widget.run_script_by_id("deploy")

        mock_post.assert_called_once()
        msg = mock_post.call_args[0][0]
        assert isinstance(msg, ScriptToolbar.ScriptRunRequested)
        assert msg.script_id == "deploy"
        assert msg.script_name == "Deploy"

    def test_run_script_by_id_not_found(self) -> None:
        """Test run_script_by_id logs warning for unknown script."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        with patch.object(widget, "post_message") as mock_post:
            with patch("iterm_controller.widgets.script_toolbar.logger") as mock_logger:
                widget.run_script_by_id("unknown")

        mock_post.assert_not_called()
        mock_logger.warning.assert_called_once()

    def test_run_script_by_keybinding(self) -> None:
        """Test running a script by keybinding."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
            make_script("deploy", "Deploy", keybinding="d"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        with patch.object(widget, "post_message") as mock_post:
            result = widget.run_script_by_keybinding("d")

        assert result is True
        mock_post.assert_called_once()
        msg = mock_post.call_args[0][0]
        assert isinstance(msg, ScriptToolbar.ScriptRunRequested)
        assert msg.script_id == "deploy"

    def test_run_script_by_keybinding_not_found(self) -> None:
        """Test run_script_by_keybinding returns False for unknown key."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        with patch.object(widget, "post_message") as mock_post:
            result = widget.run_script_by_keybinding("x")

        assert result is False
        mock_post.assert_not_called()


class TestScriptToolbarMessages:
    """Tests for message classes."""

    def test_script_run_requested_message(self) -> None:
        """Test ScriptRunRequested message."""
        msg = ScriptToolbar.ScriptRunRequested(
            script_id="test",
            script_name="Test Suite",
            keybinding="t",
        )

        assert msg.script_id == "test"
        assert msg.script_name == "Test Suite"
        assert msg.keybinding == "t"

    def test_script_run_requested_message_no_keybinding(self) -> None:
        """Test ScriptRunRequested message without keybinding."""
        msg = ScriptToolbar.ScriptRunRequested(
            script_id="manual",
            script_name="Manual Script",
            keybinding=None,
        )

        assert msg.script_id == "manual"
        assert msg.keybinding is None

    def test_script_selected_message(self) -> None:
        """Test ScriptSelected message."""
        msg = ScriptToolbar.ScriptSelected(script_id="test")

        assert msg.script_id == "test"


class TestScriptToolbarSetProject:
    """Tests for set_project method."""

    def test_set_project_updates_scripts(self) -> None:
        """Test set_project updates available scripts."""
        widget = ScriptToolbar()

        # Initially uses defaults
        assert widget.get_script_count() == len(DEFAULT_SCRIPTS)

        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
        ]
        project = make_project(scripts=scripts)

        with patch.object(widget, "refresh"):
            widget.set_project(project)

        assert widget.get_script_count() == 1

    def test_set_project_resets_selection(self) -> None:
        """Test set_project resets selection index."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
            make_script("deploy", "Deploy", keybinding="d"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        with patch.object(widget, "refresh"):
            with patch.object(widget, "post_message"):
                widget.select_next()  # Move to second script

        assert widget._selected_index == 1

        new_project = make_project(scripts=[
            make_script("build", "Build", keybinding="b"),
        ])

        with patch.object(widget, "refresh"):
            widget.set_project(new_project)

        assert widget._selected_index == 0


class TestScriptToolbarKeybindings:
    """Tests for keybinding-related methods."""

    def test_get_keybindings_map(self) -> None:
        """Test get_keybindings_map returns correct mapping."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
            make_script("deploy", "Deploy", keybinding="d"),
            make_script("manual", "Manual", keybinding=None),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        mapping = widget.get_keybindings_map()

        assert mapping == {
            "t": "test",
            "d": "deploy",
        }

    def test_get_keybindings_map_defaults(self) -> None:
        """Test get_keybindings_map returns defaults when no project."""
        widget = ScriptToolbar()

        mapping = widget.get_keybindings_map()

        assert "s" in mapping
        assert mapping["s"] == "server"
        assert "t" in mapping
        assert mapping["t"] == "tests"


class TestScriptToolbarGetScriptById:
    """Tests for get_script_by_id method."""

    def test_get_script_by_id_found(self) -> None:
        """Test get_script_by_id returns script when found."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        script = widget.get_script_by_id("test")

        assert script is not None
        assert script.id == "test"
        assert script.name == "Test Suite"

    def test_get_script_by_id_not_found(self) -> None:
        """Test get_script_by_id returns None when not found."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        script = widget.get_script_by_id("unknown")

        assert script is None

    def test_get_script_by_id_no_project(self) -> None:
        """Test get_script_by_id returns None when no project."""
        widget = ScriptToolbar()

        script = widget.get_script_by_id("test")

        assert script is None

    def test_get_script_by_id_no_scripts(self) -> None:
        """Test get_script_by_id returns None when project has no scripts."""
        project = make_project(scripts=None)
        widget = ScriptToolbar(project=project)

        script = widget.get_script_by_id("test")

        assert script is None


class TestScriptToolbarHasScripts:
    """Tests for has_scripts property."""

    def test_has_scripts_with_defaults(self) -> None:
        """Test has_scripts is True with default scripts."""
        widget = ScriptToolbar()

        assert widget.has_scripts is True

    def test_has_scripts_with_project_scripts(self) -> None:
        """Test has_scripts is True with project scripts."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        assert widget.has_scripts is True

    def test_has_scripts_empty_list(self) -> None:
        """Test has_scripts is False when project has empty list."""
        project = make_project(scripts=[])
        widget = ScriptToolbar(project=project)

        # Empty list means no scripts, but falls back to defaults
        assert widget.has_scripts is True  # Defaults are used

    def test_has_scripts_all_hidden(self) -> None:
        """Test has_scripts is False when all scripts are hidden."""
        scripts = [
            make_script("hidden1", "Hidden 1", show_in_toolbar=False),
            make_script("hidden2", "Hidden 2", show_in_toolbar=False),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        # All scripts are hidden, so has_scripts is False
        assert widget.has_scripts is False


class TestScriptToolbarCount:
    """Tests for get_script_count method."""

    def test_get_script_count_defaults(self) -> None:
        """Test get_script_count returns default count."""
        widget = ScriptToolbar()

        assert widget.get_script_count() == len(DEFAULT_SCRIPTS)

    def test_get_script_count_project_scripts(self) -> None:
        """Test get_script_count returns project script count."""
        scripts = [
            make_script("test", "Test Suite", keybinding="t"),
            make_script("deploy", "Deploy", keybinding="d"),
            make_script("lint", "Lint", keybinding="l"),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        assert widget.get_script_count() == 3

    def test_get_script_count_excludes_hidden(self) -> None:
        """Test get_script_count excludes hidden scripts."""
        scripts = [
            make_script("visible", "Visible", show_in_toolbar=True),
            make_script("hidden", "Hidden", show_in_toolbar=False),
        ]
        project = make_project(scripts=scripts)
        widget = ScriptToolbar(project=project)

        assert widget.get_script_count() == 1


class TestDefaultScripts:
    """Tests for DEFAULT_SCRIPTS constant."""

    def test_default_scripts_format(self) -> None:
        """Test DEFAULT_SCRIPTS has correct format."""
        for keybinding, script_id, name in DEFAULT_SCRIPTS:
            assert isinstance(keybinding, str)
            assert len(keybinding) == 1
            assert isinstance(script_id, str)
            assert isinstance(name, str)

    def test_default_scripts_has_expected_scripts(self) -> None:
        """Test DEFAULT_SCRIPTS has expected entries."""
        script_ids = [script_id for _, script_id, _ in DEFAULT_SCRIPTS]

        assert "server" in script_ids
        assert "tests" in script_ids
        assert "lint" in script_ids
        assert "build" in script_ids
        assert "orchestrator" in script_ids

    def test_default_scripts_keybindings_unique(self) -> None:
        """Test DEFAULT_SCRIPTS keybindings are unique."""
        keybindings = [key for key, _, _ in DEFAULT_SCRIPTS]

        assert len(keybindings) == len(set(keybindings))
