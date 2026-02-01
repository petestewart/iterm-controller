"""Tests for environment file parser."""

import os
from pathlib import Path

import pytest

from iterm_controller.env_parser import EnvParser, load_env_file


class TestEnvParser:
    """Tests for EnvParser class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.parser = EnvParser()

    def test_parse_simple_key_value(self) -> None:
        """Parse simple KEY=value pairs."""
        content = "FOO=bar"
        result = self.parser.parse(content)
        assert result == {"FOO": "bar"}

    def test_parse_multiple_variables(self) -> None:
        """Parse multiple KEY=value pairs."""
        content = """FOO=bar
BAZ=qux
HELLO=world"""
        result = self.parser.parse(content)
        assert result == {"FOO": "bar", "BAZ": "qux", "HELLO": "world"}

    def test_parse_empty_content(self) -> None:
        """Parse empty content returns empty dict."""
        result = self.parser.parse("")
        assert result == {}

    def test_parse_skip_empty_lines(self) -> None:
        """Skip empty lines in content."""
        content = """FOO=bar

BAZ=qux

"""
        result = self.parser.parse(content)
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_parse_skip_comments(self) -> None:
        """Skip comment lines (starting with #)."""
        content = """# This is a comment
FOO=bar
# Another comment
BAZ=qux"""
        result = self.parser.parse(content)
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_parse_double_quoted_value(self) -> None:
        """Parse double-quoted values."""
        content = 'FOO="bar baz"'
        result = self.parser.parse(content)
        assert result == {"FOO": "bar baz"}

    def test_parse_single_quoted_value(self) -> None:
        """Parse single-quoted values."""
        content = "FOO='bar baz'"
        result = self.parser.parse(content)
        assert result == {"FOO": "bar baz"}

    def test_parse_value_with_equals_sign(self) -> None:
        """Value containing = is preserved."""
        content = "DATABASE_URL=postgres://user:pass@host:5432/db?option=value"
        result = self.parser.parse(content)
        assert result == {
            "DATABASE_URL": "postgres://user:pass@host:5432/db?option=value"
        }

    def test_parse_strips_whitespace(self) -> None:
        """Strip whitespace around key and value."""
        content = "  FOO  =  bar  "
        result = self.parser.parse(content)
        assert result == {"FOO": "bar"}

    def test_parse_empty_value(self) -> None:
        """Empty value is allowed."""
        content = "FOO="
        result = self.parser.parse(content)
        assert result == {"FOO": ""}

    def test_parse_value_with_hash(self) -> None:
        """Value with # is preserved (not treated as inline comment)."""
        content = 'COLOR="#ff0000"'
        result = self.parser.parse(content)
        assert result == {"COLOR": "#ff0000"}

    def test_expand_internal_variable_reference(self) -> None:
        """Expand ${VAR} references from parsed env."""
        content = """BASE_URL=http://localhost
API_URL=${BASE_URL}/api"""
        result = self.parser.parse(content)
        assert result == {
            "BASE_URL": "http://localhost",
            "API_URL": "http://localhost/api",
        }

    def test_expand_system_variable_reference(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Expand ${VAR} references from system environment."""
        monkeypatch.setenv("SYSTEM_VAR", "system_value")
        content = "FOO=${SYSTEM_VAR}"
        result = self.parser.parse(content)
        assert result == {"FOO": "system_value"}

    def test_expand_unknown_variable_to_empty(self) -> None:
        """Unknown variable references expand to empty string."""
        content = "FOO=${UNKNOWN_VAR}"
        result = self.parser.parse(content)
        assert result == {"FOO": ""}

    def test_expand_multiple_references(self) -> None:
        """Expand multiple ${VAR} references in one value."""
        content = """HOST=localhost
PORT=3000
URL=http://${HOST}:${PORT}"""
        result = self.parser.parse(content)
        assert result == {
            "HOST": "localhost",
            "PORT": "3000",
            "URL": "http://localhost:3000",
        }

    def test_internal_takes_precedence_over_system(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Internal env var takes precedence over system env."""
        monkeypatch.setenv("FOO", "system_foo")
        content = """FOO=internal_foo
BAR=${FOO}"""
        result = self.parser.parse(content)
        assert result == {"FOO": "internal_foo", "BAR": "internal_foo"}


class TestEnvParserLoadFile:
    """Tests for EnvParser.load_file method."""

    def test_load_existing_file(self, tmp_path: Path) -> None:
        """Load environment from existing .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=qux")

        parser = EnvParser()
        result = parser.load_file(env_file)
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """Return empty dict for nonexistent file."""
        env_file = tmp_path / ".env"

        parser = EnvParser()
        result = parser.load_file(env_file)
        assert result == {}

    def test_load_file_with_string_path(self, tmp_path: Path) -> None:
        """Load file when path is provided as string."""
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar")

        parser = EnvParser()
        result = parser.load_file(str(env_file))
        assert result == {"FOO": "bar"}


class TestLoadEnvFileFunction:
    """Tests for the load_env_file convenience function."""

    def test_load_existing_file(self, tmp_path: Path) -> None:
        """Load environment using convenience function."""
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar")

        result = load_env_file(env_file)
        assert result == {"FOO": "bar"}

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """Return empty dict for nonexistent file."""
        result = load_env_file(tmp_path / ".env")
        assert result == {}


class TestEdgeCases:
    """Tests for edge cases and complex scenarios."""

    def test_mixed_quotes_preserved(self) -> None:
        """Mixed quotes inside value are preserved."""
        parser = EnvParser()
        content = """MSG="He said 'hello'"\n"""
        result = parser.parse(content)
        assert result == {"MSG": "He said 'hello'"}

    def test_unicode_values(self) -> None:
        """Unicode values are handled correctly."""
        parser = EnvParser()
        content = "GREETING=Hello, 世界!"
        result = parser.parse(content)
        assert result == {"GREETING": "Hello, 世界!"}

    def test_multiline_quoted_value_not_supported(self) -> None:
        """Multiline values are not supported (each line is separate)."""
        parser = EnvParser()
        content = '''FOO="line1
line2"'''
        result = parser.parse(content)
        # The second line doesn't have = so it's ignored
        assert result == {"FOO": '"line1'}

    def test_export_prefix_not_supported(self) -> None:
        """export prefix is treated as part of the key."""
        parser = EnvParser()
        content = "export FOO=bar"
        result = parser.parse(content)
        # 'export FOO' becomes the key
        assert result == {"export FOO": "bar"}

    def test_line_with_only_whitespace(self) -> None:
        """Lines with only whitespace are skipped."""
        parser = EnvParser()
        content = "FOO=bar\n   \t\nBAZ=qux"
        result = parser.parse(content)
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_key_with_underscore(self) -> None:
        """Keys with underscores are valid."""
        parser = EnvParser()
        content = "MY_LONG_KEY=value"
        result = parser.parse(content)
        assert result == {"MY_LONG_KEY": "value"}

    def test_key_with_numbers(self) -> None:
        """Keys with numbers are valid."""
        parser = EnvParser()
        content = "KEY123=value"
        result = parser.parse(content)
        assert result == {"KEY123": "value"}

    def test_quoted_empty_value(self) -> None:
        """Quoted empty value is preserved as empty."""
        parser = EnvParser()
        content = 'FOO=""'
        result = parser.parse(content)
        assert result == {"FOO": ""}

    def test_variable_in_quoted_value(self) -> None:
        """Variable expansion works inside quoted values."""
        parser = EnvParser()
        content = """BASE=http://localhost
URL="${BASE}/api\""""
        result = parser.parse(content)
        assert result == {"BASE": "http://localhost", "URL": "http://localhost/api"}
