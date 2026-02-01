"""Tests for centralized logging configuration."""

import io
import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from iterm_controller.logging_config import (
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_LEVEL,
    LOG_DIR,
    get_log_file_path,
    get_logger,
    get_recent_logs,
    log_exception,
    setup_logging,
    LogContext,
)


class TestSetupLogging:
    """Test logging setup functionality."""

    def test_setup_logging_creates_log_dir(self):
        """setup_logging creates log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            with patch("iterm_controller.logging_config.LOG_DIR", log_dir):
                setup_logging(log_to_file=True, log_to_console=False)
                assert log_dir.exists()

    def test_setup_logging_default_level(self):
        """Default log level is INFO."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            with patch("iterm_controller.logging_config.LOG_DIR", log_dir):
                setup_logging()
                logger = logging.getLogger("iterm_controller")
                assert logger.level == logging.INFO

    def test_setup_logging_custom_level_string(self):
        """Log level can be set as string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            with patch("iterm_controller.logging_config.LOG_DIR", log_dir):
                setup_logging(level="DEBUG")
                logger = logging.getLogger("iterm_controller")
                assert logger.level == logging.DEBUG

    def test_setup_logging_custom_level_int(self):
        """Log level can be set as int."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            with patch("iterm_controller.logging_config.LOG_DIR", log_dir):
                setup_logging(level=logging.WARNING)
                logger = logging.getLogger("iterm_controller")
                assert logger.level == logging.WARNING

    def test_setup_logging_console_handler(self):
        """Console handler can be enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            stream = io.StringIO()
            with patch("iterm_controller.logging_config.LOG_DIR", log_dir):
                setup_logging(log_to_console=True, console_stream=stream, log_to_file=False)
                logger = logging.getLogger("iterm_controller")
                logger.info("test message")
                assert "test message" in stream.getvalue()

    def test_setup_logging_file_handler(self):
        """File handler writes to log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            with patch("iterm_controller.logging_config.LOG_DIR", log_dir):
                setup_logging(log_to_file=True, log_to_console=False)
                logger = logging.getLogger("iterm_controller")
                logger.info("file test message")

                # Flush handlers
                for handler in logger.handlers:
                    handler.flush()

                log_file = log_dir / "iterm-controller.log"
                assert log_file.exists()
                content = log_file.read_text()
                assert "file test message" in content

    def test_setup_logging_debug_modules(self):
        """Specific modules can be set to DEBUG."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            with patch("iterm_controller.logging_config.LOG_DIR", log_dir):
                setup_logging(level="INFO", debug_modules=["github", "config"])
                github_logger = logging.getLogger("iterm_controller.github")
                config_logger = logging.getLogger("iterm_controller.config")
                assert github_logger.level == logging.DEBUG
                assert config_logger.level == logging.DEBUG


class TestGetLogger:
    """Test logger retrieval."""

    def test_get_logger_adds_prefix(self):
        """get_logger adds iterm_controller prefix."""
        logger = get_logger("mymodule")
        assert logger.name == "iterm_controller.mymodule"

    def test_get_logger_preserves_full_name(self):
        """get_logger preserves full names starting with iterm_controller."""
        logger = get_logger("iterm_controller.mymodule")
        assert logger.name == "iterm_controller.mymodule"


class TestLogFilePath:
    """Test log file path utilities."""

    def test_get_log_file_path_creates_dir(self):
        """get_log_file_path creates log directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            with patch("iterm_controller.logging_config.LOG_DIR", log_dir):
                path = get_log_file_path()
                assert log_dir.exists()
                assert path.name == "iterm-controller.log"


class TestLogException:
    """Test exception logging helper."""

    def test_log_exception_with_traceback(self):
        """log_exception logs with traceback by default."""
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = logging.getLogger("test_exc_1")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            raise ValueError("test error")
        except ValueError as e:
            log_exception(logger, e, "An error occurred", include_traceback=True)

        output = stream.getvalue()
        assert "An error occurred" in output
        assert "test error" in output

    def test_log_exception_without_traceback(self):
        """log_exception can omit traceback."""
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = logging.getLogger("test_exc_2")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            raise ValueError("test error")
        except ValueError as e:
            log_exception(logger, e, "Short error", include_traceback=False)

        output = stream.getvalue()
        assert "Short error" in output
        assert "ValueError" in output

    def test_log_exception_custom_level(self):
        """log_exception can use custom log level."""
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

        logger = logging.getLogger("test_exc_3")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        try:
            raise ValueError("test")
        except ValueError as e:
            log_exception(logger, e, "Warning", level=logging.WARNING, include_traceback=False)

        output = stream.getvalue()
        assert "WARNING" in output


class TestGetRecentLogs:
    """Test recent log retrieval."""

    def test_get_recent_logs_nonexistent_file(self):
        """get_recent_logs returns empty list for nonexistent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            with patch("iterm_controller.logging_config.LOG_DIR", log_dir):
                logs = get_recent_logs()
                assert logs == []

    def test_get_recent_logs_returns_lines(self):
        """get_recent_logs returns recent log lines."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            log_dir.mkdir(parents=True)
            log_file = log_dir / "iterm-controller.log"
            log_file.write_text("line1\nline2\nline3\n")

            with patch("iterm_controller.logging_config.LOG_DIR", log_dir):
                logs = get_recent_logs(lines=2)
                assert len(logs) == 2
                assert "line2" in logs[0]
                assert "line3" in logs[1]

    def test_get_recent_logs_respects_limit(self):
        """get_recent_logs respects line limit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "logs"
            log_dir.mkdir(parents=True)
            log_file = log_dir / "iterm-controller.log"
            log_file.write_text("\n".join(f"line{i}" for i in range(200)))

            with patch("iterm_controller.logging_config.LOG_DIR", log_dir):
                logs = get_recent_logs(lines=50)
                assert len(logs) == 50


class TestLogContext:
    """Test LogContext context manager."""

    def test_log_context_basic(self):
        """LogContext adds context to log messages."""
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter("%(message)s"))

        logger = logging.getLogger("test_ctx_1")
        logger.handlers = [handler]
        logger.setLevel(logging.DEBUG)

        with LogContext(logger, operation="test_op", id="123"):
            logger.info("inside context")

        # Context is restored after exiting
        logger.info("outside context")

    def test_log_context_restores_format(self):
        """LogContext restores original format on exit."""
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        original_format = "ORIGINAL: %(message)s"
        handler.setFormatter(logging.Formatter(original_format))

        logger = logging.getLogger("test_ctx_2")
        logger.handlers = [handler]
        logger.setLevel(logging.DEBUG)

        with LogContext(logger, key="value"):
            pass

        # Verify format was restored
        assert handler.formatter._fmt == original_format
