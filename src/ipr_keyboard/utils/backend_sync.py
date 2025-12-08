"""Utilities for synchronizing backend selection between config.json and /etc/ipr-keyboard/backend.

This module provides functions to read and write the /etc/ipr-keyboard/backend file,
ensuring that the system-level backend selection stays in sync with the application config.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

BACKEND_FILE_PATH = "/etc/ipr-keyboard/backend"


def read_backend_file() -> Optional[str]:
    """Read the current backend selection from /etc/ipr-keyboard/backend.
    
    Returns:
        The backend type ("uinput" or "ble"), or None if the file doesn't exist or is unreadable.
    """
    try:
        if os.path.exists(BACKEND_FILE_PATH):
            with open(BACKEND_FILE_PATH, "r") as f:
                backend = f.read().strip()
                # Normalize to valid values
                if backend in ("uinput", "ble"):
                    return backend
    except (OSError, PermissionError):
        pass
    return None


def write_backend_file(backend: str) -> bool:
    """Write the backend selection to /etc/ipr-keyboard/backend.
    
    Args:
        backend: The backend type to write ("uinput" or "ble").
        
    Returns:
        True if successful, False if the write failed (e.g., insufficient permissions).
    """
    if backend not in ("uinput", "ble"):
        return False
    
    try:
        # Ensure directory exists
        backend_dir = Path(BACKEND_FILE_PATH).parent
        backend_dir.mkdir(parents=True, exist_ok=True)
        
        with open(BACKEND_FILE_PATH, "w") as f:
            f.write(backend + "\n")
        return True
    except (OSError, PermissionError):
        return False
