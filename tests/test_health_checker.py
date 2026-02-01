"""Tests for HTTP health check polling system."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from iterm_controller.health_checker import HealthCheckPoller, ProjectHealthManager
from iterm_controller.models import HealthCheck, HealthStatus, Project


class TestHealthCheckPoller:
    """Test HealthCheckPoller functionality."""

    def test_init_defaults(self):
        """Poller initializes with correct defaults."""
        poller = HealthCheckPoller(env={})

        assert poller.env == {}
        assert poller.on_status_change is None
        assert poller.is_running() is False
        assert poller.get_all_status() == {}

    def test_init_with_env(self):
        """Poller initializes with environment variables."""
        env = {"API_PORT": "8080", "HOST": "localhost"}
        poller = HealthCheckPoller(env=env)

        assert poller.env == env

    def test_init_with_callback(self):
        """Poller initializes with callback."""
        callback = MagicMock()
        poller = HealthCheckPoller(env={}, on_status_change=callback)

        assert poller.on_status_change is callback

    # ==========================================================================
    # URL Resolution
    # ==========================================================================

    def test_resolve_url_no_placeholders(self):
        """resolve_url returns URL unchanged when no placeholders."""
        poller = HealthCheckPoller(env={})

        result = poller.resolve_url("http://localhost:8080/health")

        assert result == "http://localhost:8080/health"

    def test_resolve_url_single_placeholder(self):
        """resolve_url replaces single placeholder."""
        poller = HealthCheckPoller(env={"API_PORT": "8080"})

        result = poller.resolve_url("http://localhost:{env.API_PORT}/health")

        assert result == "http://localhost:8080/health"

    def test_resolve_url_multiple_placeholders(self):
        """resolve_url replaces multiple placeholders."""
        poller = HealthCheckPoller(env={"HOST": "api.example.com", "PORT": "443"})

        result = poller.resolve_url("https://{env.HOST}:{env.PORT}/health")

        assert result == "https://api.example.com:443/health"

    def test_resolve_url_missing_env_var(self):
        """resolve_url replaces missing env var with empty string."""
        poller = HealthCheckPoller(env={})

        result = poller.resolve_url("http://localhost:{env.MISSING_PORT}/health")

        assert result == "http://localhost:/health"

    def test_resolve_url_partial_env(self):
        """resolve_url handles mix of present and missing vars."""
        poller = HealthCheckPoller(env={"HOST": "localhost"})

        result = poller.resolve_url("http://{env.HOST}:{env.PORT}/health")

        assert result == "http://localhost:/health"

    # ==========================================================================
    # Status Management
    # ==========================================================================

    def test_get_status_unknown_for_new_check(self):
        """get_status returns UNKNOWN for check that hasn't been performed."""
        poller = HealthCheckPoller(env={})

        result = poller.get_status("nonexistent")

        assert result == HealthStatus.UNKNOWN

    def test_get_all_status_empty(self):
        """get_all_status returns empty dict when no checks."""
        poller = HealthCheckPoller(env={})

        result = poller.get_all_status()

        assert result == {}

    def test_get_all_status_returns_copy(self):
        """get_all_status returns a copy."""
        poller = HealthCheckPoller(env={})
        poller._status["test"] = HealthStatus.HEALTHY

        result = poller.get_all_status()
        result["test"] = HealthStatus.UNHEALTHY

        # Original should not be modified
        assert poller.get_status("test") == HealthStatus.HEALTHY

    # ==========================================================================
    # Polling Lifecycle
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_start_polling_sets_running(self):
        """start_polling sets running flag."""
        poller = HealthCheckPoller(env={})
        check = HealthCheck(name="test", url="http://localhost:8080")

        await poller.start_polling([check])

        assert poller.is_running() is True
        assert poller.get_status("test") == HealthStatus.UNKNOWN

        await poller.stop_polling()

    @pytest.mark.asyncio
    async def test_start_polling_creates_tasks_for_interval_checks(self):
        """start_polling creates tasks for checks with interval > 0."""
        poller = HealthCheckPoller(env={})
        check1 = HealthCheck(name="with_interval", url="http://localhost", interval_seconds=10.0)
        check2 = HealthCheck(name="manual_only", url="http://localhost", interval_seconds=0.0)

        await poller.start_polling([check1, check2])

        # Should have task for check1 but not check2
        assert "with_interval" in poller._tasks
        assert "manual_only" not in poller._tasks

        await poller.stop_polling()

    @pytest.mark.asyncio
    async def test_stop_polling_clears_running(self):
        """stop_polling clears running flag."""
        poller = HealthCheckPoller(env={})
        check = HealthCheck(name="test", url="http://localhost", interval_seconds=10.0)

        await poller.start_polling([check])
        await poller.stop_polling()

        assert poller.is_running() is False
        assert len(poller._tasks) == 0

    @pytest.mark.asyncio
    async def test_stop_polling_cancels_tasks(self):
        """stop_polling cancels running tasks."""
        poller = HealthCheckPoller(env={})
        check = HealthCheck(name="test", url="http://localhost", interval_seconds=10.0)

        await poller.start_polling([check])
        task = poller._tasks["test"]

        await poller.stop_polling()

        assert task.cancelled()

    # ==========================================================================
    # Health Check Execution
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_perform_check_healthy(self):
        """_perform_check returns HEALTHY for successful check."""
        poller = HealthCheckPoller(env={})
        check = HealthCheck(name="test", url="http://localhost:8080", expected_status=200)

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await poller._perform_check(check)

        assert result == HealthStatus.HEALTHY
        assert poller.get_status("test") == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_perform_check_unhealthy_wrong_status(self):
        """_perform_check returns UNHEALTHY for wrong status code."""
        poller = HealthCheckPoller(env={})
        check = HealthCheck(name="test", url="http://localhost:8080", expected_status=200)

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await poller._perform_check(check)

        assert result == HealthStatus.UNHEALTHY
        assert poller.get_status("test") == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_perform_check_unhealthy_connect_error(self):
        """_perform_check returns UNHEALTHY on connection error."""
        poller = HealthCheckPoller(env={})
        check = HealthCheck(name="test", url="http://localhost:8080")

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.request = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await poller._perform_check(check)

        assert result == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_perform_check_unhealthy_timeout(self):
        """_perform_check returns UNHEALTHY on timeout."""
        poller = HealthCheckPoller(env={})
        check = HealthCheck(name="test", url="http://localhost:8080")

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.request = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await poller._perform_check(check)

        assert result == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_perform_check_unhealthy_generic_exception(self):
        """_perform_check returns UNHEALTHY on generic exception."""
        poller = HealthCheckPoller(env={})
        check = HealthCheck(name="test", url="http://localhost:8080")

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.request = AsyncMock(side_effect=Exception("Unknown error"))
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await poller._perform_check(check)

        assert result == HealthStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_perform_check_uses_correct_method(self):
        """_perform_check uses configured HTTP method."""
        poller = HealthCheckPoller(env={})
        check = HealthCheck(name="test", url="http://localhost:8080", method="POST")

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_request = AsyncMock(return_value=mock_response)
            mock_client.request = mock_request
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            await poller._perform_check(check)

        mock_request.assert_called_once_with(
            method="POST",
            url="http://localhost:8080",
            timeout=5.0,
        )

    @pytest.mark.asyncio
    async def test_perform_check_uses_timeout(self):
        """_perform_check uses configured timeout."""
        poller = HealthCheckPoller(env={})
        check = HealthCheck(name="test", url="http://localhost:8080", timeout_seconds=2.5)

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_request = AsyncMock(return_value=mock_response)
            mock_client.request = mock_request
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            await poller._perform_check(check)

        mock_request.assert_called_once_with(
            method="GET",
            url="http://localhost:8080",
            timeout=2.5,
        )

    @pytest.mark.asyncio
    async def test_perform_check_resolves_url_placeholders(self):
        """_perform_check resolves URL placeholders."""
        poller = HealthCheckPoller(env={"PORT": "9000"})
        check = HealthCheck(name="test", url="http://localhost:{env.PORT}/health")

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_request = AsyncMock(return_value=mock_response)
            mock_client.request = mock_request
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            await poller._perform_check(check)

        mock_request.assert_called_once_with(
            method="GET",
            url="http://localhost:9000/health",
            timeout=5.0,
        )

    # ==========================================================================
    # Callback
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_callback_invoked_on_status_change(self):
        """Callback is invoked when status changes."""
        callback_calls = []

        def on_change(name, status):
            callback_calls.append((name, status))

        poller = HealthCheckPoller(env={}, on_status_change=on_change)
        check = HealthCheck(name="test", url="http://localhost:8080")

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            await poller._perform_check(check)

        assert len(callback_calls) == 1
        assert callback_calls[0] == ("test", HealthStatus.HEALTHY)

    @pytest.mark.asyncio
    async def test_callback_not_invoked_when_status_unchanged(self):
        """Callback is not invoked when status doesn't change."""
        callback_calls = []

        def on_change(name, status):
            callback_calls.append((name, status))

        poller = HealthCheckPoller(env={}, on_status_change=on_change)
        check = HealthCheck(name="test", url="http://localhost:8080")

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            # First check - status changes from None to HEALTHY
            await poller._perform_check(check)
            # Second check - status stays HEALTHY
            await poller._perform_check(check)

        # Callback should only be called once (first change)
        assert len(callback_calls) == 1

    @pytest.mark.asyncio
    async def test_callback_invoked_on_status_transition(self):
        """Callback is invoked when status transitions between states."""
        callback_calls = []

        def on_change(name, status):
            callback_calls.append((name, status))

        poller = HealthCheckPoller(env={}, on_status_change=on_change)
        check = HealthCheck(name="test", url="http://localhost:8080")

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            # First check - HEALTHY
            mock_response.status_code = 200
            mock_client.request = AsyncMock(return_value=mock_response)
            await poller._perform_check(check)

            # Second check - UNHEALTHY
            mock_response.status_code = 500
            await poller._perform_check(check)

        assert len(callback_calls) == 2
        assert callback_calls[0] == ("test", HealthStatus.HEALTHY)
        assert callback_calls[1] == ("test", HealthStatus.UNHEALTHY)

    # ==========================================================================
    # Manual Checks
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_check_now(self):
        """check_now performs a manual check."""
        poller = HealthCheckPoller(env={})
        check = HealthCheck(name="test", url="http://localhost:8080")

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await poller.check_now(check)

        assert result == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_check_by_name_found(self):
        """check_by_name performs check for registered name."""
        poller = HealthCheckPoller(env={})
        check = HealthCheck(name="test", url="http://localhost:8080")

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            # Register the check (this creates the shared client)
            await poller.start_polling([check])

            result = await poller.check_by_name("test")

            assert result == HealthStatus.HEALTHY

            await poller.stop_polling()

    @pytest.mark.asyncio
    async def test_check_by_name_not_found(self):
        """check_by_name returns None for unknown name."""
        poller = HealthCheckPoller(env={})

        result = await poller.check_by_name("unknown")

        assert result is None

    # ==========================================================================
    # Client Reuse
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_start_polling_creates_shared_client(self):
        """start_polling creates a shared httpx client."""
        poller = HealthCheckPoller(env={})
        check = HealthCheck(name="test", url="http://localhost:8080", interval_seconds=10.0)

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            await poller.start_polling([check])

            # Shared client should be created
            assert poller._client is not None
            assert poller._client is mock_client

            await poller.stop_polling()

    @pytest.mark.asyncio
    async def test_stop_polling_closes_shared_client(self):
        """stop_polling closes the shared httpx client."""
        poller = HealthCheckPoller(env={})
        check = HealthCheck(name="test", url="http://localhost:8080", interval_seconds=10.0)

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            await poller.start_polling([check])
            await poller.stop_polling()

            # Client should be closed and cleared
            mock_client.aclose.assert_called_once()
            assert poller._client is None

    @pytest.mark.asyncio
    async def test_perform_check_reuses_shared_client(self):
        """_perform_check reuses the shared client when available."""
        poller = HealthCheckPoller(env={})
        check = HealthCheck(name="test", url="http://localhost:8080", interval_seconds=10.0)

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            await poller.start_polling([check])

            # Perform multiple checks
            await poller._perform_check(check)
            await poller._perform_check(check)
            await poller._perform_check(check)

            # Client should only be created once (in start_polling)
            assert mock_client_class.call_count == 1

            await poller.stop_polling()

    @pytest.mark.asyncio
    async def test_perform_check_creates_temporary_client_when_no_shared(self):
        """_perform_check creates a temporary client when shared is unavailable."""
        poller = HealthCheckPoller(env={})
        check = HealthCheck(name="test", url="http://localhost:8080")

        with patch("iterm_controller.health_checker.httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client.aclose = AsyncMock()
            mock_client_class.return_value = mock_client

            # Don't call start_polling - directly call _perform_check
            await poller._perform_check(check)

            # Temporary client should be created and closed
            assert mock_client_class.call_count == 1
            mock_client.aclose.assert_called_once()


class TestProjectHealthManager:
    """Test ProjectHealthManager functionality."""

    def make_project(self, project_id="project-1"):
        """Create a Project for testing."""
        return Project(
            id=project_id,
            name="Test Project",
            path="/path/to/project",
        )

    def test_init(self):
        """Manager initializes with empty pollers."""
        manager = ProjectHealthManager()

        assert manager.pollers == {}

    @pytest.mark.asyncio
    async def test_start_project_checks(self):
        """start_project_checks creates and starts a poller."""
        manager = ProjectHealthManager()
        project = self.make_project()
        checks = [HealthCheck(name="test", url="http://localhost:8080")]
        env = {"API_PORT": "8080"}

        poller = await manager.start_project_checks(project, checks, env)

        assert project.id in manager.pollers
        assert manager.pollers[project.id] is poller
        assert poller.is_running() is True

        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_start_project_checks_with_callback(self):
        """start_project_checks passes callback to poller."""
        manager = ProjectHealthManager()
        project = self.make_project()
        checks = [HealthCheck(name="test", url="http://localhost:8080")]
        callback = MagicMock()

        poller = await manager.start_project_checks(
            project, checks, env={}, on_status_change=callback
        )

        assert poller.on_status_change is callback

        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_start_project_checks_replaces_existing(self):
        """start_project_checks replaces existing poller for project."""
        manager = ProjectHealthManager()
        project = self.make_project()
        checks = [HealthCheck(name="test", url="http://localhost:8080")]

        poller1 = await manager.start_project_checks(project, checks, env={})
        poller2 = await manager.start_project_checks(project, checks, env={})

        assert manager.pollers[project.id] is poller2
        assert poller2 is not poller1
        assert poller1.is_running() is False  # Should be stopped

        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_stop_project_checks(self):
        """stop_project_checks stops and removes poller."""
        manager = ProjectHealthManager()
        project = self.make_project()
        checks = [HealthCheck(name="test", url="http://localhost:8080")]

        poller = await manager.start_project_checks(project, checks, env={})
        await manager.stop_project_checks(project.id)

        assert project.id not in manager.pollers
        assert poller.is_running() is False

    @pytest.mark.asyncio
    async def test_stop_project_checks_nonexistent(self):
        """stop_project_checks is safe for nonexistent project."""
        manager = ProjectHealthManager()

        # Should not raise
        await manager.stop_project_checks("nonexistent")

    @pytest.mark.asyncio
    async def test_stop_all(self):
        """stop_all stops all pollers."""
        manager = ProjectHealthManager()
        project1 = self.make_project("project-1")
        project2 = self.make_project("project-2")
        checks = [HealthCheck(name="test", url="http://localhost:8080")]

        poller1 = await manager.start_project_checks(project1, checks, env={})
        poller2 = await manager.start_project_checks(project2, checks, env={})

        await manager.stop_all()

        assert len(manager.pollers) == 0
        assert poller1.is_running() is False
        assert poller2.is_running() is False

    @pytest.mark.asyncio
    async def test_get_project_status(self):
        """get_project_status returns status from project's poller."""
        manager = ProjectHealthManager()
        project = self.make_project()
        checks = [HealthCheck(name="test", url="http://localhost:8080")]

        await manager.start_project_checks(project, checks, env={})

        # Manually set status for testing
        manager.pollers[project.id]._status["test"] = HealthStatus.HEALTHY

        result = manager.get_project_status(project.id)

        assert result == {"test": HealthStatus.HEALTHY}

        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_get_project_status_nonexistent(self):
        """get_project_status returns empty dict for nonexistent project."""
        manager = ProjectHealthManager()

        result = manager.get_project_status("nonexistent")

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_poller(self):
        """get_poller returns poller for project."""
        manager = ProjectHealthManager()
        project = self.make_project()
        checks = [HealthCheck(name="test", url="http://localhost:8080")]

        poller = await manager.start_project_checks(project, checks, env={})

        result = manager.get_poller(project.id)

        assert result is poller

        await manager.stop_all()

    @pytest.mark.asyncio
    async def test_get_poller_nonexistent(self):
        """get_poller returns None for nonexistent project."""
        manager = ProjectHealthManager()

        result = manager.get_poller("nonexistent")

        assert result is None
