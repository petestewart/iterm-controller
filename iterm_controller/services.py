"""Service container for dependency injection.

This module provides a ServiceContainer that holds all injectable services,
enabling screens and other components to access services via the app rather
than instantiating them directly.

Services are initialized eagerly when the container is created, but the
actual iTerm2 connection is deferred until connect() is called.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from iterm_controller.github import GitHubIntegration
from iterm_controller.iterm import (
    ItermController,
    SessionSpawner,
    SessionTerminator,
    WindowLayoutManager,
    WindowLayoutSpawner,
)
from iterm_controller.notifications import Notifier

if TYPE_CHECKING:
    from iterm_controller.models import WindowLayout

logger = logging.getLogger(__name__)


@dataclass
class ServiceContainer:
    """Container for all injectable services.

    This container holds references to all services that screens and other
    components need. Instead of screens instantiating services directly,
    they access them via the app's service container.

    Services are created during container initialization but remain
    disconnected until the async initialization methods are called.

    Attributes:
        iterm: The iTerm2 connection controller.
        spawner: Service for creating terminal sessions.
        terminator: Service for closing terminal sessions.
        layout_manager: Service for managing window layouts.
        layout_spawner: Service for spawning window layouts.
        github: GitHub integration service.
        notifier: macOS notification service.
    """

    iterm: ItermController
    spawner: SessionSpawner
    terminator: SessionTerminator
    layout_manager: WindowLayoutManager
    layout_spawner: WindowLayoutSpawner
    github: GitHubIntegration
    notifier: Notifier

    @classmethod
    def create(cls) -> "ServiceContainer":
        """Create a new service container with all services initialized.

        The services are created but not yet connected. Call the async
        initialization methods (connect_iterm, initialize_github, etc.)
        to complete setup.

        Returns:
            A new ServiceContainer with all services.
        """
        # Create the core iTerm2 controller
        iterm = ItermController()

        # Create dependent services
        spawner = SessionSpawner(iterm)
        terminator = SessionTerminator(iterm)
        layout_manager = WindowLayoutManager(iterm)
        layout_spawner = WindowLayoutSpawner(iterm, spawner)

        # Create integration services
        github = GitHubIntegration()
        notifier = Notifier()

        return cls(
            iterm=iterm,
            spawner=spawner,
            terminator=terminator,
            layout_manager=layout_manager,
            layout_spawner=layout_spawner,
            github=github,
            notifier=notifier,
        )

    async def connect_iterm(self) -> None:
        """Connect to iTerm2.

        Raises:
            Exception: If the connection fails.
        """
        await self.iterm.connect()

    async def disconnect_iterm(self) -> None:
        """Disconnect from iTerm2."""
        await self.iterm.disconnect()

    async def initialize_github(self) -> None:
        """Initialize the GitHub integration."""
        await self.github.initialize()

    def load_layouts(self, layouts: list["WindowLayout"]) -> None:
        """Load window layouts into the layout manager.

        Args:
            layouts: The window layouts to load.
        """
        self.layout_manager.load_from_config(layouts)

    @property
    def is_connected(self) -> bool:
        """Check if connected to iTerm2."""
        return self.iterm.is_connected
