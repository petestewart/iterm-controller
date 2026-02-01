"""Tests for custom exception hierarchy."""

import pytest

from iterm_controller.exceptions import (
    ItermControllerError,
    ConfigError,
    ConfigLoadError,
    ConfigSaveError,
    ConfigValidationError,
    ItermControllerConnectionError,
    GitHubError,
    GitHubUnavailableError,
    HealthCheckError,
    HealthCheckTimeoutError,
    ItermConnectionError,
    ItermNotConnectedError,
    ItermSessionError,
    NetworkError,
    NotificationError,
    NotificationUnavailableError,
    PlanConflictError,
    PlanError,
    PlanParseError,
    PlanWriteError,
    RateLimitError,
    SessionError,
    SessionSpawnError,
    SessionTerminationError,
    TemplateError,
    TemplateNotFoundError,
    TemplateValidationError,
    ErrorStats,
    error_stats,
    record_error,
)


class TestExceptionHierarchy:
    """Test that exceptions are properly organized in hierarchy."""

    def test_base_exception_properties(self):
        """ItermControllerError has expected properties."""
        exc = ItermControllerError("test message", context={"key": "value"})
        assert exc.message == "test message"
        assert exc.context == {"key": "value"}
        assert exc.timestamp is not None
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

    def test_iterm_connection_error_default_message(self):
        """ItermConnectionError has default message."""
        exc = ItermConnectionError()
        assert "connect" in exc.message.lower()

    def test_iterm_connection_error_custom_message(self):
        """ItermConnectionError accepts custom message."""
        exc = ItermConnectionError("Custom connection error")
        assert exc.message == "Custom connection error"

    def test_iterm_not_connected_error(self):
        """ItermNotConnectedError includes operation."""
        exc = ItermNotConnectedError("spawn_session")
        assert "spawn_session" in str(exc)

    def test_network_error_with_url(self):
        """NetworkError includes URL in context."""
        exc = NetworkError("Connection failed", url="http://example.com")
        assert exc.context["url"] == "http://example.com"


class TestConfigErrors:
    """Test configuration-related exceptions."""

    def test_config_load_error_with_file(self):
        """ConfigLoadError includes file path."""
        exc = ConfigLoadError(file_path="/path/to/config.json")
        assert exc.context["file_path"] == "/path/to/config.json"

    def test_config_validation_error_with_field(self):
        """ConfigValidationError includes field info."""
        exc = ConfigValidationError(
            "Invalid value",
            field="polling_interval_ms",
            value=-1,
            expected="positive integer",
        )
        assert exc.context["field"] == "polling_interval_ms"
        assert exc.context["value"] == "-1"
        assert exc.context["expected"] == "positive integer"

    def test_config_save_error(self):
        """ConfigSaveError includes file path."""
        exc = ConfigSaveError(file_path="/path/to/config.json")
        assert exc.context["file_path"] == "/path/to/config.json"


class TestPlanErrors:
    """Test PLAN.md-related exceptions."""

    def test_plan_parse_error_with_line(self):
        """PlanParseError includes line number."""
        exc = PlanParseError(
            "Invalid syntax",
            file_path="/project/PLAN.md",
            line_number=42,
        )
        assert exc.context["file_path"] == "/project/PLAN.md"
        assert exc.context["line_number"] == 42

    def test_plan_write_error(self):
        """PlanWriteError includes file path."""
        exc = PlanWriteError(file_path="/project/PLAN.md")
        assert "file_path" in exc.context

    def test_plan_conflict_error(self):
        """PlanConflictError has default message."""
        exc = PlanConflictError()
        assert "modified externally" in exc.message.lower()


class TestSessionErrors:
    """Test session-related exceptions."""

    def test_session_error_with_id_and_operation(self):
        """ItermSessionError includes session ID and operation."""
        exc = ItermSessionError(
            "Failed to send command",
            session_id="abc123",
            operation="send_text",
        )
        assert exc.context["session_id"] == "abc123"
        assert exc.context["operation"] == "send_text"

    def test_session_spawn_error(self):
        """SessionSpawnError includes template ID."""
        exc = SessionSpawnError(template_id="dev-server")
        assert exc.context["template_id"] == "dev-server"

    def test_session_termination_error(self):
        """SessionTerminationError includes timeout."""
        exc = SessionTerminationError(session_id="abc", timeout=5.0)
        assert exc.context["timeout"] == 5.0


class TestGitHubErrors:
    """Test GitHub-related exceptions."""

    def test_github_unavailable_error(self):
        """GitHubUnavailableError includes reason."""
        exc = GitHubUnavailableError(reason="gh CLI not installed")
        assert exc.context["reason"] == "gh CLI not installed"

    def test_rate_limit_error(self):
        """RateLimitError has meaningful message."""
        exc = RateLimitError()
        assert "rate limit" in exc.message.lower()


class TestHealthCheckErrors:
    """Test health check exceptions."""

    def test_health_check_timeout_error(self):
        """HealthCheckTimeoutError includes URL and timeout."""
        exc = HealthCheckTimeoutError(
            url="http://localhost:3000/health",
            timeout=5.0,
        )
        assert exc.context["url"] == "http://localhost:3000/health"
        assert exc.context["timeout_seconds"] == 5.0


class TestTemplateErrors:
    """Test template-related exceptions."""

    def test_template_not_found_error(self):
        """TemplateNotFoundError includes template ID in message."""
        exc = TemplateNotFoundError("my-template")
        assert "my-template" in exc.message
        assert exc.context["template_id"] == "my-template"

    def test_template_validation_error(self):
        """TemplateValidationError includes field."""
        exc = TemplateValidationError(template_id="t1", field="command")
        assert exc.context["template_id"] == "t1"
        assert exc.context["field"] == "command"


class TestNotificationErrors:
    """Test notification-related exceptions."""

    def test_notification_unavailable_error(self):
        """NotificationUnavailableError has default message."""
        exc = NotificationUnavailableError()
        assert "not available" in exc.message.lower()


class TestErrorStats:
    """Test error statistics tracking."""

    def test_error_stats_initial_state(self):
        """ErrorStats starts with zero counts."""
        stats = ErrorStats()
        assert stats.total_count == 0
        assert stats.by_type == {}
        assert stats.recent_errors == []

    def test_error_stats_records_error(self):
        """record() increments counts."""
        stats = ErrorStats()
        exc = ValueError("test error")
        stats.record(exc)
        assert stats.total_count == 1
        assert stats.by_type["ValueError"] == 1

    def test_error_stats_tracks_multiple_types(self):
        """record() tracks different error types."""
        stats = ErrorStats()
        stats.record(ValueError("v1"))
        stats.record(ValueError("v2"))
        stats.record(TypeError("t1"))

        assert stats.total_count == 3
        assert stats.by_type["ValueError"] == 2
        assert stats.by_type["TypeError"] == 1

    def test_error_stats_recent_errors_limit(self):
        """recent_errors respects max_recent limit."""
        stats = ErrorStats(max_recent=5)
        for i in range(10):
            stats.record(ValueError(f"error {i}"))

        assert len(stats.recent_errors) == 5
        # Should have the last 5 errors
        assert "error 5" in stats.recent_errors[0][2]

    def test_global_error_stats(self):
        """Global error_stats and record_error work."""
        initial_count = error_stats.total_count
        record_error(RuntimeError("test"))
        assert error_stats.total_count == initial_count + 1


class TestExceptionInheritance:
    """Test that exceptions inherit correctly."""

    def test_config_errors_inherit_from_base(self):
        """Config errors inherit from ItermControllerError."""
        assert issubclass(ConfigError, ItermControllerError)
        assert issubclass(ConfigLoadError, ConfigError)
        assert issubclass(ConfigSaveError, ConfigError)
        assert issubclass(ConfigValidationError, ConfigError)

    def test_plan_errors_inherit_from_base(self):
        """Plan errors inherit from ItermControllerError."""
        assert issubclass(PlanError, ItermControllerError)
        assert issubclass(PlanParseError, PlanError)
        assert issubclass(PlanWriteError, PlanError)
        assert issubclass(PlanConflictError, PlanError)

    def test_session_errors_inherit_from_base(self):
        """Session errors inherit from ItermControllerError."""
        assert issubclass(SessionError, ItermControllerError)
        assert issubclass(ItermSessionError, SessionError)
        assert issubclass(SessionSpawnError, SessionError)
        assert issubclass(SessionTerminationError, SessionError)

    def test_connection_errors_inherit_from_base(self):
        """Connection errors inherit from ItermControllerError."""
        assert issubclass(ItermControllerConnectionError, ItermControllerError)
        assert issubclass(ItermConnectionError, ItermControllerConnectionError)
        assert issubclass(ItermNotConnectedError, ItermControllerConnectionError)
        assert issubclass(NetworkError, ItermControllerConnectionError)

    def test_github_errors_inherit_from_base(self):
        """GitHub errors inherit from ItermControllerError."""
        assert issubclass(GitHubError, ItermControllerError)
        assert issubclass(GitHubUnavailableError, GitHubError)
        assert issubclass(RateLimitError, GitHubError)
