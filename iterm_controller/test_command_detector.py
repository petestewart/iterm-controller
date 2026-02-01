"""Test command detection for different project types.

Auto-detects the test command based on project files like pytest.ini,
pyproject.toml, package.json, Makefile, Cargo.toml, and go.mod.

See specs/test-mode.md#test-command-detection for specification.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TestCommandConfig:
    """Detected or configured test commands."""

    test_command: str = ""
    watch_command: str = ""
    source: str = ""  # How the command was determined (e.g., "config", "pyproject.toml")


class TestCommandDetector:
    """Detects the test command for a project.

    Detection order (from spec):
    1. Project config override (test_command in .iterm-controller.json)
    2. pytest.ini -> pytest
    3. pyproject.toml -> pytest (if [tool.pytest] section exists)
    4. package.json -> npm test (if "test" script exists)
    5. Makefile -> make test (if test target exists)
    6. Cargo.toml -> cargo test
    7. go.mod -> go test ./...
    """

    # Default detection order - maps filename to (detection_func, default_command)
    DETECTION_ORDER = [
        ("pytest.ini", "pytest"),
        ("pyproject.toml", "pytest"),  # Requires [tool.pytest] section
        ("package.json", "npm test"),  # Requires "test" script
        ("Makefile", "make test"),  # Requires test target
        ("Cargo.toml", "cargo test"),
        ("go.mod", "go test ./..."),
    ]

    # Watch commands for each test runner
    WATCH_COMMANDS = {
        "pytest": "pytest-watch",
        "npm test": "npm test -- --watch",
        "cargo test": "cargo watch -x test",
        "go test ./...": "",  # No standard watch mode for Go
        "make test": "",  # Depends on Makefile
    }

    def __init__(self, project_path: str | Path):
        """Initialize the detector.

        Args:
            project_path: Path to the project root directory.
        """
        self.project_path = Path(project_path)

    def detect(self, project_config: dict | None = None) -> TestCommandConfig:
        """Detect the test command for the project.

        Args:
            project_config: Optional project configuration dict from
                           .iterm-controller.json. May contain test_command
                           and test_watch_command overrides.

        Returns:
            TestCommandConfig with detected or configured commands.
        """
        # 1. Check for explicit config override
        if project_config:
            test_cmd = project_config.get("test_command")
            watch_cmd = project_config.get("test_watch_command", "")

            if test_cmd:
                logger.debug("Using configured test_command: %s", test_cmd)
                return TestCommandConfig(
                    test_command=test_cmd,
                    watch_command=watch_cmd,
                    source="config",
                )

        # 2. Auto-detect from project files
        for filename, default_command in self.DETECTION_ORDER:
            file_path = self.project_path / filename
            if not file_path.exists():
                continue

            # Check if file actually indicates test support
            if self._file_supports_tests(file_path, filename):
                watch_cmd = self.WATCH_COMMANDS.get(default_command, "")
                logger.debug(
                    "Detected test command from %s: %s", filename, default_command
                )
                return TestCommandConfig(
                    test_command=default_command,
                    watch_command=watch_cmd,
                    source=filename,
                )

        logger.debug("No test command detected for project")
        return TestCommandConfig()

    def _file_supports_tests(self, file_path: Path, filename: str) -> bool:
        """Check if the file actually indicates test support.

        Some files need content inspection to verify they support tests.

        Args:
            file_path: Path to the file.
            filename: Name of the file.

        Returns:
            True if the file indicates test support.
        """
        # Files that always indicate test support when present
        if filename in ("pytest.ini", "Cargo.toml", "go.mod"):
            return True

        # Files that need content inspection
        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Failed to read %s: %s", file_path, e)
            return False

        if filename == "pyproject.toml":
            return self._pyproject_has_pytest(content)
        elif filename == "package.json":
            return self._package_json_has_test_script(content)
        elif filename == "Makefile":
            return self._makefile_has_test_target(content)

        return True

    def _pyproject_has_pytest(self, content: str) -> bool:
        """Check if pyproject.toml has pytest configuration.

        Looks for [tool.pytest] or [tool.pytest.ini_options] sections.

        Args:
            content: Content of pyproject.toml.

        Returns:
            True if pytest configuration found.
        """
        # Simple check for pytest tool section
        # Matches [tool.pytest], [tool.pytest.ini_options], etc.
        if re.search(r"\[tool\.pytest", content):
            return True

        # Also check for pytest in dependencies (pyproject.toml format)
        # Check in [project.dependencies], [project.optional-dependencies.dev], etc.
        if re.search(r'["\'](pytest|pytest-[a-zA-Z]+)["\']', content):
            return True

        return False

    def _package_json_has_test_script(self, content: str) -> bool:
        """Check if package.json has a test script.

        Args:
            content: Content of package.json.

        Returns:
            True if a test script is defined.
        """
        try:
            data = json.loads(content)
            scripts = data.get("scripts", {})

            # Check if test script exists and is not the npm placeholder
            test_script = scripts.get("test", "")
            if test_script and "no test specified" not in test_script.lower():
                return True

            return False

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse package.json: %s", e)
            return False

    def _makefile_has_test_target(self, content: str) -> bool:
        """Check if Makefile has a test target.

        Args:
            content: Content of Makefile.

        Returns:
            True if a test target is defined.
        """
        # Look for test: target at the start of a line
        # Handles tabs and spaces before the colon
        if re.search(r"^test\s*:", content, re.MULTILINE):
            return True

        # Also check for common variations
        if re.search(r"^tests?\s*:", content, re.MULTILINE):
            return True

        return False


def detect_test_command(
    project_path: str | Path,
    project_config: dict | None = None,
) -> str:
    """Convenience function to detect test command for a project.

    Args:
        project_path: Path to the project root directory.
        project_config: Optional project configuration dict.

    Returns:
        The detected test command, or empty string if none found.
    """
    detector = TestCommandDetector(project_path)
    result = detector.detect(project_config)
    return result.test_command


def detect_watch_command(
    project_path: str | Path,
    project_config: dict | None = None,
) -> str:
    """Convenience function to detect watch command for a project.

    Args:
        project_path: Path to the project root directory.
        project_config: Optional project configuration dict.

    Returns:
        The detected watch command, or empty string if none found.
    """
    detector = TestCommandDetector(project_path)
    result = detector.detect(project_config)
    return result.watch_command
