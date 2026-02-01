"""Entry point for python -m iterm_controller."""

import argparse
import sys


def main() -> int:
    """Main entry point for the iTerm2 Controller application."""
    parser = argparse.ArgumentParser(
        description="iTerm2 Project Orchestrator - A control room for dev projects"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging to console",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set log level (default: INFO)",
    )
    parser.add_argument(
        "--no-log-file",
        action="store_true",
        help="Disable logging to file",
    )
    args = parser.parse_args()

    # Initialize logging
    from iterm_controller.logging_config import setup_logging

    if args.debug:
        setup_logging(
            level="DEBUG",
            log_to_console=True,
            log_to_file=True,
        )
    else:
        setup_logging(
            level=args.log_level,
            log_to_console=False,
            log_to_file=not args.no_log_file,
        )

    from iterm_controller.app import ItermControllerApp

    app = ItermControllerApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
