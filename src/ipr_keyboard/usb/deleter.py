"""USB file deletion utilities.

Provides functions for deleting files from the IrisPen USB mount point.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, List


def delete_file(path: Path) -> bool:
    """Delete a single file.
    
    Args:
        path: Path to the file to delete.
        
    Returns:
        True if the file was deleted successfully or doesn't exist,
        False if an error occurred during deletion.
    """
    try:
        if path.exists() and path.is_file():
            path.unlink()
        return True
    except OSError:
        return False


def delete_all(folder: Path) -> List[Path]:
    """Delete all files in a folder.
    
    Args:
        folder: Path to the folder containing files to delete.
        
    Returns:
        List of Path objects for successfully deleted files.
    """
    deleted: List[Path] = []
    if not folder.exists():
        return deleted

    for p in folder.iterdir():
        if p.is_file():
            try:
                p.unlink()
                deleted.append(p)
            except OSError:
                continue
    return deleted


def delete_newest(folder: Path) -> Optional[Path]:
    """Delete the newest file in a folder.
    
    Args:
        folder: Path to the folder containing files.
        
    Returns:
        Path to the deleted file if successful, or None if no files exist
        or deletion failed.
    """
    from .detector import newest_file

    newest = newest_file(folder)
    if newest is None:
        return None
    return newest if delete_file(newest) else None
