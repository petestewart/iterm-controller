"""Tests for iTerm2 connection and session management."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iterm_controller.exceptions import (
    ItermConnectionError,
    ItermNotConnectedError,
)
from iterm_controller.iterm import (
    CloseResult,
    ItermController,
    LayoutSpawnResult,
    SessionSpawner,
    SessionTerminator,
    SpawnResult,
    TabState,
    WindowLayoutManager,
    WindowLayoutSpawner,
    WindowState,
    WindowTracker,
    with_reconnect,
)
from iterm_controller.models import (
    Project,
    SessionLayout,
    SessionTemplate,
    TabLayout,
    WindowLayout,
)


class TestItermController:
    """Test ItermController connection management."""

    def test_init_not_connected(self):
        """Controller starts in disconnected state."""
        controller = ItermController()
        assert controller.connection is None
        assert controller.app is None
        assert controller.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Successful connection sets state correctly."""
        controller = ItermController()

        mock_connection = MagicMock()
        mock_app = MagicMock()

        with patch("iterm2.Connection.async_create", new_callable=AsyncMock) as mock_create:
            with patch("iterm2.async_get_app", new_callable=AsyncMock) as mock_get_app:
                mock_create.return_value = mock_connection
                mock_get_app.return_value = mock_app

                result = await controller.connect()

        assert result is True
        assert controller.connection is mock_connection
        assert controller.app is mock_app
        assert controller.is_connected is True

    @pytest.mark.asyncio
    async def test_connect_connection_refused(self):
        """Connection refused raises ItermConnectionError."""
        controller = ItermController()

        with patch("iterm2.Connection.async_create", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = ConnectionRefusedError("Connection refused")

            with pytest.raises(ItermConnectionError) as exc_info:
                await controller.connect()

            assert "Connection refused" in str(exc_info.value)
            assert "Python API enabled" in str(exc_info.value)
            assert controller.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_generic_error(self):
        """Generic connection error raises ItermConnectionError."""
        controller = ItermController()

        with patch("iterm2.Connection.async_create", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = Exception("Unknown error")

            with pytest.raises(ItermConnectionError) as exc_info:
                await controller.connect()

            assert "Failed to connect" in str(exc_info.value)
            assert controller.is_connected is False

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Disconnect clears connection state."""
        controller = ItermController()
        controller.connection = MagicMock()
        controller.app = MagicMock()
        controller._connected = True

        await controller.disconnect()

        assert controller.connection is None
        assert controller.app is None
        assert controller.is_connected is False

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self):
        """Disconnect is safe when not connected."""
        controller = ItermController()
        assert controller.is_connected is False

        # Should not raise
        await controller.disconnect()

        assert controller.is_connected is False

    @pytest.mark.asyncio
    async def test_reconnect(self):
        """Reconnect disconnects then connects."""
        controller = ItermController()
        controller.connection = MagicMock()
        controller._connected = True

        mock_new_connection = MagicMock()
        mock_new_app = MagicMock()

        with patch("iterm2.Connection.async_create", new_callable=AsyncMock) as mock_create:
            with patch("iterm2.async_get_app", new_callable=AsyncMock) as mock_get_app:
                mock_create.return_value = mock_new_connection
                mock_get_app.return_value = mock_new_app

                result = await controller.reconnect()

        assert result is True
        assert controller.connection is mock_new_connection
        assert controller.app is mock_new_app

    @pytest.mark.asyncio
    async def test_verify_version_not_connected(self):
        """Verify version fails when not connected."""
        controller = ItermController()

        success, message = await controller.verify_version()

        assert success is False
        assert "Not connected" in message

    @pytest.mark.asyncio
    async def test_verify_version_connected(self):
        """Verify version succeeds when connected."""
        controller = ItermController()
        controller.app = MagicMock()

        success, message = await controller.verify_version()

        assert success is True
        assert "3.5+" in message

    def test_require_connection_when_connected(self):
        """require_connection does nothing when connected."""
        controller = ItermController()
        controller.connection = MagicMock()
        controller._connected = True

        # Should not raise
        controller.require_connection()

    def test_require_connection_when_not_connected(self):
        """require_connection raises when not connected."""
        controller = ItermController()

        with pytest.raises(ItermNotConnectedError) as exc_info:
            controller.require_connection()

        assert "Not connected" in str(exc_info.value)

    def test_is_connected_property(self):
        """is_connected property reflects actual state."""
        controller = ItermController()

        # Not connected
        assert controller.is_connected is False

        # Set _connected but no connection object
        controller._connected = True
        assert controller.is_connected is False

        # Set connection but not _connected flag
        controller._connected = False
        controller.connection = MagicMock()
        assert controller.is_connected is False

        # Both set
        controller._connected = True
        assert controller.is_connected is True


class TestWithReconnect:
    """Test the with_reconnect retry helper."""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self):
        """Operation succeeding on first try returns result."""
        controller = ItermController()
        controller._connected = True
        controller.connection = MagicMock()

        async def operation():
            return "success"

        result = await with_reconnect(controller, operation)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        """Connection error triggers reconnect and retry."""
        controller = ItermController()

        attempt = {"count": 0}

        async def operation():
            attempt["count"] += 1
            if attempt["count"] == 1:
                raise Exception("Connection closed")
            return "success"

        mock_connection = MagicMock()
        mock_app = MagicMock()

        with patch("iterm2.Connection.async_create", new_callable=AsyncMock) as mock_create:
            with patch("iterm2.async_get_app", new_callable=AsyncMock) as mock_get_app:
                mock_create.return_value = mock_connection
                mock_get_app.return_value = mock_app

                result = await with_reconnect(controller, operation)

        assert result == "success"
        assert attempt["count"] == 2

    @pytest.mark.asyncio
    async def test_non_connection_error_not_retried(self):
        """Non-connection errors are not retried."""
        controller = ItermController()

        async def operation():
            raise ValueError("Not a connection error")

        with pytest.raises(ValueError):
            await with_reconnect(controller, operation)

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Error raised after max retries exhausted."""
        controller = ItermController()

        async def operation():
            raise Exception("Connection failed")

        with patch("iterm2.Connection.async_create", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = Exception("Reconnect failed")

            with pytest.raises(Exception) as exc_info:
                await with_reconnect(controller, operation, max_retries=2)

            assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_reconnect_failure_continues_to_next_attempt(self):
        """Failed reconnect attempts continue to next retry."""
        controller = ItermController()

        attempt = {"count": 0}

        async def operation():
            attempt["count"] += 1
            if attempt["count"] < 3:
                raise Exception("Connection closed")
            return "success"

        # First reconnect fails, second succeeds
        with patch("iterm2.Connection.async_create", new_callable=AsyncMock) as mock_create:
            with patch("iterm2.async_get_app", new_callable=AsyncMock) as mock_get_app:
                mock_create.side_effect = [
                    ItermConnectionError("First reconnect failed"),
                    MagicMock(),  # Second reconnect succeeds
                ]
                mock_get_app.return_value = MagicMock()

                result = await with_reconnect(controller, operation, max_retries=3)

        assert result == "success"
        assert attempt["count"] == 3


class TestSpawnResult:
    """Test SpawnResult dataclass."""

    def test_spawn_result_success(self):
        """SpawnResult with success state."""
        result = SpawnResult(
            session_id="session-1",
            tab_id="tab-1",
            success=True,
        )
        assert result.session_id == "session-1"
        assert result.tab_id == "tab-1"
        assert result.success is True
        assert result.error is None

    def test_spawn_result_failure(self):
        """SpawnResult with failure state."""
        result = SpawnResult(
            session_id="",
            tab_id="",
            success=False,
            error="Failed to spawn session",
        )
        assert result.success is False
        assert result.error == "Failed to spawn session"


class TestWindowState:
    """Test WindowState and TabState dataclasses."""

    def test_tab_state_defaults(self):
        """TabState has correct defaults."""
        tab = TabState(tab_id="tab-1", title="Test Tab")
        assert tab.tab_id == "tab-1"
        assert tab.title == "Test Tab"
        assert tab.session_ids == []
        assert tab.is_managed is False

    def test_window_state_defaults(self):
        """WindowState has correct defaults."""
        window = WindowState(window_id="window-1")
        assert window.window_id == "window-1"
        assert window.tabs == []
        assert window.managed_tab_ids == set()

    def test_window_state_with_tabs(self):
        """WindowState can contain tabs."""
        tabs = [
            TabState(tab_id="tab-1", title="Tab 1", session_ids=["s1", "s2"]),
            TabState(tab_id="tab-2", title="Tab 2", session_ids=["s3"]),
        ]
        window = WindowState(
            window_id="window-1",
            tabs=tabs,
            managed_tab_ids={"tab-1"},
        )
        assert len(window.tabs) == 2
        assert "tab-1" in window.managed_tab_ids
        assert "tab-2" not in window.managed_tab_ids


class TestWindowTracker:
    """Test WindowTracker class."""

    def test_init(self):
        """WindowTracker initializes with empty state."""
        controller = ItermController()
        tracker = WindowTracker(controller)
        assert tracker.controller is controller
        assert tracker.windows == {}

    def test_mark_managed(self):
        """mark_managed adds tab to managed set."""
        controller = ItermController()
        tracker = WindowTracker(controller)

        # Create a window state
        tracker.windows["window-1"] = WindowState(window_id="window-1")

        # Mark tab as managed
        tracker.mark_managed("tab-1", "window-1")

        assert "tab-1" in tracker.windows["window-1"].managed_tab_ids

    def test_mark_managed_nonexistent_window(self):
        """mark_managed is safe for nonexistent window."""
        controller = ItermController()
        tracker = WindowTracker(controller)

        # Should not raise
        tracker.mark_managed("tab-1", "nonexistent")

    def test_get_managed_tab_ids_all(self):
        """get_managed_tab_ids returns all managed tabs."""
        controller = ItermController()
        tracker = WindowTracker(controller)

        tracker.windows["window-1"] = WindowState(
            window_id="window-1",
            managed_tab_ids={"tab-1", "tab-2"},
        )
        tracker.windows["window-2"] = WindowState(
            window_id="window-2",
            managed_tab_ids={"tab-3"},
        )

        all_managed = tracker.get_managed_tab_ids()

        assert all_managed == {"tab-1", "tab-2", "tab-3"}

    def test_get_managed_tab_ids_by_window(self):
        """get_managed_tab_ids filters by window."""
        controller = ItermController()
        tracker = WindowTracker(controller)

        tracker.windows["window-1"] = WindowState(
            window_id="window-1",
            managed_tab_ids={"tab-1", "tab-2"},
        )
        tracker.windows["window-2"] = WindowState(
            window_id="window-2",
            managed_tab_ids={"tab-3"},
        )

        window1_managed = tracker.get_managed_tab_ids("window-1")
        window2_managed = tracker.get_managed_tab_ids("window-2")
        nonexistent_managed = tracker.get_managed_tab_ids("nonexistent")

        assert window1_managed == {"tab-1", "tab-2"}
        assert window2_managed == {"tab-3"}
        assert nonexistent_managed == set()

    @pytest.mark.asyncio
    async def test_refresh_requires_connection(self):
        """refresh raises when not connected."""
        controller = ItermController()
        tracker = WindowTracker(controller)

        with pytest.raises(ItermNotConnectedError):
            await tracker.refresh()

    @pytest.mark.asyncio
    async def test_refresh_clears_existing_state(self):
        """refresh clears existing window state."""
        controller = ItermController()
        controller._connected = True
        controller.connection = MagicMock()
        controller.app = MagicMock()
        controller.app.terminal_windows = []

        tracker = WindowTracker(controller)
        tracker.windows["old-window"] = WindowState(window_id="old-window")

        await tracker.refresh()

        assert "old-window" not in tracker.windows
        assert tracker.windows == {}

    @pytest.mark.asyncio
    async def test_refresh_populates_window_state(self):
        """refresh populates window state from iTerm2."""
        controller = ItermController()
        controller._connected = True
        controller.connection = MagicMock()

        # Mock iTerm2 app structure
        mock_session = MagicMock()
        mock_session.session_id = "session-1"

        mock_tab = MagicMock()
        mock_tab.tab_id = "tab-1"
        mock_tab.sessions = [mock_session]
        mock_tab.async_get_variable = AsyncMock(return_value="Test Tab")

        mock_window = MagicMock()
        mock_window.window_id = "window-1"
        mock_window.tabs = [mock_tab]

        mock_app = MagicMock()
        mock_app.terminal_windows = [mock_window]
        controller.app = mock_app

        tracker = WindowTracker(controller)
        await tracker.refresh()

        assert "window-1" in tracker.windows
        window_state = tracker.windows["window-1"]
        assert len(window_state.tabs) == 1
        assert window_state.tabs[0].tab_id == "tab-1"
        assert window_state.tabs[0].title == "Test Tab"
        assert window_state.tabs[0].session_ids == ["session-1"]


class TestSessionSpawner:
    """Test SessionSpawner session spawning functionality."""

    def make_template(
        self,
        id: str = "test-template",
        name: str = "Test Template",
        command: str = "echo hello",
        working_dir: str | None = None,
        env: dict | None = None,
    ) -> SessionTemplate:
        """Create a test session template."""
        return SessionTemplate(
            id=id,
            name=name,
            command=command,
            working_dir=working_dir,
            env=env or {},
        )

    def make_project(
        self,
        id: str = "test-project",
        name: str = "Test Project",
        path: str = "/path/to/project",
    ) -> Project:
        """Create a test project."""
        return Project(id=id, name=name, path=path)

    def make_connected_controller(self) -> ItermController:
        """Create a controller in connected state."""
        controller = ItermController()
        controller._connected = True
        controller.connection = MagicMock()
        controller.app = MagicMock()
        return controller

    def test_init(self):
        """SessionSpawner initializes with empty sessions."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        assert spawner.controller is controller
        assert spawner.managed_sessions == {}

    def test_build_command_simple(self):
        """Build command with just command, no env."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        template = self.make_template(command="npm start")
        project = self.make_project(path="/my/project")

        cmd = spawner._build_command(template, project)

        assert cmd == "cd /my/project && npm start"

    def test_build_command_with_working_dir(self):
        """Build command uses template working_dir over project path."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        template = self.make_template(
            command="npm start",
            working_dir="/custom/dir",
        )
        project = self.make_project(path="/my/project")

        cmd = spawner._build_command(template, project)

        assert cmd == "cd /custom/dir && npm start"

    def test_build_command_with_spaces_in_path(self):
        """Build command quotes paths with spaces using shlex.quote."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        template = self.make_template(command="npm start")
        project = self.make_project(path="/path with spaces/project")

        cmd = spawner._build_command(template, project)

        # shlex.quote uses single quotes for paths with spaces
        assert cmd == "cd '/path with spaces/project' && npm start"

    def test_build_command_with_env(self):
        """Build command includes environment variable exports."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        template = self.make_template(
            command="npm start",
            env={"PORT": "3000", "NODE_ENV": "development"},
        )
        project = self.make_project(path="/my/project")

        cmd = spawner._build_command(template, project)

        # Order may vary, so check parts
        # shlex.quote doesn't add quotes for simple alphanumeric values
        assert cmd.startswith("cd /my/project && export ")
        assert "PORT=3000" in cmd
        assert "NODE_ENV=development" in cmd
        assert cmd.endswith(" && npm start")

    def test_build_command_empty_command(self):
        """Build command handles empty template command."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        template = self.make_template(command="")
        project = self.make_project(path="/my/project")

        cmd = spawner._build_command(template, project)

        assert cmd == "cd /my/project"

    def test_build_command_escapes_env_values(self):
        """Build command escapes special characters in env values using shlex.quote."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        template = self.make_template(
            command="echo test",
            env={"MSG": 'Hello "World"'},
        )
        project = self.make_project()

        cmd = spawner._build_command(template, project)

        # shlex.quote uses single quotes to protect double quotes
        assert "MSG='Hello \"World\"'" in cmd

    # -------------------------------------------------------------------------
    # Security Tests - Command Injection Prevention
    # -------------------------------------------------------------------------

    def test_build_command_prevents_command_injection_via_env_value(self):
        """Verify env values with command injection attempts are safely quoted."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        template = self.make_template(
            command="echo test",
            env={"MALICIOUS": "$(rm -rf /)"},
        )
        project = self.make_project()

        cmd = spawner._build_command(template, project)

        # The command substitution should be quoted, not executed
        assert "MALICIOUS='$(rm -rf /)'" in cmd
        # Ensure it's not unquoted
        assert "MALICIOUS=$(rm -rf /)" not in cmd

    def test_build_command_prevents_backtick_injection(self):
        """Verify env values with backtick command substitution are safely quoted."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        template = self.make_template(
            command="echo test",
            env={"INJECT": "`whoami`"},
        )
        project = self.make_project()

        cmd = spawner._build_command(template, project)

        # Backticks should be quoted
        assert "INJECT='`whoami`'" in cmd

    def test_build_command_prevents_semicolon_injection(self):
        """Verify env values with semicolons are safely quoted."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        template = self.make_template(
            command="echo test",
            env={"EVIL": "innocent; rm -rf /"},
        )
        project = self.make_project()

        cmd = spawner._build_command(template, project)

        # Semicolons should be quoted
        assert "EVIL='innocent; rm -rf /'" in cmd

    def test_build_command_prevents_pipe_injection(self):
        """Verify env values with pipes are safely quoted."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        template = self.make_template(
            command="echo test",
            env={"PIPE": "test | cat /etc/passwd"},
        )
        project = self.make_project()

        cmd = spawner._build_command(template, project)

        # Pipes should be quoted
        assert "PIPE='test | cat /etc/passwd'" in cmd

    def test_build_command_prevents_env_variable_expansion(self):
        """Verify env values with variable references are safely quoted."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        template = self.make_template(
            command="echo test",
            env={"EXPAND": "$HOME"},
        )
        project = self.make_project()

        cmd = spawner._build_command(template, project)

        # Variable references should be quoted
        assert "EXPAND='$HOME'" in cmd

    def test_build_command_prevents_newline_injection(self):
        """Verify env values with newlines are safely quoted."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        template = self.make_template(
            command="echo test",
            env={"NEWLINE": "first\nsecond"},
        )
        project = self.make_project()

        cmd = spawner._build_command(template, project)

        # The newline should be properly handled by shlex.quote
        # shlex.quote wraps strings with special chars in single quotes
        assert "NEWLINE=" in cmd
        # Verify the value is quoted (single quotes)
        assert "'" in cmd

    def test_validate_env_key_valid_keys(self):
        """Verify valid environment variable keys pass validation."""
        controller = ItermController()
        spawner = SessionSpawner(controller)

        # Valid keys
        assert spawner._validate_env_key("PATH") is True
        assert spawner._validate_env_key("MY_VAR") is True
        assert spawner._validate_env_key("_PRIVATE") is True
        assert spawner._validate_env_key("VAR123") is True
        assert spawner._validate_env_key("a") is True
        assert spawner._validate_env_key("_") is True
        assert spawner._validate_env_key("A1_B2_C3") is True

    def test_validate_env_key_invalid_keys(self):
        """Verify invalid environment variable keys fail validation."""
        controller = ItermController()
        spawner = SessionSpawner(controller)

        # Invalid keys
        assert spawner._validate_env_key("") is False
        assert spawner._validate_env_key("123") is False  # Starts with digit
        assert spawner._validate_env_key("1VAR") is False
        assert spawner._validate_env_key("MY-VAR") is False  # Contains hyphen
        assert spawner._validate_env_key("MY VAR") is False  # Contains space
        assert spawner._validate_env_key("VAR=VALUE") is False  # Contains =
        assert spawner._validate_env_key("$(cmd)") is False
        assert spawner._validate_env_key("`cmd`") is False
        assert spawner._validate_env_key("VAR;rm") is False

    def test_build_command_rejects_invalid_env_key(self):
        """Verify build_command raises for invalid environment variable keys."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        template = self.make_template(
            command="echo test",
            env={"VALID_KEY": "value", "$(injection)": "bad"},
        )
        project = self.make_project()

        with pytest.raises(ValueError) as exc_info:
            spawner._build_command(template, project)

        assert "Invalid environment variable key" in str(exc_info.value)
        assert "$(injection)" in str(exc_info.value)

    def test_build_command_rejects_key_with_equals(self):
        """Verify build_command raises for env key containing equals sign."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        template = self.make_template(
            command="echo test",
            env={"KEY=VALUE": "extra"},
        )
        project = self.make_project()

        with pytest.raises(ValueError) as exc_info:
            spawner._build_command(template, project)

        assert "Invalid environment variable key" in str(exc_info.value)

    def test_quote_path_prevents_injection(self):
        """Verify paths with shell metacharacters are safely quoted."""
        controller = ItermController()
        spawner = SessionSpawner(controller)

        # Path with command substitution
        path = "/path/$(whoami)/project"
        quoted = spawner._quote_path(path)
        assert quoted == "'/path/$(whoami)/project'"

        # Path with backticks
        path = "/path/`id`/project"
        quoted = spawner._quote_path(path)
        assert quoted == "'/path/`id`/project'"

        # Path with semicolon
        path = "/path; rm -rf /"
        quoted = spawner._quote_path(path)
        assert quoted == "'/path; rm -rf /'"

    def test_quote_path_simple_paths(self):
        """Verify simple paths are properly handled."""
        controller = ItermController()
        spawner = SessionSpawner(controller)

        # Simple path without special chars - shlex.quote may or may not quote
        path = "/simple/path"
        quoted = spawner._quote_path(path)
        # Either unquoted or quoted is fine as long as it's safe
        assert quoted == "/simple/path" or quoted == "'/simple/path'"

        # Path with space - must be quoted
        path = "/path with space"
        quoted = spawner._quote_path(path)
        assert quoted == "'/path with space'"

    @pytest.mark.asyncio
    async def test_spawn_session_requires_connection(self):
        """spawn_session raises when not connected."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        template = self.make_template()
        project = self.make_project()

        with pytest.raises(ItermNotConnectedError):
            await spawner.spawn_session(template, project)

    @pytest.mark.asyncio
    async def test_spawn_session_uses_provided_window(self):
        """spawn_session uses provided window."""
        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        template = self.make_template(command="npm start")
        project = self.make_project(path="/my/project")

        # Mock window and tab/session
        mock_session = MagicMock()
        mock_session.session_id = "session-123"
        mock_session.async_send_text = AsyncMock()

        mock_tab = MagicMock()
        mock_tab.tab_id = "tab-456"
        mock_tab.current_session = mock_session

        mock_window = MagicMock()
        mock_window.async_create_tab = AsyncMock(return_value=mock_tab)

        result = await spawner.spawn_session(template, project, window=mock_window)

        assert result.success is True
        assert result.session_id == "session-123"
        assert result.tab_id == "tab-456"
        mock_window.async_create_tab.assert_called_once()
        mock_session.async_send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_spawn_session_uses_current_window(self):
        """spawn_session uses current window when none provided."""
        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        template = self.make_template()
        project = self.make_project()

        mock_session = MagicMock()
        mock_session.session_id = "session-789"
        mock_session.async_send_text = AsyncMock()

        mock_tab = MagicMock()
        mock_tab.tab_id = "tab-101"
        mock_tab.current_session = mock_session

        mock_current_window = MagicMock()
        mock_current_window.async_create_tab = AsyncMock(return_value=mock_tab)

        controller.app.current_terminal_window = mock_current_window

        result = await spawner.spawn_session(template, project)

        assert result.success is True
        mock_current_window.async_create_tab.assert_called_once()

    @pytest.mark.asyncio
    async def test_spawn_session_creates_window_if_none_exists(self):
        """spawn_session creates new window when no current window."""
        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        template = self.make_template()
        project = self.make_project()

        mock_session = MagicMock()
        mock_session.session_id = "session-new"
        mock_session.async_send_text = AsyncMock()

        mock_tab = MagicMock()
        mock_tab.tab_id = "tab-new"
        mock_tab.current_session = mock_session

        mock_new_window = MagicMock()
        mock_new_window.async_create_tab = AsyncMock(return_value=mock_tab)

        controller.app.current_terminal_window = None

        with patch("iterm2.Window.async_create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_new_window

            result = await spawner.spawn_session(template, project)

        assert result.success is True
        mock_create.assert_called_once_with(controller.connection)

    @pytest.mark.asyncio
    async def test_spawn_session_tracks_managed_session(self):
        """spawn_session registers the session in managed_sessions."""
        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        template = self.make_template(id="my-template")
        project = self.make_project(id="my-project")

        mock_session = MagicMock()
        mock_session.session_id = "session-tracked"
        mock_session.async_send_text = AsyncMock()

        mock_tab = MagicMock()
        mock_tab.tab_id = "tab-tracked"
        mock_tab.current_session = mock_session

        mock_window = MagicMock()
        mock_window.async_create_tab = AsyncMock(return_value=mock_tab)

        await spawner.spawn_session(template, project, window=mock_window)

        assert "session-tracked" in spawner.managed_sessions
        managed = spawner.managed_sessions["session-tracked"]
        assert managed.template_id == "my-template"
        assert managed.project_id == "my-project"
        assert managed.tab_id == "tab-tracked"

    @pytest.mark.asyncio
    async def test_spawn_session_sends_correct_command(self):
        """spawn_session sends the built command to session."""
        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        template = self.make_template(command="npm run dev")
        project = self.make_project(path="/code/app")

        mock_session = MagicMock()
        mock_session.session_id = "session-cmd"
        mock_session.async_send_text = AsyncMock()

        mock_tab = MagicMock()
        mock_tab.tab_id = "tab-cmd"
        mock_tab.current_session = mock_session

        mock_window = MagicMock()
        mock_window.async_create_tab = AsyncMock(return_value=mock_tab)

        await spawner.spawn_session(template, project, window=mock_window)

        mock_session.async_send_text.assert_called_once_with(
            "cd /code/app && npm run dev\n"
        )

    @pytest.mark.asyncio
    async def test_spawn_session_handles_error(self):
        """spawn_session returns failure result on error."""
        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        template = self.make_template()
        project = self.make_project()

        mock_window = MagicMock()
        mock_window.async_create_tab = AsyncMock(
            side_effect=Exception("Tab creation failed")
        )

        result = await spawner.spawn_session(template, project, window=mock_window)

        assert result.success is False
        assert result.session_id == ""
        assert result.tab_id == ""
        assert "Tab creation failed" in result.error

    @pytest.mark.asyncio
    async def test_spawn_split_requires_connection(self):
        """spawn_split raises when not connected."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        template = self.make_template()
        project = self.make_project()
        parent = MagicMock()

        with pytest.raises(ItermNotConnectedError):
            await spawner.spawn_split(template, project, parent)

    @pytest.mark.asyncio
    async def test_spawn_split_creates_vertical_split(self):
        """spawn_split creates vertical split by default."""
        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        template = self.make_template(command="tail -f log")
        project = self.make_project(path="/app")

        mock_new_session = MagicMock()
        mock_new_session.session_id = "split-session-v"
        mock_new_session.async_send_text = AsyncMock()

        mock_parent_tab = MagicMock()
        mock_parent_tab.tab_id = "parent-tab"

        mock_parent_session = MagicMock()
        mock_parent_session.async_split_pane = AsyncMock(return_value=mock_new_session)
        mock_parent_session.tab = mock_parent_tab

        result = await spawner.spawn_split(template, project, mock_parent_session)

        assert result.success is True
        assert result.session_id == "split-session-v"
        assert result.tab_id == "parent-tab"
        mock_parent_session.async_split_pane.assert_called_once_with(vertical=True)

    @pytest.mark.asyncio
    async def test_spawn_split_creates_horizontal_split(self):
        """spawn_split creates horizontal split when requested."""
        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        template = self.make_template()
        project = self.make_project()

        mock_new_session = MagicMock()
        mock_new_session.session_id = "split-session-h"
        mock_new_session.async_send_text = AsyncMock()

        mock_parent_tab = MagicMock()
        mock_parent_tab.tab_id = "parent-tab-h"

        mock_parent_session = MagicMock()
        mock_parent_session.async_split_pane = AsyncMock(return_value=mock_new_session)
        mock_parent_session.tab = mock_parent_tab

        result = await spawner.spawn_split(
            template, project, mock_parent_session, vertical=False
        )

        assert result.success is True
        mock_parent_session.async_split_pane.assert_called_once_with(vertical=False)

    @pytest.mark.asyncio
    async def test_spawn_split_tracks_managed_session(self):
        """spawn_split registers the session in managed_sessions."""
        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        template = self.make_template(id="split-tmpl")
        project = self.make_project(id="split-proj")

        mock_new_session = MagicMock()
        mock_new_session.session_id = "split-tracked"
        mock_new_session.async_send_text = AsyncMock()

        mock_parent_tab = MagicMock()
        mock_parent_tab.tab_id = "split-tab"

        mock_parent_session = MagicMock()
        mock_parent_session.async_split_pane = AsyncMock(return_value=mock_new_session)
        mock_parent_session.tab = mock_parent_tab

        await spawner.spawn_split(template, project, mock_parent_session)

        assert "split-tracked" in spawner.managed_sessions
        managed = spawner.managed_sessions["split-tracked"]
        assert managed.template_id == "split-tmpl"
        assert managed.project_id == "split-proj"
        assert managed.tab_id == "split-tab"

    @pytest.mark.asyncio
    async def test_spawn_split_sends_correct_command(self):
        """spawn_split sends the built command to split session."""
        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        template = self.make_template(
            command="python manage.py runserver",
            env={"DEBUG": "true"},
        )
        project = self.make_project(path="/django/app")

        mock_new_session = MagicMock()
        mock_new_session.session_id = "split-cmd"
        mock_new_session.async_send_text = AsyncMock()

        mock_parent_session = MagicMock()
        mock_parent_session.async_split_pane = AsyncMock(return_value=mock_new_session)
        mock_parent_session.tab = MagicMock(tab_id="tab")

        await spawner.spawn_split(template, project, mock_parent_session)

        call_args = mock_new_session.async_send_text.call_args[0][0]
        assert "cd /django/app" in call_args
        # shlex.quote doesn't add quotes for simple alphanumeric values
        assert "DEBUG=true" in call_args
        assert "python manage.py runserver" in call_args
        assert call_args.endswith("\n")

    @pytest.mark.asyncio
    async def test_spawn_split_handles_error(self):
        """spawn_split returns failure result on error."""
        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        template = self.make_template()
        project = self.make_project()

        mock_parent_session = MagicMock()
        mock_parent_session.async_split_pane = AsyncMock(
            side_effect=Exception("Split failed")
        )

        result = await spawner.spawn_split(template, project, mock_parent_session)

        assert result.success is False
        assert "Split failed" in result.error

    def test_get_session_found(self):
        """get_session returns managed session by ID."""
        controller = ItermController()
        spawner = SessionSpawner(controller)

        from iterm_controller.models import ManagedSession

        session = ManagedSession(
            id="test-id",
            template_id="tmpl",
            project_id="proj",
            tab_id="tab",
        )
        spawner.managed_sessions["test-id"] = session

        result = spawner.get_session("test-id")
        assert result is session

    def test_get_session_not_found(self):
        """get_session returns None for unknown ID."""
        controller = ItermController()
        spawner = SessionSpawner(controller)

        result = spawner.get_session("nonexistent")
        assert result is None

    def test_get_sessions_for_project(self):
        """get_sessions_for_project returns sessions for a project."""
        controller = ItermController()
        spawner = SessionSpawner(controller)

        from iterm_controller.models import ManagedSession

        s1 = ManagedSession(id="s1", template_id="t", project_id="proj-a", tab_id="t1")
        s2 = ManagedSession(id="s2", template_id="t", project_id="proj-b", tab_id="t2")
        s3 = ManagedSession(id="s3", template_id="t", project_id="proj-a", tab_id="t3")

        spawner.managed_sessions = {"s1": s1, "s2": s2, "s3": s3}

        result = spawner.get_sessions_for_project("proj-a")

        assert len(result) == 2
        assert s1 in result
        assert s3 in result
        assert s2 not in result

    def test_untrack_session(self):
        """untrack_session removes session from tracking."""
        controller = ItermController()
        spawner = SessionSpawner(controller)

        from iterm_controller.models import ManagedSession

        session = ManagedSession(
            id="to-remove",
            template_id="t",
            project_id="p",
            tab_id="tab",
        )
        spawner.managed_sessions["to-remove"] = session

        spawner.untrack_session("to-remove")

        assert "to-remove" not in spawner.managed_sessions

    def test_untrack_session_nonexistent(self):
        """untrack_session is safe for nonexistent session."""
        controller = ItermController()
        spawner = SessionSpawner(controller)

        # Should not raise
        spawner.untrack_session("nonexistent")


class TestLayoutSpawnResult:
    """Test LayoutSpawnResult dataclass."""

    def test_layout_spawn_result_success(self):
        """LayoutSpawnResult with success state."""
        from iterm_controller.iterm import LayoutSpawnResult

        results = [
            SpawnResult(session_id="s1", tab_id="t1", success=True),
            SpawnResult(session_id="s2", tab_id="t1", success=True),
        ]
        result = LayoutSpawnResult(
            window_id="window-1",
            results=results,
            success=True,
        )
        assert result.window_id == "window-1"
        assert result.success is True
        assert result.error is None
        assert result.all_successful is True
        assert result.spawned_session_ids == ["s1", "s2"]

    def test_layout_spawn_result_partial_failure(self):
        """LayoutSpawnResult with some failed sessions."""
        from iterm_controller.iterm import LayoutSpawnResult

        results = [
            SpawnResult(session_id="s1", tab_id="t1", success=True),
            SpawnResult(session_id="", tab_id="t1", success=False, error="Failed"),
        ]
        result = LayoutSpawnResult(
            window_id="window-1",
            results=results,
            success=False,
        )
        assert result.all_successful is False
        assert result.spawned_session_ids == ["s1"]

    def test_layout_spawn_result_failure(self):
        """LayoutSpawnResult with failure state."""
        from iterm_controller.iterm import LayoutSpawnResult

        result = LayoutSpawnResult(
            window_id="",
            results=[],
            success=False,
            error="Window creation failed",
        )
        assert result.success is False
        assert result.error == "Window creation failed"
        assert result.all_successful is True  # No results means all (zero) succeeded
        assert result.spawned_session_ids == []


class TestWindowLayoutSpawner:
    """Test WindowLayoutSpawner window layout spawning functionality."""

    def make_template(
        self,
        id: str = "test-template",
        name: str = "Test Template",
        command: str = "echo hello",
        working_dir: str | None = None,
        env: dict | None = None,
    ) -> SessionTemplate:
        """Create a test session template."""
        return SessionTemplate(
            id=id,
            name=name,
            command=command,
            working_dir=working_dir,
            env=env or {},
        )

    def make_project(
        self,
        id: str = "test-project",
        name: str = "Test Project",
        path: str = "/path/to/project",
    ) -> Project:
        """Create a test project."""
        return Project(id=id, name=name, path=path)

    def make_connected_controller(self) -> ItermController:
        """Create a controller in connected state."""
        controller = ItermController()
        controller._connected = True
        controller.connection = MagicMock()
        controller.app = MagicMock()
        return controller

    def make_mock_session(self, session_id: str) -> MagicMock:
        """Create a mock iTerm2 session."""
        session = MagicMock()
        session.session_id = session_id
        session.async_send_text = AsyncMock()
        session.async_split_pane = AsyncMock()
        return session

    def make_mock_tab(self, tab_id: str, session: MagicMock) -> MagicMock:
        """Create a mock iTerm2 tab."""
        tab = MagicMock()
        tab.tab_id = tab_id
        tab.current_session = session
        tab.sessions = [session]
        tab.async_set_title = AsyncMock()
        return tab

    def make_mock_window(self, window_id: str, tab: MagicMock) -> MagicMock:
        """Create a mock iTerm2 window."""
        window = MagicMock()
        window.window_id = window_id
        window.current_tab = tab
        window.async_create_tab = AsyncMock()
        return window

    def test_init(self):
        """WindowLayoutSpawner initializes correctly."""
        from iterm_controller.iterm import WindowLayoutSpawner

        controller = ItermController()
        spawner = SessionSpawner(controller)
        layout_spawner = WindowLayoutSpawner(controller, spawner)

        assert layout_spawner.controller is controller
        assert layout_spawner.spawner is spawner

    @pytest.mark.asyncio
    async def test_spawn_layout_requires_connection(self):
        """spawn_layout raises when not connected."""
        from iterm_controller.iterm import WindowLayoutSpawner
        from iterm_controller.models import WindowLayout

        controller = ItermController()
        spawner = SessionSpawner(controller)
        layout_spawner = WindowLayoutSpawner(controller, spawner)

        layout = WindowLayout(id="test", name="Test Layout")
        project = self.make_project()

        with pytest.raises(ItermNotConnectedError):
            await layout_spawner.spawn_layout(layout, project, {})

    @pytest.mark.asyncio
    async def test_spawn_layout_empty_tabs(self):
        """spawn_layout handles layout with no tabs."""
        from iterm_controller.iterm import WindowLayoutSpawner
        from iterm_controller.models import WindowLayout

        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        layout_spawner = WindowLayoutSpawner(controller, spawner)

        mock_window = MagicMock()
        mock_window.window_id = "window-empty"

        with patch("iterm2.Window.async_create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_window

            layout = WindowLayout(id="empty", name="Empty Layout", tabs=[])
            project = self.make_project()

            result = await layout_spawner.spawn_layout(layout, project, {})

        assert result.success is True
        assert result.window_id == "window-empty"
        assert result.results == []

    @pytest.mark.asyncio
    async def test_spawn_layout_single_tab_single_session(self):
        """spawn_layout creates a single tab with one session."""
        from iterm_controller.iterm import WindowLayoutSpawner
        from iterm_controller.models import SessionLayout, TabLayout, WindowLayout

        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        layout_spawner = WindowLayoutSpawner(controller, spawner)

        mock_session = self.make_mock_session("session-1")
        mock_tab = self.make_mock_tab("tab-1", mock_session)
        mock_window = self.make_mock_window("window-1", mock_tab)

        with patch("iterm2.Window.async_create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_window

            template = self.make_template(id="tmpl-1", command="npm start")
            layout = WindowLayout(
                id="single",
                name="Single Session",
                tabs=[
                    TabLayout(
                        name="Main",
                        sessions=[SessionLayout(template_id="tmpl-1")],
                    )
                ],
            )
            project = self.make_project(path="/app")

            result = await layout_spawner.spawn_layout(
                layout, project, {"tmpl-1": template}
            )

        assert result.success is True
        assert result.window_id == "window-1"
        assert len(result.results) == 1
        assert result.results[0].success is True
        assert result.results[0].session_id == "session-1"

        # Verify tab title was set
        mock_tab.async_set_title.assert_called_once_with("Main")

        # Verify command was sent to session
        mock_session.async_send_text.assert_called_once()
        call_arg = mock_session.async_send_text.call_args[0][0]
        assert "cd /app" in call_arg
        assert "npm start" in call_arg

    @pytest.mark.asyncio
    async def test_spawn_layout_multiple_tabs(self):
        """spawn_layout creates multiple tabs."""
        from iterm_controller.iterm import WindowLayoutSpawner
        from iterm_controller.models import SessionLayout, TabLayout, WindowLayout

        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        layout_spawner = WindowLayoutSpawner(controller, spawner)

        # First tab uses window's default
        mock_session1 = self.make_mock_session("session-1")
        mock_tab1 = self.make_mock_tab("tab-1", mock_session1)

        # Second tab is created
        mock_session2 = self.make_mock_session("session-2")
        mock_tab2 = self.make_mock_tab("tab-2", mock_session2)

        mock_window = self.make_mock_window("window-multi", mock_tab1)
        mock_window.async_create_tab = AsyncMock(return_value=mock_tab2)

        with patch("iterm2.Window.async_create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_window

            templates = {
                "server": self.make_template(id="server", command="npm run server"),
                "client": self.make_template(id="client", command="npm run client"),
            }
            layout = WindowLayout(
                id="multi",
                name="Multi Tab",
                tabs=[
                    TabLayout(
                        name="Server",
                        sessions=[SessionLayout(template_id="server")],
                    ),
                    TabLayout(
                        name="Client",
                        sessions=[SessionLayout(template_id="client")],
                    ),
                ],
            )
            project = self.make_project()

            result = await layout_spawner.spawn_layout(layout, project, templates)

        assert result.success is True
        assert len(result.results) == 2

        # First tab uses window's default tab
        mock_tab1.async_set_title.assert_called_once_with("Server")

        # Second tab is created
        mock_window.async_create_tab.assert_called_once()
        mock_tab2.async_set_title.assert_called_once_with("Client")

    @pytest.mark.asyncio
    async def test_spawn_layout_with_splits(self):
        """spawn_layout creates split panes within a tab."""
        from iterm_controller.iterm import WindowLayoutSpawner
        from iterm_controller.models import SessionLayout, TabLayout, WindowLayout

        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        layout_spawner = WindowLayoutSpawner(controller, spawner)

        # Main session
        mock_session1 = self.make_mock_session("session-main")
        # Split session
        mock_session2 = self.make_mock_session("session-split")
        mock_session1.async_split_pane = AsyncMock(return_value=mock_session2)

        mock_tab = self.make_mock_tab("tab-split", mock_session1)
        mock_tab.tab = mock_tab  # For spawn_split to get tab_id
        mock_session1.tab = mock_tab

        mock_window = self.make_mock_window("window-split", mock_tab)

        with patch("iterm2.Window.async_create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_window

            templates = {
                "main": self.make_template(id="main", command="npm start"),
                "logs": self.make_template(id="logs", command="tail -f logs"),
            }
            layout = WindowLayout(
                id="splits",
                name="With Splits",
                tabs=[
                    TabLayout(
                        name="Dev",
                        sessions=[
                            SessionLayout(template_id="main"),
                            SessionLayout(template_id="logs", split="vertical"),
                        ],
                    )
                ],
            )
            project = self.make_project()

            result = await layout_spawner.spawn_layout(layout, project, templates)

        assert result.success is True
        assert len(result.results) == 2
        assert result.results[0].session_id == "session-main"
        assert result.results[1].session_id == "session-split"

        # First session used directly
        assert mock_session1.async_send_text.called

        # Second session created via split
        mock_session1.async_split_pane.assert_called_once_with(vertical=True)

    @pytest.mark.asyncio
    async def test_spawn_layout_horizontal_split(self):
        """spawn_layout creates horizontal splits correctly."""
        from iterm_controller.iterm import WindowLayoutSpawner
        from iterm_controller.models import SessionLayout, TabLayout, WindowLayout

        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        layout_spawner = WindowLayoutSpawner(controller, spawner)

        mock_session1 = self.make_mock_session("session-1")
        mock_session2 = self.make_mock_session("session-2")
        mock_session1.async_split_pane = AsyncMock(return_value=mock_session2)
        mock_session1.tab = MagicMock(tab_id="tab-1")

        mock_tab = self.make_mock_tab("tab-1", mock_session1)
        mock_window = self.make_mock_window("window-1", mock_tab)

        with patch("iterm2.Window.async_create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_window

            templates = {
                "top": self.make_template(id="top"),
                "bottom": self.make_template(id="bottom"),
            }
            layout = WindowLayout(
                id="horizontal",
                name="Horizontal Split",
                tabs=[
                    TabLayout(
                        name="Split",
                        sessions=[
                            SessionLayout(template_id="top"),
                            SessionLayout(template_id="bottom", split="horizontal"),
                        ],
                    )
                ],
            )
            project = self.make_project()

            await layout_spawner.spawn_layout(layout, project, templates)

        # Horizontal split means vertical=False
        mock_session1.async_split_pane.assert_called_once_with(vertical=False)

    @pytest.mark.asyncio
    async def test_spawn_layout_missing_template(self):
        """spawn_layout handles missing template gracefully."""
        from iterm_controller.iterm import WindowLayoutSpawner
        from iterm_controller.models import SessionLayout, TabLayout, WindowLayout

        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        layout_spawner = WindowLayoutSpawner(controller, spawner)

        mock_session = self.make_mock_session("session-1")
        mock_tab = self.make_mock_tab("tab-1", mock_session)
        mock_window = self.make_mock_window("window-1", mock_tab)

        with patch("iterm2.Window.async_create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_window

            # No templates provided
            layout = WindowLayout(
                id="missing",
                name="Missing Template",
                tabs=[
                    TabLayout(
                        name="Tab",
                        sessions=[SessionLayout(template_id="nonexistent")],
                    )
                ],
            )
            project = self.make_project()

            result = await layout_spawner.spawn_layout(layout, project, {})

        assert result.success is False
        assert len(result.results) == 1
        assert result.results[0].success is False
        assert "nonexistent" in result.results[0].error

    @pytest.mark.asyncio
    async def test_spawn_layout_tracks_sessions(self):
        """spawn_layout registers sessions in managed_sessions."""
        from iterm_controller.iterm import WindowLayoutSpawner
        from iterm_controller.models import SessionLayout, TabLayout, WindowLayout

        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        layout_spawner = WindowLayoutSpawner(controller, spawner)

        mock_session = self.make_mock_session("tracked-session")
        mock_tab = self.make_mock_tab("tab-1", mock_session)
        mock_window = self.make_mock_window("window-1", mock_tab)

        with patch("iterm2.Window.async_create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_window

            template = self.make_template(id="tmpl-tracked")
            layout = WindowLayout(
                id="track",
                name="Track Test",
                tabs=[
                    TabLayout(
                        name="Main",
                        sessions=[SessionLayout(template_id="tmpl-tracked")],
                    )
                ],
            )
            project = self.make_project(id="test-proj")

            await layout_spawner.spawn_layout(
                layout, project, {"tmpl-tracked": template}
            )

        assert "tracked-session" in spawner.managed_sessions
        managed = spawner.managed_sessions["tracked-session"]
        assert managed.template_id == "tmpl-tracked"
        assert managed.project_id == "test-proj"

    @pytest.mark.asyncio
    async def test_spawn_layout_window_creation_failure(self):
        """spawn_layout handles window creation failure."""
        from iterm_controller.iterm import WindowLayoutSpawner
        from iterm_controller.models import WindowLayout

        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        layout_spawner = WindowLayoutSpawner(controller, spawner)

        with patch("iterm2.Window.async_create", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = Exception("Window creation failed")

            layout = WindowLayout(id="fail", name="Fail Layout")
            project = self.make_project()

            result = await layout_spawner.spawn_layout(layout, project, {})

        assert result.success is False
        assert result.window_id == ""
        assert "Window creation failed" in result.error

    @pytest.mark.asyncio
    async def test_spawn_layout_tab_with_no_sessions(self):
        """spawn_layout handles tabs with no sessions defined."""
        from iterm_controller.iterm import WindowLayoutSpawner
        from iterm_controller.models import TabLayout, WindowLayout

        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        layout_spawner = WindowLayoutSpawner(controller, spawner)

        mock_session = self.make_mock_session("session-1")
        mock_tab = self.make_mock_tab("tab-1", mock_session)
        mock_window = self.make_mock_window("window-1", mock_tab)

        with patch("iterm2.Window.async_create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_window

            layout = WindowLayout(
                id="empty-tab",
                name="Empty Tab",
                tabs=[TabLayout(name="Empty", sessions=[])],
            )
            project = self.make_project()

            result = await layout_spawner.spawn_layout(layout, project, {})

        assert result.success is True
        assert result.results == []
        mock_tab.async_set_title.assert_called_once_with("Empty")


class TestCloseResult:
    """Test CloseResult dataclass."""

    def test_close_result_success(self):
        """CloseResult with success state."""
        result = CloseResult(
            session_id="session-1",
            success=True,
        )
        assert result.session_id == "session-1"
        assert result.success is True
        assert result.force_required is False
        assert result.error is None

    def test_close_result_force_required(self):
        """CloseResult when force was required."""
        result = CloseResult(
            session_id="session-2",
            success=True,
            force_required=True,
        )
        assert result.success is True
        assert result.force_required is True

    def test_close_result_failure(self):
        """CloseResult with failure state."""
        result = CloseResult(
            session_id="session-3",
            success=False,
            error="Session not found",
        )
        assert result.success is False
        assert result.error == "Session not found"


class TestSessionTerminator:
    """Test SessionTerminator session termination functionality."""

    def make_connected_controller(self) -> ItermController:
        """Create a controller in connected state."""
        controller = ItermController()
        controller._connected = True
        controller.connection = MagicMock()
        controller.app = MagicMock()
        return controller

    def make_mock_session(self, session_id: str = "session-1") -> MagicMock:
        """Create a mock iTerm2 session."""
        session = MagicMock()
        session.session_id = session_id
        session.async_send_text = AsyncMock()
        session.async_close = AsyncMock()
        session.async_get_screen_contents = AsyncMock()
        return session

    def test_init(self):
        """SessionTerminator initializes correctly."""
        controller = ItermController()
        terminator = SessionTerminator(controller)
        assert terminator.controller is controller
        assert terminator.SIGTERM_TIMEOUT == 5.0
        assert terminator.POLL_INTERVAL == 0.1

    @pytest.mark.asyncio
    async def test_close_session_force(self):
        """close_session with force=True closes immediately."""
        controller = self.make_connected_controller()
        terminator = SessionTerminator(controller)

        mock_session = self.make_mock_session("force-session")

        result = await terminator.close_session(mock_session, force=True)

        assert result.success is True
        assert result.session_id == "force-session"
        assert result.force_required is True
        mock_session.async_close.assert_called_once_with(force=True)
        # Should not send exit command when force=True
        mock_session.async_send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_close_session_graceful_success(self):
        """close_session gracefully closes when session exits on its own."""
        controller = self.make_connected_controller()
        terminator = SessionTerminator(controller)

        mock_session = self.make_mock_session("graceful-session")

        # Session closes after exit command
        call_count = {"count": 0}

        async def mock_get_contents():
            call_count["count"] += 1
            if call_count["count"] >= 2:
                raise Exception("Session closed")
            return MagicMock()

        mock_session.async_get_screen_contents = mock_get_contents

        result = await terminator.close_session(mock_session, force=False)

        assert result.success is True
        assert result.force_required is False
        assert result.session_id == "graceful-session"

        # Should send Ctrl+C and exit
        calls = mock_session.async_send_text.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == "\x03"  # Ctrl+C
        assert calls[1][0][0] == "exit\n"

    @pytest.mark.asyncio
    async def test_close_session_graceful_timeout_then_force(self):
        """close_session force-closes after timeout."""
        controller = self.make_connected_controller()
        terminator = SessionTerminator(controller)
        terminator.SIGTERM_TIMEOUT = 0.2  # Short timeout for testing

        mock_session = self.make_mock_session("timeout-session")

        # Session never closes gracefully
        mock_session.async_get_screen_contents = AsyncMock(return_value=MagicMock())

        result = await terminator.close_session(mock_session, force=False)

        assert result.success is True
        assert result.force_required is True
        assert result.session_id == "timeout-session"

        # Should have called force close after timeout
        mock_session.async_close.assert_called_once_with(force=True)

    @pytest.mark.asyncio
    async def test_close_session_error_handling(self):
        """close_session handles errors gracefully."""
        controller = self.make_connected_controller()
        terminator = SessionTerminator(controller)

        mock_session = self.make_mock_session("error-session")
        mock_session.async_send_text = AsyncMock(side_effect=Exception("Send failed"))

        result = await terminator.close_session(mock_session, force=False)

        assert result.success is False
        assert result.session_id == "error-session"
        assert "Send failed" in result.error

    @pytest.mark.asyncio
    async def test_close_session_force_error(self):
        """close_session handles force close errors."""
        controller = self.make_connected_controller()
        terminator = SessionTerminator(controller)

        mock_session = self.make_mock_session("force-error")
        mock_session.async_close = AsyncMock(side_effect=Exception("Close failed"))

        result = await terminator.close_session(mock_session, force=True)

        assert result.success is False
        assert "Close failed" in result.error

    @pytest.mark.asyncio
    async def test_close_tab_success(self):
        """close_tab closes the tab successfully."""
        controller = self.make_connected_controller()
        terminator = SessionTerminator(controller)

        mock_tab = MagicMock()
        mock_tab.tab_id = "tab-1"
        mock_tab.async_close = AsyncMock()

        result = await terminator.close_tab(mock_tab)

        assert result is True
        mock_tab.async_close.assert_called_once_with(force=False)

    @pytest.mark.asyncio
    async def test_close_tab_force(self):
        """close_tab with force=True passes force to async_close."""
        controller = self.make_connected_controller()
        terminator = SessionTerminator(controller)

        mock_tab = MagicMock()
        mock_tab.tab_id = "tab-force"
        mock_tab.async_close = AsyncMock()

        result = await terminator.close_tab(mock_tab, force=True)

        assert result is True
        mock_tab.async_close.assert_called_once_with(force=True)

    @pytest.mark.asyncio
    async def test_close_tab_error(self):
        """close_tab handles errors gracefully."""
        controller = self.make_connected_controller()
        terminator = SessionTerminator(controller)

        mock_tab = MagicMock()
        mock_tab.tab_id = "tab-error"
        mock_tab.async_close = AsyncMock(side_effect=Exception("Tab close failed"))

        result = await terminator.close_tab(mock_tab)

        assert result is False

    @pytest.mark.asyncio
    async def test_close_all_managed_empty_list(self):
        """close_all_managed handles empty session list."""
        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        terminator = SessionTerminator(controller)

        closed, results = await terminator.close_all_managed([], spawner)

        assert closed == 0
        assert results == []

    @pytest.mark.asyncio
    async def test_close_all_managed_requires_connection(self):
        """close_all_managed raises when not connected."""
        controller = ItermController()
        spawner = SessionSpawner(controller)
        terminator = SessionTerminator(controller)

        from iterm_controller.models import ManagedSession

        sessions = [
            ManagedSession(id="s1", template_id="t", project_id="p", tab_id="tab")
        ]

        with pytest.raises(ItermNotConnectedError):
            await terminator.close_all_managed(sessions, spawner)

    @pytest.mark.asyncio
    async def test_close_all_managed_success(self):
        """close_all_managed closes all sessions successfully."""
        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        terminator = SessionTerminator(controller)

        from iterm_controller.models import ManagedSession

        # Track sessions in spawner
        s1 = ManagedSession(id="s1", template_id="t", project_id="p", tab_id="tab")
        s2 = ManagedSession(id="s2", template_id="t", project_id="p", tab_id="tab")
        spawner.managed_sessions = {"s1": s1, "s2": s2}

        # Mock iTerm sessions
        mock_session1 = self.make_mock_session("s1")
        mock_session2 = self.make_mock_session("s2")

        # Sessions close immediately
        mock_session1.async_get_screen_contents = AsyncMock(
            side_effect=Exception("Closed")
        )
        mock_session2.async_get_screen_contents = AsyncMock(
            side_effect=Exception("Closed")
        )

        async def get_session(session_id):
            if session_id == "s1":
                return mock_session1
            elif session_id == "s2":
                return mock_session2
            return None

        controller.app.async_get_session_by_id = AsyncMock(side_effect=get_session)

        closed, results = await terminator.close_all_managed([s1, s2], spawner)

        assert closed == 2
        assert len(results) == 2
        assert all(r.success for r in results)

        # Sessions should be untracked
        assert "s1" not in spawner.managed_sessions
        assert "s2" not in spawner.managed_sessions

    @pytest.mark.asyncio
    async def test_close_all_managed_partial_failure(self):
        """close_all_managed handles partial failures."""
        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        terminator = SessionTerminator(controller)

        from iterm_controller.models import ManagedSession

        s1 = ManagedSession(id="s1", template_id="t", project_id="p", tab_id="tab")
        s2 = ManagedSession(id="s2", template_id="t", project_id="p", tab_id="tab")
        spawner.managed_sessions = {"s1": s1, "s2": s2}

        mock_session1 = self.make_mock_session("s1")
        mock_session1.async_get_screen_contents = AsyncMock(
            side_effect=Exception("Closed")
        )

        mock_session2 = self.make_mock_session("s2")
        mock_session2.async_send_text = AsyncMock(side_effect=Exception("Send failed"))

        async def get_session(session_id):
            if session_id == "s1":
                return mock_session1
            elif session_id == "s2":
                return mock_session2
            return None

        controller.app.async_get_session_by_id = AsyncMock(side_effect=get_session)

        closed, results = await terminator.close_all_managed([s1, s2], spawner)

        assert closed == 1
        assert len(results) == 2

        # s1 succeeded, s2 failed
        s1_result = next(r for r in results if r.session_id == "s1")
        s2_result = next(r for r in results if r.session_id == "s2")

        assert s1_result.success is True
        assert s2_result.success is False

        # Only s1 should be untracked
        assert "s1" not in spawner.managed_sessions
        assert "s2" in spawner.managed_sessions

    @pytest.mark.asyncio
    async def test_close_all_managed_session_not_found(self):
        """close_all_managed handles sessions that no longer exist."""
        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        terminator = SessionTerminator(controller)

        from iterm_controller.models import ManagedSession

        s1 = ManagedSession(id="s1", template_id="t", project_id="p", tab_id="tab")
        spawner.managed_sessions = {"s1": s1}

        # Session not found (already closed)
        controller.app.async_get_session_by_id = AsyncMock(return_value=None)

        closed, results = await terminator.close_all_managed([s1], spawner)

        assert closed == 1
        assert len(results) == 1
        assert results[0].success is True
        assert "already closed" in results[0].error

        # Should still be untracked
        assert "s1" not in spawner.managed_sessions

    @pytest.mark.asyncio
    async def test_close_all_managed_with_force(self):
        """close_all_managed with force=True force-closes all sessions."""
        controller = self.make_connected_controller()
        spawner = SessionSpawner(controller)
        terminator = SessionTerminator(controller)

        from iterm_controller.models import ManagedSession

        s1 = ManagedSession(id="s1", template_id="t", project_id="p", tab_id="tab")
        spawner.managed_sessions = {"s1": s1}

        mock_session = self.make_mock_session("s1")
        controller.app.async_get_session_by_id = AsyncMock(return_value=mock_session)

        closed, results = await terminator.close_all_managed([s1], spawner, force=True)

        assert closed == 1
        assert results[0].force_required is True
        mock_session.async_close.assert_called_once_with(force=True)

    @pytest.mark.asyncio
    async def test_close_all_managed_no_app(self):
        """close_all_managed handles missing app gracefully."""
        controller = self.make_connected_controller()
        controller.app = None
        spawner = SessionSpawner(controller)
        terminator = SessionTerminator(controller)

        from iterm_controller.models import ManagedSession

        s1 = ManagedSession(id="s1", template_id="t", project_id="p", tab_id="tab")

        closed, results = await terminator.close_all_managed([s1], spawner)

        assert closed == 0
        assert results == []


class TestWindowLayoutManager:
    """Test WindowLayoutManager layout persistence functionality."""

    def make_connected_controller(self) -> ItermController:
        """Create a controller in connected state."""
        controller = ItermController()
        controller._connected = True
        controller.connection = MagicMock()
        controller.app = MagicMock()
        return controller

    def test_init(self):
        """WindowLayoutManager initializes with empty layouts."""
        controller = ItermController()
        manager = WindowLayoutManager(controller)
        assert manager.controller is controller
        assert manager._layouts == {}

    def test_load_from_config(self):
        """load_from_config populates layouts from list."""
        controller = ItermController()
        manager = WindowLayoutManager(controller)

        layouts = [
            WindowLayout(id="layout-1", name="Layout 1"),
            WindowLayout(id="layout-2", name="Layout 2"),
        ]
        manager.load_from_config(layouts)

        assert len(manager._layouts) == 2
        assert "layout-1" in manager._layouts
        assert "layout-2" in manager._layouts
        assert manager._layouts["layout-1"].name == "Layout 1"

    def test_list_layouts(self):
        """list_layouts returns all stored layouts."""
        controller = ItermController()
        manager = WindowLayoutManager(controller)

        layout1 = WindowLayout(id="l1", name="L1")
        layout2 = WindowLayout(id="l2", name="L2")
        manager._layouts = {"l1": layout1, "l2": layout2}

        result = manager.list_layouts()

        assert len(result) == 2
        assert layout1 in result
        assert layout2 in result

    def test_list_layouts_empty(self):
        """list_layouts returns empty list when no layouts."""
        controller = ItermController()
        manager = WindowLayoutManager(controller)

        result = manager.list_layouts()

        assert result == []

    def test_get_layout_found(self):
        """get_layout returns layout by ID when found."""
        controller = ItermController()
        manager = WindowLayoutManager(controller)

        layout = WindowLayout(id="test-layout", name="Test Layout")
        manager._layouts = {"test-layout": layout}

        result = manager.get_layout("test-layout")

        assert result is layout

    def test_get_layout_not_found(self):
        """get_layout returns None when layout not found."""
        controller = ItermController()
        manager = WindowLayoutManager(controller)

        result = manager.get_layout("nonexistent")

        assert result is None

    def test_save_layout_new(self):
        """save_layout adds a new layout."""
        controller = ItermController()
        manager = WindowLayoutManager(controller)

        layout = WindowLayout(id="new-layout", name="New Layout")
        manager.save_layout(layout)

        assert "new-layout" in manager._layouts
        assert manager._layouts["new-layout"] is layout

    def test_save_layout_update(self):
        """save_layout updates an existing layout."""
        controller = ItermController()
        manager = WindowLayoutManager(controller)

        old_layout = WindowLayout(id="update-layout", name="Old Name")
        manager._layouts = {"update-layout": old_layout}

        new_layout = WindowLayout(id="update-layout", name="New Name")
        manager.save_layout(new_layout)

        assert manager._layouts["update-layout"].name == "New Name"
        assert manager._layouts["update-layout"] is new_layout

    def test_delete_layout_found(self):
        """delete_layout removes layout and returns True."""
        controller = ItermController()
        manager = WindowLayoutManager(controller)

        layout = WindowLayout(id="to-delete", name="Delete Me")
        manager._layouts = {"to-delete": layout}

        result = manager.delete_layout("to-delete")

        assert result is True
        assert "to-delete" not in manager._layouts

    def test_delete_layout_not_found(self):
        """delete_layout returns False when layout not found."""
        controller = ItermController()
        manager = WindowLayoutManager(controller)

        result = manager.delete_layout("nonexistent")

        assert result is False

    def test_get_layouts_for_config(self):
        """get_layouts_for_config returns list for saving to config."""
        controller = ItermController()
        manager = WindowLayoutManager(controller)

        layout1 = WindowLayout(id="l1", name="L1")
        layout2 = WindowLayout(id="l2", name="L2")
        manager._layouts = {"l1": layout1, "l2": layout2}

        result = manager.get_layouts_for_config()

        assert len(result) == 2
        assert layout1 in result
        assert layout2 in result
