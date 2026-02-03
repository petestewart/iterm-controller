"""Tests for PLAN.md parser and updater."""

import tempfile
from pathlib import Path

import pytest

from iterm_controller.models import Phase, Plan, Task, TaskStatus
from iterm_controller.plan_parser import PlanParser, PlanUpdater


# Sample PLAN.md content for testing
SAMPLE_PLAN_MD = """# Plan: Test Project

## Overview

Build a test application for unit testing the plan parser.

**Success criteria:**
- Parser correctly extracts phases
- Parser correctly extracts tasks
- Dependencies are resolved correctly

## Tasks

### Phase 1: Foundation

- [x] **Set up project structure** `[complete]`
  - Spec: specs/setup.md
  - Scope: Create basic directory structure
  - Acceptance: All directories exist

- [x] **Create data models** `[complete]`
  - Spec: specs/models.md#data-models
  - Scope: Define dataclasses for entities
  - Acceptance: Models serialize to JSON

### Phase 2: Features

- [ ] **Implement parser** `[pending]`
  - Spec: specs/parser.md
  - Scope: Parse PLAN.md files
  - Acceptance: Extracts phases and tasks correctly

- [ ] **Add file watcher** `[in_progress]`
  - Spec: specs/watcher.md
  - Session: claude
  - Scope: Watch for file changes
  - Acceptance: Detects changes within 1 second

### Phase 3: Integration

- [ ] **Blocked task** `[blocked]`
  - Depends: 2.1, 2.2
  - Scope: Can only start after phase 2 complete
  - Acceptance: Works correctly

- [ ] **Another blocked task** `[pending]`
  - Depends: 3.1
  - Scope: Depends on first blocked task
"""

MINIMAL_PLAN_MD = """# Plan: Minimal

### Phase 1: Only Phase

- [ ] **Only task** `[pending]`
  - Scope: Single task
"""


class TestPlanParser:
    """Test PlanParser class."""

    def test_parse_empty_plan(self):
        parser = PlanParser()
        plan = parser.parse("")
        assert plan.phases == []
        assert plan.overview == ""
        assert plan.success_criteria == []

    def test_parse_overview(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        assert "Build a test application" in plan.overview
        assert "unit testing the plan parser" in plan.overview

    def test_parse_success_criteria(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        assert len(plan.success_criteria) == 3
        assert "Parser correctly extracts phases" in plan.success_criteria
        assert "Dependencies are resolved correctly" in plan.success_criteria

    def test_parse_phases(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        assert len(plan.phases) == 3
        assert plan.phases[0].id == "1"
        assert plan.phases[0].title == "Foundation"
        assert plan.phases[1].id == "2"
        assert plan.phases[1].title == "Features"
        assert plan.phases[2].id == "3"
        assert plan.phases[2].title == "Integration"

    def test_parse_tasks_per_phase(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        assert len(plan.phases[0].tasks) == 2  # Phase 1 has 2 tasks
        assert len(plan.phases[1].tasks) == 2  # Phase 2 has 2 tasks
        assert len(plan.phases[2].tasks) == 2  # Phase 3 has 2 tasks

    def test_parse_task_ids(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        # Phase 1 tasks
        assert plan.phases[0].tasks[0].id == "1.1"
        assert plan.phases[0].tasks[1].id == "1.2"
        # Phase 2 tasks
        assert plan.phases[1].tasks[0].id == "2.1"
        assert plan.phases[1].tasks[1].id == "2.2"

    def test_parse_task_titles(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        assert plan.phases[0].tasks[0].title == "Set up project structure"
        assert plan.phases[0].tasks[1].title == "Create data models"
        assert plan.phases[1].tasks[0].title == "Implement parser"

    def test_parse_task_statuses(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        # Complete tasks
        assert plan.phases[0].tasks[0].status == TaskStatus.COMPLETE
        assert plan.phases[0].tasks[1].status == TaskStatus.COMPLETE
        # Pending tasks
        assert plan.phases[1].tasks[0].status == TaskStatus.PENDING
        # In progress tasks
        assert plan.phases[1].tasks[1].status == TaskStatus.IN_PROGRESS

    def test_parse_spec_refs(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        assert plan.phases[0].tasks[0].spec_ref == "specs/setup.md"
        assert plan.phases[0].tasks[1].spec_ref == "specs/models.md#data-models"
        assert plan.phases[1].tasks[0].spec_ref == "specs/parser.md"

    def test_parse_scope(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        assert plan.phases[0].tasks[0].scope == "Create basic directory structure"
        assert plan.phases[1].tasks[0].scope == "Parse PLAN.md files"

    def test_parse_acceptance(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        assert plan.phases[0].tasks[0].acceptance == "All directories exist"
        assert plan.phases[0].tasks[1].acceptance == "Models serialize to JSON"

    def test_parse_session_id(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        # Task 2.2 has a Session field
        assert plan.phases[1].tasks[1].session_id == "claude"
        # Other tasks should have no session
        assert plan.phases[0].tasks[0].session_id is None

    def test_parse_dependencies(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        # Task 3.1 depends on 2.1 and 2.2
        assert plan.phases[2].tasks[0].depends == ["2.1", "2.2"]
        # Task 3.2 depends on 3.1
        assert plan.phases[2].tasks[1].depends == ["3.1"]
        # Other tasks have no dependencies
        assert plan.phases[0].tasks[0].depends == []

    def test_resolve_blocked_status(self):
        """Test that tasks with incomplete dependencies are marked blocked."""
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        # Task 3.1 should be blocked because 2.1 and 2.2 are not complete
        assert plan.phases[2].tasks[0].status == TaskStatus.BLOCKED
        # Task 3.2 should also be blocked because 3.1 is blocked
        assert plan.phases[2].tasks[1].status == TaskStatus.BLOCKED

    def test_all_tasks_property(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        all_tasks = plan.all_tasks
        assert len(all_tasks) == 6
        task_ids = [t.id for t in all_tasks]
        assert task_ids == ["1.1", "1.2", "2.1", "2.2", "3.1", "3.2"]

    def test_parse_minimal_plan(self):
        parser = PlanParser()
        plan = parser.parse(MINIMAL_PLAN_MD)
        assert len(plan.phases) == 1
        assert plan.phases[0].id == "1"
        assert plan.phases[0].title == "Only Phase"
        assert len(plan.phases[0].tasks) == 1
        assert plan.phases[0].tasks[0].title == "Only task"


class TestPlanParserFile:
    """Test parsing from files."""

    def test_parse_file(self):
        parser = PlanParser()
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)
            plan = parser.parse_file(plan_path)
            assert len(plan.phases) == 3
            assert plan.phases[0].tasks[0].title == "Set up project structure"

    @pytest.mark.asyncio
    async def test_parse_file_async(self):
        """Test async file parsing."""
        parser = PlanParser()
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(SAMPLE_PLAN_MD)
            plan = await parser.parse_file_async(plan_path)
            assert len(plan.phases) == 3
            assert plan.phases[0].tasks[0].title == "Set up project structure"

    @pytest.mark.asyncio
    async def test_parse_file_async_not_found(self):
        """Test async file parsing with missing file."""
        from iterm_controller.exceptions import PlanParseError

        parser = PlanParser()
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            # Don't create the file
            with pytest.raises(PlanParseError, match="Failed to read"):
                await parser.parse_file_async(plan_path)


class TestParseStatus:
    """Test status parsing edge cases."""

    def test_parse_all_statuses(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Pending** `[pending]`
- [ ] **In Progress** `[in_progress]`
- [ ] **Awaiting Review** `[awaiting_review]`
- [x] **Complete** `[complete]`
- [ ] **Skipped** `[skipped]`
- [ ] **Blocked** `[blocked]`
"""
        parser = PlanParser()
        plan = parser.parse(plan_md)
        tasks = plan.phases[0].tasks
        assert tasks[0].status == TaskStatus.PENDING
        assert tasks[1].status == TaskStatus.IN_PROGRESS
        assert tasks[2].status == TaskStatus.AWAITING_REVIEW
        assert tasks[3].status == TaskStatus.COMPLETE
        assert tasks[4].status == TaskStatus.SKIPPED
        assert tasks[5].status == TaskStatus.BLOCKED

    def test_parse_unknown_status_defaults_to_pending(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Unknown status** `[unknown_status]`
"""
        parser = PlanParser()
        plan = parser.parse(plan_md)
        assert plan.phases[0].tasks[0].status == TaskStatus.PENDING


class TestDependencyResolution:
    """Test dependency resolution logic."""

    def test_no_blocking_when_all_deps_complete(self):
        plan_md = """# Plan

### Phase 1: Foundation

- [x] **Task A** `[complete]`
- [x] **Task B** `[complete]`

### Phase 2: Features

- [ ] **Dependent Task** `[pending]`
  - Depends: 1.1, 1.2
"""
        parser = PlanParser()
        plan = parser.parse(plan_md)
        # Task should remain pending since all deps are complete
        assert plan.phases[1].tasks[0].status == TaskStatus.PENDING

    def test_blocking_when_one_dep_incomplete(self):
        plan_md = """# Plan

### Phase 1: Foundation

- [x] **Task A** `[complete]`
- [ ] **Task B** `[pending]`

### Phase 2: Features

- [ ] **Dependent Task** `[pending]`
  - Depends: 1.1, 1.2
"""
        parser = PlanParser()
        plan = parser.parse(plan_md)
        # Task should be blocked since 1.2 is not complete
        assert plan.phases[1].tasks[0].status == TaskStatus.BLOCKED

    def test_skipped_deps_dont_block(self):
        plan_md = """# Plan

### Phase 1: Foundation

- [x] **Task A** `[complete]`
- [ ] **Task B** `[skipped]`

### Phase 2: Features

- [ ] **Dependent Task** `[pending]`
  - Depends: 1.1, 1.2
"""
        parser = PlanParser()
        plan = parser.parse(plan_md)
        # Task should remain pending since skipped counts as done
        assert plan.phases[1].tasks[0].status == TaskStatus.PENDING

    def test_nonexistent_dep_does_not_block(self):
        plan_md = """# Plan

### Phase 1: Foundation

- [ ] **Task with missing dep** `[pending]`
  - Depends: 99.99
"""
        parser = PlanParser()
        plan = parser.parse(plan_md)
        # Task should remain pending since the dep doesn't exist
        assert plan.phases[0].tasks[0].status == TaskStatus.PENDING


class TestMetadataParsing:
    """Test metadata parsing edge cases."""

    def test_multiple_metadata_fields(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Task with many fields** `[pending]`
  - Spec: specs/test.md
  - Session: my-session
  - Scope: Do the thing
  - Acceptance: It works
  - Depends: 1.0
  - Notes: Some notes here
"""
        parser = PlanParser()
        plan = parser.parse(plan_md)
        task = plan.phases[0].tasks[0]
        assert task.spec_ref == "specs/test.md"
        assert task.session_id == "my-session"
        assert task.scope == "Do the thing"
        assert task.acceptance == "It works"
        assert task.depends == ["1.0"]

    def test_no_metadata(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Task without metadata** `[pending]`
"""
        parser = PlanParser()
        plan = parser.parse(plan_md)
        task = plan.phases[0].tasks[0]
        assert task.spec_ref is None
        assert task.session_id is None
        assert task.scope == ""
        assert task.acceptance == ""
        assert task.depends == []


class TestPlanProperties:
    """Test Plan computed properties work correctly after parsing."""

    def test_overall_progress(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        # 2 complete out of 6 tasks (3.1 and 3.2 are blocked, not complete)
        # But we have 2 complete, 1 pending, 1 in_progress, 2 blocked
        # Complete only: 2/6 = 33.33%
        assert plan.overall_progress == pytest.approx(33.33, rel=0.1)

    def test_completion_summary(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        summary = plan.completion_summary
        assert summary["complete"] == 2
        assert summary["pending"] == 1
        assert summary["in_progress"] == 1
        assert summary["blocked"] == 2

    def test_phase_completion(self):
        parser = PlanParser()
        plan = parser.parse(SAMPLE_PLAN_MD)
        # Phase 1 has 2/2 complete
        assert plan.phases[0].completion_count == (2, 2)
        assert plan.phases[0].completion_percent == 100.0
        # Phase 2 has 0/2 complete
        assert plan.phases[1].completion_count == (0, 2)
        assert plan.phases[1].completion_percent == 0.0


# =============================================================================
# PlanUpdater Tests
# =============================================================================


class TestPlanUpdaterTaskStatus:
    """Test PlanUpdater.update_task_status method."""

    def test_update_pending_to_complete(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Task A** `[pending]`
  - Scope: Do A

- [ ] **Task B** `[pending]`
  - Scope: Do B
"""
        updater = PlanUpdater()
        result = updater.update_task_status(plan_md, "1.1", TaskStatus.COMPLETE)

        assert "- [x] **Task A** `[complete]`" in result
        # Task B should be unchanged
        assert "- [ ] **Task B** `[pending]`" in result

    def test_update_complete_to_pending(self):
        plan_md = """# Plan

### Phase 1: Test

- [x] **Task A** `[complete]`
  - Scope: Do A
"""
        updater = PlanUpdater()
        result = updater.update_task_status(plan_md, "1.1", TaskStatus.PENDING)

        assert "- [ ] **Task A** `[pending]`" in result

    def test_update_to_in_progress(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Task A** `[pending]`
  - Scope: Do A
"""
        updater = PlanUpdater()
        result = updater.update_task_status(plan_md, "1.1", TaskStatus.IN_PROGRESS)

        assert "- [ ] **Task A** `[in_progress]`" in result

    def test_update_specific_task_in_phase(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Task A** `[pending]`
- [ ] **Task B** `[pending]`
- [ ] **Task C** `[pending]`
"""
        updater = PlanUpdater()
        result = updater.update_task_status(plan_md, "1.2", TaskStatus.COMPLETE)

        assert "- [ ] **Task A** `[pending]`" in result
        assert "- [x] **Task B** `[complete]`" in result
        assert "- [ ] **Task C** `[pending]`" in result

    def test_update_task_in_second_phase(self):
        plan_md = """# Plan

### Phase 1: Foundation

- [x] **Task 1A** `[complete]`

### Phase 2: Features

- [ ] **Task 2A** `[pending]`
- [ ] **Task 2B** `[pending]`
"""
        updater = PlanUpdater()
        result = updater.update_task_status(plan_md, "2.1", TaskStatus.IN_PROGRESS)

        # Phase 1 task unchanged
        assert "- [x] **Task 1A** `[complete]`" in result
        # Phase 2 first task updated
        assert "- [ ] **Task 2A** `[in_progress]`" in result
        # Phase 2 second task unchanged
        assert "- [ ] **Task 2B** `[pending]`" in result

    def test_update_preserves_metadata(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Task A** `[pending]`
  - Spec: specs/test.md
  - Scope: Do something
  - Acceptance: It works
"""
        updater = PlanUpdater()
        result = updater.update_task_status(plan_md, "1.1", TaskStatus.COMPLETE)

        assert "- [x] **Task A** `[complete]`" in result
        assert "  - Spec: specs/test.md" in result
        assert "  - Scope: Do something" in result
        assert "  - Acceptance: It works" in result

    def test_update_nonexistent_phase_raises(self):
        from iterm_controller.exceptions import PlanWriteError

        plan_md = """# Plan

### Phase 1: Test

- [ ] **Task A** `[pending]`
"""
        updater = PlanUpdater()
        with pytest.raises(PlanWriteError, match="Phase 99 not found"):
            updater.update_task_status(plan_md, "99.1", TaskStatus.COMPLETE)

    def test_update_to_skipped(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Task A** `[pending]`
"""
        updater = PlanUpdater()
        result = updater.update_task_status(plan_md, "1.1", TaskStatus.SKIPPED)

        assert "- [ ] **Task A** `[skipped]`" in result

    def test_update_to_blocked(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Task A** `[pending]`
"""
        updater = PlanUpdater()
        result = updater.update_task_status(plan_md, "1.1", TaskStatus.BLOCKED)

        assert "- [ ] **Task A** `[blocked]`" in result

    def test_update_to_awaiting_review(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Task A** `[pending]`
"""
        updater = PlanUpdater()
        result = updater.update_task_status(plan_md, "1.1", TaskStatus.AWAITING_REVIEW)

        assert "- [ ] **Task A** `[awaiting_review]`" in result


class TestPlanUpdaterAddTask:
    """Test PlanUpdater.add_task method."""

    def test_add_simple_task(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Existing Task** `[pending]`
"""
        task = Task(id="1.2", title="New Task", status=TaskStatus.PENDING)

        updater = PlanUpdater()
        result = updater.add_task(plan_md, "1", task)

        assert "- [ ] **Existing Task** `[pending]`" in result
        assert "- [ ] **New Task** `[pending]`" in result

    def test_add_task_with_metadata(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Existing Task** `[pending]`
"""
        task = Task(
            id="1.2",
            title="New Task",
            status=TaskStatus.PENDING,
            spec_ref="specs/new.md",
            scope="Do new things",
            acceptance="New things done",
        )

        updater = PlanUpdater()
        result = updater.add_task(plan_md, "1", task)

        assert "- [ ] **New Task** `[pending]`" in result
        assert "  - Spec: specs/new.md" in result
        assert "  - Scope: Do new things" in result
        assert "  - Acceptance: New things done" in result

    def test_add_task_with_dependencies(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Existing Task** `[pending]`
"""
        task = Task(
            id="1.2",
            title="Dependent Task",
            status=TaskStatus.PENDING,
            depends=["1.1", "1.0"],
        )

        updater = PlanUpdater()
        result = updater.add_task(plan_md, "1", task)

        assert "- [ ] **Dependent Task** `[pending]`" in result
        assert "  - Depends: 1.1, 1.0" in result

    def test_add_task_with_session(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Existing Task** `[pending]`
"""
        task = Task(
            id="1.2",
            title="Session Task",
            status=TaskStatus.IN_PROGRESS,
            session_id="claude",
        )

        updater = PlanUpdater()
        result = updater.add_task(plan_md, "1", task)

        assert "- [ ] **Session Task** `[in_progress]`" in result
        assert "  - Session: claude" in result

    def test_add_complete_task(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Existing Task** `[pending]`
"""
        task = Task(id="1.2", title="Done Task", status=TaskStatus.COMPLETE)

        updater = PlanUpdater()
        result = updater.add_task(plan_md, "1", task)

        assert "- [x] **Done Task** `[complete]`" in result

    def test_add_task_to_second_phase(self):
        plan_md = """# Plan

### Phase 1: Foundation

- [x] **Phase 1 Task** `[complete]`

### Phase 2: Features

- [ ] **Phase 2 Task** `[pending]`
"""
        task = Task(id="2.2", title="New Feature Task", status=TaskStatus.PENDING)

        updater = PlanUpdater()
        result = updater.add_task(plan_md, "2", task)

        # Phase 1 unchanged
        assert "- [x] **Phase 1 Task** `[complete]`" in result
        # Phase 2 has both tasks
        assert "- [ ] **Phase 2 Task** `[pending]`" in result
        assert "- [ ] **New Feature Task** `[pending]`" in result

    def test_add_task_nonexistent_phase_raises(self):
        from iterm_controller.exceptions import PlanWriteError

        plan_md = """# Plan

### Phase 1: Test

- [ ] **Task** `[pending]`
"""
        task = Task(id="99.1", title="New Task", status=TaskStatus.PENDING)

        updater = PlanUpdater()
        with pytest.raises(PlanWriteError, match="Phase 99 not found"):
            updater.add_task(plan_md, "99", task)


class TestPlanUpdaterFileOperations:
    """Test PlanUpdater file operations."""

    def test_update_task_status_in_file(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Task A** `[pending]`
"""
        updater = PlanUpdater()

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(plan_md)

            updater.update_task_status_in_file(plan_path, "1.1", TaskStatus.COMPLETE)

            result = plan_path.read_text()
            assert "- [x] **Task A** `[complete]`" in result

    def test_add_task_to_file(self):
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Task A** `[pending]`
"""
        task = Task(id="1.2", title="Task B", status=TaskStatus.PENDING)
        updater = PlanUpdater()

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(plan_md)

            updater.add_task_to_file(plan_path, "1", task)

            result = plan_path.read_text()
            assert "- [ ] **Task A** `[pending]`" in result
            assert "- [ ] **Task B** `[pending]`" in result

    @pytest.mark.asyncio
    async def test_update_task_status_in_file_async(self):
        """Test async file update."""
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Task A** `[pending]`
"""
        updater = PlanUpdater()

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(plan_md)

            await updater.update_task_status_in_file_async(plan_path, "1.1", TaskStatus.COMPLETE)

            result = plan_path.read_text()
            assert "- [x] **Task A** `[complete]`" in result

    @pytest.mark.asyncio
    async def test_add_task_to_file_async(self):
        """Test async file task addition."""
        plan_md = """# Plan

### Phase 1: Test

- [ ] **Task A** `[pending]`
"""
        task = Task(id="1.2", title="Task B", status=TaskStatus.PENDING)
        updater = PlanUpdater()

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            plan_path.write_text(plan_md)

            await updater.add_task_to_file_async(plan_path, "1", task)

            result = plan_path.read_text()
            assert "- [ ] **Task A** `[pending]`" in result
            assert "- [ ] **Task B** `[pending]`" in result

    @pytest.mark.asyncio
    async def test_update_task_status_in_file_async_not_found(self):
        """Test async file update with missing file."""
        from iterm_controller.exceptions import PlanParseError

        updater = PlanUpdater()

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            # Don't create the file
            with pytest.raises(PlanParseError, match="Failed to read"):
                await updater.update_task_status_in_file_async(plan_path, "1.1", TaskStatus.COMPLETE)

    @pytest.mark.asyncio
    async def test_add_task_to_file_async_not_found(self):
        """Test async file task addition with missing file."""
        from iterm_controller.exceptions import PlanParseError

        task = Task(id="1.2", title="Task B", status=TaskStatus.PENDING)
        updater = PlanUpdater()

        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "PLAN.md"
            # Don't create the file
            with pytest.raises(PlanParseError, match="Failed to read"):
                await updater.add_task_to_file_async(plan_path, "1", task)


class TestPlanUpdaterRoundTrip:
    """Test that updates can be parsed back correctly."""

    def test_update_and_parse_roundtrip(self):
        plan_md = """# Plan

## Overview

Test plan for roundtrip testing.

### Phase 1: Test

- [ ] **Task A** `[pending]`
  - Scope: Do A

- [ ] **Task B** `[pending]`
  - Scope: Do B
"""
        updater = PlanUpdater()
        parser = PlanParser()

        # Update task 1.1 to complete
        updated = updater.update_task_status(plan_md, "1.1", TaskStatus.COMPLETE)

        # Parse the result
        plan = parser.parse(updated)

        # Verify the update was parsed correctly
        assert plan.phases[0].tasks[0].status == TaskStatus.COMPLETE
        assert plan.phases[0].tasks[1].status == TaskStatus.PENDING

    def test_add_and_parse_roundtrip(self):
        plan_md = """# Plan

## Overview

Test plan for roundtrip testing.

### Phase 1: Test

- [ ] **Task A** `[pending]`
  - Scope: Do A
"""
        task = Task(
            id="1.2",
            title="Task B",
            status=TaskStatus.IN_PROGRESS,
            spec_ref="specs/b.md",
            scope="Do B",
            acceptance="B works",
        )

        updater = PlanUpdater()
        parser = PlanParser()

        # Add the task
        updated = updater.add_task(plan_md, "1", task)

        # Parse the result
        plan = parser.parse(updated)

        # Verify both tasks exist with correct data
        assert len(plan.phases[0].tasks) == 2
        assert plan.phases[0].tasks[0].title == "Task A"
        assert plan.phases[0].tasks[0].status == TaskStatus.PENDING
        assert plan.phases[0].tasks[1].title == "Task B"
        assert plan.phases[0].tasks[1].status == TaskStatus.IN_PROGRESS
        assert plan.phases[0].tasks[1].spec_ref == "specs/b.md"
        assert plan.phases[0].tasks[1].scope == "Do B"
        assert plan.phases[0].tasks[1].acceptance == "B works"
