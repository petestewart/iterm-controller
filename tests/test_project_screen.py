"""Tests for the unified Project Screen."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iterm_controller.app import ItermControllerApp
from iterm_controller.models import (
    AttentionState,
    GitFileStatus,
    GitStatus,
    ManagedSession,
    Phase,
    Plan,
    Project,
    SessionType,
    Task,
    TaskStatus,
)
from iterm_controller.screens.project_screen import ProjectScreen
from iterm_controller.screens.modals.commit_modal import CommitModal
from iterm_controller.screens.modals.review_detail import ReviewAction, ReviewDetailModal
from iterm_controller.screens.modals.task_detail import TaskDetailModal
from iterm_controller.screens.modals.env_edit import EnvEditModal
from iterm_controller.models import ReviewResult, TaskReview
from iterm_controller.widgets import (
    DocsSection,
    EnvSection,
    GitSection,
    PlanningSection,
    ScriptToolbar,
    SessionsPanel,
    TasksSection,
)


def make_project(
    project_id: str = "project-1",
    name: str = "Test Project",
    path: str = "/tmp/test-project",
) -> Project:
    """Create a test project."""
    return Project(
        id=project_id,
        name=name,
        path=path,
    )


def make_session(
    session_id: str = "session-1",
    template_id: str = "test-template",
    project_id: str = "project-1",
    attention_state: AttentionState = AttentionState.IDLE,
    session_type: SessionType = SessionType.SHELL,
) -> ManagedSession:
    """Create a test session."""
    return ManagedSession(
        id=session_id,
        template_id=template_id,
        project_id=project_id,
        tab_id="tab-1",
        attention_state=attention_state,
        session_type=session_type,
        spawned_at=datetime.now(),
    )


def make_git_file_status(
    path: str = "test.py",
    status: str = "M",
    staged: bool = True,
) -> GitFileStatus:
    """Create a test git file status."""
    return GitFileStatus(path=path, status=status, staged=staged)


def make_git_status(
    branch: str = "main",
    ahead: int = 0,
    behind: int = 0,
    staged: list[GitFileStatus] | None = None,
    unstaged: list[GitFileStatus] | None = None,
    untracked: list[GitFileStatus] | None = None,
) -> GitStatus:
    """Create a test git status."""
    return GitStatus(
        branch=branch,
        ahead=ahead,
        behind=behind,
        staged=staged or [],
        unstaged=unstaged or [],
        untracked=untracked or [],
    )


def make_plan(phases: list[Phase] | None = None) -> Plan:
    """Create a test plan."""
    if phases is None:
        phases = [
            Phase(
                id="1",
                title="Phase 1: Setup",
                tasks=[
                    Task(id="1.1", title="Create project", status=TaskStatus.COMPLETE),
                    Task(id="1.2", title="Add models", status=TaskStatus.IN_PROGRESS),
                ],
            )
        ]
    return Plan(phases=phases)


class TestProjectScreen:
    """Tests for ProjectScreen."""

    def test_screen_has_bindings(self) -> None:
        """Test that screen has required keybindings."""
        screen = ProjectScreen(project_id="project-1")
        binding_keys = [b.key for b in screen.BINDINGS]

        # Core actions
        assert "e" in binding_keys  # Edit
        assert "c" in binding_keys  # Commit
        assert "p" in binding_keys  # Push
        assert "r" in binding_keys  # Refresh

        # Script shortcuts
        assert "s" in binding_keys  # Server
        assert "t" in binding_keys  # Tests
        assert "l" in binding_keys  # Lint
        assert "b" in binding_keys  # Build
        assert "o" in binding_keys  # Orchestrator

        # Navigation
        assert "tab" in binding_keys  # Next Section
        assert "shift+tab" in binding_keys  # Prev Section
        assert "escape" in binding_keys  # Back

        # Number shortcuts for sessions
        for num in "123456789":
            assert num in binding_keys

    def test_screen_has_css(self) -> None:
        """Test that screen has CSS styling."""
        assert ProjectScreen.DEFAULT_CSS is not None
        assert "#project-header" in ProjectScreen.DEFAULT_CSS
        assert "#content-grid" in ProjectScreen.DEFAULT_CSS
        assert "#left-column" in ProjectScreen.DEFAULT_CSS
        assert "#right-column" in ProjectScreen.DEFAULT_CSS
        assert "#bottom-section" in ProjectScreen.DEFAULT_CSS

    def test_screen_has_sections_list(self) -> None:
        """Test that screen defines navigable sections."""
        screen = ProjectScreen(project_id="project-1")
        expected_sections = [
            "planning",
            "tasks",
            "docs",
            "git",
            "env",
            "scripts",
            "sessions",
        ]
        assert screen._sections == expected_sections


@pytest.mark.asyncio
class TestProjectScreenAsync:
    """Async tests for ProjectScreen."""

    async def test_screen_composes_widgets(self) -> None:
        """Test that screen composes all required widgets."""
        app = ItermControllerApp()
        async with app.run_test():
            # Add a project to state
            project = make_project()
            app.state.projects[project.id] = project

            # Push Project screen
            await app.push_screen(ProjectScreen(project_id=project.id))

            assert isinstance(app.screen, ProjectScreen)

            # Check for all section widgets
            planning = app.screen.query_one("#planning", PlanningSection)
            assert planning is not None

            tasks = app.screen.query_one("#tasks", TasksSection)
            assert tasks is not None

            docs = app.screen.query_one("#docs", DocsSection)
            assert docs is not None

            git = app.screen.query_one("#git", GitSection)
            assert git is not None

            env = app.screen.query_one("#env", EnvSection)
            assert env is not None

            scripts = app.screen.query_one("#scripts", ScriptToolbar)
            assert scripts is not None

            sessions = app.screen.query_one("#sessions", SessionsPanel)
            assert sessions is not None

    async def test_screen_displays_project_name(self) -> None:
        """Test that screen displays project name in header."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project(name="My Test Project")
            app.state.projects[project.id] = project

            await app.push_screen(ProjectScreen(project_id=project.id))

            from textual.widgets import Static

            project_name = app.screen.query_one("#project-name", Static)
            assert "My Test Project" in str(project_name.renderable)

    async def test_screen_shows_not_found_for_missing_project(self) -> None:
        """Test that screen shows not found for missing project."""
        app = ItermControllerApp()
        async with app.run_test():
            # Don't add project to state
            await app.push_screen(ProjectScreen(project_id="nonexistent"))

            from textual.widgets import Static

            project_name = app.screen.query_one("#project-name", Static)
            assert "Not found" in str(project_name.renderable)


@pytest.mark.asyncio
class TestProjectScreenGitSection:
    """Tests for git section functionality."""

    async def test_git_status_updates_display(self) -> None:
        """Test that git status updates the display."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project

            # Mock git refresh to return a status
            # Note: branch name avoids special characters that might be interpreted as markup
            git_status = make_git_status(
                branch="feature-test",
                ahead=2,
                staged=[make_git_file_status(path="src/main.py", status="M", staged=True)],
            )
            app.state.git.refresh = AsyncMock(return_value=git_status)

            await app.push_screen(ProjectScreen(project_id=project.id))

            # Verify git section has the status
            git_section = app.screen.query_one("#git", GitSection)
            assert git_section.git_status is not None
            assert git_section.git_status.branch == "feature-test"
            assert git_section.git_status.ahead == 2

    async def test_commit_action_checks_staged(self) -> None:
        """Test that commit action checks for staged changes."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project

            # Mock git refresh with no staged files
            git_status = make_git_status()
            app.state.git.refresh = AsyncMock(return_value=git_status)

            await app.push_screen(ProjectScreen(project_id=project.id))
            screen = app.screen
            assert isinstance(screen, ProjectScreen)

            # Verify git section has no staged changes
            git_section = screen.query_one("#git", GitSection)
            assert not git_section.has_staged_changes

    async def test_push_action_checks_ahead(self) -> None:
        """Test that push action checks for commits ahead."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project

            # Mock git refresh with nothing ahead
            git_status = make_git_status(ahead=0)
            app.state.git.refresh = AsyncMock(return_value=git_status)

            await app.push_screen(ProjectScreen(project_id=project.id))
            screen = app.screen
            assert isinstance(screen, ProjectScreen)

            # Verify git section cannot push
            git_section = screen.query_one("#git", GitSection)
            assert not git_section.can_push


@pytest.mark.asyncio
class TestProjectScreenNavigation:
    """Tests for navigation functionality."""

    async def test_next_section_increments_index(self) -> None:
        """Test that action_next_section increments section index."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project
            app.state.git.refresh = AsyncMock(return_value=make_git_status())

            await app.push_screen(ProjectScreen(project_id=project.id))
            screen = app.screen
            assert isinstance(screen, ProjectScreen)

            # Initially at section 0
            assert screen._section_index == 0

            # Call action directly to avoid timing issues
            screen.action_next_section()
            assert screen._section_index == 1

            screen.action_next_section()
            assert screen._section_index == 2

    async def test_prev_section_decrements_index(self) -> None:
        """Test that action_prev_section decrements section index."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project
            app.state.git.refresh = AsyncMock(return_value=make_git_status())

            await app.push_screen(ProjectScreen(project_id=project.id))
            screen = app.screen
            assert isinstance(screen, ProjectScreen)

            # Initially at section 0
            assert screen._section_index == 0

            # Call action directly - should wrap to last
            screen.action_prev_section()
            assert screen._section_index == len(screen._sections) - 1


@pytest.mark.asyncio
class TestProjectScreenActions:
    """Tests for screen actions."""

    async def test_refresh_action_calls_git_refresh(self) -> None:
        """Test that refresh action reloads git data."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project

            refresh_count = 0

            async def mock_refresh(*args, **kwargs):
                nonlocal refresh_count
                refresh_count += 1
                return make_git_status()

            app.state.git.refresh = mock_refresh

            await app.push_screen(ProjectScreen(project_id=project.id))
            screen = app.screen
            assert isinstance(screen, ProjectScreen)

            # Initial load counts as 1
            initial_count = refresh_count

            # Call refresh action directly
            await screen.action_refresh()

            # Should have called refresh again
            assert refresh_count > initial_count

    async def test_escape_pops_screen(self) -> None:
        """Test that escape key pops the screen."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            project = make_project()
            app.state.projects[project.id] = project
            app.state.git.refresh = AsyncMock(return_value=make_git_status())

            await app.push_screen(ProjectScreen(project_id=project.id))
            assert isinstance(app.screen, ProjectScreen)

            # Press escape to go back
            await pilot.press("escape")

            # Should be back to main screen
            assert not isinstance(app.screen, ProjectScreen)

    async def test_focus_session_by_index_with_no_sessions(self) -> None:
        """Test that focus session action handles empty session list."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project
            app.state.git.refresh = AsyncMock(return_value=make_git_status())

            await app.push_screen(ProjectScreen(project_id=project.id))
            screen = app.screen
            assert isinstance(screen, ProjectScreen)

            # Call action directly - should not error
            await screen._focus_session_by_index(1)


@pytest.mark.asyncio
class TestProjectScreenEventHandlers:
    """Tests for event handlers."""

    async def test_git_status_changed_updates_display(self) -> None:
        """Test that GitStatusChanged event updates display."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project
            app.state.git.refresh = AsyncMock(return_value=make_git_status())

            await app.push_screen(ProjectScreen(project_id=project.id))
            screen = app.screen
            assert isinstance(screen, ProjectScreen)

            # Create a new git status
            new_status = make_git_status(branch="develop", ahead=5)

            # Trigger the event
            from iterm_controller.state import GitStatusChanged

            await screen.on_git_status_changed(
                GitStatusChanged(project_id=project.id, status=new_status)
            )

            # Verify git section updated
            git_section = screen.query_one("#git", GitSection)
            assert git_section.git_status is not None
            assert git_section.git_status.branch == "develop"
            assert git_section.git_status.ahead == 5

    async def test_session_spawned_adds_to_list(self) -> None:
        """Test that SessionSpawned event adds session to panel."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project
            app.state.git.refresh = AsyncMock(return_value=make_git_status())

            await app.push_screen(ProjectScreen(project_id=project.id))
            screen = app.screen
            assert isinstance(screen, ProjectScreen)

            # Initially no sessions
            assert len(screen._sessions) == 0

            # Create and trigger session spawned
            session = make_session(project_id=project.id)
            from iterm_controller.state import SessionSpawned

            await screen.on_session_spawned(SessionSpawned(session))

            # Should now have one session
            assert len(screen._sessions) == 1

    async def test_session_closed_removes_from_list(self) -> None:
        """Test that SessionClosed event removes session from panel."""
        app = ItermControllerApp()
        async with app.run_test():
            project = make_project()
            app.state.projects[project.id] = project
            app.state.git.refresh = AsyncMock(return_value=make_git_status())

            await app.push_screen(ProjectScreen(project_id=project.id))
            screen = app.screen
            assert isinstance(screen, ProjectScreen)

            # Add a session
            session = make_session(project_id=project.id)
            screen._sessions.append(session)

            # Trigger session closed
            from iterm_controller.state import SessionClosed

            await screen.on_session_closed(SessionClosed(session))

            # Should now have no sessions
            assert len(screen._sessions) == 0


class TestCommitModal:
    """Tests for CommitModal."""

    def test_modal_has_bindings(self) -> None:
        """Test that modal has required bindings."""
        modal = CommitModal()
        binding_keys = [b.key for b in modal.BINDINGS]

        assert "escape" in binding_keys
        assert "ctrl+enter" in binding_keys

    def test_modal_has_css(self) -> None:
        """Test that modal has CSS styling."""
        assert CommitModal.DEFAULT_CSS is not None
        assert ".modal-title" in CommitModal.DEFAULT_CSS
        assert "#staged-files" in CommitModal.DEFAULT_CSS
        assert "#commit-message" in CommitModal.DEFAULT_CSS


@pytest.mark.asyncio
class TestCommitModalAsync:
    """Async tests for CommitModal."""

    async def test_modal_displays_staged_files(self) -> None:
        """Test that modal displays staged files."""
        app = ItermControllerApp()
        async with app.run_test():
            staged = ["src/main.py", "src/utils.py"]
            modal = CommitModal(staged_files=staged)

            await app.push_screen(modal)

            # Check staged files container has content
            from textual.containers import Vertical

            container = app.screen.query_one("#staged-files", Vertical)
            assert container is not None

    async def test_modal_dismiss_on_cancel(self) -> None:
        """Test that cancel button dismisses modal."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            modal = CommitModal()

            result = None

            def on_dismiss(value):
                nonlocal result
                result = value

            await app.push_screen(modal, on_dismiss)

            # Press escape to cancel
            await pilot.press("escape")

            # Result should be None
            assert result is None

    async def test_modal_requires_message(self) -> None:
        """Test that commit requires a message."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            modal = CommitModal()

            await app.push_screen(modal)

            # Try to submit without a message
            from textual.widgets import Button

            commit_btn = app.screen.query_one("#commit-btn", Button)
            await pilot.click(commit_btn)

            # Should still be on the modal (not dismissed)
            assert isinstance(app.screen, CommitModal)

    async def test_modal_submits_with_message(self) -> None:
        """Test that modal submits with valid message."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            modal = CommitModal()

            result = None

            def on_dismiss(value):
                nonlocal result
                result = value

            await app.push_screen(modal, on_dismiss)

            # Type a message
            from textual.widgets import Input

            message_input = app.screen.query_one("#commit-message", Input)
            message_input.value = "Test commit message"

            # Submit with Enter
            await pilot.press("enter")

            # Result should be the message
            assert result == "Test commit message"


class TestReviewDetailModal:
    """Tests for ReviewDetailModal."""

    def test_modal_has_bindings(self) -> None:
        """Test that modal has required bindings."""
        task = Task(id="1.1", title="Test task")
        modal = ReviewDetailModal(review_task=task)
        binding_keys = [b.key for b in modal.BINDINGS]

        assert "escape" in binding_keys
        assert "a" in binding_keys  # Approve
        assert "c" in binding_keys  # Request changes
        assert "r" in binding_keys  # Reject

    def test_modal_has_css(self) -> None:
        """Test that modal has CSS styling."""
        assert ReviewDetailModal.DEFAULT_CSS is not None
        assert ".modal-title" in ReviewDetailModal.DEFAULT_CSS
        assert "#issues-container" in ReviewDetailModal.DEFAULT_CSS
        assert "#summary-container" in ReviewDetailModal.DEFAULT_CSS

    def test_modal_with_review(self) -> None:
        """Test that modal accepts task with review."""
        review = TaskReview(
            id="review-1",
            task_id="1.1",
            attempt=1,
            result=ReviewResult.NEEDS_REVISION,
            issues=["Issue 1", "Issue 2"],
            summary="Test summary",
            blocking=False,
            reviewed_at=datetime.now(),
            reviewer_command="/review",
        )
        task = Task(id="1.1", title="Test task", current_review=review)
        modal = ReviewDetailModal(review_task=task)

        assert modal.review_task == task
        assert modal.review_data == review


@pytest.mark.asyncio
class TestReviewDetailModalAsync:
    """Async tests for ReviewDetailModal."""

    async def test_modal_displays_task_info(self) -> None:
        """Test that modal displays task information."""
        app = ItermControllerApp()
        async with app.run_test():
            task = Task(id="1.1", title="Implement feature")
            modal = ReviewDetailModal(review_task=task)

            await app.push_screen(modal)

            # Check task info is displayed
            content = app.screen.query_one(".modal-title").render()
            assert "1.1" in str(content)

    async def test_modal_displays_issues(self) -> None:
        """Test that modal displays review issues."""
        app = ItermControllerApp()
        async with app.run_test():
            review = TaskReview(
                id="review-1",
                task_id="1.1",
                attempt=1,
                result=ReviewResult.NEEDS_REVISION,
                issues=["Fix typo in function name", "Add unit tests"],
                summary="Review summary",
                blocking=False,
                reviewed_at=datetime.now(),
                reviewer_command="/review",
            )
            task = Task(id="1.1", title="Test task", current_review=review)
            modal = ReviewDetailModal(review_task=task, review=review)

            await app.push_screen(modal)

            # Check issues are displayed
            issues_container = app.screen.query_one("#issues-list")
            assert issues_container is not None

    async def test_modal_approve_action(self) -> None:
        """Test that approve button returns correct action."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            task = Task(id="1.1", title="Test task")
            modal = ReviewDetailModal(review_task=task)

            result = None

            def on_dismiss(action: ReviewAction | None) -> None:
                nonlocal result
                result = action

            await app.push_screen(modal, on_dismiss)

            # Press approve button
            await pilot.press("a")

            assert result == ReviewAction.APPROVE

    async def test_modal_request_changes_action(self) -> None:
        """Test that request changes button returns correct action."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            task = Task(id="1.1", title="Test task")
            modal = ReviewDetailModal(review_task=task)

            result = None

            def on_dismiss(action: ReviewAction | None) -> None:
                nonlocal result
                result = action

            await app.push_screen(modal, on_dismiss)

            # Press request changes
            await pilot.press("c")

            assert result == ReviewAction.REQUEST_CHANGES

    async def test_modal_reject_action(self) -> None:
        """Test that reject button returns correct action."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            task = Task(id="1.1", title="Test task")
            modal = ReviewDetailModal(review_task=task)

            result = None

            def on_dismiss(action: ReviewAction | None) -> None:
                nonlocal result
                result = action

            await app.push_screen(modal, on_dismiss)

            # Press reject
            await pilot.press("r")

            assert result == ReviewAction.REJECT

    async def test_modal_close_on_escape(self) -> None:
        """Test that escape closes the modal."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            task = Task(id="1.1", title="Test task")
            modal = ReviewDetailModal(review_task=task)

            result = None

            def on_dismiss(action: ReviewAction | None) -> None:
                nonlocal result
                result = action

            await app.push_screen(modal, on_dismiss)

            # Press escape
            await pilot.press("escape")

            assert result == ReviewAction.CLOSE

    async def test_modal_displays_summary(self) -> None:
        """Test that modal displays review summary."""
        app = ItermControllerApp()
        async with app.run_test():
            review = TaskReview(
                id="review-1",
                task_id="1.1",
                attempt=1,
                result=ReviewResult.APPROVED,
                issues=[],
                summary="Task implementation looks good!",
                blocking=False,
                reviewed_at=datetime.now(),
                reviewer_command="/review",
            )
            task = Task(id="1.1", title="Test task", current_review=review)
            modal = ReviewDetailModal(review_task=task, review=review)

            await app.push_screen(modal)

            # Check summary is displayed
            summary_container = app.screen.query_one("#summary-container")
            assert summary_container is not None


class TestTaskDetailModal:
    """Tests for TaskDetailModal."""

    def test_modal_has_bindings(self) -> None:
        """Test that modal has required bindings."""
        task = Task(id="1.1", title="Test task")
        modal = TaskDetailModal(detail_task=task)
        binding_keys = [b.key for b in modal.BINDINGS]

        assert "escape" in binding_keys
        assert "enter" in binding_keys

    def test_modal_has_css(self) -> None:
        """Test that modal has CSS styling."""
        assert TaskDetailModal.DEFAULT_CSS is not None
        assert ".modal-title" in TaskDetailModal.DEFAULT_CSS
        assert ".task-title" in TaskDetailModal.DEFAULT_CSS
        assert ".task-status" in TaskDetailModal.DEFAULT_CSS

    def test_modal_stores_task(self) -> None:
        """Test that modal stores the task."""
        task = Task(
            id="1.1",
            title="Test task",
            scope="Test scope",
            acceptance="Test acceptance",
        )
        modal = TaskDetailModal(detail_task=task)

        assert modal.detail_task == task


@pytest.mark.asyncio
class TestTaskDetailModalAsync:
    """Async tests for TaskDetailModal."""

    async def test_modal_displays_task_info(self) -> None:
        """Test that modal displays task information."""
        app = ItermControllerApp()
        async with app.run_test():
            task = Task(id="2.1", title="Implement feature")
            modal = TaskDetailModal(detail_task=task)

            await app.push_screen(modal)

            # Check task info is displayed
            content = app.screen.query_one(".modal-title").render()
            assert "2.1" in str(content)

    async def test_modal_displays_status(self) -> None:
        """Test that modal displays task status."""
        app = ItermControllerApp()
        async with app.run_test():
            task = Task(id="1.1", title="Test task", status=TaskStatus.IN_PROGRESS)
            modal = TaskDetailModal(detail_task=task)

            await app.push_screen(modal)

            # Check status is displayed
            status_widget = app.screen.query_one(".task-status")
            assert status_widget is not None

    async def test_modal_displays_dependencies(self) -> None:
        """Test that modal displays dependencies."""
        app = ItermControllerApp()
        async with app.run_test():
            task = Task(id="1.1", title="Test task", depends=["1.0", "0.9"])
            modal = TaskDetailModal(detail_task=task)

            await app.push_screen(modal)

            # Check dependencies displayed
            deps_widget = app.screen.query_one(".task-deps")
            content = deps_widget.render()
            assert "1.0" in str(content) or "0.9" in str(content)

    async def test_modal_close_on_escape(self) -> None:
        """Test that escape closes the modal."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            task = Task(id="1.1", title="Test task")
            modal = TaskDetailModal(detail_task=task)

            dismissed = False

            def on_dismiss(value: None) -> None:
                nonlocal dismissed
                dismissed = True

            await app.push_screen(modal, on_dismiss)

            # Press escape
            await pilot.press("escape")

            assert dismissed is True

    async def test_modal_close_on_enter(self) -> None:
        """Test that enter closes the modal."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            task = Task(id="1.1", title="Test task")
            modal = TaskDetailModal(detail_task=task)

            dismissed = False

            def on_dismiss(value: None) -> None:
                nonlocal dismissed
                dismissed = True

            await app.push_screen(modal, on_dismiss)

            # Press enter
            await pilot.press("enter")

            assert dismissed is True

    async def test_modal_displays_scope(self) -> None:
        """Test that modal displays task scope."""
        app = ItermControllerApp()
        async with app.run_test():
            task = Task(
                id="1.1",
                title="Test task",
                scope="Implement user authentication",
            )
            modal = TaskDetailModal(detail_task=task)

            await app.push_screen(modal)

            # Check content sections exist
            content_container = app.screen.query_one("#content-sections")
            assert content_container is not None

    async def test_modal_displays_review_history(self) -> None:
        """Test that modal displays review history."""
        app = ItermControllerApp()
        async with app.run_test():
            review = TaskReview(
                id="review-1",
                task_id="1.1",
                attempt=1,
                result=ReviewResult.APPROVED,
                issues=[],
                summary="Looks good!",
                blocking=False,
                reviewed_at=datetime.now(),
                reviewer_command="/review",
            )
            task = Task(
                id="1.1",
                title="Test task",
                review_history=[review],
            )
            modal = TaskDetailModal(detail_task=task)

            await app.push_screen(modal)

            # Check review history container exists
            review_container = app.screen.query_one("#review-history")
            assert review_container is not None


class TestEnvEditModal:
    """Tests for EnvEditModal."""

    def test_modal_has_bindings(self) -> None:
        """Test that modal has required bindings."""
        modal = EnvEditModal()
        binding_keys = [b.key for b in modal.BINDINGS]

        assert "escape" in binding_keys
        assert "ctrl+s" in binding_keys

    def test_modal_has_css(self) -> None:
        """Test that modal has CSS styling."""
        assert EnvEditModal.DEFAULT_CSS is not None
        assert ".modal-title" in EnvEditModal.DEFAULT_CSS
        assert "#env-editor" in EnvEditModal.DEFAULT_CSS

    def test_modal_stores_env_vars(self) -> None:
        """Test that modal stores initial env vars."""
        env_vars = {"API_KEY": "secret", "DEBUG": "true"}
        modal = EnvEditModal(env_vars=env_vars)

        assert modal.env_vars == env_vars

    def test_is_valid_env_key(self) -> None:
        """Test environment key validation."""
        modal = EnvEditModal()

        # Valid keys
        assert modal._is_valid_env_key("API_KEY") is True
        assert modal._is_valid_env_key("DEBUG") is True
        assert modal._is_valid_env_key("_PRIVATE") is True
        assert modal._is_valid_env_key("VAR_123") is True

        # Invalid keys
        assert modal._is_valid_env_key("") is False
        assert modal._is_valid_env_key("123_VAR") is False
        assert modal._is_valid_env_key("VAR-NAME") is False
        assert modal._is_valid_env_key("VAR NAME") is False


@pytest.mark.asyncio
class TestEnvEditModalAsync:
    """Async tests for EnvEditModal."""

    async def test_modal_displays_env_vars(self) -> None:
        """Test that modal displays environment variables."""
        app = ItermControllerApp()
        async with app.run_test():
            env_vars = {"API_KEY": "secret", "DEBUG": "true"}
            modal = EnvEditModal(env_vars=env_vars)

            await app.push_screen(modal)

            # Check editor exists
            from textual.widgets import TextArea

            editor = app.screen.query_one("#env-editor", TextArea)
            assert editor is not None

    async def test_modal_cancel_returns_none(self) -> None:
        """Test that cancel returns None."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            modal = EnvEditModal(env_vars={"TEST": "value"})

            result = "not_set"

            def on_dismiss(value: dict[str, str] | None) -> None:
                nonlocal result
                result = value

            await app.push_screen(modal, on_dismiss)

            # Press escape to cancel
            await pilot.press("escape")

            assert result is None

    async def test_modal_save_with_ctrl_s(self) -> None:
        """Test that ctrl+s saves and returns the env vars."""
        app = ItermControllerApp()
        async with app.run_test() as pilot:
            modal = EnvEditModal()

            result = None

            def on_dismiss(value: dict[str, str] | None) -> None:
                nonlocal result
                result = value

            await app.push_screen(modal, on_dismiss)

            # Press ctrl+s to save
            await pilot.press("ctrl+s")

            assert result == {}
