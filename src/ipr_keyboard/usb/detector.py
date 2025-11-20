from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional


def list_files(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return sorted(
        [p for p in folder.iterdir() if p.is_file()],
        key=lambda p: p.stat().st_mtime,
    )


def newest_file(folder: Path) -> Optional[Path]:
    files = list_files(folder)
    if not files:
        return None
    return files[-1]


def wait_for_new_file(
    folder: Path, last_seen_mtime: float, interval: float = 1.0
) -> Optional[Path]:
    """
    Poll 'folder' until a file with newer mtime than 'last_seen_mtime'
    appears. Returns that file or None if folder doesn't exist.
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
