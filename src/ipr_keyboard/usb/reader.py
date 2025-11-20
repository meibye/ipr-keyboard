"""USB file reading utilities.

Provides functions for reading text files from the IrisPen USB mount point.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


def read_file(path: Path, max_size: int) -> Optional[str]:
    """Read a text file with size limit.
    
    Args:
        path: Path to the file to read.
        max_size: Maximum file size in bytes. Files larger than this
            will not be read.
            
    Returns:
        File contents as a string, or None if the file doesn't exist,
        is not a regular file, or exceeds the size limit.
    """
    if not path.exists() or not path.is_file():
        return None
    if path.stat().st_size > max_size:
        return None
    return path.read_text(encoding="utf-8", errors="ignore")


def read_newest(folder: Path, max_size: int) -> Optional[str]:
    """Read the newest file in a folder.
    
    Args:
        folder: Path to the folder containing files.
        max_size: Maximum file size in bytes.
        
    Returns:
        Contents of the newest file, or None if no files exist or
        the newest file is too large.
    """
    from .detector import newest_file

    newest = newest_file(folder)
    if newest is None:
        return None
    return read_file(newest, max_size)
