"""Tests for test command detection.

Tests the TestCommandDetector class which auto-detects test commands
based on project files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from iterm_controller.test_command_detector import (
    TestCommandConfig,
    TestCommandDetector,
    detect_test_command,
    detect_watch_command,
)


class TestTestCommandDetector:
    """Tests for TestCommandDetector."""

    def test_detect_from_pytest_ini(self, tmp_path: Path) -> None:
        """Should detect pytest from pytest.ini."""
        (tmp_path / "pytest.ini").write_text("[pytest]\n")

        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        assert result.test_command == "pytest"
        assert result.watch_command == "pytest-watch"
        assert result.source == "pytest.ini"

    def test_detect_from_pyproject_toml_with_pytest(self, tmp_path: Path) -> None:
        """Should detect pytest from pyproject.toml with [tool.pytest] section."""
        content = """
[project]
name = "my-project"

[tool.pytest.ini_options]
testpaths = ["tests"]
"""
        (tmp_path / "pyproject.toml").write_text(content)

        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        assert result.test_command == "pytest"
        assert result.source == "pyproject.toml"

    def test_skip_pyproject_toml_without_pytest(self, tmp_path: Path) -> None:
        """Should not detect pytest from pyproject.toml without pytest config."""
        content = """
[project]
name = "my-project"
dependencies = ["requests"]
"""
        (tmp_path / "pyproject.toml").write_text(content)

        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        assert result.test_command == ""
        assert result.source == ""

    def test_detect_pytest_in_dependencies(self, tmp_path: Path) -> None:
        """Should detect pytest from pyproject.toml with pytest in dependencies."""
        content = """
[project]
name = "my-project"
dependencies = ["pytest", "pytest-cov"]
"""
        (tmp_path / "pyproject.toml").write_text(content)

        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        assert result.test_command == "pytest"
        assert result.source == "pyproject.toml"

    def test_detect_from_package_json_with_test_script(self, tmp_path: Path) -> None:
        """Should detect npm test from package.json with test script."""
        content = {
            "name": "my-project",
            "scripts": {
                "test": "jest",
                "build": "webpack",
            },
        }
        (tmp_path / "package.json").write_text(json.dumps(content))

        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        assert result.test_command == "npm test"
        assert result.watch_command == "npm test -- --watch"
        assert result.source == "package.json"

    def test_skip_package_json_without_test_script(self, tmp_path: Path) -> None:
        """Should not detect npm test from package.json without test script."""
        content = {
            "name": "my-project",
            "scripts": {
                "build": "webpack",
            },
        }
        (tmp_path / "package.json").write_text(json.dumps(content))

        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        assert result.test_command == ""

    def test_skip_package_json_with_placeholder_test(self, tmp_path: Path) -> None:
        """Should not detect npm test if test script is the npm placeholder."""
        content = {
            "name": "my-project",
            "scripts": {
                "test": 'echo "Error: no test specified" && exit 1',
            },
        }
        (tmp_path / "package.json").write_text(json.dumps(content))

        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        assert result.test_command == ""

    def test_detect_from_makefile_with_test_target(self, tmp_path: Path) -> None:
        """Should detect make test from Makefile with test target."""
        content = """
.PHONY: build test clean

build:
\tgo build

test:
\tgo test ./...

clean:
\trm -rf build/
"""
        (tmp_path / "Makefile").write_text(content)

        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        assert result.test_command == "make test"
        assert result.source == "Makefile"

    def test_skip_makefile_without_test_target(self, tmp_path: Path) -> None:
        """Should not detect make test from Makefile without test target."""
        content = """
.PHONY: build clean

build:
\tgo build

clean:
\trm -rf build/
"""
        (tmp_path / "Makefile").write_text(content)

        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        assert result.test_command == ""

    def test_detect_from_cargo_toml(self, tmp_path: Path) -> None:
        """Should detect cargo test from Cargo.toml."""
        content = """
[package]
name = "my-project"
version = "0.1.0"
"""
        (tmp_path / "Cargo.toml").write_text(content)

        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        assert result.test_command == "cargo test"
        assert result.watch_command == "cargo watch -x test"
        assert result.source == "Cargo.toml"

    def test_detect_from_go_mod(self, tmp_path: Path) -> None:
        """Should detect go test from go.mod."""
        content = """
module example.com/my-project

go 1.21
"""
        (tmp_path / "go.mod").write_text(content)

        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        assert result.test_command == "go test ./..."
        assert result.watch_command == ""  # No standard watch for Go
        assert result.source == "go.mod"

    def test_detection_order_priority(self, tmp_path: Path) -> None:
        """Should prefer earlier files in detection order."""
        # Create both pytest.ini and package.json
        (tmp_path / "pytest.ini").write_text("[pytest]\n")
        content = {
            "name": "my-project",
            "scripts": {"test": "jest"},
        }
        (tmp_path / "package.json").write_text(json.dumps(content))

        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        # pytest.ini comes before package.json in detection order
        assert result.test_command == "pytest"
        assert result.source == "pytest.ini"

    def test_config_override_takes_precedence(self, tmp_path: Path) -> None:
        """Should use config override when provided."""
        # Create pytest.ini (would normally be detected)
        (tmp_path / "pytest.ini").write_text("[pytest]\n")

        # Provide config override
        project_config = {
            "test_command": "custom-test-runner",
            "test_watch_command": "custom-watch",
        }

        detector = TestCommandDetector(tmp_path)
        result = detector.detect(project_config)

        assert result.test_command == "custom-test-runner"
        assert result.watch_command == "custom-watch"
        assert result.source == "config"

    def test_no_project_files(self, tmp_path: Path) -> None:
        """Should return empty config when no project files found."""
        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        assert result.test_command == ""
        assert result.watch_command == ""
        assert result.source == ""


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_detect_test_command(self, tmp_path: Path) -> None:
        """Should detect test command using convenience function."""
        (tmp_path / "pytest.ini").write_text("[pytest]\n")

        command = detect_test_command(tmp_path)
        assert command == "pytest"

    def test_detect_test_command_with_config(self, tmp_path: Path) -> None:
        """Should respect config override in convenience function."""
        (tmp_path / "pytest.ini").write_text("[pytest]\n")

        command = detect_test_command(tmp_path, {"test_command": "custom"})
        assert command == "custom"

    def test_detect_watch_command(self, tmp_path: Path) -> None:
        """Should detect watch command using convenience function."""
        (tmp_path / "pytest.ini").write_text("[pytest]\n")

        command = detect_watch_command(tmp_path)
        assert command == "pytest-watch"

    def test_detect_watch_command_with_config(self, tmp_path: Path) -> None:
        """Should respect config override in convenience function."""
        (tmp_path / "pytest.ini").write_text("[pytest]\n")

        command = detect_watch_command(tmp_path, {"test_watch_command": "custom-watch"})
        # Note: test_command also needs to be set for watch to be returned
        # When only test_watch_command is in config without test_command,
        # the detector falls through to file detection
        command = detect_watch_command(
            tmp_path,
            {"test_command": "pytest", "test_watch_command": "custom-watch"},
        )
        assert command == "custom-watch"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_invalid_package_json(self, tmp_path: Path) -> None:
        """Should handle invalid JSON in package.json gracefully."""
        (tmp_path / "package.json").write_text("not valid json {")

        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        # Should not crash and should skip this file
        assert result.test_command == ""

    def test_unreadable_file(self, tmp_path: Path) -> None:
        """Should handle unreadable files gracefully."""
        file_path = tmp_path / "pyproject.toml"
        file_path.write_text("[tool.pytest]")
        # Make file unreadable (may not work on all platforms)
        try:
            file_path.chmod(0o000)

            detector = TestCommandDetector(tmp_path)
            # Should not crash
            result = detector.detect()

        finally:
            # Restore permissions for cleanup
            file_path.chmod(0o644)

    def test_empty_files(self, tmp_path: Path) -> None:
        """Should handle empty files gracefully."""
        (tmp_path / "pyproject.toml").write_text("")
        (tmp_path / "package.json").write_text("")
        (tmp_path / "Makefile").write_text("")

        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        # Empty files don't indicate test support
        assert result.test_command == ""

    def test_makefile_tests_plural(self, tmp_path: Path) -> None:
        """Should detect 'tests:' target as well as 'test:'."""
        content = """
tests:
\tpytest
"""
        (tmp_path / "Makefile").write_text(content)

        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        assert result.test_command == "make test"

    def test_pyproject_with_pytest_in_optional_deps(self, tmp_path: Path) -> None:
        """Should detect pytest in optional dependencies."""
        content = """
[project]
name = "my-project"

[project.optional-dependencies]
dev = ["pytest", "black"]
"""
        (tmp_path / "pyproject.toml").write_text(content)

        detector = TestCommandDetector(tmp_path)
        result = detector.detect()

        assert result.test_command == "pytest"
