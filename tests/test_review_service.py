"""Tests for ReviewService."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iterm_controller.models import (
    GitConfig,
    Project,
    ReviewConfig,
    ReviewContextConfig,
    ReviewResult,
    SessionType,
    Task,
    TaskReview,
    TaskStatus,
)
from iterm_controller.review_service import (
    ParsedReviewResult,
    ReviewContext,
    ReviewContextError,
    ReviewError,
    ReviewService,
    ReviewStateManager,
    generate_id,
)


class TestGenerateId:
    """Tests for the generate_id helper."""

    def test_generates_unique_ids(self):
        """Test that generate_id produces unique IDs."""
        ids = [generate_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_generates_8_char_ids(self):
        """Test that IDs are 8 characters."""
        id1 = generate_id()
        assert len(id1) == 8


class TestReviewContext:
    """Tests for ReviewContext dataclass."""

    def test_create_minimal_context(self):
        """Test creating context with just task_id."""
        context = ReviewContext(task_id="task-1")
        assert context.task_id == "task-1"
        assert context.task_definition is None
        assert context.git_diff is None
        assert context.test_results is None
        assert context.lint_results is None
        assert context.session_log is None

    def test_create_full_context(self):
        """Test creating context with all fields."""
        context = ReviewContext(
            task_id="task-1",
            task_definition="# Task 1: Do something",
            git_diff="diff --git a/file.py",
            test_results="All tests passed",
            lint_results="No issues found",
            session_log="[Session log]",
        )
        assert context.task_id == "task-1"
        assert context.task_definition is not None
        assert context.git_diff is not None
        assert context.test_results is not None
        assert context.lint_results is not None
        assert context.session_log is not None


class TestParsedReviewResult:
    """Tests for ParsedReviewResult dataclass."""

    def test_create_minimal_result(self):
        """Test creating result with just status."""
        result = ParsedReviewResult(result=ReviewResult.APPROVED)
        assert result.result == ReviewResult.APPROVED
        assert result.issues == []
        assert result.summary == ""
        assert result.blocking is False

    def test_create_full_result(self):
        """Test creating result with all fields."""
        result = ParsedReviewResult(
            result=ReviewResult.NEEDS_REVISION,
            issues=["Missing tests", "Type errors"],
            summary="Good progress but needs work",
            blocking=False,
        )
        assert result.result == ReviewResult.NEEDS_REVISION
        assert len(result.issues) == 2
        assert "Missing tests" in result.issues
        assert result.summary == "Good progress but needs work"
        assert result.blocking is False


class TestReviewService:
    """Tests for ReviewService core functionality."""

    @pytest.fixture
    def mock_spawner(self) -> MagicMock:
        """Create a mock SessionSpawner."""
        spawner = MagicMock()
        spawner.controller = MagicMock()
        spawner.controller.app = MagicMock()
        spawner.controller.app.windows = []
        spawner.get_session = MagicMock(return_value=None)
        spawner.get_sessions_for_project = MagicMock(return_value=[])
        spawner.spawn_session = AsyncMock(
            return_value=MagicMock(success=True, session_id="session-1")
        )
        return spawner

    @pytest.fixture
    def mock_git_service(self) -> MagicMock:
        """Create a mock GitService."""
        git = MagicMock()
        git.get_diff = AsyncMock(return_value="diff --git a/file.py\n+new line")
        return git

    @pytest.fixture
    def mock_plan_manager(self) -> MagicMock:
        """Create a mock PlanStateManager."""
        manager = MagicMock()
        manager.update_task_status = MagicMock()
        return manager

    @pytest.fixture
    def mock_notifier(self) -> MagicMock:
        """Create a mock Notifier."""
        notifier = MagicMock()
        notifier.notify = AsyncMock(return_value=True)
        return notifier

    @pytest.fixture
    def service(
        self,
        mock_spawner: MagicMock,
        mock_git_service: MagicMock,
        mock_plan_manager: MagicMock,
        mock_notifier: MagicMock,
    ) -> ReviewService:
        """Create a ReviewService instance."""
        return ReviewService(
            session_spawner=mock_spawner,
            git_service=mock_git_service,
            plan_manager=mock_plan_manager,
            notifier=mock_notifier,
        )

    @pytest.fixture
    def project(self) -> Project:
        """Create a test project."""
        return Project(
            id="test-project",
            name="Test Project",
            path="/test/path",
            review_config=ReviewConfig(
                enabled=True,
                command="/review-task",
                max_revisions=3,
            ),
            git_config=GitConfig(default_branch="main"),
        )

    @pytest.fixture
    def task(self) -> Task:
        """Create a test task."""
        return Task(
            id="1.1",
            title="Implement feature X",
            status=TaskStatus.AWAITING_REVIEW,
            scope="Add the feature X to the system",
            acceptance="Feature X works correctly",
            notes=["Consider edge cases"],
        )

    def test_init(
        self,
        service: ReviewService,
        mock_spawner: MagicMock,
        mock_git_service: MagicMock,
        mock_plan_manager: MagicMock,
        mock_notifier: MagicMock,
    ):
        """Test ReviewService initialization."""
        assert service.session_spawner is mock_spawner
        assert service.git_service is mock_git_service
        assert service.plan_manager is mock_plan_manager
        assert service.notifier is mock_notifier
        assert service._active_reviews == {}

    # =========================================================================
    # Test build_review_context
    # =========================================================================

    @pytest.mark.asyncio
    async def test_build_context_default_config(
        self,
        service: ReviewService,
        project: Project,
        task: Task,
    ):
        """Test building context with default configuration."""
        context = await service.build_review_context(project, task)

        assert context.task_id == "1.1"
        assert context.task_definition is not None
        assert "# Task 1.1: Implement feature X" in context.task_definition
        assert context.git_diff is not None
        # test_results might be None in tests since no actual test command exists

    @pytest.mark.asyncio
    async def test_build_context_task_definition_only(
        self,
        service: ReviewService,
        project: Project,
        task: Task,
    ):
        """Test building context with only task definition."""
        config = ReviewContextConfig(
            include_task_definition=True,
            include_git_diff=False,
            include_test_results=False,
            include_lint_results=False,
        )
        context = await service.build_review_context(project, task, config)

        assert context.task_id == "1.1"
        assert context.task_definition is not None
        assert context.git_diff is None
        assert context.test_results is None
        assert context.lint_results is None

    @pytest.mark.asyncio
    async def test_build_context_includes_task_scope(
        self,
        service: ReviewService,
        project: Project,
        task: Task,
    ):
        """Test that context includes task scope."""
        context = await service.build_review_context(project, task)

        assert "## Scope" in context.task_definition
        assert "Add the feature X" in context.task_definition

    @pytest.mark.asyncio
    async def test_build_context_includes_acceptance_criteria(
        self,
        service: ReviewService,
        project: Project,
        task: Task,
    ):
        """Test that context includes acceptance criteria."""
        context = await service.build_review_context(project, task)

        assert "## Acceptance Criteria" in context.task_definition
        assert "Feature X works correctly" in context.task_definition

    @pytest.mark.asyncio
    async def test_build_context_includes_notes(
        self,
        service: ReviewService,
        project: Project,
        task: Task,
    ):
        """Test that context includes notes."""
        context = await service.build_review_context(project, task)

        assert "## Notes" in context.task_definition
        assert "Consider edge cases" in context.task_definition

    @pytest.mark.asyncio
    async def test_build_context_git_diff_error_handled(
        self,
        service: ReviewService,
        mock_git_service: MagicMock,
        project: Project,
        task: Task,
    ):
        """Test that git diff errors are handled gracefully."""
        mock_git_service.get_diff = AsyncMock(side_effect=Exception("Git error"))

        context = await service.build_review_context(project, task)

        assert context.git_diff is not None
        assert "[Error getting diff:" in context.git_diff

    # =========================================================================
    # Test _format_task_definition
    # =========================================================================

    def test_format_task_definition(self, service: ReviewService, task: Task):
        """Test task definition formatting."""
        formatted = service._format_task_definition(task)

        assert "# Task 1.1: Implement feature X" in formatted
        assert "## Scope" in formatted
        assert "Add the feature X" in formatted
        assert "## Acceptance Criteria" in formatted
        assert "Feature X works correctly" in formatted
        assert "## Notes" in formatted
        assert "- Consider edge cases" in formatted

    def test_format_task_definition_minimal(self, service: ReviewService):
        """Test task definition formatting with minimal task."""
        task = Task(id="2.1", title="Simple task")
        formatted = service._format_task_definition(task)

        assert "# Task 2.1: Simple task" in formatted
        assert "## Scope" not in formatted
        assert "## Acceptance" not in formatted

    # =========================================================================
    # Test _format_review_prompt
    # =========================================================================

    def test_format_review_prompt(self, service: ReviewService, task: Task):
        """Test review prompt formatting."""
        context = ReviewContext(
            task_id="1.1",
            task_definition="# Task 1.1: Do X",
            git_diff="diff --git",
            test_results="Tests passed",
        )
        prompt = service._format_review_prompt(task, context)

        assert "# Task 1.1: Do X" in prompt
        assert "## Git Diff" in prompt
        assert "```diff" in prompt
        assert "## Test Results" in prompt

    def test_format_review_prompt_minimal(self, service: ReviewService, task: Task):
        """Test review prompt formatting with minimal context."""
        context = ReviewContext(task_id="1.1")
        prompt = service._format_review_prompt(task, context)

        assert prompt == ""

    # =========================================================================
    # Test _detect_result
    # =========================================================================

    def test_detect_result_approved(self, service: ReviewService):
        """Test detecting approved result."""
        assert service._detect_result("lgtm, looks good") == ReviewResult.APPROVED
        assert service._detect_result("approved") == ReviewResult.APPROVED
        assert service._detect_result("passes the review") == ReviewResult.APPROVED
        assert service._detect_result("all good") == ReviewResult.APPROVED

    def test_detect_result_needs_revision(self, service: ReviewService):
        """Test detecting needs revision result."""
        assert (
            service._detect_result("needs revision") == ReviewResult.NEEDS_REVISION
        )
        assert (
            service._detect_result("requires changes") == ReviewResult.NEEDS_REVISION
        )
        assert (
            service._detect_result("please fix this") == ReviewResult.NEEDS_REVISION
        )

    def test_detect_result_rejected(self, service: ReviewService):
        """Test detecting rejected result."""
        assert service._detect_result("rejected") == ReviewResult.REJECTED
        assert (
            service._detect_result("blocking issue found") == ReviewResult.REJECTED
        )
        assert (
            service._detect_result("critical error in code") == ReviewResult.REJECTED
        )

    def test_detect_result_default(self, service: ReviewService):
        """Test default result when patterns don't match."""
        # Unclear output defaults to needs revision
        assert service._detect_result("some random text") == ReviewResult.NEEDS_REVISION
        assert service._detect_result("") == ReviewResult.NEEDS_REVISION

    def test_detect_result_rejection_takes_priority(self, service: ReviewService):
        """Test that rejection takes priority over approval."""
        # Even if "approved" appears, rejection patterns should win
        output = "approved the first part but rejected the security changes"
        assert service._detect_result(output) == ReviewResult.REJECTED

    # =========================================================================
    # Test _extract_issues
    # =========================================================================

    def test_extract_issues_bullets(self, service: ReviewService):
        """Test extracting issues from bullet points."""
        output = """
        Issues found:
        - Missing error handling in the main function
        * Type hints are incomplete on several functions
        • Tests don't cover edge cases properly
        """
        issues = service._extract_issues(output)

        assert len(issues) >= 3
        assert any("error handling" in i for i in issues)
        assert any("Type hints" in i for i in issues)
        assert any("edge cases" in i for i in issues)

    def test_extract_issues_numbered(self, service: ReviewService):
        """Test extracting issues from numbered list."""
        output = """
        1. Add input validation
        2. Fix the memory leak in the loop
        3) Update the documentation
        """
        issues = service._extract_issues(output)

        assert len(issues) >= 3
        assert any("input validation" in i for i in issues)
        assert any("memory leak" in i for i in issues)

    def test_extract_issues_labeled(self, service: ReviewService):
        """Test extracting issues with labels."""
        output = """
        Issue: The function doesn't handle None values
        Problem: Missing return statement in branch
        Fix: Update the conditional logic
        """
        issues = service._extract_issues(output)

        assert len(issues) >= 3
        assert any("None values" in i for i in issues)

    def test_extract_issues_skips_short_items(self, service: ReviewService):
        """Test that very short items are skipped."""
        output = """
        - Yes
        - This is a longer issue that should be captured
        - No
        """
        issues = service._extract_issues(output)

        assert "Yes" not in issues
        assert "No" not in issues
        assert len([i for i in issues if "longer issue" in i]) == 1

    def test_extract_issues_deduplicates(self, service: ReviewService):
        """Test that duplicate issues are removed."""
        output = """
        - Missing error handling
        - Missing error handling
        Issue: Missing error handling
        """
        issues = service._extract_issues(output)

        # Should have only one instance of the issue
        error_handling_count = sum(1 for i in issues if "error handling" in i.lower())
        assert error_handling_count == 1

    def test_extract_issues_limits_count(self, service: ReviewService):
        """Test that issues are limited to 10."""
        output = "\n".join(
            f"- Issue number {i} with some description" for i in range(20)
        )
        issues = service._extract_issues(output)

        assert len(issues) <= 10

    # =========================================================================
    # Test _extract_summary
    # =========================================================================

    def test_extract_summary_first_paragraph(self, service: ReviewService):
        """Test extracting summary from first paragraph."""
        output = """
        The implementation looks good overall. The code is clean and well-organized.

        ## Issues
        - Some minor issues found
        """
        summary = service._extract_summary(output)

        assert "implementation looks good" in summary
        assert "## Issues" not in summary

    def test_extract_summary_skips_headers(self, service: ReviewService):
        """Test that summary skips headers."""
        output = """
        # Code Review

        The code has several problems that need addressing.
        """
        summary = service._extract_summary(output)

        assert "Code Review" not in summary
        assert "several problems" in summary

    def test_extract_summary_skips_bullets(self, service: ReviewService):
        """Test that summary skips bullet points."""
        output = """
        - Item 1
        - Item 2
        This is the actual summary text.
        """
        summary = service._extract_summary(output)

        assert "Item 1" not in summary
        assert "actual summary" in summary

    def test_extract_summary_truncates_long_text(self, service: ReviewService):
        """Test that long summaries are truncated."""
        long_text = "A" * 400
        summary = service._extract_summary(long_text)

        assert len(summary) <= 300
        assert summary.endswith("...")

    # =========================================================================
    # Test _detect_blocking
    # =========================================================================

    def test_detect_blocking_true(self, service: ReviewService):
        """Test detecting blocking issues."""
        assert service._detect_blocking("blocking issue found") is True
        assert service._detect_blocking("security vulnerability") is True
        assert service._detect_blocking("potential data loss") is True
        assert service._detect_blocking("breaking change") is True
        assert service._detect_blocking("requires human review") is True
        assert service._detect_blocking("manual intervention needed") is True
        assert service._detect_blocking("architectural issue") is True

    def test_detect_blocking_false(self, service: ReviewService):
        """Test non-blocking issues."""
        assert service._detect_blocking("minor style issue") is False
        assert service._detect_blocking("could be improved") is False
        assert service._detect_blocking("approved with suggestions") is False

    # =========================================================================
    # Test _parse_review_output
    # =========================================================================

    @pytest.mark.asyncio
    async def test_parse_review_output_approved(
        self, service: ReviewService, task: Task
    ):
        """Test parsing approved review output."""
        output = """
        LGTM! The implementation looks great.

        All tests pass and the code follows our standards.
        """
        result = await service._parse_review_output(output, task)

        assert result.result == ReviewResult.APPROVED
        assert len(result.summary) > 0
        assert result.blocking is False

    @pytest.mark.asyncio
    async def test_parse_review_output_needs_revision(
        self, service: ReviewService, task: Task
    ):
        """Test parsing needs revision output."""
        output = """
        The implementation needs some changes.

        Issues:
        - Missing error handling for edge cases
        - Tests don't cover all scenarios

        Please fix these before we can approve.
        """
        result = await service._parse_review_output(output, task)

        assert result.result == ReviewResult.NEEDS_REVISION
        assert len(result.issues) >= 2
        assert result.blocking is False

    @pytest.mark.asyncio
    async def test_parse_review_output_rejected(
        self, service: ReviewService, task: Task
    ):
        """Test parsing rejected output."""
        output = """
        Rejected due to security vulnerability in the authentication logic.

        This is a blocking issue that requires immediate attention.
        """
        result = await service._parse_review_output(output, task)

        assert result.result == ReviewResult.REJECTED
        assert result.blocking is True

    # =========================================================================
    # Test _handle_review_result
    # =========================================================================

    @pytest.mark.asyncio
    async def test_handle_approved_result(
        self,
        service: ReviewService,
        mock_plan_manager: MagicMock,
        project: Project,
        task: Task,
    ):
        """Test handling approved review result."""
        review = TaskReview(
            id="rev-1",
            task_id=task.id,
            attempt=1,
            result=ReviewResult.APPROVED,
            issues=[],
            summary="All good",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="/review-task",
        )
        config = ReviewConfig(max_revisions=3)

        await service._handle_review_result(project, task, review, config)

        mock_plan_manager.update_task_status.assert_called_once_with(
            project.id, task.id
        )

    @pytest.mark.asyncio
    async def test_handle_needs_revision_within_limit(
        self,
        service: ReviewService,
        mock_plan_manager: MagicMock,
        mock_notifier: MagicMock,
        project: Project,
        task: Task,
    ):
        """Test handling needs revision within revision limit."""
        review = TaskReview(
            id="rev-1",
            task_id=task.id,
            attempt=1,  # First attempt, max is 3
            result=ReviewResult.NEEDS_REVISION,
            issues=["Fix this"],
            summary="Needs work",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="/review-task",
        )
        config = ReviewConfig(max_revisions=3)

        await service._handle_review_result(project, task, review, config)

        mock_plan_manager.update_task_status.assert_called()
        # Should NOT notify since within limit
        mock_notifier.notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_needs_revision_at_limit(
        self,
        service: ReviewService,
        mock_plan_manager: MagicMock,
        mock_notifier: MagicMock,
        project: Project,
        task: Task,
    ):
        """Test handling needs revision at revision limit."""
        review = TaskReview(
            id="rev-1",
            task_id=task.id,
            attempt=3,  # At max
            result=ReviewResult.NEEDS_REVISION,
            issues=["Still failing"],
            summary="Failed again",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="/review-task",
        )
        config = ReviewConfig(max_revisions=3)

        await service._handle_review_result(project, task, review, config)

        mock_plan_manager.update_task_status.assert_called()
        # Should notify since at limit
        mock_notifier.notify.assert_called_once()
        call_args = mock_notifier.notify.call_args
        assert "Failed" in call_args.kwargs.get("title", "")

    @pytest.mark.asyncio
    async def test_handle_rejected_result(
        self,
        service: ReviewService,
        mock_plan_manager: MagicMock,
        mock_notifier: MagicMock,
        project: Project,
        task: Task,
    ):
        """Test handling rejected review result."""
        review = TaskReview(
            id="rev-1",
            task_id=task.id,
            attempt=1,
            result=ReviewResult.REJECTED,
            issues=["Security issue"],
            summary="Critical security problem",
            blocking=True,
            reviewed_at=datetime.now(),
            reviewer_command="/review-task",
        )
        config = ReviewConfig(max_revisions=3)

        await service._handle_review_result(project, task, review, config)

        mock_plan_manager.update_task_status.assert_called()
        mock_notifier.notify.assert_called_once()
        call_args = mock_notifier.notify.call_args
        assert "Rejected" in call_args.kwargs.get("title", "")

    # =========================================================================
    # Test is_review_in_progress and get_active_review
    # =========================================================================

    def test_is_review_in_progress_false(self, service: ReviewService):
        """Test is_review_in_progress when no review is active."""
        assert service.is_review_in_progress("task-1") is False

    def test_is_review_in_progress_true(self, service: ReviewService):
        """Test is_review_in_progress when a review is active."""
        service._active_reviews["task-1"] = MagicMock()
        assert service.is_review_in_progress("task-1") is True

    def test_get_active_review_none(self, service: ReviewService):
        """Test get_active_review when no review is active."""
        assert service.get_active_review("task-1") is None

    def test_get_active_review_returns_review(self, service: ReviewService):
        """Test get_active_review returns the active review."""
        review = MagicMock()
        service._active_reviews["task-1"] = review
        assert service.get_active_review("task-1") is review


class TestReviewStateManager:
    """Tests for ReviewStateManager."""

    @pytest.fixture
    def manager(self) -> ReviewStateManager:
        """Create a ReviewStateManager instance."""
        return ReviewStateManager()

    def test_init(self, manager: ReviewStateManager):
        """Test ReviewStateManager initialization."""
        assert manager.active_reviews == {}
        assert manager._app is None

    def test_connect_app(self, manager: ReviewStateManager):
        """Test connecting to a Textual app."""
        app = MagicMock()
        manager.connect_app(app)
        assert manager._app is app

    @pytest.mark.asyncio
    async def test_start_review(self, manager: ReviewStateManager):
        """Test starting a new review."""
        review = await manager.start_review("task-1", "project-1")

        assert review.task_id == "task-1"
        assert review.result == ReviewResult.PENDING
        assert review.attempt == 1
        assert "task-1" in manager.active_reviews

    @pytest.mark.asyncio
    async def test_start_review_creates_pending_status(
        self, manager: ReviewStateManager
    ):
        """Test that started reviews have PENDING status."""
        review = await manager.start_review("task-1", "project-1")
        assert review.result == ReviewResult.PENDING

    @pytest.mark.asyncio
    async def test_complete_review(self, manager: ReviewStateManager):
        """Test completing a review."""
        await manager.start_review("task-1", "project-1")

        result = ParsedReviewResult(
            result=ReviewResult.APPROVED,
            issues=[],
            summary="All good",
            blocking=False,
        )
        await manager.complete_review("task-1", result)

        # Review should be removed from active
        assert "task-1" not in manager.active_reviews

    @pytest.mark.asyncio
    async def test_complete_review_no_active(self, manager: ReviewStateManager):
        """Test completing a review when none is active."""
        result = ParsedReviewResult(
            result=ReviewResult.APPROVED, issues=[], summary="", blocking=False
        )
        # Should not raise, just log warning
        await manager.complete_review("nonexistent", result)

    def test_get_active_review(self, manager: ReviewStateManager):
        """Test getting an active review."""
        review = TaskReview(
            id="rev-1",
            task_id="task-1",
            attempt=1,
            result=ReviewResult.PENDING,
            issues=[],
            summary="",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="",
        )
        manager.active_reviews["task-1"] = review

        retrieved = manager.get_active_review("task-1")
        assert retrieved is review

    def test_get_active_review_none(self, manager: ReviewStateManager):
        """Test getting an active review that doesn't exist."""
        assert manager.get_active_review("nonexistent") is None

    def test_get_all_active_reviews(self, manager: ReviewStateManager):
        """Test getting all active reviews."""
        review1 = MagicMock()
        review2 = MagicMock()
        manager.active_reviews["task-1"] = review1
        manager.active_reviews["task-2"] = review2

        all_reviews = manager.get_all_active_reviews()
        assert len(all_reviews) == 2
        assert review1 in all_reviews
        assert review2 in all_reviews

    def test_is_reviewing(self, manager: ReviewStateManager):
        """Test checking if a task is being reviewed."""
        assert manager.is_reviewing("task-1") is False

        manager.active_reviews["task-1"] = MagicMock()
        assert manager.is_reviewing("task-1") is True

    def test_clear(self, manager: ReviewStateManager):
        """Test clearing all active reviews."""
        manager.active_reviews["task-1"] = MagicMock()
        manager.active_reviews["task-2"] = MagicMock()

        manager.clear()
        assert len(manager.active_reviews) == 0


class TestReviewServiceRunReview:
    """Tests for ReviewService.run_review method."""

    @pytest.fixture
    def mock_spawner(self) -> MagicMock:
        """Create a mock SessionSpawner."""
        spawner = MagicMock()
        spawner.controller = MagicMock()
        spawner.controller.app = MagicMock()
        spawner.controller.app.windows = []
        spawner.get_session = MagicMock(return_value=None)
        spawner.get_sessions_for_project = MagicMock(return_value=[])
        spawner.spawn_session = AsyncMock(
            return_value=MagicMock(success=True, session_id="session-1")
        )
        return spawner

    @pytest.fixture
    def mock_git_service(self) -> MagicMock:
        """Create a mock GitService."""
        git = MagicMock()
        git.get_diff = AsyncMock(return_value="diff --git a/file.py\n+new line")
        return git

    @pytest.fixture
    def mock_plan_manager(self) -> MagicMock:
        """Create a mock PlanStateManager."""
        manager = MagicMock()
        manager.update_task_status = MagicMock()
        return manager

    @pytest.fixture
    def mock_notifier(self) -> MagicMock:
        """Create a mock Notifier."""
        notifier = MagicMock()
        notifier.notify = AsyncMock(return_value=True)
        return notifier

    @pytest.fixture
    def service(
        self,
        mock_spawner: MagicMock,
        mock_git_service: MagicMock,
        mock_plan_manager: MagicMock,
        mock_notifier: MagicMock,
    ) -> ReviewService:
        """Create a ReviewService instance."""
        return ReviewService(
            session_spawner=mock_spawner,
            git_service=mock_git_service,
            plan_manager=mock_plan_manager,
            notifier=mock_notifier,
        )

    @pytest.fixture
    def project(self) -> Project:
        """Create a test project."""
        return Project(
            id="test-project",
            name="Test Project",
            path="/test/path",
            review_config=ReviewConfig(
                enabled=True,
                command="/review-task",
                max_revisions=3,
            ),
            git_config=GitConfig(default_branch="main"),
        )

    @pytest.fixture
    def task(self) -> Task:
        """Create a test task."""
        return Task(
            id="1.1",
            title="Implement feature X",
            status=TaskStatus.AWAITING_REVIEW,
            scope="Add the feature X to the system",
            acceptance="Feature X works correctly",
            revision_count=0,
        )

    @pytest.fixture
    def context(self) -> ReviewContext:
        """Create a test review context."""
        return ReviewContext(
            task_id="1.1",
            task_definition="# Task 1.1: Implement feature X",
            git_diff="diff --git a/file.py\n+new line",
        )

    @pytest.mark.asyncio
    async def test_run_review_creates_pending_review(
        self,
        service: ReviewService,
        project: Project,
        task: Task,
        context: ReviewContext,
    ):
        """Test that run_review creates a pending review initially."""
        # The review should be tracked during execution
        review = await service.run_review(project, task, context)

        assert review.task_id == task.id
        assert review.attempt == 1
        assert review.reviewer_command == "/review-task"

    @pytest.mark.asyncio
    async def test_run_review_returns_parsed_result(
        self,
        service: ReviewService,
        project: Project,
        task: Task,
        context: ReviewContext,
    ):
        """Test that run_review returns a TaskReview with parsed results."""
        review = await service.run_review(project, task, context)

        assert review is not None
        assert isinstance(review.result, ReviewResult)
        assert review.reviewed_at is not None

    @pytest.mark.asyncio
    async def test_run_review_cleans_up_active_reviews(
        self,
        service: ReviewService,
        project: Project,
        task: Task,
        context: ReviewContext,
    ):
        """Test that run_review removes active review on completion."""
        await service.run_review(project, task, context)

        # Should be cleaned up after completion
        assert task.id not in service._active_reviews

    @pytest.mark.asyncio
    async def test_run_review_handles_spawn_failure(
        self,
        service: ReviewService,
        mock_spawner: MagicMock,
        project: Project,
        task: Task,
        context: ReviewContext,
    ):
        """Test that run_review handles session spawn failure."""
        mock_spawner.spawn_session = AsyncMock(
            return_value=MagicMock(success=False, error="Connection failed")
        )

        with pytest.raises(ReviewError):
            await service.run_review(project, task, context)

        # Should clean up even on failure
        assert task.id not in service._active_reviews

    @pytest.mark.asyncio
    async def test_run_review_increments_attempt(
        self,
        service: ReviewService,
        project: Project,
        context: ReviewContext,
    ):
        """Test that run_review uses correct attempt number."""
        task = Task(
            id="1.1",
            title="Implement feature X",
            status=TaskStatus.AWAITING_REVIEW,
            revision_count=2,  # Already revised twice
        )

        review = await service.run_review(project, task, context)

        assert review.attempt == 3  # revision_count + 1

    @pytest.mark.asyncio
    async def test_run_review_uses_project_config(
        self,
        service: ReviewService,
        task: Task,
        context: ReviewContext,
    ):
        """Test that run_review uses project's review config."""
        project = Project(
            id="test-project",
            name="Test Project",
            path="/test/path",
            review_config=ReviewConfig(
                enabled=True,
                command="/custom-review",
                model="claude-opus",
            ),
        )

        review = await service.run_review(project, task, context)

        assert review.reviewer_command == "/custom-review"

    @pytest.mark.asyncio
    async def test_run_review_uses_default_config_when_none(
        self,
        service: ReviewService,
        task: Task,
        context: ReviewContext,
    ):
        """Test that run_review uses default config when project has none."""
        project = Project(
            id="test-project",
            name="Test Project",
            path="/test/path",
            review_config=None,
        )

        review = await service.run_review(project, task, context)

        # Should use default command
        assert review.reviewer_command == "/review-task"


class TestReviewServiceRunTests:
    """Tests for ReviewService._run_tests method."""

    @pytest.fixture
    def mock_spawner(self) -> MagicMock:
        """Create a mock SessionSpawner."""
        spawner = MagicMock()
        spawner.controller = MagicMock()
        spawner.get_sessions_for_project = MagicMock(return_value=[])
        return spawner

    @pytest.fixture
    def mock_git_service(self) -> MagicMock:
        """Create a mock GitService."""
        return MagicMock()

    @pytest.fixture
    def mock_plan_manager(self) -> MagicMock:
        """Create a mock PlanStateManager."""
        return MagicMock()

    @pytest.fixture
    def service(
        self,
        mock_spawner: MagicMock,
        mock_git_service: MagicMock,
        mock_plan_manager: MagicMock,
    ) -> ReviewService:
        """Create a ReviewService instance."""
        return ReviewService(
            session_spawner=mock_spawner,
            git_service=mock_git_service,
            plan_manager=mock_plan_manager,
        )

    @pytest.mark.asyncio
    async def test_run_tests_no_test_files(
        self, service: ReviewService, tmp_path: Path
    ):
        """Test _run_tests returns None when no test config exists."""
        project = Project(
            id="test-project",
            name="Test Project",
            path=str(tmp_path),
        )

        result = await service._run_tests(project)

        assert result is None

    @pytest.mark.asyncio
    async def test_run_tests_detects_pytest(
        self, service: ReviewService, tmp_path: Path
    ):
        """Test _run_tests detects pytest.ini."""
        (tmp_path / "pytest.ini").write_text("[pytest]\n")
        project = Project(
            id="test-project",
            name="Test Project",
            path=str(tmp_path),
        )

        # Mock the subprocess to avoid actually running pytest
        with patch("asyncio.create_subprocess_shell") as mock_proc:
            mock_process = MagicMock()
            mock_process.communicate = AsyncMock(
                return_value=(b"Tests passed!", None)
            )
            mock_proc.return_value = mock_process

            result = await service._run_tests(project)

            assert result == "Tests passed!"
            mock_proc.assert_called()

    @pytest.mark.asyncio
    async def test_run_tests_detects_package_json(
        self, service: ReviewService, tmp_path: Path
    ):
        """Test _run_tests detects package.json for npm test."""
        (tmp_path / "package.json").write_text("{}")
        project = Project(
            id="test-project",
            name="Test Project",
            path=str(tmp_path),
        )

        with patch("asyncio.create_subprocess_shell") as mock_proc:
            mock_process = MagicMock()
            mock_process.communicate = AsyncMock(return_value=(b"npm tests ok", None))
            mock_proc.return_value = mock_process

            result = await service._run_tests(project)

            assert "npm tests ok" in result

    @pytest.mark.asyncio
    async def test_run_tests_handles_timeout(
        self, service: ReviewService, tmp_path: Path
    ):
        """Test _run_tests handles test timeout."""
        (tmp_path / "pytest.ini").write_text("[pytest]\n")
        project = Project(
            id="test-project",
            name="Test Project",
            path=str(tmp_path),
        )

        import asyncio

        with patch("asyncio.create_subprocess_shell") as mock_proc:
            mock_process = MagicMock()
            mock_process.communicate = AsyncMock(
                side_effect=asyncio.TimeoutError()
            )
            mock_proc.return_value = mock_process

            result = await service._run_tests(project)

            assert "[Test timeout" in result

    @pytest.mark.asyncio
    async def test_run_tests_handles_command_failure(
        self, service: ReviewService, tmp_path: Path
    ):
        """Test _run_tests handles command failures gracefully."""
        (tmp_path / "pytest.ini").write_text("[pytest]\n")
        project = Project(
            id="test-project",
            name="Test Project",
            path=str(tmp_path),
        )

        with patch("asyncio.create_subprocess_shell") as mock_proc:
            mock_proc.side_effect = Exception("Command not found")

            result = await service._run_tests(project)

            # Should return None when all commands fail
            assert result is None


class TestReviewServiceRunLint:
    """Tests for ReviewService._run_lint method."""

    @pytest.fixture
    def mock_spawner(self) -> MagicMock:
        """Create a mock SessionSpawner."""
        spawner = MagicMock()
        spawner.controller = MagicMock()
        spawner.get_sessions_for_project = MagicMock(return_value=[])
        return spawner

    @pytest.fixture
    def mock_git_service(self) -> MagicMock:
        """Create a mock GitService."""
        return MagicMock()

    @pytest.fixture
    def mock_plan_manager(self) -> MagicMock:
        """Create a mock PlanStateManager."""
        return MagicMock()

    @pytest.fixture
    def service(
        self,
        mock_spawner: MagicMock,
        mock_git_service: MagicMock,
        mock_plan_manager: MagicMock,
    ) -> ReviewService:
        """Create a ReviewService instance."""
        return ReviewService(
            session_spawner=mock_spawner,
            git_service=mock_git_service,
            plan_manager=mock_plan_manager,
        )

    @pytest.mark.asyncio
    async def test_run_lint_no_lint_config(
        self, service: ReviewService, tmp_path: Path
    ):
        """Test _run_lint returns None when no lint config exists."""
        project = Project(
            id="test-project",
            name="Test Project",
            path=str(tmp_path),
        )

        result = await service._run_lint(project)

        assert result is None

    @pytest.mark.asyncio
    async def test_run_lint_detects_pyproject(
        self, service: ReviewService, tmp_path: Path
    ):
        """Test _run_lint detects pyproject.toml for ruff."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        project = Project(
            id="test-project",
            name="Test Project",
            path=str(tmp_path),
        )

        with patch("asyncio.create_subprocess_shell") as mock_proc:
            mock_process = MagicMock()
            mock_process.communicate = AsyncMock(
                return_value=(b"All checks passed", None)
            )
            mock_proc.return_value = mock_process

            result = await service._run_lint(project)

            assert result == "All checks passed"

    @pytest.mark.asyncio
    async def test_run_lint_handles_timeout(
        self, service: ReviewService, tmp_path: Path
    ):
        """Test _run_lint handles lint timeout."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
        project = Project(
            id="test-project",
            name="Test Project",
            path=str(tmp_path),
        )

        import asyncio

        with patch("asyncio.create_subprocess_shell") as mock_proc:
            mock_process = MagicMock()
            mock_process.communicate = AsyncMock(
                side_effect=asyncio.TimeoutError()
            )
            mock_proc.return_value = mock_process

            result = await service._run_lint(project)

            assert "[Lint timeout" in result


class TestReviewServiceGetProjectWindow:
    """Tests for ReviewService._get_project_window method."""

    @pytest.fixture
    def mock_spawner(self) -> MagicMock:
        """Create a mock SessionSpawner."""
        spawner = MagicMock()
        spawner.controller = MagicMock()
        spawner.controller.app = MagicMock()
        spawner.controller.app.windows = []
        spawner.get_sessions_for_project = MagicMock(return_value=[])
        return spawner

    @pytest.fixture
    def mock_git_service(self) -> MagicMock:
        """Create a mock GitService."""
        return MagicMock()

    @pytest.fixture
    def mock_plan_manager(self) -> MagicMock:
        """Create a mock PlanStateManager."""
        return MagicMock()

    @pytest.fixture
    def service(
        self,
        mock_spawner: MagicMock,
        mock_git_service: MagicMock,
        mock_plan_manager: MagicMock,
    ) -> ReviewService:
        """Create a ReviewService instance."""
        return ReviewService(
            session_spawner=mock_spawner,
            git_service=mock_git_service,
            plan_manager=mock_plan_manager,
        )

    @pytest.fixture
    def project(self) -> Project:
        """Create a test project."""
        return Project(
            id="test-project",
            name="Test Project",
            path="/test/path",
        )

    @pytest.mark.asyncio
    async def test_get_project_window_no_sessions(
        self,
        service: ReviewService,
        mock_spawner: MagicMock,
        project: Project,
    ):
        """Test _get_project_window returns None when no sessions exist."""
        mock_spawner.get_sessions_for_project.return_value = []

        result = await service._get_project_window(project)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_project_window_session_without_window_id(
        self,
        service: ReviewService,
        mock_spawner: MagicMock,
        project: Project,
    ):
        """Test _get_project_window handles sessions without window_id."""
        session = MagicMock()
        session.window_id = None
        mock_spawner.get_sessions_for_project.return_value = [session]

        result = await service._get_project_window(project)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_project_window_finds_window(
        self,
        service: ReviewService,
        mock_spawner: MagicMock,
        project: Project,
    ):
        """Test _get_project_window finds matching window."""
        session = MagicMock()
        session.window_id = "window-1"

        mock_window = MagicMock()
        mock_window.window_id = "window-1"

        mock_spawner.get_sessions_for_project.return_value = [session]
        mock_spawner.controller.app.windows = [mock_window]

        result = await service._get_project_window(project)

        assert result is mock_window

    @pytest.mark.asyncio
    async def test_get_project_window_no_matching_window(
        self,
        service: ReviewService,
        mock_spawner: MagicMock,
        project: Project,
    ):
        """Test _get_project_window returns None when window not found."""
        session = MagicMock()
        session.window_id = "window-1"

        mock_window = MagicMock()
        mock_window.window_id = "window-2"  # Different ID

        mock_spawner.get_sessions_for_project.return_value = [session]
        mock_spawner.controller.app.windows = [mock_window]

        result = await service._get_project_window(project)

        assert result is None


class TestReviewServiceNotificationTriggers:
    """Tests for notification triggers in ReviewService."""

    @pytest.fixture
    def mock_spawner(self) -> MagicMock:
        """Create a mock SessionSpawner."""
        spawner = MagicMock()
        spawner.controller = MagicMock()
        spawner.controller.app = MagicMock()
        spawner.controller.app.windows = []
        spawner.get_session = MagicMock(return_value=None)
        spawner.get_sessions_for_project = MagicMock(return_value=[])
        return spawner

    @pytest.fixture
    def mock_git_service(self) -> MagicMock:
        """Create a mock GitService."""
        return MagicMock()

    @pytest.fixture
    def mock_plan_manager(self) -> MagicMock:
        """Create a mock PlanStateManager."""
        manager = MagicMock()
        manager.update_task_status = MagicMock()
        return manager

    @pytest.fixture
    def mock_notifier(self) -> MagicMock:
        """Create a mock Notifier."""
        notifier = MagicMock()
        notifier.notify = AsyncMock(return_value=True)
        return notifier

    @pytest.fixture
    def service(
        self,
        mock_spawner: MagicMock,
        mock_git_service: MagicMock,
        mock_plan_manager: MagicMock,
        mock_notifier: MagicMock,
    ) -> ReviewService:
        """Create a ReviewService instance."""
        return ReviewService(
            session_spawner=mock_spawner,
            git_service=mock_git_service,
            plan_manager=mock_plan_manager,
            notifier=mock_notifier,
        )

    @pytest.fixture
    def project(self) -> Project:
        """Create a test project."""
        return Project(
            id="test-project",
            name="Test Project",
            path="/test/path",
        )

    @pytest.fixture
    def task(self) -> Task:
        """Create a test task."""
        return Task(
            id="1.1",
            title="Implement feature X",
            status=TaskStatus.AWAITING_REVIEW,
        )

    @pytest.mark.asyncio
    async def test_no_notification_on_approval(
        self,
        service: ReviewService,
        mock_notifier: MagicMock,
        project: Project,
        task: Task,
    ):
        """Test that approval doesn't trigger notification."""
        review = TaskReview(
            id="rev-1",
            task_id=task.id,
            attempt=1,
            result=ReviewResult.APPROVED,
            issues=[],
            summary="LGTM",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="/review-task",
        )
        config = ReviewConfig(max_revisions=3)

        await service._handle_review_result(project, task, review, config)

        mock_notifier.notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_notification_on_max_revisions(
        self,
        service: ReviewService,
        mock_notifier: MagicMock,
        project: Project,
        task: Task,
    ):
        """Test notification when max revisions reached."""
        review = TaskReview(
            id="rev-1",
            task_id=task.id,
            attempt=3,
            result=ReviewResult.NEEDS_REVISION,
            issues=["Still failing"],
            summary="Failed again",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="/review-task",
        )
        config = ReviewConfig(max_revisions=3)

        await service._handle_review_result(project, task, review, config)

        mock_notifier.notify.assert_called_once()
        call_kwargs = mock_notifier.notify.call_args.kwargs
        assert "Failed" in call_kwargs["title"]
        assert "3 attempts" in call_kwargs["message"]
        assert call_kwargs["sound"] == "Basso"

    @pytest.mark.asyncio
    async def test_notification_on_rejection(
        self,
        service: ReviewService,
        mock_notifier: MagicMock,
        project: Project,
        task: Task,
    ):
        """Test notification when review is rejected."""
        review = TaskReview(
            id="rev-1",
            task_id=task.id,
            attempt=1,
            result=ReviewResult.REJECTED,
            issues=["Security vulnerability"],
            summary="Critical security flaw detected",
            blocking=True,
            reviewed_at=datetime.now(),
            reviewer_command="/review-task",
        )
        config = ReviewConfig(max_revisions=3)

        await service._handle_review_result(project, task, review, config)

        mock_notifier.notify.assert_called_once()
        call_kwargs = mock_notifier.notify.call_args.kwargs
        assert "Rejected" in call_kwargs["title"]
        assert "Blocking issue" in call_kwargs["message"]

    @pytest.mark.asyncio
    async def test_no_notification_without_notifier(
        self,
        mock_spawner: MagicMock,
        mock_git_service: MagicMock,
        mock_plan_manager: MagicMock,
        project: Project,
        task: Task,
    ):
        """Test no crash when notifier is None."""
        service = ReviewService(
            session_spawner=mock_spawner,
            git_service=mock_git_service,
            plan_manager=mock_plan_manager,
            notifier=None,
        )

        review = TaskReview(
            id="rev-1",
            task_id=task.id,
            attempt=3,
            result=ReviewResult.NEEDS_REVISION,
            issues=["Still failing"],
            summary="Failed",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="/review-task",
        )
        config = ReviewConfig(max_revisions=3)

        # Should not raise
        await service._handle_review_result(project, task, review, config)

    @pytest.mark.asyncio
    async def test_notification_truncates_long_title(
        self,
        service: ReviewService,
        mock_notifier: MagicMock,
        project: Project,
    ):
        """Test that notification title is truncated for long task titles."""
        task = Task(
            id="1.1",
            title="A" * 100,  # Very long title
            status=TaskStatus.AWAITING_REVIEW,
        )
        review = TaskReview(
            id="rev-1",
            task_id=task.id,
            attempt=1,
            result=ReviewResult.REJECTED,
            issues=[],
            summary="Rejected",
            blocking=True,
            reviewed_at=datetime.now(),
            reviewer_command="/review-task",
        )
        config = ReviewConfig(max_revisions=3)

        await service._handle_review_result(project, task, review, config)

        call_kwargs = mock_notifier.notify.call_args.kwargs
        # Title should be truncated to ~30 chars for task name
        assert len(call_kwargs["title"]) < 50

    @pytest.mark.asyncio
    async def test_notification_truncates_long_summary(
        self,
        service: ReviewService,
        mock_notifier: MagicMock,
        project: Project,
        task: Task,
    ):
        """Test that notification message truncates long summaries."""
        review = TaskReview(
            id="rev-1",
            task_id=task.id,
            attempt=1,
            result=ReviewResult.REJECTED,
            issues=[],
            summary="B" * 200,  # Very long summary
            blocking=True,
            reviewed_at=datetime.now(),
            reviewer_command="/review-task",
        )
        config = ReviewConfig(max_revisions=3)

        await service._handle_review_result(project, task, review, config)

        call_kwargs = mock_notifier.notify.call_args.kwargs
        # Message should be truncated to ~100 chars for summary
        assert len(call_kwargs["message"]) < 120


class TestReviewServiceRunReviewCommand:
    """Tests for ReviewService._run_review_command method."""

    @pytest.fixture
    def mock_spawner(self) -> MagicMock:
        """Create a mock SessionSpawner."""
        spawner = MagicMock()
        spawner.controller = MagicMock()
        spawner.controller.app = MagicMock()
        spawner.controller.app.windows = []
        spawner.get_session = MagicMock(return_value=MagicMock())
        spawner.get_sessions_for_project = MagicMock(return_value=[])
        spawner.spawn_session = AsyncMock(
            return_value=MagicMock(success=True, session_id="session-1")
        )
        return spawner

    @pytest.fixture
    def mock_git_service(self) -> MagicMock:
        """Create a mock GitService."""
        return MagicMock()

    @pytest.fixture
    def mock_plan_manager(self) -> MagicMock:
        """Create a mock PlanStateManager."""
        return MagicMock()

    @pytest.fixture
    def service(
        self,
        mock_spawner: MagicMock,
        mock_git_service: MagicMock,
        mock_plan_manager: MagicMock,
    ) -> ReviewService:
        """Create a ReviewService instance."""
        return ReviewService(
            session_spawner=mock_spawner,
            git_service=mock_git_service,
            plan_manager=mock_plan_manager,
        )

    @pytest.fixture
    def project(self) -> Project:
        """Create a test project."""
        return Project(
            id="test-project",
            name="Test Project",
            path="/test/path",
        )

    @pytest.fixture
    def task(self) -> Task:
        """Create a test task."""
        return Task(
            id="1.1",
            title="Implement feature X",
            status=TaskStatus.AWAITING_REVIEW,
        )

    @pytest.fixture
    def context(self) -> ReviewContext:
        """Create a test review context."""
        return ReviewContext(
            task_id="1.1",
            task_definition="# Task 1.1",
        )

    @pytest.mark.asyncio
    async def test_run_review_command_spawns_session(
        self,
        service: ReviewService,
        mock_spawner: MagicMock,
        project: Project,
        task: Task,
        context: ReviewContext,
    ):
        """Test that _run_review_command spawns a session."""
        await service._run_review_command(
            project=project,
            task=task,
            context=context,
            command="/review-task",
            model=None,
        )

        mock_spawner.spawn_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_review_command_uses_model_override(
        self,
        service: ReviewService,
        mock_spawner: MagicMock,
        project: Project,
        task: Task,
        context: ReviewContext,
    ):
        """Test that _run_review_command uses model override in command."""
        await service._run_review_command(
            project=project,
            task=task,
            context=context,
            command="/review-task",
            model="claude-opus",
        )

        # Check that the template includes the model flag
        call_args = mock_spawner.spawn_session.call_args
        template = call_args.kwargs.get("template") or call_args.args[0]
        assert "--model claude-opus" in template.command

    @pytest.mark.asyncio
    async def test_run_review_command_raises_on_spawn_failure(
        self,
        service: ReviewService,
        mock_spawner: MagicMock,
        project: Project,
        task: Task,
        context: ReviewContext,
    ):
        """Test that _run_review_command raises on spawn failure."""
        mock_spawner.spawn_session = AsyncMock(
            return_value=MagicMock(success=False, error="Connection refused")
        )

        from iterm_controller.review_service import ReviewCommandError

        with pytest.raises(ReviewCommandError) as exc_info:
            await service._run_review_command(
                project=project,
                task=task,
                context=context,
                command="/review-task",
                model=None,
            )

        assert "Failed to spawn review session" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_run_review_command_sets_session_type(
        self,
        service: ReviewService,
        mock_spawner: MagicMock,
        project: Project,
        task: Task,
        context: ReviewContext,
    ):
        """Test that _run_review_command sets session type to REVIEW."""
        mock_session = MagicMock()
        mock_spawner.get_session.return_value = mock_session

        await service._run_review_command(
            project=project,
            task=task,
            context=context,
            command="/review-task",
            model=None,
        )

        assert mock_session.session_type == SessionType.REVIEW
        assert mock_session.task_id == task.id

    @pytest.mark.asyncio
    async def test_run_review_command_uses_project_working_dir(
        self,
        service: ReviewService,
        mock_spawner: MagicMock,
        project: Project,
        task: Task,
        context: ReviewContext,
    ):
        """Test that _run_review_command uses project path as working dir."""
        await service._run_review_command(
            project=project,
            task=task,
            context=context,
            command="/review-task",
            model=None,
        )

        call_args = mock_spawner.spawn_session.call_args
        template = call_args.kwargs.get("template") or call_args.args[0]
        assert template.working_dir == project.path
