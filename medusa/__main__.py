"""Entry point for the Medusa CLI.

This module serves as the main entry point when running the medusa package directly.
It imports and calls the main function from the cli module.
"""

from .cli import main

if __name__ == "__main__":  # pragma: no cover
    main()
