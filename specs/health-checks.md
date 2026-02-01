# Health Checks

## Overview

HTTP endpoint polling to verify that services are running and healthy.

## Configuration

```python
from dataclasses import dataclass

@dataclass
class HealthCheck:
    """HTTP health check configuration."""
    name: str                        # Display name (e.g., "API Health")
    url: str                         # URL with optional {env.VAR} placeholders
    method: str = "GET"              # HTTP method
    expected_status: int = 200       # Expected response code
    timeout_seconds: float = 5.0     # Request timeout
    interval_seconds: float = 10.0   # Polling interval (0 = manual only)

class HealthStatus(Enum):
    """Health check result status."""
    UNKNOWN = "unknown"     # Not yet checked
    CHECKING = "checking"   # Check in progress
    HEALTHY = "healthy"     # Check passed
    UNHEALTHY = "unhealthy" # Check failed
```

## Health Check Poller

```python
import asyncio
import httpx
import re

class HealthCheckPoller:
    """Polls HTTP health check endpoints."""

    def __init__(self, env: dict[str, str]):
        self.env = env
        self._running = False
        self._tasks: dict[str, asyncio.Task] = {}
        self._status: dict[str, HealthStatus] = {}

    def resolve_url(self, url: str) -> str:
        """Resolve {env.VAR} placeholders in URL."""
        pattern = re.compile(r'\{env\.(\w+)\}')

        def replace(match):
            var_name = match.group(1)
            return self.env.get(var_name, "")

        return pattern.sub(replace, url)

    async def start_polling(self, checks: list[HealthCheck]):
        """Start polling all health checks."""
        self._running = True

        for check in checks:
            if check.interval_seconds > 0:
                task = asyncio.create_task(self._poll_loop(check))
                self._tasks[check.name] = task
                self._status[check.name] = HealthStatus.UNKNOWN

    async def stop_polling(self):
        """Stop all polling tasks."""
        self._running = False
        for task in self._tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()

    async def _poll_loop(self, check: HealthCheck):
        """Polling loop for a single health check."""
        while self._running:
            await self._perform_check(check)
            await asyncio.sleep(check.interval_seconds)

    async def _perform_check(self, check: HealthCheck) -> HealthStatus:
        """Perform a single health check."""
        self._status[check.name] = HealthStatus.CHECKING

        url = self.resolve_url(check.url)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=check.method,
                    url=url,
                    timeout=check.timeout_seconds
                )

                if response.status_code == check.expected_status:
                    self._status[check.name] = HealthStatus.HEALTHY
                else:
                    self._status[check.name] = HealthStatus.UNHEALTHY

        except httpx.ConnectError:
            self._status[check.name] = HealthStatus.UNHEALTHY
        except httpx.TimeoutException:
            self._status[check.name] = HealthStatus.UNHEALTHY
        except Exception:
            self._status[check.name] = HealthStatus.UNHEALTHY

        return self._status[check.name]

    def get_status(self, name: str) -> HealthStatus:
        """Get current status of a health check."""
        return self._status.get(name, HealthStatus.UNKNOWN)

    def get_all_status(self) -> dict[str, HealthStatus]:
        """Get status of all health checks."""
        return self._status.copy()

    async def check_now(self, check: HealthCheck) -> HealthStatus:
        """Manually trigger a health check."""
        return await self._perform_check(check)
```

## Health Status Widget

```python
class HealthStatusWidget(Static):
    """Displays health check status indicators."""

    def __init__(self, poller: HealthCheckPoller, **kwargs):
        super().__init__(**kwargs)
        self.poller = poller

    def render(self) -> str:
        """Render health status indicators."""
        statuses = self.poller.get_all_status()

        if not statuses:
            return ""

        parts = []
        for name, status in statuses.items():
            icon, color = self._get_icon_color(status)
            parts.append(f"[{color}]{name} {icon}[/{color}]")

        return " ".join(parts)

    def _get_icon_color(self, status: HealthStatus) -> tuple[str, str]:
        """Get icon and color for status."""
        return {
            HealthStatus.UNKNOWN: ("○", "dim"),
            HealthStatus.CHECKING: ("◐", "yellow"),
            HealthStatus.HEALTHY: ("●", "green"),
            HealthStatus.UNHEALTHY: ("✗", "red"),
        }[status]
```

## Integration with Project

```python
class ProjectHealthManager:
    """Manages health checks for a project."""

    def __init__(self):
        self.pollers: dict[str, HealthCheckPoller] = {}

    async def start_project_checks(
        self,
        project: Project,
        checks: list[HealthCheck],
        env: dict[str, str]
    ):
        """Start health checks for a project."""
        poller = HealthCheckPoller(env)
        await poller.start_polling(checks)
        self.pollers[project.id] = poller

    async def stop_project_checks(self, project_id: str):
        """Stop health checks for a project."""
        poller = self.pollers.pop(project_id, None)
        if poller:
            await poller.stop_polling()

    def get_project_status(
        self,
        project_id: str
    ) -> dict[str, HealthStatus]:
        """Get health status for a project."""
        poller = self.pollers.get(project_id)
        if poller:
            return poller.get_all_status()
        return {}
```

## Error Handling

| Error | Result |
|-------|--------|
| Connection refused | `UNHEALTHY` |
| Timeout | `UNHEALTHY` |
| Wrong status code | `UNHEALTHY` |
| Invalid URL | `UNHEALTHY` |
| DNS resolution failure | `UNHEALTHY` |

All checks stop when project closes.

## Example Configuration

```json
{
  "health_checks": [
    {
      "name": "API",
      "url": "http://localhost:{env.API_PORT}/health",
      "method": "GET",
      "expected_status": 200,
      "timeout_seconds": 5.0,
      "interval_seconds": 10.0,
      "service": "api_server"
    },
    {
      "name": "Web",
      "url": "http://localhost:3000",
      "method": "GET",
      "expected_status": 200,
      "interval_seconds": 10.0
    },
    {
      "name": "Database",
      "url": "http://localhost:5432",
      "method": "GET",
      "expected_status": 200,
      "timeout_seconds": 2.0,
      "interval_seconds": 30.0
    }
  ]
}
```

## Status Display

```
Health: API ● Web ● DB ○
```

- `●` Green = Healthy
- `✗` Red = Unhealthy
- `○` Gray = Unknown/Not checked
- `◐` Yellow = Checking
