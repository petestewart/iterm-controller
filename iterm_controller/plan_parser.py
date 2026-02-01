"""PLAN.md parsing and updates.

Parses markdown task lists with metadata (Status, Spec, Session, Depends)
and extracts phases, tasks, statuses, and dependencies.

Also provides PlanUpdater for updating PLAN.md files while preserving formatting.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from pathlib import Path

from .exceptions import PlanParseError, PlanWriteError, record_error
from .models import Phase, Plan, Task, TaskStatus

logger = logging.getLogger(__name__)


class PlanParser:
    """Parses PLAN.md files into structured data."""

    PHASE_PATTERN = re.compile(r"^###\s+Phase\s+(\d+):\s+(.+)$", re.MULTILINE)
    TASK_PATTERN = re.compile(
        r"^-\s+\[([ x])\]\s+\*\*(.+?)\*\*\s+`\[(\w+)\]`",
        re.MULTILINE,
    )
    METADATA_PATTERN = re.compile(r"^\s+-\s+(\w+):\s+(.+)$", re.MULTILINE)

    def parse(self, content: str) -> Plan:
        """Parse PLAN.md content into Plan object."""
        plan = Plan()

        # Extract overview
        overview_match = re.search(
            r"^## Overview\s*\n(.*?)(?=^##|\Z)", content, re.MULTILINE | re.DOTALL
        )
        if overview_match:
            plan.overview = overview_match.group(1).strip()

        # Extract success criteria
        criteria_match = re.search(
            r"\*\*Success criteria:\*\*\s*\n((?:-\s+.+\n?)+)", content
        )
        if criteria_match:
            plan.success_criteria = [
                line.strip("- \n")
                for line in criteria_match.group(1).split("\n")
                if line.strip().startswith("-")
            ]

        # Parse phases and tasks
        phases = self._parse_phases(content)
        plan.phases = phases

        # Resolve dependencies
        self._resolve_dependencies(plan)

        return plan

    def parse_file(self, path: Path) -> Plan:
        """Parse PLAN.md file from disk.

        Args:
            path: Path to the PLAN.md file.

        Returns:
            Parsed Plan object.

        Raises:
            PlanParseError: If the file cannot be read or parsed.
        """
        try:
            content = path.read_text(encoding="utf-8")
            logger.debug("Read PLAN.md from %s (%d bytes)", path, len(content))
        except OSError as e:
            logger.error("Failed to read PLAN.md: %s", e)
            record_error(e)
            raise PlanParseError(
                f"Failed to read PLAN.md: {e}",
                file_path=str(path),
                cause=e,
            ) from e

        try:
            plan = self.parse(content)
            logger.debug(
                "Parsed %d phases with %d total tasks",
                len(plan.phases),
                len(plan.all_tasks),
            )
            return plan
        except Exception as e:
            logger.error("Failed to parse PLAN.md content: %s", e)
            record_error(e)
            raise PlanParseError(
                f"Failed to parse PLAN.md content: {e}",
                file_path=str(path),
                cause=e,
            ) from e

    async def parse_file_async(self, path: Path) -> Plan:
        """Parse PLAN.md file from disk asynchronously.

        Uses asyncio.to_thread to avoid blocking the event loop during file I/O.

        Args:
            path: Path to the PLAN.md file.

        Returns:
            Parsed Plan object.

        Raises:
            PlanParseError: If the file cannot be read or parsed.
        """
        try:
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
            logger.debug("Read PLAN.md from %s (%d bytes)", path, len(content))
        except OSError as e:
            logger.error("Failed to read PLAN.md: %s", e)
            record_error(e)
            raise PlanParseError(
                f"Failed to read PLAN.md: {e}",
                file_path=str(path),
                cause=e,
            ) from e

        try:
            plan = self.parse(content)
            logger.debug(
                "Parsed %d phases with %d total tasks",
                len(plan.phases),
                len(plan.all_tasks),
            )
            return plan
        except Exception as e:
            logger.error("Failed to parse PLAN.md content: %s", e)
            record_error(e)
            raise PlanParseError(
                f"Failed to parse PLAN.md content: {e}",
                file_path=str(path),
                cause=e,
            ) from e

    def _parse_phases(self, content: str) -> list[Phase]:
        """Parse all phases from content."""
        phases = []
        phase_matches = list(self.PHASE_PATTERN.finditer(content))

        for i, match in enumerate(phase_matches):
            phase_id = match.group(1)
            phase_title = match.group(2)

            # Get content until next phase or end
            start = match.end()
            end = (
                phase_matches[i + 1].start()
                if i + 1 < len(phase_matches)
                else len(content)
            )
            phase_content = content[start:end]

            tasks = self._parse_tasks(phase_content, phase_id)
            phases.append(Phase(id=phase_id, title=phase_title, tasks=tasks))

        return phases

    def _parse_tasks(self, content: str, phase_id: str) -> list[Task]:
        """Parse tasks from phase content."""
        tasks = []
        task_matches = list(self.TASK_PATTERN.finditer(content))

        for i, match in enumerate(task_matches):
            checkbox = match.group(1)
            title = match.group(2)
            status_str = match.group(3)

            # Get task content until next task
            start = match.end()
            end = (
                task_matches[i + 1].start()
                if i + 1 < len(task_matches)
                else len(content)
            )
            task_content = content[start:end]

            # Parse metadata
            metadata = self._parse_metadata(task_content)

            task = Task(
                id=f"{phase_id}.{i + 1}",
                title=title,
                status=self._parse_status(status_str, checkbox),
                spec_ref=metadata.get("Spec"),
                scope=metadata.get("Scope", ""),
                acceptance=metadata.get("Acceptance", ""),
                depends=self._parse_depends(metadata.get("Depends", "")),
            )

            # Parse Session if present
            if "Session" in metadata:
                task.session_id = metadata["Session"]

            tasks.append(task)

        return tasks

    def _parse_metadata(self, content: str) -> dict[str, str]:
        """Parse metadata lines from task content."""
        metadata: dict[str, str] = {}
        for match in self.METADATA_PATTERN.finditer(content):
            key = match.group(1)
            value = match.group(2).strip()
            metadata[key] = value
        return metadata

    def _parse_status(self, status_str: str, checkbox: str) -> TaskStatus:
        """Convert status string to enum."""
        status_map = {
            "pending": TaskStatus.PENDING,
            "in_progress": TaskStatus.IN_PROGRESS,
            "complete": TaskStatus.COMPLETE,
            "skipped": TaskStatus.SKIPPED,
            "blocked": TaskStatus.BLOCKED,
        }
        return status_map.get(status_str.lower(), TaskStatus.PENDING)

    def _parse_depends(self, depends_str: str) -> list[str]:
        """Parse dependency list."""
        if not depends_str:
            return []
        return [d.strip() for d in depends_str.split(",") if d.strip()]

    def _resolve_dependencies(self, plan: Plan) -> None:
        """Mark tasks as blocked based on incomplete dependencies."""
        task_map = {t.id: t for t in plan.all_tasks}

        for task in plan.all_tasks:
            if task.depends:
                for dep_id in task.depends:
                    dep = task_map.get(dep_id)
                    if dep and dep.status not in (
                        TaskStatus.COMPLETE,
                        TaskStatus.SKIPPED,
                    ):
                        task.status = TaskStatus.BLOCKED
                        break


class PlanUpdater:
    """Updates PLAN.md files while preserving formatting."""

    # Pattern to match a task line and capture its components
    # Group 1: checkbox prefix "- ["
    # Group 2: checkbox state " " or "x"
    # Group 3: rest before status "**Title** `["
    # Group 4: status word
    # Group 5: closing "]`"
    TASK_LINE_PATTERN = re.compile(
        r"^(-\s+\[)([ x])(\]\s+\*\*.+?\*\*\s+`\[)(\w+)(\]`)",
        re.MULTILINE,
    )

    def update_task_status(
        self,
        content: str,
        task_id: str,
        new_status: TaskStatus,
    ) -> str:
        """Update a task's status in PLAN.md content.

        Args:
            content: The PLAN.md file content
            task_id: The task ID to update (e.g., "2.1")
            new_status: The new status to set

        Returns:
            Updated content with the task status changed
        """
        phase_id, task_num = task_id.split(".")
        target_phase = int(phase_id)
        target_task = int(task_num)

        # Parse to find phase boundaries
        phase_pattern = re.compile(r"^###\s+Phase\s+(\d+):", re.MULTILINE)
        phase_starts: dict[int, int] = {}  # phase_num -> content position

        for match in phase_pattern.finditer(content):
            phase_num = int(match.group(1))
            phase_starts[phase_num] = match.start()

        # Sort phases by position
        sorted_phases = sorted(phase_starts.items(), key=lambda x: x[1])

        # Find the start and end positions for our target phase
        phase_start = None
        phase_end = None

        for i, (phase_num, pos) in enumerate(sorted_phases):
            if phase_num == target_phase:
                phase_start = pos
                # End is start of next phase or end of content
                if i + 1 < len(sorted_phases):
                    phase_end = sorted_phases[i + 1][1]
                else:
                    phase_end = len(content)
                break

        if phase_start is None:
            logger.warning("Phase %s not found in PLAN.md", phase_id)
            raise PlanWriteError(
                f"Phase {phase_id} not found in PLAN.md",
                context={"phase_id": phase_id, "task_id": task_id},
            )

        # Extract phase content
        phase_content = content[phase_start:phase_end]

        # Create a replacer function that tracks task count
        def make_replacer() -> Callable[[re.Match[str]], str]:
            count = [0]  # Use list for mutable closure

            def replacer(match: re.Match[str]) -> str:
                count[0] += 1
                if count[0] == target_task:
                    checkbox = "x" if new_status == TaskStatus.COMPLETE else " "
                    return (
                        f"{match.group(1)}{checkbox}{match.group(3)}"
                        f"{new_status.value}{match.group(5)}"
                    )
                return match.group(0)

            return replacer

        updated_phase = self.TASK_LINE_PATTERN.sub(make_replacer(), phase_content)

        return content[:phase_start] + updated_phase + content[phase_end:]

    def add_task(
        self,
        content: str,
        phase_id: str,
        task: Task,
    ) -> str:
        """Add a new task to a phase.

        Args:
            content: The PLAN.md file content
            phase_id: The phase to add the task to (e.g., "2")
            task: The task to add

        Returns:
            Updated content with the new task added
        """
        # Find the phase header
        phase_pattern = re.compile(
            rf"^###\s+Phase\s+{phase_id}:\s+.+$",
            re.MULTILINE,
        )

        match = phase_pattern.search(content)
        if not match:
            logger.warning("Phase %s not found for adding task", phase_id)
            raise PlanWriteError(
                f"Phase {phase_id} not found",
                context={"phase_id": phase_id},
            )

        # Find the end of this phase (start of next phase or end of content)
        next_phase_pattern = re.compile(r"^###\s+Phase\s+\d+:", re.MULTILINE)
        next_phase_match = next_phase_pattern.search(content, match.end())

        if next_phase_match:
            insert_pos = next_phase_match.start()
            # Insert before the blank lines preceding next phase
            # Walk backwards to find where content ends
            while insert_pos > 0 and content[insert_pos - 1] in "\n\r":
                insert_pos -= 1
            insert_pos += 1  # Keep one newline
        else:
            insert_pos = len(content)
            # Ensure we end with a newline
            if not content.endswith("\n"):
                insert_pos = len(content)

        # Format the new task
        task_md = self._format_task(task)

        # Add appropriate spacing
        if not content[:insert_pos].endswith("\n\n"):
            if content[:insert_pos].endswith("\n"):
                prefix = "\n"
            else:
                prefix = "\n\n"
        else:
            prefix = ""

        return content[:insert_pos] + prefix + task_md + "\n" + content[insert_pos:]

    def _format_task(self, task: Task) -> str:
        """Format a task as markdown.

        Args:
            task: The task to format

        Returns:
            Markdown representation of the task
        """
        checkbox = "x" if task.status == TaskStatus.COMPLETE else " "
        lines = [f"- [{checkbox}] **{task.title}** `[{task.status.value}]`"]

        if task.spec_ref:
            lines.append(f"  - Spec: {task.spec_ref}")
        if task.depends:
            lines.append(f"  - Depends: {', '.join(task.depends)}")
        if task.session_id:
            lines.append(f"  - Session: {task.session_id}")
        if task.scope:
            lines.append(f"  - Scope: {task.scope}")
        if task.acceptance:
            lines.append(f"  - Acceptance: {task.acceptance}")

        return "\n".join(lines)

    def update_task_status_in_file(
        self,
        path: Path,
        task_id: str,
        new_status: TaskStatus,
    ) -> None:
        """Update a task's status in a PLAN.md file.

        Args:
            path: Path to the PLAN.md file
            task_id: The task ID to update (e.g., "2.1")
            new_status: The new status to set

        Raises:
            PlanParseError: If the file cannot be read.
            PlanWriteError: If the file cannot be written.
        """
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.error("Failed to read PLAN.md for update: %s", e)
            record_error(e)
            raise PlanParseError(
                f"Failed to read PLAN.md: {e}",
                file_path=str(path),
                cause=e,
            ) from e

        updated_content = self.update_task_status(content, task_id, new_status)

        try:
            path.write_text(updated_content, encoding="utf-8")
            logger.info("Updated task %s to %s in %s", task_id, new_status.value, path)
        except OSError as e:
            logger.error("Failed to write PLAN.md: %s", e)
            record_error(e)
            raise PlanWriteError(
                f"Failed to write PLAN.md: {e}",
                file_path=str(path),
                cause=e,
            ) from e

    def add_task_to_file(
        self,
        path: Path,
        phase_id: str,
        task: Task,
    ) -> None:
        """Add a new task to a phase in a PLAN.md file.

        Args:
            path: Path to the PLAN.md file
            phase_id: The phase to add the task to (e.g., "2")
            task: The task to add

        Raises:
            PlanParseError: If the file cannot be read.
            PlanWriteError: If the file cannot be written.
        """
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.error("Failed to read PLAN.md for adding task: %s", e)
            record_error(e)
            raise PlanParseError(
                f"Failed to read PLAN.md: {e}",
                file_path=str(path),
                cause=e,
            ) from e

        updated_content = self.add_task(content, phase_id, task)

        try:
            path.write_text(updated_content, encoding="utf-8")
            logger.info("Added task '%s' to phase %s in %s", task.title, phase_id, path)
        except OSError as e:
            logger.error("Failed to write PLAN.md: %s", e)
            record_error(e)
            raise PlanWriteError(
                f"Failed to write PLAN.md: {e}",
                file_path=str(path),
                cause=e,
            ) from e

    async def update_task_status_in_file_async(
        self,
        path: Path,
        task_id: str,
        new_status: TaskStatus,
    ) -> None:
        """Update a task's status in a PLAN.md file asynchronously.

        Uses asyncio.to_thread to avoid blocking the event loop during file I/O.

        Args:
            path: Path to the PLAN.md file
            task_id: The task ID to update (e.g., "2.1")
            new_status: The new status to set

        Raises:
            PlanParseError: If the file cannot be read.
            PlanWriteError: If the file cannot be written.
        """
        try:
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
        except OSError as e:
            logger.error("Failed to read PLAN.md for update: %s", e)
            record_error(e)
            raise PlanParseError(
                f"Failed to read PLAN.md: {e}",
                file_path=str(path),
                cause=e,
            ) from e

        updated_content = self.update_task_status(content, task_id, new_status)

        try:
            await asyncio.to_thread(path.write_text, updated_content, encoding="utf-8")
            logger.info("Updated task %s to %s in %s", task_id, new_status.value, path)
        except OSError as e:
            logger.error("Failed to write PLAN.md: %s", e)
            record_error(e)
            raise PlanWriteError(
                f"Failed to write PLAN.md: {e}",
                file_path=str(path),
                cause=e,
            ) from e

    async def add_task_to_file_async(
        self,
        path: Path,
        phase_id: str,
        task: Task,
    ) -> None:
        """Add a new task to a phase in a PLAN.md file asynchronously.

        Uses asyncio.to_thread to avoid blocking the event loop during file I/O.

        Args:
            path: Path to the PLAN.md file
            phase_id: The phase to add the task to (e.g., "2")
            task: The task to add

        Raises:
            PlanParseError: If the file cannot be read.
            PlanWriteError: If the file cannot be written.
        """
        try:
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
        except OSError as e:
            logger.error("Failed to read PLAN.md for adding task: %s", e)
            record_error(e)
            raise PlanParseError(
                f"Failed to read PLAN.md: {e}",
                file_path=str(path),
                cause=e,
            ) from e

        updated_content = self.add_task(content, phase_id, task)

        try:
            await asyncio.to_thread(path.write_text, updated_content, encoding="utf-8")
            logger.info("Added task '%s' to phase %s in %s", task.title, phase_id, path)
        except OSError as e:
            logger.error("Failed to write PLAN.md: %s", e)
            record_error(e)
            raise PlanWriteError(
                f"Failed to write PLAN.md: {e}",
                file_path=str(path),
                cause=e,
            ) from e
