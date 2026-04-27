"""USB file detection and monitoring utilities.

Provides functions for detecting and waiting for new files from the IrisPen scanner.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import List, Optional

_log = logging.getLogger(__name__)


VERSION = '2026-04-12 19:41:04'

def log_version_info():
    import logging
    logging.getLogger(__name__).info(f"==== ipr_keyboard.usb.detector VERSION: {VERSION} ====")


def list_files(folder: Path, pattern: str = "*.txt") -> List[Path]:
    """List files matching pattern under folder (recursive), sorted by modification time.

    Args:
        folder: Root path to search.
        pattern: Glob pattern passed to rglob (default ``"*.txt"``).

    Returns:
        List of Path objects sorted by modification time (oldest first),
        or an empty list if the folder doesn't exist.
    """
    try:
        if not folder.exists():
            return []
    except OSError as exc:
        _log.warning("list_files: cannot access folder %s: %s", folder, exc)
        return []

    files: list[tuple[float, str, Path]] = []
    try:
        for path in folder.rglob(pattern):
            try:
                if not path.is_file():
                    continue
                mtime = path.stat().st_mtime
                files.append((mtime, path.name, path))
            except OSError:
                continue
    except OSError as exc:
        _log.warning("list_files: failed while scanning %s: %s", folder, exc)
        return []

    files.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in files]


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
    polls = 0
    while True:
        try:
            folder_exists = folder.exists()
        except OSError as exc:
            _log.warning("wait_for_new_file: folder access failed for %s: %s", folder, exc)
            time.sleep(interval)
            continue

        if not folder_exists:
            time.sleep(interval)
            continue

        files = list_files(folder)
        if files:
            newest = files[-1]
            try:
                mtime = newest.stat().st_mtime
            except OSError as exc:
                _log.warning("wait_for_new_file: stat failed for %s: %s", newest, exc)
                time.sleep(interval)
                continue
            if mtime > last_seen_mtime:
                return newest

        polls += 1
        if polls % 30 == 0:
            _log.debug(
                "wait_for_new_file: %d .txt file(s) visible in %s (last_mtime=%.0f)",
                len(files),
                folder,
                last_seen_mtime,
            )
        time.sleep(interval)
