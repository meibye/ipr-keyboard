"""Which scans have already been typed, so none is lost and none is repeated.

The pen is an MTP device, and an MTP directory listing is not immediately
consistent: a file can show up in it *after* files written later have already
been delivered.  The original rule -- "deliver anything newer than the newest
thing delivered so far" -- then skipped it for good.  Observed on a device:

    14:38:17  1 existing file(s) left untouched as baseline
    14:38:53  (the pen writes 20261003143851.txt -- not yet visible)
    14:51:21  20261003145155.txt delivered
    14:53:55  20261003145426.txt delivered, mark now 14:54:27
    later     20261003143851.txt appears, is older than the mark, never sent

So this records the files that *have* been delivered rather than a point in
time.  Anything not in the log is delivered once, whatever its timestamp; a
restart repeats nothing, which is the property the high-water mark existed to
provide in the first place.

A file is identified by name, mtime and size together: a pen that reuses a
name for a new scan produces a different key and is delivered.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .logging.logger import get_logger

logger = get_logger()

#: The log's file name, in the project root (main.py and the dashboard).
STATE_FILE = "pen_state.json"

# Keys kept per folder.  Bounded so the file cannot grow without end on a pen
# whose scans are never deleted; the oldest are dropped first, and a dropped
# file would only be re-delivered if it were still on the pen after hundreds
# of newer ones.
MAX_KEYS_PER_FOLDER = 1000


def _key(path: Path) -> str | None:
    """Identity of one scan: name, mtime and size."""
    try:
        st = path.stat()
    except OSError:
        return None
    return f"{path.name}|{int(st.st_mtime)}|{st.st_size}"


class DeliveryLog:
    """What has been typed, per watched folder.  Persisted across restarts."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._folders: dict[str, list[str]] = {}
        self._load()

    # -- persistence ------------------------------------------------------

    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, dict):
            return
        for folder, value in raw.items():
            if isinstance(value, list):
                self._folders[str(folder)] = [str(v) for v in value]
            else:
                # The old format was {folder: high-water mtime}.  There is no
                # way to recover which files that covered, so the folder is
                # simply re-baselined on its next sweep: everything presently
                # on the pen counts as delivered.  Conservative on purpose --
                # upgrading must not suddenly type a pile of old scans.
                logger.info(
                    "Pen delivery log for %s is in the old format; re-baselining",
                    folder,
                )
        if self._folders:
            logger.info(
                "Pen delivery log: %d folder(s), %d known scan(s)",
                len(self._folders),
                sum(len(v) for v in self._folders.values()),
            )

    def save(self) -> None:
        try:
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp.write_text(json.dumps(self._folders, indent=1), encoding="utf-8")
            os.replace(tmp, self._path)
        except OSError as exc:
            logger.warning("Could not write %s: %s", self._path, exc)

    # -- the questions the loop asks --------------------------------------

    def knows(self, folder: Path) -> bool:
        """Has this folder been baselined?"""
        return str(folder) in self._folders

    def baseline(self, folder: Path, files: list[Path]) -> None:
        """First sight of a folder: everything already there counts as done."""
        keys = [k for k in (_key(f) for f in files) if k]
        self._folders[str(folder)] = keys[-MAX_KEYS_PER_FOLDER:]
        self.save()
        logger.info(
            "Pen folder %s: %d existing file(s) left untouched as baseline",
            folder,
            len(keys),
        )

    def delivered(self, folder: Path, path: Path) -> bool:
        key = _key(path)
        return key is not None and key in self._folders.get(str(folder), ())

    def mark(self, folder: Path, path: Path) -> None:
        key = _key(path)
        if key is None:
            return
        keys = self._folders.setdefault(str(folder), [])
        keys.append(key)
        del keys[:-MAX_KEYS_PER_FOLDER]
        self.save()

    @staticmethod
    def recent(path: Path | str, limit: int = 10) -> list[dict]:
        """The scans most recently handled, newest first, read without logging.

        For the dashboard, which polls: it must neither log on every refresh
        nor hold the loop's instance.  "Handled" is typed, or already on the
        pen when its folder was first seen.  The scans themselves are usually
        gone -- deleted from the pen after typing -- so this is the only
        record of them.
        """
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        out = []
        for folder, keys in (raw.items() if isinstance(raw, dict) else ()):
            if not isinstance(keys, list):
                continue
            for key in keys:
                name, _, rest = str(key).partition("|")
                mtime, _, size = rest.partition("|")
                try:
                    out.append(
                        {"name": name, "folder": folder, "mtime": int(mtime), "size_bytes": int(size)}
                    )
                except ValueError:
                    continue
        out.sort(key=lambda e: e["mtime"], reverse=True)
        return out[:limit]

    def next_undelivered(self, folder: Path, files: list[Path]) -> Path | None:
        """The oldest file in `files` that has not been typed yet."""
        for candidate in files:
            if not self.delivered(folder, candidate):
                return candidate
        return None
