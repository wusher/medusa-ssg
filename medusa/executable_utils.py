"""Executable discovery utilities for Medusa.

This module provides utility functions for finding executable programs,
supporting both system PATH lookups and local node_modules discovery.

This centralizes executable finding logic that was previously duplicated
across multiple modules (asset_processors.py, assets.py), following the
DRY (Don't Repeat Yourself) principle.

Functions:
    find_executable: Locate an executable in PATH or node_modules.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def find_executable(name: str, project_root: Path | None = None) -> str | None:
    """Find an executable in PATH or local node_modules.

    Searches for an executable first in the system PATH, then in the
    project's local node_modules/.bin directory if a project root is provided.

    Args:
        name: Name of the executable to find (e.g., 'tailwindcss', 'terser').
        project_root: Optional project root directory to search for
            local node_modules installations.

    Returns:
        Full path to the executable if found, None otherwise.

    Examples:
        >>> find_executable('node')  # System PATH lookup
        '/usr/local/bin/node'

        >>> find_executable('tailwindcss', Path('/my/project'))  # With local lookup
        '/my/project/node_modules/.bin/tailwindcss'
    """
    # First check system PATH
    found = shutil.which(name)
    if found:
        return found

    # Then check local node_modules if project_root provided
    if project_root is not None:
        local = project_root / "node_modules" / ".bin" / name
        if local.exists():
            return str(local)

    return None
