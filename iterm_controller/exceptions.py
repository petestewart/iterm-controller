"""Custom exception hierarchy for iTerm Controller.

This module provides a structured exception hierarchy that enables:
- Consistent error handling across the application
- Rich error context for debugging
- User-friendly error messages
- Error categorization for different handling strategies
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class ItermControllerError(Exception):
    """Base exception for all iTerm Controller errors.

    Attributes:
        message: Human-readable error description.
        context: Additional context for debugging.
        timestamp: When the error occurred.
    """

    def __init__(
        self,
        message: str,
        *,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.message = message
        self.context = context or {}
        self.timestamp = datetime.now()
        self.cause = cause
        super().__init__(message)

    def __str__(self) -> str:
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({ctx_str})"
        return self.message


# =============================================================================
# Connection Errors
# =============================================================================


class ConnectionError(ItermControllerError):
    """Base class for connection-related errors."""

    pass


class ItermConnectionError(ConnectionError):
    """Raised when iTerm2 connection fails."""

    def __init__(
        self,
        message: str = "Failed to connect to iTerm2",
        *,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            message,
            context=context,
            cause=cause,
        )


class ItermNotConnectedError(ConnectionError):
    """Raised when operation requires connection but not connected."""

    def __init__(self, operation: str = "unknown") -> None:
        super().__init__(
            "Not connected to iTerm2",
            context={"attempted_operation": operation},
        )


class NetworkError(ConnectionError):
    """Raised when network connection fails."""

    def __init__(
        self,
        message: str = "Network error occurred",
        *,
        url: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        if url:
            ctx["url"] = url
        super().__init__(message, context=ctx, cause=cause)


# =============================================================================
# Session Errors
# =============================================================================


class SessionError(ItermControllerError):
    """Base class for session-related errors."""

    pass


class ItermSessionError(SessionError):
    """Raised when session operations fail."""

    def __init__(
        self,
        message: str,
        *,
        session_id: str | None = None,
        operation: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        if session_id:
            ctx["session_id"] = session_id
        if operation:
            ctx["operation"] = operation
        super().__init__(message, context=ctx, cause=cause)


class SessionSpawnError(SessionError):
    """Raised when session spawning fails."""

    def __init__(
        self,
        message: str = "Failed to spawn session",
        *,
        template_id: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        if template_id:
            ctx["template_id"] = template_id
        super().__init__(message, context=ctx, cause=cause)


class SessionTerminationError(SessionError):
    """Raised when session termination fails."""

    def __init__(
        self,
        message: str = "Failed to terminate session",
        *,
        session_id: str | None = None,
        timeout: float | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        if session_id:
            ctx["session_id"] = session_id
        if timeout is not None:
            ctx["timeout"] = timeout
        super().__init__(message, context=ctx, cause=cause)


# =============================================================================
# Configuration Errors
# =============================================================================


class ConfigError(ItermControllerError):
    """Base class for configuration-related errors."""

    pass


class ConfigLoadError(ConfigError):
    """Raised when configuration file fails to load."""

    def __init__(
        self,
        message: str = "Failed to load configuration",
        *,
        file_path: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        if file_path:
            ctx["file_path"] = file_path
        super().__init__(message, context=ctx, cause=cause)


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails."""

    def __init__(
        self,
        message: str = "Configuration validation failed",
        *,
        field: str | None = None,
        value: Any = None,
        expected: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        if field:
            ctx["field"] = field
        if value is not None:
            ctx["value"] = str(value)[:100]  # Truncate long values
        if expected:
            ctx["expected"] = expected
        super().__init__(message, context=ctx, cause=cause)


class ConfigSaveError(ConfigError):
    """Raised when configuration fails to save."""

    def __init__(
        self,
        message: str = "Failed to save configuration",
        *,
        file_path: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        if file_path:
            ctx["file_path"] = file_path
        super().__init__(message, context=ctx, cause=cause)


# =============================================================================
# Plan Parsing Errors
# =============================================================================


class PlanError(ItermControllerError):
    """Base class for PLAN.md-related errors."""

    pass


class PlanParseError(PlanError):
    """Raised when PLAN.md parsing fails."""

    def __init__(
        self,
        message: str = "Failed to parse PLAN.md",
        *,
        file_path: str | None = None,
        line_number: int | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        if file_path:
            ctx["file_path"] = file_path
        if line_number is not None:
            ctx["line_number"] = line_number
        super().__init__(message, context=ctx, cause=cause)


class PlanWriteError(PlanError):
    """Raised when PLAN.md update fails."""

    def __init__(
        self,
        message: str = "Failed to update PLAN.md",
        *,
        file_path: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        if file_path:
            ctx["file_path"] = file_path
        super().__init__(message, context=ctx, cause=cause)


class PlanConflictError(PlanError):
    """Raised when there's a conflict with external changes."""

    def __init__(
        self,
        message: str = "PLAN.md was modified externally",
        *,
        file_path: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        if file_path:
            ctx["file_path"] = file_path
        super().__init__(message, context=ctx, cause=cause)


# =============================================================================
# Test Plan Parsing Errors
# =============================================================================


class TestPlanError(ItermControllerError):
    """Base class for TEST_PLAN.md-related errors."""

    pass


class TestPlanParseError(TestPlanError):
    """Raised when TEST_PLAN.md parsing fails."""

    def __init__(
        self,
        message: str = "Failed to parse TEST_PLAN.md",
        *,
        file_path: str | None = None,
        line_number: int | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        if file_path:
            ctx["file_path"] = file_path
        if line_number is not None:
            ctx["line_number"] = line_number
        super().__init__(message, context=ctx, cause=cause)


class TestPlanWriteError(TestPlanError):
    """Raised when TEST_PLAN.md update fails."""

    def __init__(
        self,
        message: str = "Failed to update TEST_PLAN.md",
        *,
        file_path: str | None = None,
        step_id: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        if file_path:
            ctx["file_path"] = file_path
        if step_id:
            ctx["step_id"] = step_id
        super().__init__(message, context=ctx, cause=cause)


# =============================================================================
# GitHub Errors
# =============================================================================


class GitHubError(ItermControllerError):
    """Base class for GitHub-related errors."""

    pass


class GitHubUnavailableError(GitHubError):
    """Raised when gh CLI is unavailable."""

    def __init__(
        self,
        message: str = "GitHub CLI is not available",
        *,
        reason: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        if reason:
            ctx["reason"] = reason
        super().__init__(message, context=ctx, cause=cause)


class RateLimitError(GitHubError):
    """Raised when GitHub API rate limit is hit."""

    def __init__(
        self,
        message: str = "GitHub API rate limit exceeded",
        *,
        reset_time: datetime | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        if reset_time:
            ctx["reset_time"] = reset_time.isoformat()
        super().__init__(message, context=ctx, cause=cause)


# =============================================================================
# Health Check Errors
# =============================================================================


class HealthCheckError(ItermControllerError):
    """Base class for health check errors."""

    pass


class HealthCheckTimeoutError(HealthCheckError):
    """Raised when health check times out."""

    def __init__(
        self,
        message: str = "Health check timed out",
        *,
        url: str | None = None,
        timeout: float | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        if url:
            ctx["url"] = url
        if timeout is not None:
            ctx["timeout_seconds"] = timeout
        super().__init__(message, context=ctx, cause=cause)


# =============================================================================
# Template Errors
# =============================================================================


class TemplateError(ItermControllerError):
    """Base class for template-related errors."""

    pass


class TemplateNotFoundError(TemplateError):
    """Raised when a template is not found."""

    def __init__(
        self,
        template_id: str,
        *,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        ctx["template_id"] = template_id
        super().__init__(f"Template not found: {template_id}", context=ctx, cause=cause)


class TemplateValidationError(TemplateError):
    """Raised when template validation fails."""

    def __init__(
        self,
        message: str = "Template validation failed",
        *,
        template_id: str | None = None,
        field: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        ctx = context or {}
        if template_id:
            ctx["template_id"] = template_id
        if field:
            ctx["field"] = field
        super().__init__(message, context=ctx, cause=cause)


# =============================================================================
# Notification Errors
# =============================================================================


class NotificationError(ItermControllerError):
    """Base class for notification errors."""

    pass


class NotificationUnavailableError(NotificationError):
    """Raised when notification system is unavailable."""

    def __init__(
        self,
        message: str = "Notification system is not available",
        *,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, context=context, cause=cause)


# =============================================================================
# Error Registry for Categorization
# =============================================================================


@dataclass
class ErrorStats:
    """Track error statistics for monitoring."""

    total_count: int = 0
    by_type: dict[str, int] = field(default_factory=dict)
    recent_errors: list[tuple[datetime, str, str]] = field(default_factory=list)
    max_recent: int = 100

    def record(self, error: Exception) -> None:
        """Record an error occurrence."""
        self.total_count += 1
        type_name = type(error).__name__
        self.by_type[type_name] = self.by_type.get(type_name, 0) + 1

        self.recent_errors.append((datetime.now(), type_name, str(error)[:200]))
        if len(self.recent_errors) > self.max_recent:
            self.recent_errors.pop(0)


# Global error stats tracker
error_stats = ErrorStats()


def record_error(error: Exception) -> None:
    """Record an error to global stats."""
    error_stats.record(error)
