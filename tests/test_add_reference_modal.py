"""Tests for AddReferenceModal."""

import pytest

from iterm_controller.models import DocReference
from iterm_controller.screens.modals.add_reference import AddReferenceModal


class TestAddReferenceModalURLValidation:
    """Tests for URL validation in AddReferenceModal."""

    def test_url_pattern_accepts_https(self) -> None:
        """Test that https URLs are accepted."""
        assert AddReferenceModal.URL_PATTERN.match("https://example.com")
        assert AddReferenceModal.URL_PATTERN.match("https://textual.textualize.io/")
        assert AddReferenceModal.URL_PATTERN.match("https://iterm2.com/python-api/")

    def test_url_pattern_accepts_http(self) -> None:
        """Test that http URLs are accepted."""
        assert AddReferenceModal.URL_PATTERN.match("http://example.com")
        # Note: localhost URLs don't have a TLD so they won't match
        # Users can still enter them and they'll be validated as-is

    def test_url_pattern_accepts_subdomains(self) -> None:
        """Test that URLs with subdomains are accepted."""
        assert AddReferenceModal.URL_PATTERN.match("https://docs.python.org")
        assert AddReferenceModal.URL_PATTERN.match("https://api.github.com")

    def test_url_pattern_accepts_paths(self) -> None:
        """Test that URLs with paths are accepted."""
        assert AddReferenceModal.URL_PATTERN.match("https://example.com/path")
        assert AddReferenceModal.URL_PATTERN.match("https://example.com/path/to/resource")
        assert AddReferenceModal.URL_PATTERN.match("https://example.com/path/to/resource/")

    def test_url_pattern_accepts_query_strings(self) -> None:
        """Test that URLs with paths containing query strings are accepted."""
        # Query strings require a path prefix in the current pattern
        assert AddReferenceModal.URL_PATTERN.match("https://example.com/path?query=value")
        assert AddReferenceModal.URL_PATTERN.match("https://example.com/?query=value")

    def test_url_pattern_accepts_fragments(self) -> None:
        """Test that URLs with paths containing fragments are accepted."""
        # Fragments require a path prefix in the current pattern
        assert AddReferenceModal.URL_PATTERN.match("https://example.com/path#section")
        assert AddReferenceModal.URL_PATTERN.match("https://example.com/#section")

    def test_url_pattern_rejects_invalid(self) -> None:
        """Test that invalid URLs are rejected."""
        assert not AddReferenceModal.URL_PATTERN.match("not-a-url")
        assert not AddReferenceModal.URL_PATTERN.match("ftp://example.com")
        assert not AddReferenceModal.URL_PATTERN.match("example.com")  # No protocol
        assert not AddReferenceModal.URL_PATTERN.match("https://")  # No domain
        assert not AddReferenceModal.URL_PATTERN.match("https://a")  # No TLD


class TestAddReferenceModalCreation:
    """Tests for AddReferenceModal creation."""

    def test_modal_creation_empty(self) -> None:
        """Test creating modal without existing reference."""
        modal = AddReferenceModal()
        assert modal._existing is None

    def test_modal_creation_with_existing(self) -> None:
        """Test creating modal with existing reference for editing."""
        existing = DocReference(
            id="ref-123",
            title="Existing Doc",
            url="https://example.com/",
            category="Test",
            notes="Some notes",
        )
        modal = AddReferenceModal(existing_reference=existing)
        assert modal._existing == existing


@pytest.mark.asyncio
class TestAddReferenceModalAsync:
    """Async tests for AddReferenceModal."""

    async def test_modal_renders(self) -> None:
        """Test that the modal renders correctly."""
        from iterm_controller.app import ItermControllerApp

        app = ItermControllerApp()
        async with app.run_test() as pilot:
            modal = AddReferenceModal()
            app.push_screen(modal)
            await pilot.pause()

            # Should have URL input
            url_input = app.screen.query_one("#url")
            assert url_input is not None

            # Should have title input
            title_input = app.screen.query_one("#title-input")
            assert title_input is not None

            # Should have cancel and add buttons
            cancel_btn = app.screen.query_one("#cancel")
            add_btn = app.screen.query_one("#add")
            assert cancel_btn is not None
            assert add_btn is not None

    async def test_cancel_dismisses_with_none(self) -> None:
        """Test that cancel button dismisses with None."""
        from iterm_controller.app import ItermControllerApp

        app = ItermControllerApp()
        async with app.run_test() as pilot:
            results = []

            def callback(result: DocReference | None) -> None:
                results.append(result)

            modal = AddReferenceModal()
            app.push_screen(modal, callback)
            await pilot.pause()

            # Press escape to cancel
            await pilot.press("escape")
            await pilot.pause()

            assert len(results) == 1
            assert results[0] is None

    async def test_create_reference(self) -> None:
        """Test creating a new reference."""
        from textual.widgets import Button, Input

        from iterm_controller.app import ItermControllerApp

        app = ItermControllerApp()
        async with app.run_test() as pilot:
            results = []

            def callback(result: DocReference | None) -> None:
                results.append(result)

            modal = AddReferenceModal()
            app.push_screen(modal, callback)
            await pilot.pause()

            # Fill in URL
            url_input = app.screen.query_one("#url", Input)
            url_input.value = "https://example.com/"

            # Fill in title
            title_input = app.screen.query_one("#title-input", Input)
            title_input.value = "Example Documentation"

            # Fill in category
            category_input = app.screen.query_one("#category", Input)
            category_input.value = "API Docs"

            # Click add button
            add_btn = app.screen.query_one("#add", Button)
            add_btn.press()
            await pilot.pause()

            assert len(results) == 1
            result = results[0]
            assert result is not None
            assert result.url == "https://example.com/"
            assert result.title == "Example Documentation"
            assert result.category == "API Docs"
            assert result.id != ""  # Should have generated ID

    async def test_validates_required_url(self) -> None:
        """Test that empty URL shows warning."""
        from textual.widgets import Button, Input

        from iterm_controller.app import ItermControllerApp

        app = ItermControllerApp()
        async with app.run_test() as pilot:
            modal = AddReferenceModal()
            app.push_screen(modal)
            await pilot.pause()

            # Fill in only title (no URL)
            title_input = app.screen.query_one("#title-input", Input)
            title_input.value = "Test Doc"

            # Click add button
            add_btn = app.screen.query_one("#add", Button)
            add_btn.press()
            await pilot.pause()

            # Modal should still be showing (not dismissed)
            # because URL is required
            assert app.screen is modal

    async def test_validates_required_title(self) -> None:
        """Test that empty title shows warning."""
        from textual.widgets import Button, Input

        from iterm_controller.app import ItermControllerApp

        app = ItermControllerApp()
        async with app.run_test() as pilot:
            modal = AddReferenceModal()
            app.push_screen(modal)
            await pilot.pause()

            # Fill in only URL (no title)
            url_input = app.screen.query_one("#url", Input)
            url_input.value = "https://example.com/"

            # Click add button
            add_btn = app.screen.query_one("#add", Button)
            add_btn.press()
            await pilot.pause()

            # Modal should still be showing (not dismissed)
            # because title is required
            assert app.screen is modal

    async def test_auto_adds_https_prefix(self) -> None:
        """Test that https:// is auto-added if missing."""
        from textual.widgets import Button, Input

        from iterm_controller.app import ItermControllerApp

        app = ItermControllerApp()
        async with app.run_test() as pilot:
            results = []

            def callback(result: DocReference | None) -> None:
                results.append(result)

            modal = AddReferenceModal()
            app.push_screen(modal, callback)
            await pilot.pause()

            # Fill in URL without protocol
            url_input = app.screen.query_one("#url", Input)
            url_input.value = "example.com"

            # Fill in title
            title_input = app.screen.query_one("#title-input", Input)
            title_input.value = "Example"

            # Click add button
            add_btn = app.screen.query_one("#add", Button)
            add_btn.press()
            await pilot.pause()

            assert len(results) == 1
            result = results[0]
            assert result is not None
            assert result.url == "https://example.com"

    async def test_edit_mode_preserves_id(self) -> None:
        """Test that editing preserves the original ID."""
        from textual.widgets import Button, Input

        from iterm_controller.app import ItermControllerApp

        app = ItermControllerApp()
        async with app.run_test() as pilot:
            results = []

            def callback(result: DocReference | None) -> None:
                results.append(result)

            existing = DocReference(
                id="original-id",
                title="Original Title",
                url="https://original.com/",
            )
            modal = AddReferenceModal(existing_reference=existing)
            app.push_screen(modal, callback)
            await pilot.pause()

            # Change the title
            title_input = app.screen.query_one("#title-input", Input)
            title_input.value = "Updated Title"

            # Click save button
            add_btn = app.screen.query_one("#add", Button)
            add_btn.press()
            await pilot.pause()

            assert len(results) == 1
            result = results[0]
            assert result is not None
            assert result.id == "original-id"  # ID preserved
            assert result.title == "Updated Title"
