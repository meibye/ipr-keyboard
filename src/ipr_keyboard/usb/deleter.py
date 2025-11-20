from __future__ import annotations

from pathlib import Path
from typing import Optional, List


def delete_file(path: Path) -> bool:
    try:
        if path.exists() and path.is_file():
            path.unlink()
        return True
    except OSError:
        return False


def delete_all(folder: Path) -> List[Path]:
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
    from .detector import newest_file

    newest = newest_file(folder)
    if newest is None:
        return None
    return newest if delete_file(newest) else None
