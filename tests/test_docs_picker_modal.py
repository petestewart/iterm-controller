"""Tests for docs picker modal."""

import tempfile
from pathlib import Path

import pytest

from iterm_controller.screens.modals import DocsPickerModal


class TestDocsPickerModalInit:
    """Test DocsPickerModal initialization."""

    def test_create_modal(self, tmp_path):
        modal = DocsPickerModal(tmp_path)
        assert modal is not None

    def test_modal_is_modal_screen(self, tmp_path):
        from textual.screen import ModalScreen

        modal = DocsPickerModal(tmp_path)
        assert isinstance(modal, ModalScreen)

    def test_modal_has_empty_docs_initially(self, tmp_path):
        modal = DocsPickerModal(tmp_path)
        assert modal._docs == []

    def test_modal_stores_project_path(self, tmp_path):
        modal = DocsPickerModal(tmp_path)
        assert modal.project_path == tmp_path

    def test_modal_accepts_string_path(self, tmp_path):
        modal = DocsPickerModal(str(tmp_path))
        assert modal.project_path == tmp_path


class TestDocsPickerModalScanDocs:
    """Test DocsPickerModal _scan_docs method."""

    def test_scan_empty_directory(self, tmp_path):
        modal = DocsPickerModal(tmp_path)
        docs = modal._scan_docs()
        assert docs == []

    def test_scan_finds_readme(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text("# Test")

        modal = DocsPickerModal(tmp_path)
        docs = modal._scan_docs()

        assert len(docs) == 1
        assert docs[0] == readme

    def test_scan_finds_plan(self, tmp_path):
        plan = tmp_path / "PLAN.md"
        plan.write_text("# Plan")

        modal = DocsPickerModal(tmp_path)
        docs = modal._scan_docs()

        assert len(docs) == 1
        assert docs[0] == plan

    def test_scan_prioritizes_readme_over_other_md(self, tmp_path):
        # Create files in specific order
        other = tmp_path / "aaa_first.md"
        readme = tmp_path / "README.md"
        other.write_text("# Other")
        readme.write_text("# README")

        modal = DocsPickerModal(tmp_path)
        docs = modal._scan_docs()

        assert len(docs) == 2
        # README should come first due to priority
        assert docs[0] == readme
        assert docs[1] == other

    def test_scan_finds_markdown_files(self, tmp_path):
        doc1 = tmp_path / "doc1.md"
        doc2 = tmp_path / "doc2.markdown"
        doc1.write_text("# Doc 1")
        doc2.write_text("# Doc 2")

        modal = DocsPickerModal(tmp_path)
        docs = modal._scan_docs()

        paths = set(docs)
        assert doc1 in paths
        assert doc2 in paths

    def test_scan_finds_txt_files(self, tmp_path):
        doc = tmp_path / "notes.txt"
        doc.write_text("Notes")

        modal = DocsPickerModal(tmp_path)
        docs = modal._scan_docs()

        assert doc in docs

    def test_scan_finds_rst_files(self, tmp_path):
        doc = tmp_path / "index.rst"
        doc.write_text("Title\n=====")

        modal = DocsPickerModal(tmp_path)
        docs = modal._scan_docs()

        assert doc in docs

    def test_scan_finds_files_in_docs_directory(self, tmp_path):
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        doc = docs_dir / "guide.md"
        doc.write_text("# Guide")

        modal = DocsPickerModal(tmp_path)
        docs = modal._scan_docs()

        assert doc in docs

    def test_scan_finds_files_in_specs_directory(self, tmp_path):
        specs_dir = tmp_path / "specs"
        specs_dir.mkdir()
        spec = specs_dir / "api.md"
        spec.write_text("# API Spec")

        modal = DocsPickerModal(tmp_path)
        docs = modal._scan_docs()

        assert spec in docs

    def test_scan_excludes_node_modules(self, tmp_path):
        nm_dir = tmp_path / "node_modules"
        nm_dir.mkdir()
        doc = nm_dir / "readme.md"
        doc.write_text("# Package")

        modal = DocsPickerModal(tmp_path)
        docs = modal._scan_docs()

        assert doc not in docs

    def test_scan_excludes_git_directory(self, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        doc = git_dir / "info.md"
        doc.write_text("# Git info")

        modal = DocsPickerModal(tmp_path)
        docs = modal._scan_docs()

        assert doc not in docs

    def test_scan_excludes_venv(self, tmp_path):
        venv_dir = tmp_path / "venv"
        venv_dir.mkdir()
        doc = venv_dir / "readme.md"
        doc.write_text("# Venv")

        modal = DocsPickerModal(tmp_path)
        docs = modal._scan_docs()

        assert doc not in docs

    def test_scan_no_duplicate_files(self, tmp_path):
        # README.md is both a priority file and matches *.md pattern
        readme = tmp_path / "README.md"
        readme.write_text("# README")

        modal = DocsPickerModal(tmp_path)
        docs = modal._scan_docs()

        # Should only appear once
        assert docs.count(readme) == 1


class TestDocsPickerModalShouldInclude:
    """Test DocsPickerModal _should_include method."""

    def test_includes_regular_file(self, tmp_path):
        doc = tmp_path / "test.md"
        doc.write_text("test")

        modal = DocsPickerModal(tmp_path)
        assert modal._should_include(doc) is True

    def test_excludes_directory(self, tmp_path):
        dir_path = tmp_path / "docs"
        dir_path.mkdir()

        modal = DocsPickerModal(tmp_path)
        assert modal._should_include(dir_path) is False

    def test_excludes_file_in_node_modules(self, tmp_path):
        nm_dir = tmp_path / "node_modules"
        nm_dir.mkdir()
        doc = nm_dir / "readme.md"
        doc.write_text("test")

        modal = DocsPickerModal(tmp_path)
        assert modal._should_include(doc) is False


class TestDocsPickerModalActions:
    """Test DocsPickerModal action methods."""

    def test_action_cancel_returns_none(self, tmp_path):
        modal = DocsPickerModal(tmp_path)

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_cancel()

        assert dismissed_with == [None]

    def test_select_doc_with_valid_index_schedules_open(self, tmp_path):
        doc = tmp_path / "README.md"
        doc.write_text("# Test")

        modal = DocsPickerModal(tmp_path)
        modal._docs = [doc]

        # Track what gets scheduled
        scheduled_calls = []
        modal.call_later = lambda fn, *args: scheduled_calls.append((fn, args))

        modal._select_doc(0)

        assert len(scheduled_calls) == 1
        assert scheduled_calls[0][1] == (doc,)

    def test_select_doc_with_invalid_index_does_nothing(self, tmp_path):
        modal = DocsPickerModal(tmp_path)
        modal._docs = []

        scheduled_calls = []
        modal.call_later = lambda fn, *args: scheduled_calls.append((fn, args))

        modal._select_doc(0)

        assert scheduled_calls == []

    def test_select_doc_with_negative_index_does_nothing(self, tmp_path):
        doc = tmp_path / "README.md"
        doc.write_text("# Test")

        modal = DocsPickerModal(tmp_path)
        modal._docs = [doc]

        scheduled_calls = []
        modal.call_later = lambda fn, *args: scheduled_calls.append((fn, args))

        modal._select_doc(-1)

        assert scheduled_calls == []


class TestDocsPickerModalBindings:
    """Test DocsPickerModal keyboard bindings."""

    def test_bindings_exist(self, tmp_path):
        modal = DocsPickerModal(tmp_path)

        binding_keys = [b.key for b in modal.BINDINGS]

        # Should have bindings for 1-9 and escape
        assert "1" in binding_keys
        assert "2" in binding_keys
        assert "9" in binding_keys
        assert "escape" in binding_keys

    def test_escape_binding_action(self, tmp_path):
        modal = DocsPickerModal(tmp_path)

        bindings = {b.key: b.action for b in modal.BINDINGS}

        assert bindings["escape"] == "cancel"

    def test_number_binding_actions(self, tmp_path):
        modal = DocsPickerModal(tmp_path)

        bindings = {b.key: b.action for b in modal.BINDINGS}

        assert bindings["1"] == "select_1"
        assert bindings["2"] == "select_2"
        assert bindings["9"] == "select_9"


class TestDocsPickerModalCompose:
    """Test DocsPickerModal composition."""

    def test_compose_returns_widgets(self, tmp_path):
        modal = DocsPickerModal(tmp_path)

        # compose returns a generator of widgets
        widgets = list(modal.compose())

        # Should have at least one container with content
        assert len(widgets) > 0

    def test_compose_has_container(self, tmp_path):
        from textual.containers import Container

        modal = DocsPickerModal(tmp_path)
        widgets = list(modal.compose())

        # Should have a container
        containers = [w for w in widgets if isinstance(w, Container)]
        assert len(containers) >= 1


class TestDocsPickerModalCSS:
    """Test DocsPickerModal CSS styling."""

    def test_has_default_css(self):
        assert hasattr(DocsPickerModal, "DEFAULT_CSS")
        assert DocsPickerModal.DEFAULT_CSS is not None
        assert len(DocsPickerModal.DEFAULT_CSS) > 0

    def test_css_contains_modal_styles(self):
        css = DocsPickerModal.DEFAULT_CSS
        assert "DocsPickerModal" in css
        assert "align" in css
        assert "center" in css


class TestDocsPickerModalReturnType:
    """Test that DocsPickerModal returns correct types."""

    def test_returns_none_on_cancel(self, tmp_path):
        modal = DocsPickerModal(tmp_path)

        dismissed_with = []
        modal.dismiss = lambda result: dismissed_with.append(result)

        modal.action_cancel()

        result = dismissed_with[0]
        assert result is None


class TestDocsPickerModalAllSelectionActions:
    """Test all selection action methods (1-9)."""

    def test_all_selection_actions_exist(self, tmp_path):
        modal = DocsPickerModal(tmp_path)

        # All action methods should exist
        assert hasattr(modal, "action_select_1")
        assert hasattr(modal, "action_select_2")
        assert hasattr(modal, "action_select_3")
        assert hasattr(modal, "action_select_4")
        assert hasattr(modal, "action_select_5")
        assert hasattr(modal, "action_select_6")
        assert hasattr(modal, "action_select_7")
        assert hasattr(modal, "action_select_8")
        assert hasattr(modal, "action_select_9")

    def test_each_action_selects_correct_index(self, tmp_path):
        # Create doc files
        docs = []
        for i in range(1, 10):
            doc = tmp_path / f"doc{i}.md"
            doc.write_text(f"# Doc {i}")
            docs.append(doc)

        # Test each action
        for i in range(1, 10):
            modal = DocsPickerModal(tmp_path)
            modal._docs = docs

            scheduled_calls = []
            modal.call_later = lambda fn, *args, sc=scheduled_calls: sc.append(args)

            action_method = getattr(modal, f"action_select_{i}")
            action_method()

            assert len(scheduled_calls) == 1
            assert scheduled_calls[0][0] == docs[i - 1]


class TestDocsPickerModalPriorityOrder:
    """Test that docs are returned in priority order."""

    def test_readme_comes_first(self, tmp_path):
        # Create files in reverse priority order
        (tmp_path / "zzz.md").write_text("last")
        (tmp_path / "CHANGELOG.md").write_text("changelog")
        (tmp_path / "README.md").write_text("readme")

        modal = DocsPickerModal(tmp_path)
        docs = modal._scan_docs()

        # README should be first
        assert docs[0].name == "README.md"

    def test_plan_comes_after_readme(self, tmp_path):
        (tmp_path / "README.md").write_text("readme")
        (tmp_path / "PLAN.md").write_text("plan")
        (tmp_path / "zzz.md").write_text("last")

        modal = DocsPickerModal(tmp_path)
        docs = modal._scan_docs()

        names = [d.name for d in docs]
        assert names.index("README.md") < names.index("PLAN.md")

    def test_priority_files_come_before_other_docs(self, tmp_path):
        (tmp_path / "aaa.md").write_text("first alphabetically")
        (tmp_path / "CONTRIBUTING.md").write_text("contributing")

        modal = DocsPickerModal(tmp_path)
        docs = modal._scan_docs()

        names = [d.name for d in docs]
        assert names.index("CONTRIBUTING.md") < names.index("aaa.md")
