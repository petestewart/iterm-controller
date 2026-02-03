"""Custom exception hierarchy for iTerm Controller."""
from __future__ import annotations
from typing import Any


class ItermControllerError(Exception):
    """Base exception for all iTerm Controller errors."""

    def __init__(
        self, message: str, *, context: dict[str, Any] | None = None, cause: Exception | None = None, **kwargs: Any
    ) -> None:
        self.message = message
        ctx = context or {}
        # Add any additional kwargs to context (e.g., file_path, line_number)
        for key, value in kwargs.items():
            if value is not None:
                ctx[key] = value
        self.context = ctx
        self.cause = cause
        super().__init__(message)

    def __str__(self) -> str:
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({ctx_str})"
        return self.message


# Connection Errors
class ItermConnectionError(ItermControllerError):
    """Raised when iTerm2 connection fails."""


class ItermNotConnectedError(ItermControllerError):
    """Raised when operation requires connection but not connected."""


# Config Errors
class ConfigError(ItermControllerError):
    """Base for configuration errors."""


class ConfigLoadError(ConfigError):
    """Raised when configuration fails to load."""


class ConfigSaveError(ConfigError):
    """Raised when configuration fails to save."""


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails."""


# Plan Errors
class PlanError(ItermControllerError):
    """Base for plan file errors."""


class PlanParseError(PlanError):
    """Raised when PLAN.md parsing fails."""


class PlanWriteError(PlanError):
    """Raised when PLAN.md update fails."""


class TestPlanParseError(PlanError):
    """Raised when TEST_PLAN.md parsing fails."""


class TestPlanWriteError(PlanError):
    """Raised when TEST_PLAN.md update fails."""


class PlanConflictError(PlanError):
    """Raised when there's a conflict with external changes."""


# Git Errors
class GitError(ItermControllerError):
    """Base for git errors."""


class GitNotARepoError(GitError):
    """Raised when path is not a git repository."""


class GitCommandError(GitError):
    """Raised when a git command fails."""


class GitPushRejectedError(GitError):
    """Raised when push is rejected by remote."""


class GitNetworkError(GitError):
    """Raised when network operation fails."""


# GitHub Errors
class GitHubError(ItermControllerError):
    """Base for GitHub errors."""


class NetworkError(GitHubError):
    """Raised when network connection fails."""


class RateLimitError(GitHubError):
    """Raised when GitHub API rate limit is hit."""


# Health Check Errors
class HealthCheckError(ItermControllerError):
    """Base for health check errors."""


class HealthCheckTimeoutError(HealthCheckError):
    """Raised when health check times out."""


# Auto Mode Errors
class CommandNotAllowedError(ItermControllerError):
    """Raised when a command is not in the allowed commands list."""

    def __init__(self, command: str, *, allowed_patterns: list[str] | None = None, context: dict[str, Any] | None = None) -> None:
        ctx = context or {}
        ctx["command"] = command
        if allowed_patterns:
            ctx["allowed_patterns"] = allowed_patterns
        super().__init__(f"Command not allowed: {command}", context=ctx)
        self.command = command
        self.allowed_patterns = allowed_patterns


# Legacy compatibility - no-op error recording
def record_error(error: Exception) -> None:
    """Record an error (no-op for compatibility)."""
    pass
