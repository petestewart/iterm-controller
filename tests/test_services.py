"""Tests for the ServiceContainer."""

import pytest

from iterm_controller.services import ServiceContainer


class TestServiceContainer:
    """Tests for ServiceContainer creation and component injection."""

    def test_create_initializes_all_services(self) -> None:
        """Test that create() initializes all required services."""
        container = ServiceContainer.create()

        # Core iTerm services
        assert container.iterm is not None
        assert container.spawner is not None
        assert container.terminator is not None
        assert container.layout_manager is not None
        assert container.layout_spawner is not None

        # Integration services
        assert container.github is not None
        assert container.notifier is not None

    def test_spawner_depends_on_iterm_controller(self) -> None:
        """Test that spawner is created with the iterm controller."""
        container = ServiceContainer.create()

        # Spawner should use the same iterm controller
        assert container.spawner.controller is container.iterm

    def test_terminator_depends_on_iterm_controller(self) -> None:
        """Test that terminator is created with the iterm controller."""
        container = ServiceContainer.create()

        # Terminator should use the same iterm controller
        assert container.terminator.controller is container.iterm

    def test_layout_spawner_depends_on_iterm_and_spawner(self) -> None:
        """Test that layout_spawner is created with both iterm and spawner."""
        container = ServiceContainer.create()

        # Layout spawner should use the same iterm controller and spawner
        assert container.layout_spawner.controller is container.iterm
        assert container.layout_spawner.spawner is container.spawner

    def test_is_connected_returns_false_initially(self) -> None:
        """Test that is_connected returns False before connecting."""
        container = ServiceContainer.create()

        # Should not be connected initially
        assert container.is_connected is False

    def test_load_layouts_populates_layout_manager(self) -> None:
        """Test that load_layouts adds layouts to the layout manager."""
        from iterm_controller.models import SessionLayout, TabLayout, WindowLayout

        container = ServiceContainer.create()

        # Create a test layout
        session_layout = SessionLayout(template_id="dev")
        tab_layout = TabLayout(name="Dev", sessions=[session_layout])
        window_layout = WindowLayout(
            id="test-layout",
            name="Test Layout",
            tabs=[tab_layout]
        )

        # Load layouts
        container.load_layouts([window_layout])

        # Layout manager should have the layout
        layouts = container.layout_manager.list_layouts()
        assert len(layouts) == 1
        assert layouts[0].id == "test-layout"


class TestServiceContainerWithApp:
    """Tests for ServiceContainer integration with app."""

    def test_app_creates_service_container(self) -> None:
        """Test that app creates and stores a service container."""
        from iterm_controller.app import ItermControllerApp

        app = ItermControllerApp()

        assert app.services is not None
        assert isinstance(app.services, ServiceContainer)

    def test_app_exposes_services_for_backwards_compatibility(self) -> None:
        """Test that app exposes common services directly."""
        from iterm_controller.app import ItermControllerApp

        app = ItermControllerApp()

        # Services should be exposed directly
        assert app.iterm is app.services.iterm
        assert app.github is app.services.github
        assert app.notifier is app.services.notifier

    def test_app_api_receives_injected_services(self) -> None:
        """Test that app.api receives the injected services."""
        from iterm_controller.app import ItermControllerApp

        app = ItermControllerApp()

        # API should have received the services
        assert app.api._services is app.services
        assert app.api._spawner is app.services.spawner
        assert app.api._terminator is app.services.terminator
        assert app.api._layout_manager is app.services.layout_manager
        assert app.api._layout_spawner is app.services.layout_spawner


class TestAppAPIWithInjectedServices:
    """Tests for AppAPI with injected services vs lazy initialization."""

    def test_api_with_services_skips_lazy_init(self) -> None:
        """Test that API with injected services skips lazy initialization."""
        from iterm_controller.api import AppAPI
        from iterm_controller.app import ItermControllerApp

        app = ItermControllerApp()
        api = app.api

        # _ensure_components should be a no-op when services are injected
        original_spawner = api._spawner
        api._ensure_components()

        # Should still be the same object (not recreated)
        assert api._spawner is original_spawner

    def test_api_without_services_uses_lazy_init(self) -> None:
        """Test that API without injected services falls back to lazy init."""
        from iterm_controller.api import AppAPI
        from iterm_controller.app import ItermControllerApp

        app = ItermControllerApp()

        # Create API without services (backwards compatibility)
        api = AppAPI(app, services=None)

        # Components should be None initially
        assert api._spawner is None

        # After _ensure_components, they should be created
        api._ensure_components()
        assert api._spawner is not None
