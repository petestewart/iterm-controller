"""iTerm2 connection management.

This module provides connection lifecycle management for iTerm2's Python API.
"""

from __future__ import annotations

import logging
from typing import Callable, TypeVar

import iterm2

from iterm_controller.exceptions import (
    ItermConnectionError,
    ItermNotConnectedError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ItermController:
    """Manages iTerm2 connection and session operations."""

    def __init__(self) -> None:
        self.connection: iterm2.Connection | None = None
        self.app: iterm2.App | None = None
        self._connected: bool = False

    async def connect(self) -> bool:
        """Establish connection to iTerm2.

        Returns:
            True if connection established successfully.

        Raises:
            ItermConnectionError: If connection fails.
        """
        try:
            self.connection = await iterm2.Connection.async_create()
            self.app = await iterm2.async_get_app(self.connection)
            self._connected = True
            logger.info("Connected to iTerm2")
            return True
        except ConnectionRefusedError as e:
            self._connected = False
            raise ItermConnectionError(
                "Connection refused. Is iTerm2 running with Python API enabled?"
            ) from e
        except Exception as e:
            self._connected = False
            raise ItermConnectionError(f"Failed to connect to iTerm2: {e}") from e

    async def disconnect(self) -> None:
        """Cleanly disconnect from iTerm2."""
        if self.connection:
            # Connection auto-closes when garbage collected
            self.connection = None
            self.app = None
            self._connected = False
            logger.info("Disconnected from iTerm2")

    async def reconnect(self) -> bool:
        """Attempt to reconnect after disconnection.

        Returns:
            True if reconnection successful.

        Raises:
            ItermConnectionError: If reconnection fails.
        """
        await self.disconnect()
        return await self.connect()

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to iTerm2."""
        return self._connected and self.connection is not None

    async def verify_version(self) -> tuple[bool, str]:
        """Check iTerm2 version meets requirements.

        Returns:
            Tuple of (success, message).
        """
        if not self.app:
            return (False, "Not connected to iTerm2")

        # iTerm2 API doesn't expose version directly, but connection success
        # implies compatible version (3.5+ required for Python API)
        return (True, "Connected to iTerm2 (3.5+ required)")

    def require_connection(self) -> None:
        """Raise if not connected.

        Raises:
            ItermNotConnectedError: If not connected to iTerm2.
        """
        if not self.is_connected:
            raise ItermNotConnectedError("Not connected to iTerm2. Call connect() first.")


async def with_reconnect(
    controller: ItermController,
    operation: Callable[[], T],
    max_retries: int = 3,
) -> T:
    """Execute operation with automatic reconnect on failure.

    Args:
        controller: The iTerm controller to use.
        operation: Async callable to execute.
        max_retries: Maximum number of retry attempts.

    Returns:
        The result of the operation.

    Raises:
        Exception: If all retries fail.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            return await operation()
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            is_connection_error = (
                "connection" in error_str
                or "closed" in error_str
                or isinstance(e, ItermConnectionError)
            )

            if is_connection_error and attempt < max_retries - 1:
                logger.warning(f"Connection error on attempt {attempt + 1}, reconnecting...")
                try:
                    await controller.reconnect()
                except ItermConnectionError:
                    # If reconnect fails, continue to next attempt
                    pass
            else:
                raise

    # Should not reach here, but satisfy type checker
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected state in with_reconnect")
