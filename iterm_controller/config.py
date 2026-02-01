"""Config loading/saving, merging, paths.

Provides configuration management with global defaults and project-local overrides.
"""

from __future__ import annotations

import copy
import json
from enum import Enum
from pathlib import Path

import dacite

from .models import AppConfig

# Configuration file locations
CONFIG_DIR = Path.home() / ".config" / "iterm-controller"
GLOBAL_CONFIG_PATH = CONFIG_DIR / "config.json"
PROJECT_CONFIG_FILENAME = ".iterm-controller.json"


def merge_configs(global_config: dict, project_config: dict) -> dict:
    """
    Merge project config into global config.

    Rules:
    - Scalars: project overrides global
    - Lists: project replaces global (no merge)
    - Dicts: recursive merge
    - None in project: removes key from global

    Args:
        global_config: The base configuration dictionary
        project_config: The override configuration dictionary

    Returns:
        Merged configuration dictionary
    """
    result = copy.deepcopy(global_config)

    for key, value in project_config.items():
        if value is None:
            # None removes key
            result.pop(key, None)
        elif isinstance(value, dict) and key in result and isinstance(result[key], dict):
            # Recursive merge for dicts
            result[key] = merge_configs(result[key], value)
        else:
            # Override for scalars and lists
            result[key] = value

    return result


def load_global_config() -> AppConfig:
    """
    Load global application configuration.

    Loads from ~/.config/iterm-controller/config.json if it exists,
    otherwise returns a default AppConfig.

    Returns:
        AppConfig instance with global settings
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if GLOBAL_CONFIG_PATH.exists():
        with open(GLOBAL_CONFIG_PATH) as f:
            data = json.load(f)
        return dacite.from_dict(
            data_class=AppConfig,
            data=data,
            config=dacite.Config(cast=[Enum]),
        )

    # Return default config
    return AppConfig()


def save_global_config(config: AppConfig) -> None:
    """
    Save global application configuration.

    Saves to ~/.config/iterm-controller/config.json, creating the
    directory if needed.

    Args:
        config: AppConfig instance to save
    """
    from .models import model_to_dict

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    data = model_to_dict(config)
    with open(GLOBAL_CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


def load_project_config(project_path: str | Path) -> dict:
    """
    Load project-local configuration overrides.

    Args:
        project_path: Path to the project root directory

    Returns:
        Dictionary of project-local overrides, or empty dict if no config exists
    """
    config_path = Path(project_path) / PROJECT_CONFIG_FILENAME

    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)

    return {}


def save_project_config(project_path: str | Path, config: dict) -> None:
    """
    Save project-local configuration.

    Args:
        project_path: Path to the project root directory
        config: Configuration dictionary to save
    """
    config_path = Path(project_path) / PROJECT_CONFIG_FILENAME

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def load_merged_config(project_path: str | Path | None = None) -> AppConfig:
    """
    Load configuration with project-local overrides merged.

    Loads the global configuration and, if a project path is provided,
    merges in project-local overrides according to the merge rules.

    Args:
        project_path: Optional path to project for local overrides

    Returns:
        AppConfig with merged configuration
    """
    # Start with global config as dict
    if GLOBAL_CONFIG_PATH.exists():
        with open(GLOBAL_CONFIG_PATH) as f:
            global_data = json.load(f)
    else:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        global_data = {}

    # Merge project config if provided
    if project_path is not None:
        project_data = load_project_config(project_path)
        merged_data = merge_configs(global_data, project_data)
    else:
        merged_data = global_data

    # Convert to AppConfig
    return dacite.from_dict(
        data_class=AppConfig,
        data=merged_data,
        config=dacite.Config(cast=[Enum]),
    )


def get_global_config_path() -> Path:
    """Return the path to the global config file."""
    return GLOBAL_CONFIG_PATH


def get_config_dir() -> Path:
    """Return the path to the config directory."""
    return CONFIG_DIR


def get_project_config_path(project_path: str | Path) -> Path:
    """Return the path to a project's local config file."""
    return Path(project_path) / PROJECT_CONFIG_FILENAME
