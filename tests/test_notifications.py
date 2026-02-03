"""Tests for macOS notification functionality."""

import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from iterm_controller.models import AttentionState, ManagedSession, NotificationSettings, Project
from iterm_controller.notifications import (
    NotificationLatencyTracker,
    NotificationManager,
    Notifier,
    SessionMonitorWithNotifications,
)
from iterm_controller.state import AppState


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_session():
    """Create a mock ManagedSession for testing."""
    return ManagedSession(
        id="session-123",
        template_id="claude",
        project_id="project-1",
        tab_id="tab-1",
        attention_state=AttentionState.IDLE,
    )


@pytest.fixture
def mock_project():
    """Create a mock Project for testing."""
    return Project(
        id="project-1",
        name="Test Project",
        path="/path/to/project",
    )


@pytest.fixture
def app_state(mock_project):
    """Create an AppState with a project."""
    state = AppState()
    state.projects[mock_project.id] = mock_project
    return state


# =============================================================================
# Notifier Tests
# =============================================================================


class TestNotifier:
    """Test Notifier functionality."""

    @pytest.mark.asyncio
    async def test_init_defaults(self):
        """Notifier initializes with correct defaults."""
        notifier = Notifier()
        assert notifier.available is False
        assert notifier.enabled is True
        assert notifier.error_message is None

    @pytest.mark.asyncio
    async def test_initialize_when_available(self):
        """Initialize sets available when terminal-notifier is found."""
        notifier = Notifier()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"/usr/local/bin/terminal-notifier\n", b""))
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            result = await notifier.initialize()

            assert result is True
            assert notifier.available is True
            assert notifier.error_message is None

    @pytest.mark.asyncio
    async def test_initialize_when_not_available(self):
        """Initialize sets available=False when terminal-notifier is not found."""
        notifier = Notifier()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 1
            mock_exec.return_value = mock_proc

            result = await notifier.initialize()

            assert result is False
            assert notifier.available is False
            assert notifier.error_message == "terminal-notifier not found"

    @pytest.mark.asyncio
    async def test_notify_when_not_available(self):
        """notify returns False when terminal-notifier is not available."""
        notifier = Notifier(available=False)

        result = await notifier.notify("Title", "Message")

        assert result is False

    @pytest.mark.asyncio
    async def test_notify_when_disabled(self):
        """notify returns False when notifications are disabled."""
        notifier = Notifier(available=True, enabled=False)

        result = await notifier.notify("Title", "Message")

        assert result is False

    @pytest.mark.asyncio
    async def test_notify_success(self):
        """notify sends notification successfully."""
        notifier = Notifier(available=True)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.wait = AsyncMock()
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            result = await notifier.notify("Title", "Message", subtitle="Sub")

            assert result is True
            mock_exec.assert_called_once()
            args = mock_exec.call_args[0]
            assert "terminal-notifier" in args
            assert "-title" in args
            assert "Title" in args
            assert "-message" in args
            assert "Message" in args
            assert "-subtitle" in args
            assert "Sub" in args

    @pytest.mark.asyncio
    async def test_notify_with_sound(self):
        """notify includes sound parameter."""
        notifier = Notifier(available=True)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.wait = AsyncMock()
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            await notifier.notify("Title", "Message", sound="Ping")

            args = mock_exec.call_args[0]
            assert "-sound" in args
            assert "Ping" in args

    @pytest.mark.asyncio
    async def test_notify_no_sound(self):
        """notify skips sound parameter when None."""
        notifier = Notifier(available=True)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.wait = AsyncMock()
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            await notifier.notify("Title", "Message", sound=None)

            args = mock_exec.call_args[0]
            assert "-sound" not in args

    @pytest.mark.asyncio
    async def test_notify_session_waiting(self, mock_session, mock_project):
        """notify_session_waiting sends correct notification."""
        notifier = Notifier(available=True)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.wait = AsyncMock()
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            result = await notifier.notify_session_waiting(mock_session, mock_project)

            assert result is True
            args = mock_exec.call_args[0]
            assert mock_project.name in args
            assert mock_session.template_id in args
            assert f"session-{mock_session.id}" in args

    @pytest.mark.asyncio
    async def test_clear_session_notification(self, mock_session):
        """clear_session_notification sends remove command."""
        notifier = Notifier(available=True)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.wait = AsyncMock()
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            result = await notifier.clear_session_notification(mock_session)

            assert result is True
            args = mock_exec.call_args[0]
            assert "-remove" in args
            assert f"session-{mock_session.id}" in args

    @pytest.mark.asyncio
    async def test_notify_with_sound(self):
        """notify_with_sound sends notification with explicit sound."""
        notifier = Notifier(available=True)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.wait = AsyncMock()
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            result = await notifier.notify_with_sound(
                "Title",
                "Message",
                sound="Glass",
                subtitle="Subtitle"
            )

            assert result is True
            args = mock_exec.call_args[0]
            assert "-sound" in args
            assert "Glass" in args
            assert "-subtitle" in args
            assert "Subtitle" in args

    @pytest.mark.asyncio
    async def test_notify_with_sound_default(self):
        """notify_with_sound uses default sound when not specified."""
        notifier = Notifier(available=True)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.wait = AsyncMock()
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            result = await notifier.notify_with_sound("Title", "Message")

            assert result is True
            args = mock_exec.call_args[0]
            assert "-sound" in args
            assert "default" in args

    @pytest.mark.asyncio
    async def test_play_sound_success(self):
        """play_sound plays macOS system sound using afplay."""
        notifier = Notifier()  # available doesn't affect play_sound

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.wait = AsyncMock()
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            result = await notifier.play_sound("Glass")

            assert result is True
            mock_exec.assert_called_once()
            args = mock_exec.call_args[0]
            assert "afplay" in args
            assert "/System/Library/Sounds/Glass.aiff" in args

    @pytest.mark.asyncio
    async def test_play_sound_default_uses_ping(self):
        """play_sound maps 'default' to 'Ping' sound."""
        notifier = Notifier()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.wait = AsyncMock()
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            result = await notifier.play_sound("default")

            assert result is True
            args = mock_exec.call_args[0]
            assert "/System/Library/Sounds/Ping.aiff" in args

    @pytest.mark.asyncio
    async def test_play_sound_failure(self):
        """play_sound returns False on failure."""
        notifier = Notifier()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.wait = AsyncMock()
            mock_proc.returncode = 1  # Failure
            mock_exec.return_value = mock_proc

            result = await notifier.play_sound("NonExistentSound")

            assert result is False

    @pytest.mark.asyncio
    async def test_play_sound_exception(self):
        """play_sound handles exceptions gracefully."""
        notifier = Notifier()

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.side_effect = FileNotFoundError("afplay not found")

            result = await notifier.play_sound("Glass")

            assert result is False


# =============================================================================
# NotificationLatencyTracker Tests
# =============================================================================


class TestNotificationLatencyTracker:
    """Test NotificationLatencyTracker functionality."""

    def test_init_defaults(self):
        """Tracker initializes with correct defaults."""
        tracker = NotificationLatencyTracker()
        assert tracker.sla_seconds == 5.0
        assert tracker.state_change_times == {}
        assert tracker.notification_times == {}

    def test_record_state_change(self):
        """record_state_change stores time."""
        tracker = NotificationLatencyTracker()
        tracker.record_state_change("session-1")

        assert "session-1" in tracker.state_change_times
        assert tracker.state_change_times["session-1"] > 0

    def test_record_notification_sent(self):
        """record_notification_sent stores time."""
        tracker = NotificationLatencyTracker()
        tracker.record_notification_sent("session-1")

        assert "session-1" in tracker.notification_times
        assert tracker.notification_times["session-1"] > 0

    def test_get_latency_calculates_correctly(self):
        """get_latency calculates difference between times."""
        tracker = NotificationLatencyTracker()

        # Record with known times
        tracker.state_change_times["session-1"] = 100.0
        tracker.notification_times["session-1"] = 100.5

        latency = tracker.get_latency("session-1")
        assert latency == pytest.approx(0.5, abs=0.01)

    def test_get_latency_returns_none_when_missing(self):
        """get_latency returns None when times are missing."""
        tracker = NotificationLatencyTracker()

        assert tracker.get_latency("nonexistent") is None

        tracker.state_change_times["session-1"] = 100.0
        assert tracker.get_latency("session-1") is None

    def test_check_sla_within_limit(self):
        """check_sla returns True when latency is within SLA."""
        tracker = NotificationLatencyTracker(sla_seconds=5.0)
        tracker.state_change_times["session-1"] = 100.0
        tracker.notification_times["session-1"] = 103.0  # 3 seconds

        assert tracker.check_sla("session-1") is True

    def test_check_sla_exceeded(self):
        """check_sla returns False when latency exceeds SLA."""
        tracker = NotificationLatencyTracker(sla_seconds=5.0)
        tracker.state_change_times["session-1"] = 100.0
        tracker.notification_times["session-1"] = 106.0  # 6 seconds

        assert tracker.check_sla("session-1") is False

    def test_check_sla_missing_data(self):
        """check_sla returns False when data is missing."""
        tracker = NotificationLatencyTracker()
        assert tracker.check_sla("nonexistent") is False

    def test_get_stats_empty(self):
        """get_stats returns count 0 when empty."""
        tracker = NotificationLatencyTracker()
        stats = tracker.get_stats()

        assert stats == {"count": 0}

    def test_get_stats_with_data(self):
        """get_stats calculates correct statistics."""
        tracker = NotificationLatencyTracker(sla_seconds=5.0)

        # Add some test data
        tracker.state_change_times["session-1"] = 100.0
        tracker.notification_times["session-1"] = 101.0  # 1s latency

        tracker.state_change_times["session-2"] = 200.0
        tracker.notification_times["session-2"] = 203.0  # 3s latency

        tracker.state_change_times["session-3"] = 300.0
        tracker.notification_times["session-3"] = 306.0  # 6s latency (violation)

        stats = tracker.get_stats()

        assert stats["count"] == 3
        assert stats["min"] == pytest.approx(1.0, abs=0.01)
        assert stats["max"] == pytest.approx(6.0, abs=0.01)
        assert stats["avg"] == pytest.approx(10.0 / 3, abs=0.01)
        assert stats["sla_met"] == 2
        assert stats["sla_violated"] == 1

    def test_clear_session(self):
        """clear_session removes data for session."""
        tracker = NotificationLatencyTracker()
        tracker.state_change_times["session-1"] = 100.0
        tracker.notification_times["session-1"] = 101.0

        tracker.clear_session("session-1")

        assert "session-1" not in tracker.state_change_times
        assert "session-1" not in tracker.notification_times

    def test_clear_all(self):
        """clear_all removes all data."""
        tracker = NotificationLatencyTracker()
        tracker.state_change_times["session-1"] = 100.0
        tracker.notification_times["session-1"] = 101.0
        tracker.state_change_times["session-2"] = 200.0

        tracker.clear_all()

        assert tracker.state_change_times == {}
        assert tracker.notification_times == {}


# =============================================================================
# NotificationSettings Tests
# =============================================================================


class TestNotificationSettings:
    """Test NotificationSettings functionality."""

    def test_init_defaults(self):
        """Settings initializes with correct defaults."""
        settings = NotificationSettings()
        assert settings.enabled is True
        assert settings.sound_enabled is True
        assert settings.sound_name == "default"
        assert settings.on_session_waiting is True
        assert settings.on_session_idle is False
        assert settings.on_review_failed is True
        assert settings.on_task_complete is False
        assert settings.on_phase_complete is True
        assert settings.on_orchestrator_done is True
        assert settings.quiet_hours_start is None
        assert settings.quiet_hours_end is None

    def test_is_quiet_time_no_config(self):
        """is_quiet_time returns False when not configured."""
        settings = NotificationSettings()
        assert settings.is_quiet_time() is False

    def test_is_quiet_time_partial_config(self):
        """is_quiet_time returns False when partially configured."""
        settings = NotificationSettings(quiet_hours_start="22:00")
        assert settings.is_quiet_time() is False

        settings = NotificationSettings(quiet_hours_end="08:00")
        assert settings.is_quiet_time() is False

    def test_is_quiet_time_normal_hours(self):
        """is_quiet_time works for normal hour ranges."""
        settings = NotificationSettings(
            quiet_hours_start="22:00",
            quiet_hours_end="23:00",
        )

        with patch("iterm_controller.models.datetime") as mock_dt:
            # Mock time to be 22:30
            mock_now = MagicMock()
            mock_now.time.return_value = datetime.strptime("22:30", "%H:%M").time()
            mock_dt.now.return_value = mock_now
            mock_dt.strptime = datetime.strptime

            assert settings.is_quiet_time() is True

            # Mock time to be 21:00 (before quiet hours)
            mock_now.time.return_value = datetime.strptime("21:00", "%H:%M").time()
            assert settings.is_quiet_time() is False

    def test_is_quiet_time_spans_midnight(self):
        """is_quiet_time works for ranges spanning midnight."""
        settings = NotificationSettings(
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
        )

        with patch("iterm_controller.models.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_dt.now.return_value = mock_now
            mock_dt.strptime = datetime.strptime

            # Mock time to be 23:00 (after start, before midnight)
            mock_now.time.return_value = datetime.strptime("23:00", "%H:%M").time()
            assert settings.is_quiet_time() is True

            # Mock time to be 02:00 (after midnight, before end)
            mock_now.time.return_value = datetime.strptime("02:00", "%H:%M").time()
            assert settings.is_quiet_time() is True

            # Mock time to be 12:00 (outside quiet hours)
            mock_now.time.return_value = datetime.strptime("12:00", "%H:%M").time()
            assert settings.is_quiet_time() is False


# =============================================================================
# NotificationManager Tests
# =============================================================================


class TestNotificationManager:
    """Test NotificationManager functionality."""

    @pytest.mark.asyncio
    async def test_init(self, app_state):
        """NotificationManager initializes correctly."""
        notifier = Notifier(available=True)
        manager = NotificationManager(notifier, app_state)

        assert manager.notifier is notifier
        assert manager.state is app_state
        assert isinstance(manager.settings, NotificationSettings)
        assert isinstance(manager.latency_tracker, NotificationLatencyTracker)

    @pytest.mark.asyncio
    async def test_on_session_state_change_to_waiting(self, mock_session, app_state):
        """on_session_state_change sends notification when entering WAITING."""
        notifier = Notifier(available=True)
        manager = NotificationManager(notifier, app_state)

        with patch.object(notifier, "notify_session_waiting", new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = True

            await manager.on_session_state_change(
                mock_session,
                AttentionState.IDLE,
                AttentionState.WAITING,
            )

            mock_notify.assert_called_once()
            # Verify latency was tracked
            assert mock_session.id in manager.latency_tracker.state_change_times
            assert mock_session.id in manager.latency_tracker.notification_times

    @pytest.mark.asyncio
    async def test_on_session_state_change_leaves_waiting(self, mock_session, app_state):
        """on_session_state_change clears notification when leaving WAITING."""
        notifier = Notifier(available=True)
        manager = NotificationManager(notifier, app_state)

        with patch.object(notifier, "clear_session_notification", new_callable=AsyncMock) as mock_clear:
            await manager.on_session_state_change(
                mock_session,
                AttentionState.WAITING,
                AttentionState.WORKING,
            )

            mock_clear.assert_called_once_with(mock_session)

    @pytest.mark.asyncio
    async def test_on_session_state_change_disabled(self, mock_session, app_state):
        """on_session_state_change does nothing when disabled."""
        notifier = Notifier(available=True)
        settings = NotificationSettings(enabled=False)
        manager = NotificationManager(notifier, app_state, settings)

        with patch.object(notifier, "notify_session_waiting", new_callable=AsyncMock) as mock_notify:
            await manager.on_session_state_change(
                mock_session,
                AttentionState.IDLE,
                AttentionState.WAITING,
            )

            mock_notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_session_state_change_quiet_hours(self, mock_session, app_state):
        """on_session_state_change respects quiet hours."""
        notifier = Notifier(available=True)
        settings = NotificationSettings(
            enabled=True,
            quiet_hours_start="00:00",
            quiet_hours_end="23:59",  # Always quiet
        )
        manager = NotificationManager(notifier, app_state, settings)

        with patch.object(notifier, "notify_session_waiting", new_callable=AsyncMock) as mock_notify:
            await manager.on_session_state_change(
                mock_session,
                AttentionState.IDLE,
                AttentionState.WAITING,
            )

            mock_notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_session_state_change_unknown_project(self, mock_session, app_state):
        """on_session_state_change handles unknown project gracefully."""
        mock_session.project_id = "unknown-project"
        notifier = Notifier(available=True)
        manager = NotificationManager(notifier, app_state)

        with patch.object(notifier, "notify_session_waiting", new_callable=AsyncMock) as mock_notify:
            # Should not raise
            await manager.on_session_state_change(
                mock_session,
                AttentionState.IDLE,
                AttentionState.WAITING,
            )

            mock_notify.assert_not_called()

    def test_get_latency_stats(self, app_state):
        """get_latency_stats returns tracker stats."""
        notifier = Notifier(available=True)
        manager = NotificationManager(notifier, app_state)

        stats = manager.get_latency_stats()
        assert stats == {"count": 0}

    def test_cleanup_session(self, app_state):
        """cleanup_session removes tracking data."""
        notifier = Notifier(available=True)
        manager = NotificationManager(notifier, app_state)

        # Add some tracking data
        manager.latency_tracker.state_change_times["session-1"] = 100.0
        manager.latency_tracker.notification_times["session-1"] = 101.0

        manager.cleanup_session("session-1")

        assert "session-1" not in manager.latency_tracker.state_change_times

    @pytest.mark.asyncio
    async def test_sla_violation_logged(self, mock_session, app_state, caplog):
        """SLA violation is logged when notification latency exceeds 5 seconds."""
        import logging

        notifier = Notifier(available=True)
        manager = NotificationManager(notifier, app_state)

        # Track the call order to simulate time passing
        call_count = 0
        base_time = 1000.0

        def mock_monotonic():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call is record_state_change
                return base_time
            else:
                # Subsequent calls (record_notification_sent, etc.) are 6 seconds later
                return base_time + 6.0

        with patch.object(notifier, "notify_session_waiting", new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = True

            with patch("time.monotonic", side_effect=mock_monotonic):
                with caplog.at_level(logging.WARNING):
                    await manager.on_session_state_change(
                        mock_session,
                        AttentionState.IDLE,
                        AttentionState.WAITING,
                    )

            # Verify SLA violation was logged
            assert any(
                "SLA violated" in record.message and mock_session.id in record.message
                for record in caplog.records
            )

    @pytest.mark.asyncio
    async def test_sla_met_logged_as_debug(self, mock_session, app_state, caplog):
        """Successful notification within SLA is logged at debug level."""
        import logging

        notifier = Notifier(available=True)
        manager = NotificationManager(notifier, app_state)

        with patch.object(notifier, "notify_session_waiting", new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = True

            caplog.clear()  # Clear any records from previous tests
            with caplog.at_level(logging.DEBUG, logger="iterm_controller.notifications"):
                await manager.on_session_state_change(
                    mock_session,
                    AttentionState.IDLE,
                    AttentionState.WAITING,
                )

                # Verify notification was logged at debug level
                assert any(
                    "Notification sent" in record.message and mock_session.id in record.message
                    for record in caplog.records
                )

    @pytest.mark.asyncio
    async def test_latency_stats_accumulate(self, mock_session, app_state):
        """Latency stats accumulate across multiple notifications."""
        notifier = Notifier(available=True)
        manager = NotificationManager(notifier, app_state)

        with patch.object(notifier, "notify_session_waiting", new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = True

            # Send first notification
            await manager.on_session_state_change(
                mock_session,
                AttentionState.IDLE,
                AttentionState.WAITING,
            )

            # Clear and send another
            mock_session2 = ManagedSession(
                id="session-456",
                template_id="server",
                project_id="project-1",
                tab_id="tab-2",
                attention_state=AttentionState.IDLE,
            )

            await manager.on_session_state_change(
                mock_session2,
                AttentionState.IDLE,
                AttentionState.WAITING,
            )

            stats = manager.get_latency_stats()
            assert stats["count"] == 2
            assert "min" in stats
            assert "max" in stats
            assert "avg" in stats
            assert "sla_met" in stats
            assert "sla_violated" in stats


# =============================================================================
# SessionMonitorWithNotifications Tests
# =============================================================================


class TestSessionMonitorWithNotifications:
    """Test SessionMonitorWithNotifications functionality."""

    @pytest.mark.asyncio
    async def test_init(self, app_state):
        """SessionMonitorWithNotifications initializes correctly."""
        notifier = Notifier(available=True)
        wrapper = SessionMonitorWithNotifications(notifier, app_state)

        assert isinstance(wrapper.notification_manager, NotificationManager)

    @pytest.mark.asyncio
    async def test_on_attention_change(self, mock_session, app_state):
        """on_attention_change delegates to notification manager."""
        notifier = Notifier(available=True)
        wrapper = SessionMonitorWithNotifications(notifier, app_state)

        with patch.object(
            wrapper.notification_manager,
            "on_session_state_change",
            new_callable=AsyncMock,
        ) as mock_handler:
            await wrapper.on_attention_change(
                mock_session,
                AttentionState.IDLE,
                AttentionState.WAITING,
            )

            mock_handler.assert_called_once_with(
                mock_session,
                AttentionState.IDLE,
                AttentionState.WAITING,
            )

    def test_get_latency_stats(self, app_state):
        """get_latency_stats returns manager stats."""
        notifier = Notifier(available=True)
        wrapper = SessionMonitorWithNotifications(notifier, app_state)

        stats = wrapper.get_latency_stats()
        assert stats == {"count": 0}

    def test_cleanup_session(self, app_state):
        """cleanup_session delegates to manager."""
        notifier = Notifier(available=True)
        wrapper = SessionMonitorWithNotifications(notifier, app_state)

        # Should not raise
        wrapper.cleanup_session("session-1")
