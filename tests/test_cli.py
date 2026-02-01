"""Tests for CLI subcommands."""

from __future__ import annotations

import argparse
import json
import sys
from io import StringIO
from typing import Any
from unittest import mock

import pytest

from iterm_controller.__main__ import (
    _create_parser,
    _print_json,
    _print_table,
    cmd_list_projects,
    cmd_list_sessions,
    cmd_task_claim,
    cmd_task_done,
    cmd_task_list,
)


class TestArgumentParser:
    """Test argument parser configuration."""

    def test_parser_has_subcommands(self) -> None:
        """Verify all expected subcommands are available."""
        parser = _create_parser()

        # Parse with help to list subparsers
        with pytest.raises(SystemExit):
            parser.parse_args(["--help"])

    def test_list_projects_subcommand(self) -> None:
        """Test list-projects subcommand parsing."""
        parser = _create_parser()
        args = parser.parse_args(["list-projects"])
        assert args.command == "list-projects"
        assert args.json is False

    def test_list_projects_with_json(self) -> None:
        """Test list-projects with JSON flag."""
        parser = _create_parser()
        args = parser.parse_args(["list-projects", "--json"])
        assert args.command == "list-projects"
        assert args.json is True

    def test_list_sessions_subcommand(self) -> None:
        """Test list-sessions subcommand parsing."""
        parser = _create_parser()
        args = parser.parse_args(["list-sessions"])
        assert args.command == "list-sessions"
        assert args.project is None

    def test_list_sessions_with_project(self) -> None:
        """Test list-sessions with project filter."""
        parser = _create_parser()
        args = parser.parse_args(["list-sessions", "--project", "my-proj"])
        assert args.command == "list-sessions"
        assert args.project == "my-proj"

    def test_spawn_subcommand(self) -> None:
        """Test spawn subcommand parsing."""
        parser = _create_parser()
        args = parser.parse_args([
            "spawn", "--project", "proj1", "--template", "dev-server"
        ])
        assert args.command == "spawn"
        assert args.project == "proj1"
        assert args.template == "dev-server"
        assert args.task is None

    def test_spawn_with_task(self) -> None:
        """Test spawn with task linkage."""
        parser = _create_parser()
        args = parser.parse_args([
            "spawn", "--project", "proj1", "--template", "dev-server",
            "--task", "2.1"
        ])
        assert args.command == "spawn"
        assert args.task == "2.1"

    def test_kill_subcommand(self) -> None:
        """Test kill subcommand parsing."""
        parser = _create_parser()
        args = parser.parse_args(["kill", "--session", "sess123"])
        assert args.command == "kill"
        assert args.session == "sess123"
        assert args.force is False

    def test_kill_with_force(self) -> None:
        """Test kill with force flag."""
        parser = _create_parser()
        args = parser.parse_args(["kill", "--session", "sess123", "--force"])
        assert args.command == "kill"
        assert args.force is True

    def test_task_claim_subcommand(self) -> None:
        """Test task claim subcommand parsing."""
        parser = _create_parser()
        args = parser.parse_args([
            "task", "claim", "--project", "proj1", "--task", "2.1"
        ])
        assert args.command == "task"
        assert args.task_command == "claim"
        assert args.project == "proj1"
        assert args.task == "2.1"

    def test_task_done_subcommand(self) -> None:
        """Test task done subcommand parsing."""
        parser = _create_parser()
        args = parser.parse_args([
            "task", "done", "--project", "proj1", "--task", "2.1"
        ])
        assert args.command == "task"
        assert args.task_command == "done"

    def test_task_unclaim_subcommand(self) -> None:
        """Test task unclaim subcommand parsing."""
        parser = _create_parser()
        args = parser.parse_args([
            "task", "unclaim", "--project", "proj1", "--task", "2.1"
        ])
        assert args.command == "task"
        assert args.task_command == "unclaim"

    def test_task_skip_subcommand(self) -> None:
        """Test task skip subcommand parsing."""
        parser = _create_parser()
        args = parser.parse_args([
            "task", "skip", "--project", "proj1", "--task", "2.1"
        ])
        assert args.command == "task"
        assert args.task_command == "skip"

    def test_task_list_subcommand(self) -> None:
        """Test task list subcommand parsing."""
        parser = _create_parser()
        args = parser.parse_args([
            "task", "list", "--project", "proj1"
        ])
        assert args.command == "task"
        assert args.task_command == "list"

    def test_task_list_with_status_filter(self) -> None:
        """Test task list with status filter."""
        parser = _create_parser()
        args = parser.parse_args([
            "task", "list", "--project", "proj1", "--status", "pending"
        ])
        assert args.status == "pending"

    def test_spawn_requires_project(self) -> None:
        """Test spawn requires --project."""
        parser = _create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["spawn", "--template", "dev-server"])

    def test_spawn_requires_template(self) -> None:
        """Test spawn requires --template."""
        parser = _create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["spawn", "--project", "proj1"])

    def test_kill_requires_session(self) -> None:
        """Test kill requires --session."""
        parser = _create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["kill"])

    def test_global_debug_flag(self) -> None:
        """Test global --debug flag."""
        parser = _create_parser()
        args = parser.parse_args(["--debug", "list-projects"])
        assert args.debug is True

    def test_global_log_level(self) -> None:
        """Test global --log-level flag."""
        parser = _create_parser()
        args = parser.parse_args(["--log-level", "DEBUG", "list-projects"])
        assert args.log_level == "DEBUG"


class TestOutputFormatting:
    """Test output formatting helpers."""

    def test_print_json(self, capsys: Any) -> None:
        """Test JSON output formatting."""
        data = {"id": "test", "name": "Test Project"}
        _print_json(data)
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == data

    def test_print_json_list(self, capsys: Any) -> None:
        """Test JSON output with list."""
        data = [{"id": "a"}, {"id": "b"}]
        _print_json(data)
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed == data

    def test_print_table_empty(self, capsys: Any) -> None:
        """Test table output with no data."""
        _print_table([], ["ID", "Name"])
        captured = capsys.readouterr()
        assert "No results" in captured.out

    def test_print_table_with_data(self, capsys: Any) -> None:
        """Test table output with data."""
        rows = [
            {"ID": "1", "Name": "First"},
            {"ID": "2", "Name": "Second"},
        ]
        _print_table(rows, ["ID", "Name"])
        captured = capsys.readouterr()
        assert "ID" in captured.out
        assert "Name" in captured.out
        assert "First" in captured.out
        assert "Second" in captured.out


class TestCommandHandlers:
    """Test async command handlers."""

    @pytest.mark.asyncio
    async def test_list_projects_empty(self) -> None:
        """Test list-projects with no projects."""
        parser = _create_parser()
        args = parser.parse_args(["list-projects", "--json"])

        with mock.patch("iterm_controller.api.ItermControllerAPI") as MockAPI:
            mock_api = mock.AsyncMock()
            mock_api.initialize = mock.AsyncMock(return_value=mock.Mock(success=True))
            mock_api.list_projects = mock.AsyncMock(return_value=[])
            mock_api.shutdown = mock.AsyncMock()
            MockAPI.return_value = mock_api

            result = await cmd_list_projects(args)
            assert result == 0
            mock_api.list_projects.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_projects_init_failure(self) -> None:
        """Test list-projects handles init failure."""
        parser = _create_parser()
        args = parser.parse_args(["list-projects"])

        with mock.patch("iterm_controller.api.ItermControllerAPI") as MockAPI:
            mock_api = mock.AsyncMock()
            mock_api.initialize = mock.AsyncMock(
                return_value=mock.Mock(success=False, error="Config error")
            )
            MockAPI.return_value = mock_api

            result = await cmd_list_projects(args)
            assert result == 1

    @pytest.mark.asyncio
    async def test_list_sessions_with_filter(self) -> None:
        """Test list-sessions with project filter."""
        parser = _create_parser()
        args = parser.parse_args(["list-sessions", "--project", "proj1", "--json"])

        with mock.patch("iterm_controller.api.ItermControllerAPI") as MockAPI:
            mock_api = mock.AsyncMock()
            mock_api.initialize = mock.AsyncMock(return_value=mock.Mock(success=True))
            mock_api.is_connected = True
            mock_api.list_sessions = mock.AsyncMock(return_value=[])
            mock_api.shutdown = mock.AsyncMock()
            MockAPI.return_value = mock_api

            result = await cmd_list_sessions(args)
            assert result == 0
            mock_api.list_sessions.assert_called_once_with("proj1")

    @pytest.mark.asyncio
    async def test_task_claim_not_found(self) -> None:
        """Test task claim with nonexistent project."""
        parser = _create_parser()
        args = parser.parse_args([
            "task", "claim", "--project", "nonexistent", "--task", "1.1"
        ])

        with mock.patch("iterm_controller.api.ItermControllerAPI") as MockAPI:
            mock_api = mock.AsyncMock()
            mock_api.initialize = mock.AsyncMock(return_value=mock.Mock(success=True))
            mock_api.open_project = mock.AsyncMock(
                return_value=mock.Mock(success=False, error="Project not found")
            )
            mock_api.shutdown = mock.AsyncMock()
            MockAPI.return_value = mock_api

            result = await cmd_task_claim(args)
            assert result == 1

    @pytest.mark.asyncio
    async def test_task_done_success(self) -> None:
        """Test task done with success."""
        parser = _create_parser()
        args = parser.parse_args([
            "task", "done", "--project", "proj1", "--task", "1.1", "--json"
        ])

        with mock.patch("iterm_controller.api.ItermControllerAPI") as MockAPI:
            mock_api = mock.AsyncMock()
            mock_api.initialize = mock.AsyncMock(return_value=mock.Mock(success=True))
            mock_api.open_project = mock.AsyncMock(
                return_value=mock.Mock(success=True, project=mock.Mock())
            )
            mock_api.complete_task = mock.AsyncMock(
                return_value=mock.Mock(
                    success=True,
                    task=mock.Mock(id="1.1", title="Test Task")
                )
            )
            mock_api.shutdown = mock.AsyncMock()
            MockAPI.return_value = mock_api

            result = await cmd_task_done(args)
            assert result == 0
            mock_api.complete_task.assert_called_once_with("proj1", "1.1")

    @pytest.mark.asyncio
    async def test_task_list_with_status_filter(self) -> None:
        """Test task list with status filter."""
        parser = _create_parser()
        args = parser.parse_args([
            "task", "list", "--project", "proj1", "--status", "pending", "--json"
        ])

        with mock.patch("iterm_controller.api.ItermControllerAPI") as MockAPI:
            from iterm_controller.models import TaskStatus

            mock_api = mock.AsyncMock()
            mock_api.initialize = mock.AsyncMock(return_value=mock.Mock(success=True))
            mock_api.open_project = mock.AsyncMock(
                return_value=mock.Mock(success=True)
            )
            mock_api.list_tasks = mock.AsyncMock(return_value=[])
            mock_api.shutdown = mock.AsyncMock()
            MockAPI.return_value = mock_api

            result = await cmd_task_list(args)
            assert result == 0
            mock_api.list_tasks.assert_called_once_with("proj1", TaskStatus.PENDING)


class TestNoSubcommandLaunchesTUI:
    """Test that no subcommand launches the TUI."""

    def test_no_command_runs_tui(self) -> None:
        """Test that no subcommand triggers TUI launch."""
        parser = _create_parser()
        args = parser.parse_args([])
        assert args.command is None
