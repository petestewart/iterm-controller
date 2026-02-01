"""Centralized logging configuration for iTerm Controller.

This module provides:
- Configurable log levels and output destinations
- Structured logging with consistent formatting
- Log file rotation with configurable size limits
- Debug mode for development troubleshooting
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TextIO

# Default configuration
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_BACKUP_COUNT = 3

# Log directory
LOG_DIR = Path.home() / ".config" / "iterm-controller" / "logs"


def get_log_file_path() -> Path:
    """Get the path to the log file, creating directory if needed."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR / "iterm-controller.log"


def setup_logging(
    *,
    level: int | str = DEFAULT_LOG_LEVEL,
    log_to_file: bool = True,
    log_to_console: bool = False,
    console_stream: TextIO = sys.stderr,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    debug_modules: list[str] | None = None,
) -> None:
    """Configure logging for the entire application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_to_file: Whether to log to file.
        log_to_console: Whether to log to console (stderr).
        console_stream: Stream for console output.
        max_bytes: Maximum log file size before rotation.
        backup_count: Number of backup log files to keep.
        debug_modules: List of module names to set to DEBUG level.
    """
    # Convert string level to int if needed
    if isinstance(level, str):
        level = getattr(logging, level.upper(), DEFAULT_LOG_LEVEL)

    # Get root logger for our package
    root_logger = logging.getLogger("iterm_controller")
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(DEFAULT_LOG_FORMAT, DEFAULT_DATE_FORMAT)

    # Add file handler
    if log_to_file:
        log_file = get_log_file_path()
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Add console handler
    if log_to_console:
        console_handler = logging.StreamHandler(console_stream)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Set debug level for specific modules if requested
    if debug_modules:
        for module_name in debug_modules:
            full_name = (
                f"iterm_controller.{module_name}"
                if not module_name.startswith("iterm_controller.")
                else module_name
            )
            module_logger = logging.getLogger(full_name)
            module_logger.setLevel(logging.DEBUG)


def enable_debug_mode() -> None:
    """Enable debug logging for all modules."""
    setup_logging(level=logging.DEBUG, log_to_console=True)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the iterm_controller namespace.

    Args:
        name: Logger name (will be prefixed with iterm_controller.).

    Returns:
        Configured logger instance.
    """
    if name.startswith("iterm_controller."):
        return logging.getLogger(name)
    return logging.getLogger(f"iterm_controller.{name}")


class LogContext:
    """Context manager for structured logging with extra context.

    Example:
        with LogContext(logger, operation="spawn_session", session_id="abc"):
            logger.info("Starting operation")
            # ... do work
            logger.info("Operation complete")
    """

    def __init__(self, logger: logging.Logger, **context: str | int | bool) -> None:
        self.logger = logger
        self.context = context
        self._old_format: str | None = None

    def __enter__(self) -> LogContext:
        if self.logger.handlers:
            handler = self.logger.handlers[0]
            if hasattr(handler, "formatter") and handler.formatter:
                self._old_format = handler.formatter._fmt
                context_str = " ".join(f"{k}={v}" for k, v in self.context.items())
                new_format = f"%(asctime)s [%(levelname)s] %(name)s [{context_str}]: %(message)s"
                handler.setFormatter(logging.Formatter(new_format, DEFAULT_DATE_FORMAT))
        return self

    def __exit__(self, *args: object) -> None:
        if self._old_format and self.logger.handlers:
            handler = self.logger.handlers[0]
            if hasattr(handler, "formatter"):
                handler.setFormatter(logging.Formatter(self._old_format, DEFAULT_DATE_FORMAT))


def log_exception(
    logger: logging.Logger,
    exc: Exception,
    message: str = "An error occurred",
    *,
    level: int = logging.ERROR,
    include_traceback: bool = True,
) -> None:
    """Log an exception with consistent formatting.

    Args:
        logger: Logger to use.
        exc: Exception to log.
        message: Human-readable message prefix.
        level: Log level (default ERROR).
        include_traceback: Whether to include full traceback.
    """
    if include_traceback:
        logger.log(level, "%s: %s", message, exc, exc_info=True)
    else:
        logger.log(level, "%s: %s (%s)", message, exc, type(exc).__name__)


def get_recent_logs(lines: int = 100) -> list[str]:
    """Get recent log entries for debugging.

    Args:
        lines: Number of lines to return.

    Returns:
        List of recent log lines.
    """
    log_file = get_log_file_path()
    if not log_file.exists():
        return []

    with open(log_file, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
        return all_lines[-lines:]
