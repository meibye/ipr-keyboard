"""USB file detection and monitoring utilities.

Provides functions for detecting and waiting for new files from the IrisPen scanner.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional


def list_files(folder: Path) -> List[Path]:
    """List all files in a folder, sorted by modification time.
    
    Args:
        folder: Path to the folder to list files from.
        
    Returns:
        List of Path objects sorted by modification time (oldest first),
        or an empty list if the folder doesn't exist.
    """
    if not folder.exists():
        return []
    return sorted(
        [p for p in folder.iterdir() if p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )


def newest_file(folder: Path) -> Optional[Path]:
    """Get the newest file in a folder by modification time.
    
    Args:
        folder: Path to the folder to search.
        
    Returns:
        Path to the newest file, or None if the folder is empty or doesn't exist.
    """
    files = list_files(folder)
    if not files:
        return None
    return files[-1]


def wait_for_new_file(
    folder: Path, last_seen_mtime: float, interval: float = 1.0
) -> Optional[Path]:
    """Poll a folder until a new file appears.
    
    Continuously polls the folder at the specified interval until a file
    with a modification time newer than last_seen_mtime is found.
    
    Args:
        folder: Path to the folder to monitor.
        last_seen_mtime: Timestamp of the last seen file. Only files newer
            than this will be detected.
        interval: Sleep interval in seconds between checks (default: 1.0).
        
    Returns:
        Path to the new file, or None if the folder doesn't exist.
        Note: This function will block indefinitely until a new file appears.
    """
    while True:
        if not folder.exists():
            time.sleep(interval)
            continue

        files = list_files(folder)
        if files:
            newest = files[-1]
            mtime = newest.stat().st_mtime
            if mtime > last_seen_mtime:
                return newest
        time.sleep(interval)
