""".env file parsing.

Parses .env files for environment variables and placeholder resolution.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


class EnvParser:
    """Parses .env files for environment variables.

    Supports:
    - KEY=value format
    - Comments (lines starting with #)
    - Quoted values (single or double quotes)
    - Variable expansion with ${VAR} syntax
    """

    VAR_PATTERN = re.compile(r"\$\{(\w+)\}")

    def parse(self, content: str) -> dict[str, str]:
        """Parse .env file content.

        Args:
            content: Raw content of a .env file

        Returns:
            Dictionary of environment variables with expanded values
        """
        env: dict[str, str] = {}

        for line in content.splitlines():
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Parse KEY=value
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = self._parse_value(value.strip())
                env[key] = value

        # Expand variable references
        return self._expand_vars(env)

    def _parse_value(self, value: str) -> str:
        """Parse value, handling quotes.

        Args:
            value: Raw value string (may be quoted)

        Returns:
            Value with surrounding quotes removed
        """
        # Remove surrounding quotes (double or single)
        if len(value) >= 2:
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]

        return value

    def _expand_vars(self, env: dict[str, str]) -> dict[str, str]:
        """Expand ${VAR} references.

        Variables are resolved in the following order:
        1. From the parsed env dict itself
        2. From the system environment (os.environ)
        3. Empty string if not found

        Args:
            env: Dictionary of parsed environment variables

        Returns:
            Dictionary with all ${VAR} references expanded
        """
        result: dict[str, str] = {}

        for key, value in env.items():
            # Expand ${VAR} references
            def replace(match: re.Match[str]) -> str:
                var_name = match.group(1)
                # First check parsed env, then system env
                return env.get(var_name, os.environ.get(var_name, ""))

            result[key] = self.VAR_PATTERN.sub(replace, value)

        return result

    def load_file(self, path: Path | str) -> dict[str, str]:
        """Load environment from .env file.

        Args:
            path: Path to the .env file

        Returns:
            Dictionary of environment variables, or empty dict if file doesn't exist
        """
        path = Path(path)
        if not path.exists():
            return {}
        return self.parse(path.read_text())


def load_env_file(path: Path | str) -> dict[str, str]:
    """Convenience function to load environment from a .env file.

    Args:
        path: Path to the .env file

    Returns:
        Dictionary of environment variables, or empty dict if file doesn't exist
    """
    return EnvParser().load_file(path)
