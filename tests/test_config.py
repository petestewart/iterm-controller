"""Tests for configuration loading, saving, and merging."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from iterm_controller.config import (
    CONFIG_DIR,
    GLOBAL_CONFIG_PATH,
    PROJECT_CONFIG_FILENAME,
    get_config_dir,
    get_global_config_path,
    get_project_config_path,
    load_global_config,
    load_merged_config,
    load_project_config,
    merge_configs,
    save_global_config,
    save_project_config,
)
from iterm_controller.exceptions import (
    ConfigLoadError,
    ConfigSaveError,
    ConfigValidationError,
)
from iterm_controller.models import (
    AppConfig,
    AppSettings,
    GitConfig,
    NotificationSettings,
    Project,
    ProjectScript,
    ReviewConfig,
    ReviewContextConfig,
    SessionTemplate,
    SessionType,
)


class TestMergeConfigs:
    """Test configuration merging logic."""

    def test_scalar_override(self):
        """Project scalars override global scalars."""
        global_config = {"key": "global_value"}
        project_config = {"key": "project_value"}
        result = merge_configs(global_config, project_config)
        assert result["key"] == "project_value"

    def test_scalar_inheritance(self):
        """Global scalars are inherited when not overridden."""
        global_config = {"key1": "value1", "key2": "value2"}
        project_config = {"key1": "override"}
        result = merge_configs(global_config, project_config)
        assert result["key1"] == "override"
        assert result["key2"] == "value2"

    def test_list_replace(self):
        """Project lists replace global lists (no merge)."""
        global_config = {"items": [1, 2, 3]}
        project_config = {"items": [4, 5]}
        result = merge_configs(global_config, project_config)
        assert result["items"] == [4, 5]

    def test_dict_recursive_merge(self):
        """Nested dicts are merged recursively."""
        global_config = {
            "settings": {
                "default_ide": "vscode",
                "polling_interval_ms": 500,
                "notification_enabled": True,
            }
        }
        project_config = {
            "settings": {
                "default_ide": "cursor",
                # polling_interval_ms should inherit
                # notification_enabled should inherit
            }
        }
        result = merge_configs(global_config, project_config)
        assert result["settings"]["default_ide"] == "cursor"
        assert result["settings"]["polling_interval_ms"] == 500
        assert result["settings"]["notification_enabled"] is True

    def test_null_removes_key(self):
        """None value in project removes key from global."""
        global_config = {"keep": "value", "remove": "value"}
        project_config = {"remove": None}
        result = merge_configs(global_config, project_config)
        assert result["keep"] == "value"
        assert "remove" not in result

    def test_project_adds_new_keys(self):
        """Project can add keys not present in global."""
        global_config = {"existing": "value"}
        project_config = {"new_key": "new_value"}
        result = merge_configs(global_config, project_config)
        assert result["existing"] == "value"
        assert result["new_key"] == "new_value"

    def test_deeply_nested_merge(self):
        """Deep nested dicts are merged correctly."""
        global_config = {
            "level1": {
                "level2": {
                    "level3": {"a": 1, "b": 2}
                }
            }
        }
        project_config = {
            "level1": {
                "level2": {
                    "level3": {"b": 3, "c": 4}
                }
            }
        }
        result = merge_configs(global_config, project_config)
        assert result["level1"]["level2"]["level3"] == {"a": 1, "b": 3, "c": 4}

    def test_empty_project_config(self):
        """Empty project config returns copy of global."""
        global_config = {"key": "value"}
        project_config = {}
        result = merge_configs(global_config, project_config)
        assert result == {"key": "value"}
        # Verify it's a copy, not the same object
        assert result is not global_config

    def test_empty_global_config(self):
        """Empty global config accepts all project values."""
        global_config = {}
        project_config = {"key": "value"}
        result = merge_configs(global_config, project_config)
        assert result == {"key": "value"}

    def test_spec_example(self):
        """Test the example from the spec document."""
        global_config = {
            "settings": {
                "default_ide": "vscode",
                "polling_interval_ms": 500,
                "notification_enabled": True,
            },
            "session_templates": [
                {"id": "shell", "name": "Shell", "command": ""}
            ],
        }
        project_config = {
            "settings": {
                "default_ide": "cursor",
            },
            "scripts": {
                "start": {"command": "npm run dev"}
            },
        }
        result = merge_configs(global_config, project_config)

        assert result["settings"]["default_ide"] == "cursor"
        assert result["settings"]["polling_interval_ms"] == 500
        assert result["settings"]["notification_enabled"] is True
        assert result["session_templates"] == [
            {"id": "shell", "name": "Shell", "command": ""}
        ]
        assert result["scripts"]["start"]["command"] == "npm run dev"


class TestGlobalConfig:
    """Test global configuration loading and saving."""

    def test_load_default_config(self):
        """Loading from nonexistent file returns default config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    config = load_global_config()
                    assert isinstance(config, AppConfig)
                    assert config.settings.default_ide == "vscode"
                    assert config.settings.polling_interval_ms == 500

    def test_load_existing_config(self):
        """Loading from existing file deserializes correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_data = {
                "settings": {
                    "default_ide": "cursor",
                    "polling_interval_ms": 250,
                },
                "projects": [
                    {"id": "test", "name": "Test", "path": "/test"}
                ],
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    config = load_global_config()
                    assert config.settings.default_ide == "cursor"
                    assert config.settings.polling_interval_ms == 250
                    assert len(config.projects) == 1
                    assert config.projects[0].id == "test"

    def test_save_config(self):
        """Saving config creates valid JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "subdir" / "config.json"
            config = AppConfig(
                settings=AppSettings(default_ide="vim"),
                projects=[Project(id="p1", name="Project 1", path="/path")],
            )

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", config_path.parent):
                    save_global_config(config)

            assert config_path.exists()
            with open(config_path) as f:
                data = json.load(f)
            assert data["settings"]["default_ide"] == "vim"
            assert len(data["projects"]) == 1

    def test_save_load_roundtrip(self):
        """Config survives save/load cycle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            original = AppConfig(
                settings=AppSettings(
                    default_ide="cursor",
                    default_shell="fish",
                    polling_interval_ms=300,
                    notification_enabled=False,
                ),
                session_templates=[
                    SessionTemplate(
                        id="dev",
                        name="Dev Server",
                        command="npm run dev",
                        env={"PORT": "3000"},
                    ),
                ],
            )

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    save_global_config(original)
                    loaded = load_global_config()

            assert loaded.settings.default_ide == "cursor"
            assert loaded.settings.default_shell == "fish"
            assert loaded.settings.polling_interval_ms == 300
            assert loaded.settings.notification_enabled is False
            assert len(loaded.session_templates) == 1
            assert loaded.session_templates[0].env == {"PORT": "3000"}


class TestProjectConfig:
    """Test project-local configuration loading."""

    def test_load_nonexistent_project_config(self):
        """Loading from project without config returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = load_project_config(tmpdir)
            assert config == {}

    def test_load_existing_project_config(self):
        """Loading from project with config returns contents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / PROJECT_CONFIG_FILENAME
            config_data = {
                "settings": {"default_ide": "cursor"},
                "scripts": {"start": {"command": "npm run dev"}},
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            config = load_project_config(tmpdir)
            assert config["settings"]["default_ide"] == "cursor"
            assert "scripts" in config

    def test_save_project_config(self):
        """Saving project config creates valid JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {"custom": "value"}
            save_project_config(tmpdir, config_data)

            config_path = Path(tmpdir) / PROJECT_CONFIG_FILENAME
            assert config_path.exists()
            with open(config_path) as f:
                loaded = json.load(f)
            assert loaded == {"custom": "value"}


class TestMergedConfig:
    """Test loading merged configuration."""

    def test_load_without_project(self):
        """Loading without project path returns global config only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_data = {
                "settings": {"default_ide": "vscode"},
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    config = load_merged_config()
                    assert config.settings.default_ide == "vscode"

    def test_load_with_project_overrides(self):
        """Loading with project path merges overrides."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create global config
            global_path = Path(tmpdir) / "global" / "config.json"
            global_path.parent.mkdir(parents=True)
            global_data = {
                "settings": {
                    "default_ide": "vscode",
                    "polling_interval_ms": 500,
                },
            }
            with open(global_path, "w") as f:
                json.dump(global_data, f)

            # Create project config
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            project_config_path = project_dir / PROJECT_CONFIG_FILENAME
            project_data = {
                "settings": {
                    "default_ide": "cursor",
                },
            }
            with open(project_config_path, "w") as f:
                json.dump(project_data, f)

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", global_path):
                with patch("iterm_controller.config.CONFIG_DIR", global_path.parent):
                    config = load_merged_config(project_dir)
                    assert config.settings.default_ide == "cursor"
                    assert config.settings.polling_interval_ms == 500

    def test_load_with_nonexistent_global(self):
        """Loading with no global config uses defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # No global config exists
            global_path = Path(tmpdir) / "nonexistent" / "config.json"

            # Create project config
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            project_config_path = project_dir / PROJECT_CONFIG_FILENAME
            project_data = {
                "settings": {
                    "default_ide": "cursor",
                },
            }
            with open(project_config_path, "w") as f:
                json.dump(project_data, f)

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", global_path):
                with patch("iterm_controller.config.CONFIG_DIR", global_path.parent):
                    config = load_merged_config(project_dir)
                    # Project override applied
                    assert config.settings.default_ide == "cursor"
                    # Defaults for unspecified values
                    assert config.settings.default_shell == "zsh"


class TestPathHelpers:
    """Test path helper functions."""

    def test_get_global_config_path(self):
        """get_global_config_path returns correct path."""
        path = get_global_config_path()
        assert path == GLOBAL_CONFIG_PATH
        assert "iterm-controller" in str(path)
        assert str(path).endswith("config.json")

    def test_get_config_dir(self):
        """get_config_dir returns correct path."""
        config_dir = get_config_dir()
        assert config_dir == CONFIG_DIR
        assert "iterm-controller" in str(config_dir)

    def test_get_project_config_path(self):
        """get_project_config_path returns correct path."""
        project_path = "/path/to/project"
        config_path = get_project_config_path(project_path)
        assert str(config_path) == f"{project_path}/{PROJECT_CONFIG_FILENAME}"

    def test_get_project_config_path_with_path_object(self):
        """get_project_config_path works with Path objects."""
        project_path = Path("/path/to/project")
        config_path = get_project_config_path(project_path)
        assert config_path == project_path / PROJECT_CONFIG_FILENAME


class TestConfigErrorHandling:
    """Test configuration error handling."""

    def test_load_invalid_json_raises_config_load_error(self):
        """Loading invalid JSON raises ConfigLoadError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text("{ invalid json }")

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    with pytest.raises(ConfigLoadError) as exc_info:
                        load_global_config()
                    assert "Invalid JSON" in str(exc_info.value)
                    assert exc_info.value.context["file_path"] == str(config_path)

    def test_load_invalid_schema_raises_config_validation_error(self):
        """Loading config with invalid schema raises ConfigValidationError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            # settings should be a dict, not a list
            config_path.write_text('{"settings": [1, 2, 3]}')

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    with pytest.raises(ConfigValidationError):
                        load_global_config()

    def test_load_project_config_invalid_json_raises_error(self):
        """Loading project config with invalid JSON raises ConfigLoadError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / PROJECT_CONFIG_FILENAME
            config_path.write_text("not valid json {")

            with pytest.raises(ConfigLoadError) as exc_info:
                load_project_config(tmpdir)
            assert "Invalid JSON" in str(exc_info.value)

    def test_save_config_to_readonly_raises_error(self):
        """Saving config to readonly location raises ConfigSaveError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a directory with the same name as the config file
            # This will cause a write error
            config_path = Path(tmpdir) / "config.json"
            config_path.mkdir()  # Create as directory, not file

            config = AppConfig()

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    with pytest.raises(ConfigSaveError):
                        save_global_config(config)

    def test_merged_config_invalid_global_json_raises_error(self):
        """Loading merged config with invalid global JSON raises ConfigLoadError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            global_path = Path(tmpdir) / "config.json"
            global_path.write_text("{ broken json")

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", global_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    with pytest.raises(ConfigLoadError):
                        load_merged_config()

    def test_merged_config_invalid_project_json_raises_error(self):
        """Loading merged config with invalid project JSON raises ConfigLoadError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Valid global config
            global_path = Path(tmpdir) / "global" / "config.json"
            global_path.parent.mkdir(parents=True)
            global_path.write_text('{"settings": {}}')

            # Invalid project config
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            project_config = project_dir / PROJECT_CONFIG_FILENAME
            project_config.write_text("invalid json")

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", global_path):
                with patch("iterm_controller.config.CONFIG_DIR", global_path.parent):
                    with pytest.raises(ConfigLoadError):
                        load_merged_config(project_dir)


class TestProjectScriptsConfig:
    """Test project scripts configuration loading (Phase 27.5.1)."""

    def test_load_scripts_array(self):
        """Scripts array is parsed into ProjectScript objects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_data = {
                "projects": [{
                    "id": "my-app",
                    "name": "My App",
                    "path": "/test/path",
                    "scripts": [
                        {
                            "id": "server",
                            "name": "Server",
                            "command": "bin/dev",
                            "keybinding": "s",
                            "session_type": "server",
                            "show_in_toolbar": True
                        },
                        {
                            "id": "tests",
                            "name": "Tests",
                            "command": "bin/rails test",
                            "keybinding": "t",
                            "session_type": "test_runner"
                        }
                    ]
                }]
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    config = load_global_config()
                    assert len(config.projects[0].scripts) == 2
                    server_script = config.projects[0].scripts[0]
                    assert isinstance(server_script, ProjectScript)
                    assert server_script.id == "server"
                    assert server_script.command == "bin/dev"
                    assert server_script.session_type == SessionType.SERVER
                    assert server_script.show_in_toolbar is True

    def test_scripts_with_env_vars(self):
        """Scripts can include environment variables."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_data = {
                "projects": [{
                    "id": "my-app",
                    "name": "My App",
                    "path": "/test/path",
                    "scripts": [{
                        "id": "server",
                        "name": "Server",
                        "command": "bin/dev",
                        "env": {"PORT": "3000", "NODE_ENV": "development"},
                        "working_dir": "./src"
                    }]
                }]
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    config = load_global_config()
                    script = config.projects[0].scripts[0]
                    assert script.env == {"PORT": "3000", "NODE_ENV": "development"}
                    assert script.working_dir == "./src"

    def test_scripts_default_values(self):
        """Scripts use correct default values for optional fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_data = {
                "projects": [{
                    "id": "my-app",
                    "name": "My App",
                    "path": "/test/path",
                    "scripts": [{
                        "id": "lint",
                        "name": "Lint",
                        "command": "bin/rubocop -A"
                    }]
                }]
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    config = load_global_config()
                    script = config.projects[0].scripts[0]
                    assert script.keybinding is None
                    assert script.working_dir is None
                    assert script.env is None
                    assert script.session_type == SessionType.SCRIPT
                    assert script.show_in_toolbar is True


class TestReviewConfig:
    """Test review configuration loading (Phase 27.5.2)."""

    def test_load_review_config(self):
        """Review config is parsed into ReviewConfig objects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_data = {
                "projects": [{
                    "id": "my-app",
                    "name": "My App",
                    "path": "/test/path",
                    "review_config": {
                        "enabled": True,
                        "command": "/review-task",
                        "model": "opus",
                        "max_revisions": 3,
                        "trigger": "script_completion"
                    }
                }]
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    config = load_global_config()
                    review_config = config.projects[0].review_config
                    assert isinstance(review_config, ReviewConfig)
                    assert review_config.enabled is True
                    assert review_config.command == "/review-task"
                    assert review_config.model == "opus"
                    assert review_config.max_revisions == 3
                    assert review_config.trigger == "script_completion"

    def test_load_review_context_config(self):
        """Review context config is parsed correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_data = {
                "projects": [{
                    "id": "my-app",
                    "name": "My App",
                    "path": "/test/path",
                    "review_config": {
                        "enabled": True,
                        "command": "/review-task",
                        "context": {
                            "include_task_definition": True,
                            "include_git_diff": True,
                            "include_test_results": False,
                            "include_lint_results": True,
                            "include_session_log": False
                        }
                    }
                }]
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    config = load_global_config()
                    context = config.projects[0].review_config.context
                    assert isinstance(context, ReviewContextConfig)
                    assert context.include_task_definition is True
                    assert context.include_git_diff is True
                    assert context.include_test_results is False
                    assert context.include_lint_results is True
                    assert context.include_session_log is False


class TestGitConfig:
    """Test git configuration loading (Phase 27.5.3)."""

    def test_load_git_config(self):
        """Git config is parsed into GitConfig objects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_data = {
                "projects": [{
                    "id": "my-app",
                    "name": "My App",
                    "path": "/test/path",
                    "git_config": {
                        "auto_stage": True,
                        "default_branch": "develop",
                        "remote": "upstream"
                    }
                }]
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    config = load_global_config()
                    git_config = config.projects[0].git_config
                    assert isinstance(git_config, GitConfig)
                    assert git_config.auto_stage is True
                    assert git_config.default_branch == "develop"
                    assert git_config.remote == "upstream"

    def test_git_config_defaults(self):
        """Git config uses correct defaults when not all fields specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_data = {
                "projects": [{
                    "id": "my-app",
                    "name": "My App",
                    "path": "/test/path",
                    "git_config": {}
                }]
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    config = load_global_config()
                    git_config = config.projects[0].git_config
                    assert git_config.auto_stage is False
                    assert git_config.default_branch == "main"
                    assert git_config.remote == "origin"


class TestNotificationSettingsConfig:
    """Test notification settings configuration loading (Phase 27.5.4)."""

    def test_load_notification_settings(self):
        """Notification settings are parsed correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_data = {
                "settings": {
                    "notifications": {
                        "enabled": True,
                        "sound_enabled": True,
                        "sound_name": "Ping",
                        "on_session_waiting": True,
                        "on_session_idle": False,
                        "on_review_failed": True,
                        "on_task_complete": False,
                        "on_phase_complete": True,
                        "on_orchestrator_done": True
                    }
                }
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    config = load_global_config()
                    n = config.settings.notifications
                    assert isinstance(n, NotificationSettings)
                    assert n.enabled is True
                    assert n.sound_enabled is True
                    assert n.sound_name == "Ping"
                    assert n.on_session_waiting is True
                    assert n.on_session_idle is False
                    assert n.on_review_failed is True
                    assert n.on_task_complete is False
                    assert n.on_phase_complete is True
                    assert n.on_orchestrator_done is True

    def test_notification_settings_defaults(self):
        """Notification settings use correct defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_data = {
                "settings": {
                    "notifications": {}
                }
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    config = load_global_config()
                    n = config.settings.notifications
                    assert n.enabled is True
                    assert n.sound_enabled is True
                    assert n.sound_name == "default"
                    assert n.on_session_waiting is True
                    assert n.on_session_idle is False

    def test_notification_settings_quiet_hours(self):
        """Notification settings parse quiet hours correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_data = {
                "settings": {
                    "notifications": {
                        "quiet_hours_start": "22:00",
                        "quiet_hours_end": "08:00"
                    }
                }
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    config = load_global_config()
                    n = config.settings.notifications
                    assert n.quiet_hours_start == "22:00"
                    assert n.quiet_hours_end == "08:00"


class TestCompleteProjectConfig:
    """Test loading complete project configuration with all new fields."""

    def test_load_complete_project_config(self):
        """Load a project with scripts, review, and git config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_data = {
                "settings": {
                    "default_ide": "cursor",
                    "polling_interval_ms": 500,
                    "notifications": {
                        "enabled": True,
                        "sound_enabled": True,
                        "on_review_failed": True,
                        "on_phase_complete": True
                    }
                },
                "projects": [{
                    "id": "my-app",
                    "name": "My App",
                    "path": "/Users/me/src/my-app",
                    "scripts": [
                        {"id": "server", "name": "Server", "command": "bin/dev", "keybinding": "s"},
                        {"id": "tests", "name": "Tests", "command": "pytest", "keybinding": "t"}
                    ],
                    "review_config": {
                        "enabled": True,
                        "command": "/review-task",
                        "max_revisions": 3
                    },
                    "git_config": {
                        "default_branch": "main"
                    }
                }]
            }
            with open(config_path, "w") as f:
                json.dump(config_data, f)

            with patch("iterm_controller.config.GLOBAL_CONFIG_PATH", config_path):
                with patch("iterm_controller.config.CONFIG_DIR", Path(tmpdir)):
                    config = load_global_config()

                    # Settings
                    assert config.settings.default_ide == "cursor"
                    assert config.settings.notifications.on_review_failed is True

                    # Project
                    project = config.projects[0]
                    assert project.id == "my-app"

                    # Scripts
                    assert len(project.scripts) == 2
                    assert project.scripts[0].keybinding == "s"

                    # Review
                    assert project.review_config.enabled is True
                    assert project.review_config.max_revisions == 3

                    # Git
                    assert project.git_config.default_branch == "main"
