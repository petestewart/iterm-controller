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
from iterm_controller.models import AppConfig, AppSettings, Project, SessionTemplate


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
