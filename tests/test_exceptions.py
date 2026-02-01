"""Tests for custom exception hierarchy."""

import pytest

from iterm_controller.exceptions import (
    CommandNotAllowedError,
    ConfigError,
    ConfigLoadError,
    ConfigSaveError,
    ConfigValidationError,
    GitHubError,
    HealthCheckError,
    HealthCheckTimeoutError,
    ItermConnectionError,
    ItermControllerError,
    ItermNotConnectedError,
    NetworkError,
    PlanConflictError,
    PlanError,
    PlanParseError,
    PlanWriteError,
    RateLimitError,
    TestPlanParseError,
    TestPlanWriteError,
    record_error,
)


class TestExceptionHierarchy:
    """Test that exceptions are properly organized in hierarchy."""

    def test_base_exception_properties(self):
        """ItermControllerError has expected properties."""
        exc = ItermControllerError("test message", context={"key": "value"})
        assert exc.message == "test message"
        assert exc.context == {"key": "value"}
        assert exc.cause is None

    def test_base_exception_with_cause(self):
        """ItermControllerError can have a cause exception."""
        cause = ValueError("original error")
        exc = ItermControllerError("wrapped error", cause=cause)
        assert exc.cause is cause

    def test_base_exception_str_with_context(self):
        """str() includes context when present."""
        exc = ItermControllerError("test", context={"file": "test.txt"})
        result = str(exc)
        assert "test" in result
        assert "file=test.txt" in result

    def test_base_exception_str_without_context(self):
        """str() is just message when no context."""
        exc = ItermControllerError("just a message")
        assert str(exc) == "just a message"


class TestConnectionErrors:
    """Test connection-related exceptions."""

    def test_iterm_connection_error(self):
        """ItermConnectionError is an ItermControllerError."""
        exc = ItermConnectionError("Connection failed")
        assert isinstance(exc, ItermControllerError)
        assert exc.message == "Connection failed"

    def test_iterm_not_connected_error(self):
        """ItermNotConnectedError is an ItermControllerError."""
        exc = ItermNotConnectedError("Not connected")
        assert isinstance(exc, ItermControllerError)


class TestConfigErrors:
    """Test configuration-related exceptions."""

    def test_config_errors_inherit_from_config_error(self):
        """Config errors inherit from ConfigError."""
        assert issubclass(ConfigLoadError, ConfigError)
        assert issubclass(ConfigSaveError, ConfigError)
        assert issubclass(ConfigValidationError, ConfigError)
        assert issubclass(ConfigError, ItermControllerError)

    def test_config_load_error(self):
        """ConfigLoadError works correctly."""
        exc = ConfigLoadError("Failed to load")
        assert isinstance(exc, ConfigError)
        assert exc.message == "Failed to load"

    def test_config_save_error(self):
        """ConfigSaveError works correctly."""
        exc = ConfigSaveError("Failed to save")
        assert isinstance(exc, ConfigError)

    def test_config_validation_error(self):
        """ConfigValidationError works correctly."""
        exc = ConfigValidationError("Validation failed")
        assert isinstance(exc, ConfigError)


class TestPlanErrors:
    """Test PLAN.md-related exceptions."""

    def test_plan_errors_inherit_from_plan_error(self):
        """Plan errors inherit from PlanError."""
        assert issubclass(PlanParseError, PlanError)
        assert issubclass(PlanWriteError, PlanError)
        assert issubclass(PlanConflictError, PlanError)
        assert issubclass(TestPlanParseError, PlanError)
        assert issubclass(TestPlanWriteError, PlanError)
        assert issubclass(PlanError, ItermControllerError)

    def test_plan_parse_error(self):
        """PlanParseError works correctly."""
        exc = PlanParseError("Parse failed")
        assert isinstance(exc, PlanError)
        assert exc.message == "Parse failed"

    def test_plan_write_error(self):
        """PlanWriteError works correctly."""
        exc = PlanWriteError("Write failed")
        assert isinstance(exc, PlanError)

    def test_plan_conflict_error(self):
        """PlanConflictError works correctly."""
        exc = PlanConflictError("Conflict detected")
        assert isinstance(exc, PlanError)

    def test_test_plan_parse_error(self):
        """TestPlanParseError works correctly."""
        exc = TestPlanParseError("Parse failed")
        assert isinstance(exc, PlanError)

    def test_test_plan_write_error(self):
        """TestPlanWriteError works correctly."""
        exc = TestPlanWriteError("Write failed")
        assert isinstance(exc, PlanError)


class TestGitHubErrors:
    """Test GitHub-related exceptions."""

    def test_github_errors_inherit_from_github_error(self):
        """GitHub errors inherit from GitHubError."""
        assert issubclass(NetworkError, GitHubError)
        assert issubclass(RateLimitError, GitHubError)
        assert issubclass(GitHubError, ItermControllerError)

    def test_network_error(self):
        """NetworkError works correctly."""
        exc = NetworkError("Network failed")
        assert isinstance(exc, GitHubError)

    def test_rate_limit_error(self):
        """RateLimitError works correctly."""
        exc = RateLimitError("Rate limited")
        assert isinstance(exc, GitHubError)


class TestHealthCheckErrors:
    """Test health check exceptions."""

    def test_health_check_errors_inherit(self):
        """Health check errors inherit correctly."""
        assert issubclass(HealthCheckTimeoutError, HealthCheckError)
        assert issubclass(HealthCheckError, ItermControllerError)

    def test_health_check_timeout_error(self):
        """HealthCheckTimeoutError includes URL and timeout."""
        exc = HealthCheckTimeoutError(
            "Timed out",
            url="http://localhost:3000/health",
            timeout=5.0,
        )
        assert exc.context["url"] == "http://localhost:3000/health"
        assert exc.context["timeout"] == 5.0


class TestAutoModeErrors:
    """Test auto mode exceptions."""

    def test_command_not_allowed_error(self):
        """CommandNotAllowedError includes command info."""
        exc = CommandNotAllowedError("rm -rf /", allowed_patterns=["npm *", "python *"])
        assert exc.command == "rm -rf /"
        assert exc.allowed_patterns == ["npm *", "python *"]
        assert exc.context["command"] == "rm -rf /"
        assert "rm -rf /" in str(exc)


class TestRecordError:
    """Test record_error function."""

    def test_record_error_accepts_exception(self):
        """record_error accepts an exception (no-op for compatibility)."""
        # Should not raise
        record_error(ValueError("test"))
        record_error(ItermControllerError("test"))
