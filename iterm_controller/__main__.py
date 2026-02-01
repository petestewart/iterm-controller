"""Entry point for python -m iterm_controller.

Supports both TUI mode (default) and CLI subcommands for headless operation.

Usage:
    # Launch TUI
    python -m iterm_controller

    # CLI commands (headless)
    python -m iterm_controller list-projects
    python -m iterm_controller list-sessions
    python -m iterm_controller spawn --project myproj --template dev-server
    python -m iterm_controller kill --session SESSION_ID
    python -m iterm_controller task claim --project myproj --task 2.1
    python -m iterm_controller task done --project myproj --task 2.1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any


def _setup_logging(args: argparse.Namespace) -> None:
    """Configure logging based on command-line arguments."""
    from iterm_controller.logging_config import setup_logging

    if args.debug:
        setup_logging(
            level="DEBUG",
            log_to_console=True,
            log_to_file=True,
        )
    else:
        setup_logging(
            level=args.log_level,
            log_to_console=False,
            log_to_file=not args.no_log_file,
        )


def _print_json(data: Any) -> None:
    """Print data as JSON to stdout."""
    print(json.dumps(data, indent=2, default=str))


def _print_table(rows: list[dict[str, Any]], columns: list[str]) -> None:
    """Print data as a simple table."""
    if not rows:
        print("No results.")
        return

    # Calculate column widths
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            val = str(row.get(col, ""))
            widths[col] = max(widths[col], len(val))

    # Print header
    header = "  ".join(col.ljust(widths[col]) for col in columns)
    print(header)
    print("-" * len(header))

    # Print rows
    for row in rows:
        line = "  ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns)
        print(line)


# =============================================================================
# CLI Command Handlers
# =============================================================================


async def cmd_list_projects(args: argparse.Namespace) -> int:
    """Handle list-projects command."""
    from iterm_controller.api import ItermControllerAPI

    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=False)
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

    try:
        projects = await api.list_projects()

        if args.json:
            _print_json([
                {
                    "id": p.id,
                    "name": p.name,
                    "path": p.path,
                    "template_id": p.template_id,
                    "jira_ticket": p.jira_ticket,
                }
                for p in projects
            ])
        else:
            if not projects:
                print("No projects configured.")
                return 0

            _print_table(
                [
                    {
                        "ID": p.id,
                        "Name": p.name,
                        "Path": p.path,
                        "Template": p.template_id or "-",
                    }
                    for p in projects
                ],
                ["ID", "Name", "Path", "Template"],
            )

        return 0
    finally:
        await api.shutdown()


async def cmd_list_sessions(args: argparse.Namespace) -> int:
    """Handle list-sessions command."""
    from iterm_controller.api import ItermControllerAPI

    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=True)
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

    try:
        project_id = getattr(args, "project", None)
        sessions = await api.list_sessions(project_id)

        if args.json:
            _print_json([
                {
                    "id": s.id,
                    "project_id": s.project_id,
                    "template_id": s.template_id,
                    "attention_state": s.attention_state.value,
                    "is_active": s.is_active,
                    "spawned_at": s.spawned_at.isoformat() if s.spawned_at else None,
                    "task_id": s.metadata.get("task_id"),
                }
                for s in sessions
            ])
        else:
            if not sessions:
                print("No active sessions.")
                return 0

            _print_table(
                [
                    {
                        "ID": s.id[:12] + "..." if len(s.id) > 15 else s.id,
                        "Project": s.project_id,
                        "Template": s.template_id,
                        "State": s.attention_state.value.upper(),
                        "Task": s.metadata.get("task_id", "-"),
                    }
                    for s in sessions
                ],
                ["ID", "Project", "Template", "State", "Task"],
            )

        return 0
    finally:
        await api.shutdown()


async def cmd_spawn(args: argparse.Namespace) -> int:
    """Handle spawn command."""
    from iterm_controller.api import ItermControllerAPI

    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=True)
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

    try:
        if not api.is_connected:
            print("Error: Not connected to iTerm2. Is iTerm2 running?", file=sys.stderr)
            return 1

        task_id = getattr(args, "task", None)
        spawn_result = await api.spawn_session(args.project, args.template, task_id)

        if not spawn_result.success:
            print(f"Error: {spawn_result.error}", file=sys.stderr)
            return 1

        if args.json:
            _print_json({
                "success": True,
                "session_id": spawn_result.session.id if spawn_result.session else None,
                "project_id": args.project,
                "template_id": args.template,
                "task_id": task_id,
            })
        else:
            session_id = spawn_result.session.id if spawn_result.session else "unknown"
            print(f"Spawned session: {session_id}")
            if task_id:
                print(f"Linked to task: {task_id}")

        return 0
    finally:
        await api.shutdown()


async def cmd_kill(args: argparse.Namespace) -> int:
    """Handle kill command."""
    from iterm_controller.api import ItermControllerAPI

    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=True)
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

    try:
        if not api.is_connected:
            print("Error: Not connected to iTerm2. Is iTerm2 running?", file=sys.stderr)
            return 1

        kill_result = await api.kill_session(args.session, force=args.force)

        if not kill_result.success:
            print(f"Error: {kill_result.error}", file=sys.stderr)
            return 1

        if args.json:
            _print_json({
                "success": True,
                "session_id": args.session,
            })
        else:
            print(f"Killed session: {args.session}")

        return 0
    finally:
        await api.shutdown()


async def cmd_task_claim(args: argparse.Namespace) -> int:
    """Handle task claim command."""
    from iterm_controller.api import ItermControllerAPI

    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=False)
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

    try:
        # First open the project to load PLAN.md
        project_result = await api.open_project(args.project)
        if not project_result.success:
            print(f"Error: {project_result.error}", file=sys.stderr)
            return 1

        claim_result = await api.claim_task(args.project, args.task)

        if not claim_result.success:
            print(f"Error: {claim_result.error}", file=sys.stderr)
            return 1

        if args.json:
            _print_json({
                "success": True,
                "project_id": args.project,
                "task_id": args.task,
                "task_title": claim_result.task.title if claim_result.task else None,
                "status": "in_progress",
            })
        else:
            task_title = claim_result.task.title if claim_result.task else "unknown"
            print(f"Claimed task {args.task}: {task_title}")
            print("Status: in_progress")

        return 0
    finally:
        await api.shutdown()


async def cmd_task_done(args: argparse.Namespace) -> int:
    """Handle task done command."""
    from iterm_controller.api import ItermControllerAPI

    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=False)
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

    try:
        # First open the project to load PLAN.md
        project_result = await api.open_project(args.project)
        if not project_result.success:
            print(f"Error: {project_result.error}", file=sys.stderr)
            return 1

        complete_result = await api.complete_task(args.project, args.task)

        if not complete_result.success:
            print(f"Error: {complete_result.error}", file=sys.stderr)
            return 1

        if args.json:
            _print_json({
                "success": True,
                "project_id": args.project,
                "task_id": args.task,
                "task_title": complete_result.task.title if complete_result.task else None,
                "status": "complete",
            })
        else:
            task_title = complete_result.task.title if complete_result.task else "unknown"
            print(f"Completed task {args.task}: {task_title}")
            print("Status: complete")

        return 0
    finally:
        await api.shutdown()


async def cmd_task_list(args: argparse.Namespace) -> int:
    """Handle task list command."""
    from iterm_controller.api import ItermControllerAPI
    from iterm_controller.models import TaskStatus

    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=False)
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

    try:
        # First open the project to load PLAN.md
        project_result = await api.open_project(args.project)
        if not project_result.success:
            print(f"Error: {project_result.error}", file=sys.stderr)
            return 1

        # Filter by status if specified
        status_filter = None
        if hasattr(args, "status") and args.status:
            try:
                status_filter = TaskStatus(args.status)
            except ValueError:
                print(f"Error: Invalid status '{args.status}'", file=sys.stderr)
                return 1

        tasks = await api.list_tasks(args.project, status_filter)

        if args.json:
            _print_json([
                {
                    "id": t.id,
                    "title": t.title,
                    "status": t.status.value,
                    "spec_ref": t.spec_ref,
                    "depends": t.depends,
                    "is_blocked": t.is_blocked,
                }
                for t in tasks
            ])
        else:
            if not tasks:
                print("No tasks found.")
                return 0

            _print_table(
                [
                    {
                        "ID": t.id,
                        "Title": t.title[:50] + "..." if len(t.title) > 53 else t.title,
                        "Status": t.status.value.upper(),
                        "Blocked": "Yes" if t.is_blocked else "-",
                    }
                    for t in tasks
                ],
                ["ID", "Title", "Status", "Blocked"],
            )

        return 0
    finally:
        await api.shutdown()


async def cmd_task_unclaim(args: argparse.Namespace) -> int:
    """Handle task unclaim command."""
    from iterm_controller.api import ItermControllerAPI

    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=False)
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

    try:
        # First open the project to load PLAN.md
        project_result = await api.open_project(args.project)
        if not project_result.success:
            print(f"Error: {project_result.error}", file=sys.stderr)
            return 1

        unclaim_result = await api.unclaim_task(args.project, args.task)

        if not unclaim_result.success:
            print(f"Error: {unclaim_result.error}", file=sys.stderr)
            return 1

        if args.json:
            _print_json({
                "success": True,
                "project_id": args.project,
                "task_id": args.task,
                "task_title": unclaim_result.task.title if unclaim_result.task else None,
                "status": "pending",
            })
        else:
            task_title = unclaim_result.task.title if unclaim_result.task else "unknown"
            print(f"Unclaimed task {args.task}: {task_title}")
            print("Status: pending")

        return 0
    finally:
        await api.shutdown()


async def cmd_task_skip(args: argparse.Namespace) -> int:
    """Handle task skip command."""
    from iterm_controller.api import ItermControllerAPI

    api = ItermControllerAPI()
    result = await api.initialize(connect_iterm=False)
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        return 1

    try:
        # First open the project to load PLAN.md
        project_result = await api.open_project(args.project)
        if not project_result.success:
            print(f"Error: {project_result.error}", file=sys.stderr)
            return 1

        skip_result = await api.skip_task(args.project, args.task)

        if not skip_result.success:
            print(f"Error: {skip_result.error}", file=sys.stderr)
            return 1

        if args.json:
            _print_json({
                "success": True,
                "project_id": args.project,
                "task_id": args.task,
                "task_title": skip_result.task.title if skip_result.task else None,
                "status": "skipped",
            })
        else:
            task_title = skip_result.task.title if skip_result.task else "unknown"
            print(f"Skipped task {args.task}: {task_title}")
            print("Status: skipped")

        return 0
    finally:
        await api.shutdown()


def _run_async(coro: Any) -> int:
    """Run an async coroutine and return exit code."""
    return asyncio.run(coro)


# =============================================================================
# Argument Parser Setup
# =============================================================================


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add common arguments to a parser."""
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format",
    )


def _create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="iTerm2 Project Orchestrator - A control room for dev projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Launch the TUI application
  python -m iterm_controller

  # List all configured projects
  python -m iterm_controller list-projects

  # List active sessions
  python -m iterm_controller list-sessions --project myproj

  # Spawn a new session
  python -m iterm_controller spawn --project myproj --template dev-server

  # Kill a session
  python -m iterm_controller kill --session SESSION_ID

  # Task operations
  python -m iterm_controller task list --project myproj
  python -m iterm_controller task claim --project myproj --task 2.1
  python -m iterm_controller task done --project myproj --task 2.1
""",
    )

    # Global arguments
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging to console",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set log level (default: INFO)",
    )
    parser.add_argument(
        "--no-log-file",
        action="store_true",
        help="Disable logging to file",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # list-projects
    list_projects_parser = subparsers.add_parser(
        "list-projects",
        help="List all configured projects",
    )
    _add_common_args(list_projects_parser)

    # list-sessions
    list_sessions_parser = subparsers.add_parser(
        "list-sessions",
        help="List active terminal sessions",
    )
    list_sessions_parser.add_argument(
        "--project",
        help="Filter sessions by project ID",
    )
    _add_common_args(list_sessions_parser)

    # spawn
    spawn_parser = subparsers.add_parser(
        "spawn",
        help="Spawn a new terminal session",
    )
    spawn_parser.add_argument(
        "--project",
        required=True,
        help="Project ID to spawn session for",
    )
    spawn_parser.add_argument(
        "--template",
        required=True,
        help="Session template ID to use",
    )
    spawn_parser.add_argument(
        "--task",
        help="Task ID to link the session to",
    )
    _add_common_args(spawn_parser)

    # kill
    kill_parser = subparsers.add_parser(
        "kill",
        help="Kill a terminal session",
    )
    kill_parser.add_argument(
        "--session",
        required=True,
        help="Session ID to terminate",
    )
    kill_parser.add_argument(
        "--force",
        action="store_true",
        help="Force kill without graceful shutdown",
    )
    _add_common_args(kill_parser)

    # task subcommands
    task_parser = subparsers.add_parser(
        "task",
        help="Task operations (claim, done, skip, list)",
    )
    task_subparsers = task_parser.add_subparsers(dest="task_command", help="Task commands")

    # task list
    task_list_parser = task_subparsers.add_parser(
        "list",
        help="List tasks from PLAN.md",
    )
    task_list_parser.add_argument(
        "--project",
        required=True,
        help="Project ID",
    )
    task_list_parser.add_argument(
        "--status",
        choices=["pending", "in_progress", "complete", "skipped", "blocked"],
        help="Filter tasks by status",
    )
    _add_common_args(task_list_parser)

    # task claim
    task_claim_parser = task_subparsers.add_parser(
        "claim",
        help="Claim a task (set to in_progress)",
    )
    task_claim_parser.add_argument(
        "--project",
        required=True,
        help="Project ID",
    )
    task_claim_parser.add_argument(
        "--task",
        required=True,
        help="Task ID (e.g., '2.1')",
    )
    _add_common_args(task_claim_parser)

    # task done
    task_done_parser = task_subparsers.add_parser(
        "done",
        help="Mark a task as complete",
    )
    task_done_parser.add_argument(
        "--project",
        required=True,
        help="Project ID",
    )
    task_done_parser.add_argument(
        "--task",
        required=True,
        help="Task ID (e.g., '2.1')",
    )
    _add_common_args(task_done_parser)

    # task unclaim
    task_unclaim_parser = task_subparsers.add_parser(
        "unclaim",
        help="Unclaim a task (set back to pending)",
    )
    task_unclaim_parser.add_argument(
        "--project",
        required=True,
        help="Project ID",
    )
    task_unclaim_parser.add_argument(
        "--task",
        required=True,
        help="Task ID (e.g., '2.1')",
    )
    _add_common_args(task_unclaim_parser)

    # task skip
    task_skip_parser = task_subparsers.add_parser(
        "skip",
        help="Skip a task",
    )
    task_skip_parser.add_argument(
        "--project",
        required=True,
        help="Project ID",
    )
    task_skip_parser.add_argument(
        "--task",
        required=True,
        help="Task ID (e.g., '2.1')",
    )
    _add_common_args(task_skip_parser)

    return parser


def main() -> int:
    """Main entry point for the iTerm2 Controller application."""
    parser = _create_parser()
    args = parser.parse_args()

    # Initialize logging
    _setup_logging(args)

    # Handle subcommands
    if args.command == "list-projects":
        return _run_async(cmd_list_projects(args))

    if args.command == "list-sessions":
        return _run_async(cmd_list_sessions(args))

    if args.command == "spawn":
        return _run_async(cmd_spawn(args))

    if args.command == "kill":
        return _run_async(cmd_kill(args))

    if args.command == "task":
        if args.task_command == "list":
            return _run_async(cmd_task_list(args))
        if args.task_command == "claim":
            return _run_async(cmd_task_claim(args))
        if args.task_command == "done":
            return _run_async(cmd_task_done(args))
        if args.task_command == "unclaim":
            return _run_async(cmd_task_unclaim(args))
        if args.task_command == "skip":
            return _run_async(cmd_task_skip(args))
        # No task subcommand provided
        parser.parse_args(["task", "--help"])
        return 1

    # No subcommand - launch TUI
    from iterm_controller.app import ItermControllerApp

    app = ItermControllerApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
