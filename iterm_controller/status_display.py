"""Shared status display constants for consistent UI across widgets.

This module centralizes status icons and colors used to display:
- Task status (pending, in progress, complete, skipped, blocked)
- Session attention state (waiting, working, idle)
- Test status (pending, in progress, passed, failed)

Usage:
    from iterm_controller.status_display import (
        TASK_STATUS_ICONS,
        TASK_STATUS_COLORS,
        ATTENTION_STATE_ICONS,
        ATTENTION_STATE_COLORS,
        TEST_STATUS_ICONS,
        TEST_STATUS_COLORS,
    )
"""

from __future__ import annotations

from iterm_controller.models import AttentionState, TaskStatus, TestStatus

# Task status display (for PLAN.md tasks)
TASK_STATUS_ICONS: dict[TaskStatus, str] = {
    TaskStatus.PENDING: "○",
    TaskStatus.IN_PROGRESS: "●",
    TaskStatus.AWAITING_REVIEW: "◎",
    TaskStatus.COMPLETE: "✓",
    TaskStatus.SKIPPED: "⊖",
    TaskStatus.BLOCKED: "⊘",
}

TASK_STATUS_COLORS: dict[TaskStatus, str] = {
    TaskStatus.PENDING: "white",
    TaskStatus.IN_PROGRESS: "yellow",
    TaskStatus.AWAITING_REVIEW: "cyan",
    TaskStatus.COMPLETE: "green",
    TaskStatus.SKIPPED: "dim",
    TaskStatus.BLOCKED: "dim",
}

# Session attention state display
ATTENTION_STATE_ICONS: dict[AttentionState, str] = {
    AttentionState.WAITING: "⧖",
    AttentionState.WORKING: "●",
    AttentionState.IDLE: "○",
}

ATTENTION_STATE_COLORS: dict[AttentionState, str] = {
    AttentionState.WAITING: "yellow",
    AttentionState.WORKING: "green",
    AttentionState.IDLE: "dim",
}

# Test status display (for TEST_PLAN.md)
# These match the markdown markers: [ ], [~], [x], [!]
TEST_STATUS_ICONS: dict[TestStatus, str] = {
    TestStatus.PENDING: "[ ]",
    TestStatus.IN_PROGRESS: "[~]",
    TestStatus.PASSED: "[x]",
    TestStatus.FAILED: "[!]",
}

TEST_STATUS_COLORS: dict[TestStatus, str] = {
    TestStatus.PENDING: "white",
    TestStatus.IN_PROGRESS: "yellow",
    TestStatus.PASSED: "green",
    TestStatus.FAILED: "red",
}


# Default fallbacks
DEFAULT_ICON = "○"
DEFAULT_COLOR = "white"

# Layout constants for widget rendering
# These define column widths and padding for consistent table layouts

# Phase header layout (task_list.py)
PHASE_HEADER_WIDTH = 40  # Total width for phase title + progress

# Session list layout (session_list.py)
SESSION_NAME_WIDTH = 25  # Width for project_id/template_id column
SESSION_TASK_ID_WIDTH = 8  # Width for task ID in "Task {id}" format
SESSION_TASK_PLACEHOLDER_WIDTH = 13  # Width for placeholder when no task linked


def get_task_icon(status: TaskStatus) -> str:
    """Get the display icon for a task status.

    Args:
        status: The task status.

    Returns:
        The icon string for display.
    """
    return TASK_STATUS_ICONS.get(status, DEFAULT_ICON)


def get_task_color(status: TaskStatus) -> str:
    """Get the display color for a task status.

    Args:
        status: The task status.

    Returns:
        The color name for Rich styling.
    """
    return TASK_STATUS_COLORS.get(status, DEFAULT_COLOR)


def get_attention_icon(state: AttentionState) -> str:
    """Get the display icon for an attention state.

    Args:
        state: The attention state.

    Returns:
        The icon string for display.
    """
    return ATTENTION_STATE_ICONS.get(state, DEFAULT_ICON)


def get_attention_color(state: AttentionState) -> str:
    """Get the display color for an attention state.

    Args:
        state: The attention state.

    Returns:
        The color name for Rich styling.
    """
    return ATTENTION_STATE_COLORS.get(state, "dim")


def get_test_icon(status: TestStatus) -> str:
    """Get the display icon for a test status.

    Args:
        status: The test status.

    Returns:
        The icon string for display.
    """
    return TEST_STATUS_ICONS.get(status, "[ ]")


def get_test_color(status: TestStatus) -> str:
    """Get the display color for a test status.

    Args:
        status: The test status.

    Returns:
        The color name for Rich styling.
    """
    return TEST_STATUS_COLORS.get(status, DEFAULT_COLOR)
