"""Tests for ScriptService."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iterm_controller.models import (
    ManagedSession,
    Project,
    ProjectScript,
    RunningScript,
    SessionTemplate,
    SessionType,
)
from iterm_controller.script_service import (
    ScriptBehavior,
    ScriptService,
    ScriptValidationError,
    ScriptValidator,
)


class TestScriptService:
    """Tests for ScriptService core functionality."""

    @pytest.fixture
    def mock_spawner(self) -> MagicMock:
        """Create a mock SessionSpawner."""
        spawner = MagicMock()
        spawner.controller = MagicMock()
        spawner.controller.app = MagicMock()
        spawner.get_session = MagicMock(return_value=None)
        spawner.get_sessions_for_project = MagicMock(return_value=[])
        spawner.spawn_session = AsyncMock()
        spawner.untrack_session = MagicMock()
        return spawner

    @pytest.fixture
    def service(self, mock_spawner: MagicMock) -> ScriptService:
        """Create a ScriptService instance."""
        return ScriptService(mock_spawner)

    @pytest.fixture
    def project(self) -> Project:
        """Create a test project."""
        return Project(
            id="test-project",
            name="Test Project",
            path="/test/path",
        )

    @pytest.fixture
    def script(self) -> ProjectScript:
        """Create a test script."""
        return ProjectScript(
            id="test-script",
            name="Test Script",
            command="echo hello",
            keybinding="t",
            session_type=SessionType.SCRIPT,
        )

    def test_init(self, service: ScriptService, mock_spawner: MagicMock):
        """Test ScriptService initialization."""
        assert service.session_spawner is mock_spawner
        assert service._running_scripts == {}

    def test_script_to_template(
        self,
        service: ScriptService,
        script: ProjectScript,
        project: Project,
    ):
        """Test converting script to session template."""
        template = service._script_to_template(script, project)

        assert isinstance(template, SessionTemplate)
        assert template.id == "script-test-script"
        assert template.name == "Test Script"
        assert template.command == "echo hello"
        assert template.working_dir == "/test/path"
        assert template.env == {}

    def test_script_to_template_with_custom_working_dir(
        self, service: ScriptService, project: Project
    ):
        """Test script with custom working directory."""
        script = ProjectScript(
            id="custom-script",
            name="Custom Script",
            command="ls",
            working_dir="/custom/path",
        )

        template = service._script_to_template(script, project)
        assert template.working_dir == "/custom/path"

    def test_script_to_template_with_env(
        self, service: ScriptService, project: Project
    ):
        """Test script with environment variables."""
        script = ProjectScript(
            id="env-script",
            name="Env Script",
            command="env",
            env={"FOO": "bar", "BAZ": "qux"},
        )

        template = service._script_to_template(script, project)
        assert template.env == {"FOO": "bar", "BAZ": "qux"}

    @pytest.mark.asyncio
    async def test_run_script_success(
        self,
        service: ScriptService,
        mock_spawner: MagicMock,
        script: ProjectScript,
        project: Project,
    ):
        """Test running a script successfully."""
        # Set up mock
        mock_session = ManagedSession(
            id="session-123",
            template_id="script-test-script",
            project_id="test-project",
            tab_id="tab-1",
        )
        mock_spawner.spawn_session.return_value = MagicMock(
            success=True,
            session_id="session-123",
            error=None,
        )
        mock_spawner.get_session.return_value = mock_session

        # Run script
        result = await service.run_script(project, script)

        # Verify
        assert result is mock_session
        assert mock_session.session_type == SessionType.SCRIPT
        assert mock_session.display_name == "Test Script"
        assert "test-script" in service._running_scripts
        assert service._running_scripts["test-script"].session_id == "session-123"

    @pytest.mark.asyncio
    async def test_run_script_failure(
        self,
        service: ScriptService,
        mock_spawner: MagicMock,
        script: ProjectScript,
        project: Project,
    ):
        """Test running a script that fails to spawn."""
        mock_spawner.spawn_session.return_value = MagicMock(
            success=False,
            session_id="",
            error="Connection lost",
        )

        with pytest.raises(RuntimeError) as exc_info:
            await service.run_script(project, script)

        assert "Failed to spawn session" in str(exc_info.value)
        assert "Connection lost" in str(exc_info.value)
        assert script.id not in service._running_scripts

    @pytest.mark.asyncio
    async def test_run_script_with_callback(
        self,
        service: ScriptService,
        mock_spawner: MagicMock,
        script: ProjectScript,
        project: Project,
    ):
        """Test running a script with completion callback."""
        mock_session = ManagedSession(
            id="session-123",
            template_id="script-test-script",
            project_id="test-project",
            tab_id="tab-1",
        )
        mock_spawner.spawn_session.return_value = MagicMock(
            success=True,
            session_id="session-123",
            error=None,
        )
        mock_spawner.get_session.return_value = mock_session

        callback = MagicMock()

        await service.run_script(project, script, on_complete=callback)

        running = service._running_scripts["test-script"]
        assert running.on_complete is callback

    def test_get_running_scripts_all(self, service: ScriptService):
        """Test getting all running scripts."""
        running1 = RunningScript(
            script=ProjectScript(id="s1", name="S1", command="cmd1"),
            session_id="sess1",
            started_at=datetime.now(),
        )
        running2 = RunningScript(
            script=ProjectScript(id="s2", name="S2", command="cmd2"),
            session_id="sess2",
            started_at=datetime.now(),
        )

        service._running_scripts = {"s1": running1, "s2": running2}

        result = service.get_running_scripts()
        assert len(result) == 2

    def test_get_running_scripts_by_project(
        self, service: ScriptService, mock_spawner: MagicMock
    ):
        """Test getting running scripts filtered by project."""
        running1 = RunningScript(
            script=ProjectScript(id="s1", name="S1", command="cmd1"),
            session_id="sess1",
            started_at=datetime.now(),
        )
        running2 = RunningScript(
            script=ProjectScript(id="s2", name="S2", command="cmd2"),
            session_id="sess2",
            started_at=datetime.now(),
        )

        service._running_scripts = {"s1": running1, "s2": running2}

        # Mock session lookups
        session1 = ManagedSession(
            id="sess1", template_id="t1", project_id="proj1", tab_id="tab1"
        )
        session2 = ManagedSession(
            id="sess2", template_id="t2", project_id="proj2", tab_id="tab2"
        )
        mock_spawner.get_session.side_effect = lambda sid: {
            "sess1": session1,
            "sess2": session2,
        }.get(sid)

        result = service.get_running_scripts(project_id="proj1")
        assert len(result) == 1
        assert result[0].script.id == "s1"

    def test_get_running_script(self, service: ScriptService):
        """Test getting a running script by ID."""
        running = RunningScript(
            script=ProjectScript(id="s1", name="S1", command="cmd1"),
            session_id="sess1",
            started_at=datetime.now(),
        )
        service._running_scripts = {"s1": running}

        result = service.get_running_script("s1")
        assert result is running

        result = service.get_running_script("nonexistent")
        assert result is None

    def test_get_running_script_for_session(self, service: ScriptService):
        """Test getting running script by session ID."""
        running = RunningScript(
            script=ProjectScript(id="s1", name="S1", command="cmd1"),
            session_id="sess1",
            started_at=datetime.now(),
        )
        service._running_scripts = {"s1": running}

        result = service.get_running_script_for_session("sess1")
        assert result is running

        result = service.get_running_script_for_session("unknown")
        assert result is None

    def test_is_script_running(self, service: ScriptService):
        """Test checking if a script is running."""
        running = RunningScript(
            script=ProjectScript(id="s1", name="S1", command="cmd1"),
            session_id="sess1",
            started_at=datetime.now(),
        )
        service._running_scripts = {"s1": running}

        assert service.is_script_running("s1") is True
        assert service.is_script_running("s2") is False

    @pytest.mark.asyncio
    async def test_stop_script_not_running(
        self, service: ScriptService
    ):
        """Test stopping a script that isn't running."""
        result = await service.stop_script("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_stop_script_success(
        self, service: ScriptService, mock_spawner: MagicMock
    ):
        """Test stopping a running script."""
        running = RunningScript(
            script=ProjectScript(id="s1", name="S1", command="cmd1"),
            session_id="sess1",
            started_at=datetime.now(),
        )
        service._running_scripts = {"s1": running}

        # Mock session
        mock_session = ManagedSession(
            id="sess1", template_id="t1", project_id="proj1", tab_id="tab1"
        )
        mock_spawner.get_session.return_value = mock_session

        # Mock iTerm2 session
        mock_iterm_session = MagicMock()
        mock_spawner.controller.app.get_session_by_id.return_value = mock_iterm_session

        # Mock terminator (imported inside stop_script)
        with patch(
            "iterm_controller.iterm.terminator.SessionTerminator"
        ) as MockTerminator:
            mock_terminator = MockTerminator.return_value
            mock_terminator.close_session = AsyncMock(
                return_value=MagicMock(success=True)
            )

            result = await service.stop_script("s1")

        assert result is True
        assert "s1" not in service._running_scripts
        mock_spawner.untrack_session.assert_called_once_with("sess1")

    def test_on_session_exit_with_callback(self, service: ScriptService):
        """Test session exit handling with callback."""
        callback = MagicMock()
        running = RunningScript(
            script=ProjectScript(id="s1", name="S1", command="cmd1"),
            session_id="sess1",
            started_at=datetime.now(),
            on_complete=callback,
        )
        service._running_scripts = {"s1": running}

        service.on_session_exit("sess1", exit_code=0)

        callback.assert_called_once_with(0)
        assert "s1" not in service._running_scripts

    def test_on_session_exit_without_callback(self, service: ScriptService):
        """Test session exit handling without callback."""
        running = RunningScript(
            script=ProjectScript(id="s1", name="S1", command="cmd1"),
            session_id="sess1",
            started_at=datetime.now(),
        )
        service._running_scripts = {"s1": running}

        service.on_session_exit("sess1", exit_code=1)

        assert "s1" not in service._running_scripts

    def test_on_session_exit_callback_error(self, service: ScriptService):
        """Test session exit handling when callback raises."""
        callback = MagicMock(side_effect=Exception("Callback error"))
        running = RunningScript(
            script=ProjectScript(id="s1", name="S1", command="cmd1"),
            session_id="sess1",
            started_at=datetime.now(),
            on_complete=callback,
        )
        service._running_scripts = {"s1": running}

        # Should not raise
        service.on_session_exit("sess1", exit_code=0)

        # Script should still be removed
        assert "s1" not in service._running_scripts

    def test_on_session_exit_unknown_session(self, service: ScriptService):
        """Test session exit for unknown session."""
        running = RunningScript(
            script=ProjectScript(id="s1", name="S1", command="cmd1"),
            session_id="sess1",
            started_at=datetime.now(),
        )
        service._running_scripts = {"s1": running}

        # Should not raise
        service.on_session_exit("unknown-session", exit_code=0)

        # Existing script should not be affected
        assert "s1" in service._running_scripts

    def test_clear(self, service: ScriptService):
        """Test clearing all running scripts."""
        running = RunningScript(
            script=ProjectScript(id="s1", name="S1", command="cmd1"),
            session_id="sess1",
            started_at=datetime.now(),
        )
        service._running_scripts = {"s1": running}

        service.clear()

        assert service._running_scripts == {}

    def test_get_keybindings(self, service: ScriptService):
        """Test getting keybindings for a project."""
        project = Project(
            id="proj1",
            name="Project 1",
            path="/path",
            scripts=[
                ProjectScript(id="s1", name="S1", command="c1", keybinding="a"),
                ProjectScript(id="s2", name="S2", command="c2", keybinding="b"),
                ProjectScript(id="s3", name="S3", command="c3"),  # No keybinding
            ],
        )

        bindings = service.get_keybindings(project)

        assert len(bindings) == 2
        assert "a" in bindings
        assert bindings["a"].id == "s1"
        assert "b" in bindings
        assert bindings["b"].id == "s2"

    def test_get_keybindings_no_scripts(self, service: ScriptService):
        """Test getting keybindings for project without scripts."""
        project = Project(
            id="proj1",
            name="Project 1",
            path="/path",
        )

        bindings = service.get_keybindings(project)
        assert bindings == {}


class TestScriptBehavior:
    """Tests for ScriptBehavior utility class."""

    def test_on_repress_server(self):
        """Test server scripts restart on repress."""
        assert ScriptBehavior.on_repress(SessionType.SERVER) == "restart"

    def test_on_repress_test_runner(self):
        """Test test runner scripts focus on repress."""
        assert ScriptBehavior.on_repress(SessionType.TEST_RUNNER) == "focus"

    def test_on_repress_script(self):
        """Test generic scripts focus on repress."""
        assert ScriptBehavior.on_repress(SessionType.SCRIPT) == "focus"

    def test_on_repress_orchestrator(self):
        """Test orchestrator scripts focus on repress."""
        assert ScriptBehavior.on_repress(SessionType.ORCHESTRATOR) == "focus"

    def test_on_complete_failure(self):
        """Test all types notify on failure."""
        for session_type in SessionType:
            assert ScriptBehavior.on_complete(session_type, exit_code=1) == "notify"

    def test_on_complete_server_success(self):
        """Test server scripts notify on success (unexpected stop)."""
        assert ScriptBehavior.on_complete(SessionType.SERVER, exit_code=0) == "notify"

    def test_on_complete_test_runner_success(self):
        """Test test runner scripts keep on success."""
        assert ScriptBehavior.on_complete(SessionType.TEST_RUNNER, exit_code=0) == "keep"

    def test_on_complete_script_success(self):
        """Test generic scripts close on success."""
        assert ScriptBehavior.on_complete(SessionType.SCRIPT, exit_code=0) == "close"

    def test_on_complete_orchestrator_success(self):
        """Test orchestrator scripts notify on success."""
        assert ScriptBehavior.on_complete(SessionType.ORCHESTRATOR, exit_code=0) == "notify"


class TestScriptValidator:
    """Tests for ScriptValidator."""

    @pytest.fixture
    def validator(self) -> ScriptValidator:
        """Create a ScriptValidator instance."""
        return ScriptValidator()

    def test_validate_valid_script(self, validator: ScriptValidator):
        """Test validating a valid script."""
        script = ProjectScript(
            id="test",
            name="Test",
            command="echo hello",
            keybinding="t",
        )

        errors = validator.validate(script)
        assert errors == []

    def test_validate_missing_id(self, validator: ScriptValidator):
        """Test validation error for missing ID."""
        script = ProjectScript(
            id="",
            name="Test",
            command="echo hello",
        )

        errors = validator.validate(script)
        assert "Script ID is required" in errors

    def test_validate_missing_name(self, validator: ScriptValidator):
        """Test validation error for missing name."""
        script = ProjectScript(
            id="test",
            name="",
            command="echo hello",
        )

        errors = validator.validate(script)
        assert "Script name is required" in errors

    def test_validate_missing_command(self, validator: ScriptValidator):
        """Test validation error for missing command."""
        script = ProjectScript(
            id="test",
            name="Test",
            command="",
        )

        errors = validator.validate(script)
        assert "Script command is required" in errors

    def test_validate_invalid_keybinding_length(self, validator: ScriptValidator):
        """Test validation error for multi-char keybinding."""
        script = ProjectScript(
            id="test",
            name="Test",
            command="echo hello",
            keybinding="ab",
        )

        errors = validator.validate(script)
        assert "Keybinding must be a single character" in errors

    def test_validate_invalid_keybinding_char(self, validator: ScriptValidator):
        """Test validation error for non-alphanumeric keybinding."""
        script = ProjectScript(
            id="test",
            name="Test",
            command="echo hello",
            keybinding="!",
        )

        errors = validator.validate(script)
        assert "Keybinding must be alphanumeric" in errors

    def test_check_keybinding_conflicts_no_conflict(self, validator: ScriptValidator):
        """Test no conflicts with unique keybindings."""
        scripts = [
            ProjectScript(id="s1", name="S1", command="c1", keybinding="a"),
            ProjectScript(id="s2", name="S2", command="c2", keybinding="b"),
        ]

        conflicts = validator.check_keybinding_conflicts(scripts)
        assert conflicts == []

    def test_check_keybinding_conflicts_with_conflict(self, validator: ScriptValidator):
        """Test detecting keybinding conflicts."""
        scripts = [
            ProjectScript(id="s1", name="S1", command="c1", keybinding="a"),
            ProjectScript(id="s2", name="S2", command="c2", keybinding="a"),
        ]

        conflicts = validator.check_keybinding_conflicts(scripts)
        assert len(conflicts) == 1
        assert "'S1'" in conflicts[0]
        assert "'S2'" in conflicts[0]

    def test_check_keybinding_conflicts_case_insensitive(
        self, validator: ScriptValidator
    ):
        """Test keybinding conflict detection is case insensitive."""
        scripts = [
            ProjectScript(id="s1", name="S1", command="c1", keybinding="A"),
            ProjectScript(id="s2", name="S2", command="c2", keybinding="a"),
        ]

        conflicts = validator.check_keybinding_conflicts(scripts)
        assert len(conflicts) == 1

    def test_validate_all(self, validator: ScriptValidator):
        """Test validating all scripts including conflicts."""
        scripts = [
            ProjectScript(id="", name="S1", command="c1", keybinding="a"),  # Missing ID
            ProjectScript(id="s2", name="S2", command="c2", keybinding="a"),  # Conflict
        ]

        errors = validator.validate_all(scripts)

        # Should have ID error and conflict
        assert len(errors) == 2
        assert any(e.message == "Script ID is required" for e in errors)
        assert any("Keybinding 'a' used by both" in e.message for e in errors)
