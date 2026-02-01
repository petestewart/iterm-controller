"""Tests for the installation script functionality."""

import subprocess
import sys
from pathlib import Path

import pytest


INSTALL_SCRIPT = Path(__file__).parent.parent / "install.sh"


class TestInstallScriptSyntax:
    """Test that the install script has valid syntax."""

    def test_script_exists(self):
        """Install script should exist."""
        assert INSTALL_SCRIPT.exists()

    def test_script_is_executable(self):
        """Install script should be executable."""
        import os

        assert os.access(INSTALL_SCRIPT, os.X_OK)

    def test_script_has_valid_bash_syntax(self):
        """Install script should have valid bash syntax."""
        result = subprocess.run(
            ["bash", "-n", str(INSTALL_SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Bash syntax error: {result.stderr}"

    def test_script_passes_shellcheck(self):
        """Install script should pass shellcheck if available."""
        # Check if shellcheck is installed
        which_result = subprocess.run(
            ["which", "shellcheck"],
            capture_output=True,
        )
        if which_result.returncode != 0:
            pytest.skip("shellcheck not installed")

        result = subprocess.run(
            ["shellcheck", "-x", str(INSTALL_SCRIPT)],
            capture_output=True,
            text=True,
        )
        # Allow SC2086 (double quote to prevent globbing) as it's often intentional
        # and SC1090/SC1091 (can't follow non-constant source)
        if result.returncode != 0:
            # Filter out acceptable warnings
            errors = [
                line
                for line in result.stdout.split("\n")
                if line and not any(
                    code in line
                    for code in ["SC2086", "SC1090", "SC1091", "SC2034"]
                )
            ]
            if errors:
                pytest.fail(f"Shellcheck errors:\n{chr(10).join(errors)}")


class TestInstallScriptHelp:
    """Test the install script help functionality."""

    def test_help_flag_shows_usage(self):
        """--help should show usage information."""
        result = subprocess.run(
            ["bash", str(INSTALL_SCRIPT), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Usage" in result.stdout or "usage" in result.stdout.lower()

    def test_unknown_option_fails(self):
        """Unknown options should cause an error."""
        result = subprocess.run(
            ["bash", str(INSTALL_SCRIPT), "--unknown-option"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "Unknown option" in result.stderr or "Unknown option" in result.stdout


class TestInstallScriptFunctions:
    """Test individual functions from the install script using sourcing."""

    def test_version_comparison_function(self):
        """Test version comparison logic."""
        # Source the script and test the version_gte function
        test_script = """
        source "{script}"

        # Test cases: version_gte returns 0 if first >= second
        version_gte "3.11" "3.11" && echo "3.11>=3.11:pass" || echo "3.11>=3.11:fail"
        version_gte "3.12" "3.11" && echo "3.12>=3.11:pass" || echo "3.12>=3.11:fail"
        version_gte "3.10" "3.11" && echo "3.10>=3.11:pass" || echo "3.10>=3.11:fail"
        version_gte "3.11.5" "3.11" && echo "3.11.5>=3.11:pass" || echo "3.11.5>=3.11:fail"
        """.format(script=INSTALL_SCRIPT)

        result = subprocess.run(
            ["bash", "-c", test_script],
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin"},  # Minimal PATH to avoid running checks
        )

        output = result.stdout
        assert "3.11>=3.11:pass" in output
        assert "3.12>=3.11:pass" in output
        assert "3.10>=3.11:fail" in output
        assert "3.11.5>=3.11:pass" in output


class TestInstallScriptContent:
    """Test the content of the install script."""

    def test_script_has_shebang(self):
        """Script should start with bash shebang."""
        content = INSTALL_SCRIPT.read_text()
        assert content.startswith("#!/bin/bash")

    def test_script_has_set_e(self):
        """Script should use set -e for error handling."""
        content = INSTALL_SCRIPT.read_text()
        assert "set -e" in content

    def test_script_checks_for_macos(self):
        """Script should check for macOS."""
        content = INSTALL_SCRIPT.read_text()
        assert "Darwin" in content

    def test_script_checks_python_version(self):
        """Script should check for Python 3.11+."""
        content = INSTALL_SCRIPT.read_text()
        assert "3.11" in content
        assert "python" in content.lower()

    def test_script_checks_iterm(self):
        """Script should check for iTerm2."""
        content = INSTALL_SCRIPT.read_text()
        assert "iTerm" in content

    def test_script_enables_iterm_api(self):
        """Script should enable iTerm2 Python API."""
        content = INSTALL_SCRIPT.read_text()
        assert "EnableAPIServer" in content

    def test_script_creates_config_directory(self):
        """Script should create config directory."""
        content = INSTALL_SCRIPT.read_text()
        assert ".config/iterm-controller" in content

    def test_script_has_default_config(self):
        """Script should create default configuration."""
        content = INSTALL_SCRIPT.read_text()
        assert "config.json" in content
        assert "default_ide" in content

    def test_script_installs_optional_dependencies(self):
        """Script should handle optional dependencies."""
        content = INSTALL_SCRIPT.read_text()
        assert "terminal-notifier" in content
        assert "gh" in content

    def test_script_supports_skip_optional_flag(self):
        """Script should support --skip-optional flag."""
        content = INSTALL_SCRIPT.read_text()
        assert "--skip-optional" in content

    def test_script_supports_no_venv_flag(self):
        """Script should support --no-venv flag."""
        content = INSTALL_SCRIPT.read_text()
        assert "--no-venv" in content


class TestDefaultConfig:
    """Test the default configuration created by the install script."""

    def test_default_config_is_valid_json(self):
        """Default config embedded in script should be valid JSON."""
        import json
        import re

        content = INSTALL_SCRIPT.read_text()

        # Extract the JSON config from the script (between << 'EOF' and EOF)
        # Find the config.json heredoc
        match = re.search(
            r"cat > \"\$CONFIG_DIR/config\.json\" << 'EOF'\n(.*?)\nEOF",
            content,
            re.DOTALL,
        )
        assert match, "Could not find config.json heredoc in script"

        config_json = match.group(1)

        # Should be valid JSON
        try:
            config = json.loads(config_json)
        except json.JSONDecodeError as e:
            pytest.fail(f"Default config is not valid JSON: {e}")

        # Check required keys
        assert "settings" in config
        assert "projects" in config
        assert "templates" in config
        assert "session_templates" in config

        # Check settings
        settings = config["settings"]
        assert "default_ide" in settings
        assert "polling_interval_ms" in settings
        assert "notification_enabled" in settings

    def test_default_session_templates(self):
        """Default config should include useful session templates."""
        import json
        import re

        content = INSTALL_SCRIPT.read_text()

        match = re.search(
            r"cat > \"\$CONFIG_DIR/config\.json\" << 'EOF'\n(.*?)\nEOF",
            content,
            re.DOTALL,
        )
        config = json.loads(match.group(1))

        templates = config["session_templates"]
        template_ids = {t["id"] for t in templates}

        # Should have common templates
        assert "shell" in template_ids
        assert "editor" in template_ids


class TestInstallScriptDryRun:
    """Test dry run behavior of install script."""

    @pytest.mark.skipif(
        sys.platform != "darwin",
        reason="macOS-specific installation test",
    )
    def test_macos_check_passes_on_macos(self):
        """macOS check should pass on macOS."""
        test_script = f"""
        source "{INSTALL_SCRIPT}"
        check_macos
        """

        result = subprocess.run(
            ["bash", "-c", test_script],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "macOS" in result.stdout

    @pytest.mark.skipif(
        sys.platform != "darwin",
        reason="macOS-specific installation test",
    )
    def test_python_check_finds_python(self):
        """Python check should find a valid Python version."""
        test_script = f"""
        source "{INSTALL_SCRIPT}"
        check_python
        echo "PYTHON_CMD=$PYTHON_CMD"
        """

        result = subprocess.run(
            ["bash", "-c", test_script],
            capture_output=True,
            text=True,
        )
        # Should find Python
        assert "PYTHON_CMD=" in result.stdout
        # Should be python3.x
        assert "python3" in result.stdout.lower()
