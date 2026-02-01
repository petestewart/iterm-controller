"""HTTP health check polling.

Polls HTTP endpoints to verify services are running and healthy.
Supports environment variable placeholder resolution in URLs.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Callable

import httpx

from .exceptions import HealthCheckError, HealthCheckTimeoutError, record_error
from .models import HealthCheck, HealthStatus

if TYPE_CHECKING:
    from .models import Project

logger = logging.getLogger(__name__)


class HealthCheckPoller:
    """Polls HTTP health check endpoints."""

    def __init__(
        self,
        env: dict[str, str],
        on_status_change: Callable[[str, HealthStatus], None] | None = None,
    ):
        """Initialize the poller.

        Args:
            env: Environment variables for URL placeholder resolution.
            on_status_change: Optional callback when status changes.
        """
        self.env = env
        self.on_status_change = on_status_change
        self._running = False
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._status: dict[str, HealthStatus] = {}
        self._checks: dict[str, HealthCheck] = {}
        self._client: httpx.AsyncClient | None = None

    def resolve_url(self, url: str) -> str:
        """Resolve {env.VAR} placeholders in URL.

        Args:
            url: URL with optional {env.VAR} placeholders.

        Returns:
            URL with placeholders replaced by environment variable values.
        """
        pattern = re.compile(r"\{env\.(\w+)\}")

        def replace(match: re.Match[str]) -> str:
            var_name = match.group(1)
            return self.env.get(var_name, "")

        return pattern.sub(replace, url)

    async def start_polling(self, checks: list[HealthCheck]) -> None:
        """Start polling all health checks.

        Args:
            checks: List of health check configurations to poll.
        """
        self._running = True

        # Create a shared httpx client for connection pooling
        self._client = httpx.AsyncClient()

        for check in checks:
            self._checks[check.name] = check
            if check.interval_seconds > 0:
                task = asyncio.create_task(self._poll_loop(check))
                self._tasks[check.name] = task
                self._status[check.name] = HealthStatus.UNKNOWN
                logger.debug(
                    "Started polling %s every %.1fs", check.name, check.interval_seconds
                )

    async def stop_polling(self) -> None:
        """Stop all polling tasks."""
        self._running = False
        for task in self._tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()

        # Close the shared httpx client
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _poll_loop(self, check: HealthCheck) -> None:
        """Polling loop for a single health check.

        Args:
            check: Health check configuration.
        """
        while self._running:
            await self._perform_check(check)
            await asyncio.sleep(check.interval_seconds)

    async def _perform_check(self, check: HealthCheck) -> HealthStatus:
        """Perform a single health check.

        Args:
            check: Health check configuration.

        Returns:
            The resulting health status.
        """
        old_status = self._status.get(check.name)
        self._set_status(check.name, HealthStatus.CHECKING)

        url = self.resolve_url(check.url)
        logger.debug("Checking %s at %s", check.name, url)

        # Use shared client if available, otherwise create a temporary one
        # (for check_now() called before start_polling())
        client = self._client
        should_close = False
        if client is None:
            client = httpx.AsyncClient()
            should_close = True

        try:
            response = await client.request(
                method=check.method,
                url=url,
                timeout=check.timeout_seconds,
            )

            if response.status_code == check.expected_status:
                new_status = HealthStatus.HEALTHY
                logger.debug("%s is healthy (status %d)", check.name, response.status_code)
            else:
                new_status = HealthStatus.UNHEALTHY
                logger.warning(
                    "%s unhealthy: expected status %d, got %d",
                    check.name,
                    check.expected_status,
                    response.status_code,
                )

        except httpx.ConnectError as e:
            logger.warning("%s connection refused: %s", check.name, e)
            record_error(e)
            new_status = HealthStatus.UNHEALTHY
        except httpx.TimeoutException as e:
            logger.warning(
                "%s timed out after %.1fs", check.name, check.timeout_seconds
            )
            record_error(HealthCheckTimeoutError(
                f"{check.name} timed out",
                url=url,
                timeout=check.timeout_seconds,
            ))
            new_status = HealthStatus.UNHEALTHY
        except Exception as e:
            logger.error("%s check failed: %s", check.name, e)
            record_error(e)
            new_status = HealthStatus.UNHEALTHY
        finally:
            # Close temporary client if we created one
            if should_close:
                await client.aclose()

        self._set_status(check.name, new_status)

        # Call callback on actual status change (not just CHECKING transitions)
        if self.on_status_change and old_status != new_status:
            logger.info(
                "%s status changed: %s -> %s",
                check.name,
                old_status.value if old_status else "unknown",
                new_status.value,
            )
            self.on_status_change(check.name, new_status)

        return new_status

    def _set_status(self, name: str, status: HealthStatus) -> None:
        """Set the status for a health check.

        Args:
            name: Health check name.
            status: New status.
        """
        self._status[name] = status

    def get_status(self, name: str) -> HealthStatus:
        """Get current status of a health check.

        Args:
            name: Health check name.

        Returns:
            Current health status.
        """
        return self._status.get(name, HealthStatus.UNKNOWN)

    def get_all_status(self) -> dict[str, HealthStatus]:
        """Get status of all health checks.

        Returns:
            Dictionary mapping check names to their status.
        """
        return self._status.copy()

    async def check_now(self, check: HealthCheck) -> HealthStatus:
        """Manually trigger a health check.

        Args:
            check: Health check configuration.

        Returns:
            The resulting health status.
        """
        return await self._perform_check(check)

    async def check_by_name(self, name: str) -> HealthStatus | None:
        """Manually trigger a health check by name.

        Args:
            name: Health check name.

        Returns:
            The resulting health status, or None if not found.
        """
        check = self._checks.get(name)
        if check:
            return await self._perform_check(check)
        return None

    def is_running(self) -> bool:
        """Check if the poller is currently running.

        Returns:
            True if polling is active.
        """
        return self._running


class ProjectHealthManager:
    """Manages health checks for multiple projects."""

    def __init__(self) -> None:
        """Initialize the manager."""
        self.pollers: dict[str, HealthCheckPoller] = {}

    async def start_project_checks(
        self,
        project: Project,
        checks: list[HealthCheck],
        env: dict[str, str],
        on_status_change: Callable[[str, HealthStatus], None] | None = None,
    ) -> HealthCheckPoller:
        """Start health checks for a project.

        Args:
            project: Project to monitor.
            checks: Health check configurations.
            env: Environment variables for URL resolution.
            on_status_change: Optional callback for status changes.

        Returns:
            The HealthCheckPoller instance for this project.
        """
        # Stop existing poller if any
        await self.stop_project_checks(project.id)

        poller = HealthCheckPoller(env, on_status_change)
        await poller.start_polling(checks)
        self.pollers[project.id] = poller
        return poller

    async def stop_project_checks(self, project_id: str) -> None:
        """Stop health checks for a project.

        Args:
            project_id: Project ID to stop monitoring.
        """
        poller = self.pollers.pop(project_id, None)
        if poller:
            await poller.stop_polling()

    async def stop_all(self) -> None:
        """Stop all health check pollers."""
        for project_id in list(self.pollers.keys()):
            await self.stop_project_checks(project_id)

    def get_project_status(self, project_id: str) -> dict[str, HealthStatus]:
        """Get health status for a project.

        Args:
            project_id: Project ID.

        Returns:
            Dictionary mapping check names to their status.
        """
        poller = self.pollers.get(project_id)
        if poller:
            return poller.get_all_status()
        return {}

    def get_poller(self, project_id: str) -> HealthCheckPoller | None:
        """Get the poller for a project.

        Args:
            project_id: Project ID.

        Returns:
            The HealthCheckPoller instance, or None if not found.
        """
        return self.pollers.get(project_id)
