"""Entry point for python -m iterm_controller."""

import sys


def main() -> int:
    """Main entry point for the iTerm2 Controller application."""
    from iterm_controller.app import ItermControllerApp

    app = ItermControllerApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
