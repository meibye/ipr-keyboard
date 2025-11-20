from __future__ import annotations

from pathlib import Path
from typing import Optional


def read_file(path: Path, max_size: int) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    if path.stat().st_size > max_size:
        return None
    return path.read_text(encoding="utf-8", errors="ignore")


def read_newest(folder: Path, max_size: int) -> Optional[str]:
    from .detector import newest_file

    newest = newest_file(folder)
    if newest is None:
        return None
    return read_file(newest, max_size)
