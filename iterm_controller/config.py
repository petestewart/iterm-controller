"""Config loading/saving, merging, paths.

Provides configuration management with global defaults and project-local overrides.
"""

from __future__ import annotations

import copy
import json
import logging
from enum import Enum
from pathlib import Path

import dacite

from .exceptions import (
    ConfigLoadError,
    ConfigSaveError,
    ConfigValidationError,
    record_error,
)
from .models import AppConfig

logger = logging.getLogger(__name__)

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

    Raises:
        ConfigLoadError: If the config file exists but cannot be parsed.
    """
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error("Failed to create config directory: %s", e)
        record_error(e)
        raise ConfigLoadError(
            f"Failed to create config directory: {CONFIG_DIR}",
            file_path=str(CONFIG_DIR),
            cause=e,
        ) from e

    if not GLOBAL_CONFIG_PATH.exists():
        logger.debug("No global config found, using defaults")
        return AppConfig()

    try:
        with open(GLOBAL_CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        logger.debug("Loaded global config from %s", GLOBAL_CONFIG_PATH)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in config file: %s", e)
        record_error(e)
        raise ConfigLoadError(
            f"Invalid JSON in config file at line {e.lineno}",
            file_path=str(GLOBAL_CONFIG_PATH),
            context={"line": e.lineno, "column": e.colno},
            cause=e,
        ) from e
    except OSError as e:
        logger.error("Failed to read config file: %s", e)
        record_error(e)
        raise ConfigLoadError(
            "Failed to read config file",
            file_path=str(GLOBAL_CONFIG_PATH),
            cause=e,
        ) from e

    try:
        return dacite.from_dict(
            data_class=AppConfig,
            data=data,
            config=dacite.Config(cast=[Enum]),
        )
    except dacite.DaciteError as e:
        logger.error("Config schema validation failed: %s", e)
        record_error(e)
        raise ConfigValidationError(
            f"Config schema validation failed: {e}",
            context={"file_path": str(GLOBAL_CONFIG_PATH)},
            cause=e,
        ) from e


def save_global_config(config: AppConfig) -> None:
    """
    Save global application configuration.

    Saves to ~/.config/iterm-controller/config.json, creating the
    directory if needed.

    Args:
        config: AppConfig instance to save

    Raises:
        ConfigSaveError: If the config cannot be saved.
    """
    from .models import model_to_dict

    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.error("Failed to create config directory: %s", e)
        record_error(e)
        raise ConfigSaveError(
            f"Failed to create config directory: {CONFIG_DIR}",
            file_path=str(CONFIG_DIR),
            cause=e,
        ) from e

    try:
        data = model_to_dict(config)
        with open(GLOBAL_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.debug("Saved global config to %s", GLOBAL_CONFIG_PATH)
    except OSError as e:
        logger.error("Failed to write config file: %s", e)
        record_error(e)
        raise ConfigSaveError(
            "Failed to write config file",
            file_path=str(GLOBAL_CONFIG_PATH),
            cause=e,
        ) from e
    except (TypeError, ValueError) as e:
        logger.error("Failed to serialize config to JSON: %s", e)
        record_error(e)
        raise ConfigSaveError(
            "Failed to serialize config to JSON",
            file_path=str(GLOBAL_CONFIG_PATH),
            cause=e,
        ) from e


def load_project_config(project_path: str | Path) -> dict:
    """
    Load project-local configuration overrides.

    Args:
        project_path: Path to the project root directory

    Returns:
        Dictionary of project-local overrides, or empty dict if no config exists

    Raises:
        ConfigLoadError: If the config file exists but cannot be parsed.
    """
    config_path = Path(project_path) / PROJECT_CONFIG_FILENAME

    if not config_path.exists():
        logger.debug("No project config found at %s", config_path)
        return {}

    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        logger.debug("Loaded project config from %s", config_path)
        return data
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in project config: %s", e)
        record_error(e)
        raise ConfigLoadError(
            f"Invalid JSON in project config at line {e.lineno}",
            file_path=str(config_path),
            context={"line": e.lineno, "column": e.colno},
            cause=e,
        ) from e
    except OSError as e:
        logger.error("Failed to read project config: %s", e)
        record_error(e)
        raise ConfigLoadError(
            "Failed to read project config",
            file_path=str(config_path),
            cause=e,
        ) from e


def save_project_config(project_path: str | Path, config: dict) -> None:
    """
    Save project-local configuration.

    Args:
        project_path: Path to the project root directory
        config: Configuration dictionary to save

    Raises:
        ConfigSaveError: If the config cannot be saved.
    """
    config_path = Path(project_path) / PROJECT_CONFIG_FILENAME

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        logger.debug("Saved project config to %s", config_path)
    except OSError as e:
        logger.error("Failed to write project config: %s", e)
        record_error(e)
        raise ConfigSaveError(
            "Failed to write project config",
            file_path=str(config_path),
            cause=e,
        ) from e
    except (TypeError, ValueError) as e:
        logger.error("Failed to serialize project config to JSON: %s", e)
        record_error(e)
        raise ConfigSaveError(
            "Failed to serialize project config to JSON",
            file_path=str(config_path),
            cause=e,
        ) from e


def load_merged_config(project_path: str | Path | None = None) -> AppConfig:
    """
    Load configuration with project-local overrides merged.

    Loads the global configuration and, if a project path is provided,
    merges in project-local overrides according to the merge rules.

    Args:
        project_path: Optional path to project for local overrides

    Returns:
        AppConfig with merged configuration

    Raises:
        ConfigLoadError: If configuration files cannot be read.
        ConfigValidationError: If the merged config is invalid.
    """
    # Start with global config as dict
    try:
        if GLOBAL_CONFIG_PATH.exists():
            with open(GLOBAL_CONFIG_PATH, encoding="utf-8") as f:
                global_data = json.load(f)
            logger.debug("Loaded global config for merging")
        else:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            global_data = {}
            logger.debug("Using empty global config for merging")
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in global config: %s", e)
        record_error(e)
        raise ConfigLoadError(
            f"Invalid JSON in global config at line {e.lineno}",
            file_path=str(GLOBAL_CONFIG_PATH),
            context={"line": e.lineno, "column": e.colno},
            cause=e,
        ) from e
    except OSError as e:
        logger.error("Failed to read global config: %s", e)
        record_error(e)
        raise ConfigLoadError(
            "Failed to read global config",
            file_path=str(GLOBAL_CONFIG_PATH),
            cause=e,
        ) from e

    # Merge project config if provided
    if project_path is not None:
        project_data = load_project_config(project_path)
        merged_data = merge_configs(global_data, project_data)
        logger.debug("Merged project config from %s", project_path)
    else:
        merged_data = global_data

    # Convert to AppConfig
    try:
        return dacite.from_dict(
            data_class=AppConfig,
            data=merged_data,
            config=dacite.Config(cast=[Enum]),
        )
    except dacite.DaciteError as e:
        logger.error("Merged config validation failed: %s", e)
        record_error(e)
        raise ConfigValidationError(
            f"Merged config validation failed: {e}",
            cause=e,
        ) from e


def get_global_config_path() -> Path:
    """Return the path to the global config file."""
    return GLOBAL_CONFIG_PATH


def get_config_dir() -> Path:
    """Return the path to the config directory."""
    return CONFIG_DIR


def get_project_config_path(project_path: str | Path) -> Path:
    """Return the path to a project's local config file."""
    return Path(project_path) / PROJECT_CONFIG_FILENAME


def save_window_layouts(config: AppConfig, layouts: list) -> None:
    """Update window layouts in config and save to disk.

    Args:
        config: The AppConfig to update.
        layouts: List of WindowLayout objects from the layout manager.
    """
    config.window_layouts = layouts
    save_global_config(config)
