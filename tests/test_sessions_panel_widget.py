"""Tests for the SessionsPanel and MiniSessionCard widgets.

Tests cover:
- MiniSessionCard: compact session display and rendering
- SessionsPanel: session list management and filtering by project
"""

from datetime import datetime

import pytest

from iterm_controller.models import (
    AttentionState,
    ManagedSession,
    SessionType,
)
from iterm_controller.state import (
    SessionClosed,
    SessionOutputUpdated,
    SessionSpawned,
    SessionStatusChanged,
)
from iterm_controller.widgets.sessions_panel import (
    MINI_OUTPUT_TRUNCATE,
    MINI_SESSION_NAME_WIDTH,
    MiniSessionCard,
    SessionsPanel,
)


def make_session(
    session_id: str = "session-1",
    template_id: str = "test-template",
    project_id: str = "project-1",
    attention_state: AttentionState = AttentionState.IDLE,
    session_type: SessionType = SessionType.SHELL,
    task_id: str | None = None,
    display_name: str | None = None,
    last_output: str = "",
    is_active: bool = True,
) -> ManagedSession:
    """Create a test session."""
    return ManagedSession(
        id=session_id,
        template_id=template_id,
        project_id=project_id,
        tab_id="tab-1",
        attention_state=attention_state,
        session_type=session_type,
        task_id=task_id,
        display_name=display_name,
        last_output=last_output,
        is_active=is_active,
        spawned_at=datetime.now(),
    )


class TestMiniSessionCard:
    """Tests for MiniSessionCard widget."""

    def test_init_with_session(self) -> None:
        """Test card initializes with session data."""
        session = make_session()
        card = MiniSessionCard(session, index=1)

        assert card.session == session
        assert card.index == 1

    def test_init_not_selected_by_default(self) -> None:
        """Test card is not selected by default."""
        session = make_session()
        card = MiniSessionCard(session, index=1)

        assert not card._selected
        assert not card.has_class("selected")

    def test_init_selected(self) -> None:
        """Test card can be initialized as selected."""
        session = make_session()
        card = MiniSessionCard(session, index=1, selected=True)

        assert card._selected
        assert card.has_class("selected")

    def test_get_session_info_with_display_name(self) -> None:
        """Test session info uses display_name when set."""
        session = make_session(display_name="Creating PLAN.md")
        card = MiniSessionCard(session, index=1)

        info = card._get_session_info()

        assert info == "Creating PLAN.md"

    def test_get_session_info_with_task_id(self) -> None:
        """Test session info includes task ID when linked."""
        session = make_session(
            session_type=SessionType.CLAUDE_TASK,
            task_id="2.3",
        )
        card = MiniSessionCard(session, index=1)

        info = card._get_session_info()

        assert "Claude" in info
        assert "2.3" in info

    def test_get_session_info_without_task(self) -> None:
        """Test session info uses template_id when no task linked."""
        session = make_session(template_id="dev-server", session_type=SessionType.SERVER)
        card = MiniSessionCard(session, index=1)

        info = card._get_session_info()

        assert "Server" in info
        assert "dev-server" in info

    def test_get_session_info_for_each_type(self) -> None:
        """Test session type names for all types."""
        type_names = {
            SessionType.CLAUDE_TASK: "Claude",
            SessionType.ORCHESTRATOR: "Orchestrator",
            SessionType.REVIEW: "Review",
            SessionType.TEST_RUNNER: "Tests",
            SessionType.SCRIPT: "Script",
            SessionType.SERVER: "Server",
            SessionType.SHELL: "Shell",
        }

        for session_type, expected_name in type_names.items():
            session = make_session(session_type=session_type, template_id="test")
            card = MiniSessionCard(session, index=1)

            info = card._get_session_info()

            assert expected_name in info

    def test_get_last_output_empty(self) -> None:
        """Test last output when no output exists."""
        session = make_session(last_output="")
        card = MiniSessionCard(session, index=1)

        output = card._get_last_output()

        assert output == ""

    def test_get_last_output_single_line(self) -> None:
        """Test last output with single line."""
        session = make_session(last_output="Hello, world!")
        card = MiniSessionCard(session, index=1)

        output = card._get_last_output()

        assert output == "> Hello, world!"

    def test_get_last_output_multiline(self) -> None:
        """Test last output returns last non-empty line."""
        session = make_session(last_output="Line 1\nLine 2\nLine 3")
        card = MiniSessionCard(session, index=1)

        output = card._get_last_output()

        assert output == "> Line 3"

    def test_get_last_output_skips_empty_lines(self) -> None:
        """Test last output skips empty trailing lines."""
        session = make_session(last_output="Line 1\nLine 2\n\n\n")
        card = MiniSessionCard(session, index=1)

        output = card._get_last_output()

        assert output == "> Line 2"

    def test_get_last_output_truncates_long_lines(self) -> None:
        """Test last output truncates long lines."""
        long_line = "A" * 100
        session = make_session(last_output=long_line)
        card = MiniSessionCard(session, index=1)

        output = card._get_last_output()

        assert len(output) < 100
        assert output.endswith("...")
        assert output.startswith(f"> {'A' * MINI_OUTPUT_TRUNCATE}")

    def test_render_includes_index(self) -> None:
        """Test render includes index number."""
        session = make_session()
        card = MiniSessionCard(session, index=3)

        text = card.render()

        assert "3." in str(text)

    def test_render_includes_status_icon(self) -> None:
        """Test render includes attention state icon."""
        session = make_session(attention_state=AttentionState.WAITING)
        card = MiniSessionCard(session, index=1)

        text = card.render()

        # Waiting icon is the hourglass
        assert "⧖" in str(text)

    def test_render_includes_separator(self) -> None:
        """Test render includes separator."""
        session = make_session()
        card = MiniSessionCard(session, index=1)

        text = card.render()

        assert "│" in str(text)

    def test_update_session(self) -> None:
        """Test updating session data."""
        session = make_session(attention_state=AttentionState.IDLE)
        card = MiniSessionCard(session, index=1)

        updated = make_session(attention_state=AttentionState.WORKING)
        card.update_session(updated)

        assert card.session.attention_state == AttentionState.WORKING

    def test_set_selected(self) -> None:
        """Test setting selected state."""
        session = make_session()
        card = MiniSessionCard(session, index=1, selected=False)

        assert not card._selected

        card.set_selected(True)

        assert card._selected
        assert card.has_class("selected")

        card.set_selected(False)

        assert not card._selected
        assert not card.has_class("selected")


class TestMiniSessionCardMessages:
    """Tests for MiniSessionCard message handling."""

    def test_selected_message_contains_session(self) -> None:
        """Test Selected message contains session data."""
        session = make_session()
        message = MiniSessionCard.Selected(session)

        assert message.session == session


class TestSessionsPanel:
    """Tests for SessionsPanel widget."""

    def test_init_without_project(self) -> None:
        """Test panel initializes without project ID."""
        panel = SessionsPanel()

        assert panel.project_id is None
        assert panel._sessions == []

    def test_init_with_project(self) -> None:
        """Test panel initializes with project ID."""
        panel = SessionsPanel(project_id="my-project")

        assert panel.project_id == "my-project"

    def test_init_with_sessions(self) -> None:
        """Test panel initializes with session list."""
        sessions = [make_session(), make_session(session_id="session-2")]
        panel = SessionsPanel(sessions=sessions)

        assert len(panel._sessions) == 2

    def test_set_project(self) -> None:
        """Test setting project ID."""
        panel = SessionsPanel()

        panel.set_project("new-project")

        assert panel.project_id == "new-project"
        assert panel._selected_index == 0

    def test_get_project_sessions_filters_by_project(self) -> None:
        """Test get_project_sessions filters by project ID."""
        sessions = [
            make_session(session_id="s1", project_id="project-a"),
            make_session(session_id="s2", project_id="project-b"),
            make_session(session_id="s3", project_id="project-a"),
        ]
        panel = SessionsPanel(project_id="project-a", sessions=sessions)

        project_sessions = panel.get_project_sessions()

        assert len(project_sessions) == 2
        assert all(s.project_id == "project-a" for s in project_sessions)

    def test_get_project_sessions_filters_inactive(self) -> None:
        """Test get_project_sessions filters out inactive sessions."""
        sessions = [
            make_session(session_id="s1", is_active=True),
            make_session(session_id="s2", is_active=False),
        ]
        panel = SessionsPanel(project_id="project-1", sessions=sessions)

        project_sessions = panel.get_project_sessions()

        assert len(project_sessions) == 1
        assert project_sessions[0].id == "s1"

    def test_get_project_sessions_empty_without_project(self) -> None:
        """Test get_project_sessions returns empty without project ID."""
        sessions = [make_session()]
        panel = SessionsPanel(sessions=sessions)

        project_sessions = panel.get_project_sessions()

        assert project_sessions == []

    def test_selected_session(self) -> None:
        """Test getting selected session."""
        sessions = [
            make_session(session_id="s1"),
            make_session(session_id="s2"),
        ]
        panel = SessionsPanel(project_id="project-1", sessions=sessions)
        panel._selected_index = 1

        selected = panel.selected_session

        assert selected is not None
        assert selected.id == "s2"

    def test_selected_session_none_when_empty(self) -> None:
        """Test selected_session returns None when no sessions."""
        panel = SessionsPanel(project_id="project-1")

        selected = panel.selected_session

        assert selected is None

    def test_select_by_index_valid(self) -> None:
        """Test selecting session by valid index."""
        sessions = [
            make_session(session_id="s1"),
            make_session(session_id="s2"),
            make_session(session_id="s3"),
        ]
        panel = SessionsPanel(project_id="project-1", sessions=sessions)

        result = panel.select_by_index(2)

        assert result is not None
        assert result.id == "s2"
        assert panel._selected_index == 1

    def test_select_by_index_invalid(self) -> None:
        """Test selecting session by invalid index returns None."""
        sessions = [make_session()]
        panel = SessionsPanel(project_id="project-1", sessions=sessions)

        result = panel.select_by_index(5)

        assert result is None

    def test_select_by_index_zero_invalid(self) -> None:
        """Test selecting by index 0 is invalid (1-based indexing)."""
        sessions = [make_session()]
        panel = SessionsPanel(project_id="project-1", sessions=sessions)

        result = panel.select_by_index(0)

        assert result is None

    def test_get_session_by_id_found(self) -> None:
        """Test getting session by ID when it exists."""
        sessions = [
            make_session(session_id="s1"),
            make_session(session_id="s2"),
        ]
        panel = SessionsPanel(sessions=sessions)

        result = panel.get_session_by_id("s2")

        assert result is not None
        assert result.id == "s2"

    def test_get_session_by_id_not_found(self) -> None:
        """Test getting session by ID when it doesn't exist."""
        sessions = [make_session(session_id="s1")]
        panel = SessionsPanel(sessions=sessions)

        result = panel.get_session_by_id("not-found")

        assert result is None

    def test_get_active_count(self) -> None:
        """Test getting active session count."""
        sessions = [
            make_session(session_id="s1"),
            make_session(session_id="s2"),
        ]
        panel = SessionsPanel(project_id="project-1", sessions=sessions)

        count = panel.get_active_count()

        assert count == 2


class TestSessionsPanelMessages:
    """Tests for SessionsPanel message handling."""

    def test_session_selected_message(self) -> None:
        """Test SessionSelected message contains session."""
        session = make_session()
        message = SessionsPanel.SessionSelected(session)

        assert message.session == session


class TestSessionsPanelEventHandlers:
    """Tests for SessionsPanel event handling."""

    @pytest.mark.asyncio
    async def test_on_session_spawned_adds_session(self) -> None:
        """Test spawned session is added to the panel."""
        panel = SessionsPanel(project_id="project-1")
        session = make_session(session_id="new-session", project_id="project-1")
        message = SessionSpawned(session)

        await panel.on_session_spawned(message)

        assert len(panel._sessions) == 1
        assert panel._sessions[0].id == "new-session"

    @pytest.mark.asyncio
    async def test_on_session_spawned_ignores_different_project(self) -> None:
        """Test spawned session from different project is not added."""
        panel = SessionsPanel(project_id="project-a")
        session = make_session(session_id="new-session", project_id="project-b")
        message = SessionSpawned(session)

        await panel.on_session_spawned(message)

        # Session is not added since it belongs to a different project
        assert len(panel._sessions) == 0

    @pytest.mark.asyncio
    async def test_on_session_spawned_avoids_duplicates(self) -> None:
        """Test spawned session isn't added if already exists."""
        session = make_session(session_id="s1")
        panel = SessionsPanel(project_id="project-1", sessions=[session])
        message = SessionSpawned(session)

        await panel.on_session_spawned(message)

        assert len(panel._sessions) == 1

    @pytest.mark.asyncio
    async def test_on_session_closed_removes_session(self) -> None:
        """Test closed session is removed from the panel."""
        session = make_session(session_id="s1")
        panel = SessionsPanel(project_id="project-1", sessions=[session])
        message = SessionClosed(session)

        await panel.on_session_closed(message)

        assert len(panel._sessions) == 0

    @pytest.mark.asyncio
    async def test_on_session_closed_updates_selection(self) -> None:
        """Test closed session updates selection index."""
        sessions = [
            make_session(session_id="s1"),
            make_session(session_id="s2"),
        ]
        panel = SessionsPanel(project_id="project-1", sessions=sessions)
        panel._selected_index = 1

        await panel.on_session_closed(SessionClosed(sessions[1]))

        assert panel._selected_index == 0

    @pytest.mark.asyncio
    async def test_on_session_status_changed_updates_session(self) -> None:
        """Test status change updates the session in the panel."""
        session = make_session(session_id="s1", attention_state=AttentionState.IDLE)
        panel = SessionsPanel(project_id="project-1", sessions=[session])

        updated = make_session(session_id="s1", attention_state=AttentionState.WORKING)
        message = SessionStatusChanged(updated)

        await panel.on_session_status_changed(message)

        assert panel._sessions[0].attention_state == AttentionState.WORKING

    @pytest.mark.asyncio
    async def test_on_session_output_updated_updates_output(self) -> None:
        """Test output update updates session last_output."""
        session = make_session(session_id="s1", last_output="")
        panel = SessionsPanel(project_id="project-1", sessions=[session])

        message = SessionOutputUpdated("s1", "New output line")

        await panel.on_session_output_updated(message)

        assert panel._sessions[0].last_output == "New output line"


class TestConstants:
    """Tests for module constants."""

    def test_mini_session_name_width(self) -> None:
        """Test mini session name width constant is reasonable."""
        assert MINI_SESSION_NAME_WIDTH == 30

    def test_mini_output_truncate(self) -> None:
        """Test mini output truncate constant is reasonable."""
        assert MINI_OUTPUT_TRUNCATE == 45
