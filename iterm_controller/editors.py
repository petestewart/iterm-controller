"""Editor command mapping utilities.

This module provides a centralized mapping from user-friendly editor names to
their actual command-line commands. This avoids duplication across the codebase.

For security validation of editor commands, see security.py which provides
ALLOWED_EDITOR_COMMANDS and validation functions.
"""

from __future__ import annotations


# Mapping from user-friendly IDE/editor names to their CLI commands.
# Used to resolve configured default_ide to actual executable.
# Note: The resulting command is still validated against ALLOWED_EDITOR_COMMANDS
# in security.py before execution.
EDITOR_COMMANDS: dict[str, str] = {
    # VS Code and variants
    "vscode": "code",
    "code": "code",
    "cursor": "cursor",
    # Vim family
    "vim": "vim",
    "nvim": "nvim",
    "neovim": "nvim",
    # Sublime Text
    "subl": "subl",
    "sublime": "subl",
    # Other editors
    "atom": "atom",
    "nano": "nano",
    "emacs": "emacs",
}


def get_editor_command(ide: str) -> str | None:
    """Get the CLI command for a given IDE/editor name.

    Args:
        ide: The user-friendly IDE name (e.g., "vscode", "neovim").

    Returns:
        The corresponding CLI command (e.g., "code", "nvim"), or None if
        the IDE name is not recognized.

    Examples:
        >>> get_editor_command("vscode")
        'code'
        >>> get_editor_command("neovim")
        'nvim'
        >>> get_editor_command("unknown")
        None
    """
    return EDITOR_COMMANDS.get(ide.lower())
