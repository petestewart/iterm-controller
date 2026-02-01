"""PLAN.md parsing and updates.

Parses markdown task lists with metadata (Status, Spec, Session, Depends)
and extracts phases, tasks, statuses, and dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import Phase, Plan, Task, TaskStatus


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
        """Parse PLAN.md file from disk."""
        content = path.read_text()
        return self.parse(content)

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
