"""How far the BLE daemon has got through typing the current text.

bt_kb_send.sh hands the text to a FIFO and returns immediately, so until now
the application learned nothing about the part that actually takes time: the
daemon typing character by character over BLE HID.  A send was marked done in
milliseconds while the host was still receiving, the panel never showed
progress, and the recorded "send" duration measured the FIFO write.

The daemon publishes its progress to a small JSON file on tmpfs (see
PROGRESS_FILE in bt_hid_ble_daemon.py).  This reads it.  Nothing here is
required for a send to work: an older daemon that publishes nothing simply
leaves the state unknown, and callers fall back to their previous behaviour.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

PROGRESS_FILE = os.environ.get("BT_PROGRESS_FILE", "/run/ipr_bt_progress.json")
# Older than this and the file is a leftover from a previous send, not news.
STALE_AFTER_S = 120.0


@dataclass(frozen=True)
class Progress:
    """A snapshot of the daemon's typing, or `unknown` when it says nothing."""

    state: str = "unknown"  # "typing" | "idle" | "unknown"
    total: int = 0
    sent: int = 0
    at: float = 0.0

    @property
    def typing(self) -> bool:
        return self.state == "typing"

    @property
    def known(self) -> bool:
        return self.state != "unknown"

    @property
    def fraction(self) -> float:
        if self.total <= 0:
            return 0.0
        return max(0.0, min(1.0, self.sent / self.total))


UNKNOWN = Progress()


def read(path: str = PROGRESS_FILE, now: float | None = None) -> Progress:
    """The daemon's latest progress, or UNKNOWN when there is none to read."""
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return UNKNOWN
    if not isinstance(raw, dict):
        return UNKNOWN
    at = float(raw.get("at", 0.0) or 0.0)
    if (now or time.time()) - at > STALE_AFTER_S:
        # A file left behind by a send that finished long ago says nothing
        # about now, and treating it as current would stall the next one.
        return UNKNOWN
    return Progress(
        state=str(raw.get("state", "unknown")),
        total=int(raw.get("total", 0) or 0),
        sent=int(raw.get("sent", 0) or 0),
        at=at,
    )


def wait_until_idle(
    path: str = PROGRESS_FILE,
    timeout_s: float = 120.0,
    poll_s: float = 0.1,
    on_progress=None,
    clock=time.monotonic,
    sleep=time.sleep,
) -> Progress:
    """Block until the daemon stops typing, so a send ends when it really has.

    Returns the last progress seen.  Returns at once when the daemon publishes
    nothing (an older version), so this can never make a send hang; the
    timeout is the backstop for a daemon that dies mid-text.
    """
    deadline = clock() + timeout_s
    last = read(path)
    if not last.known:
        return last
    started_typing = last.typing
    while clock() < deadline:
        current = read(path)
        if on_progress is not None and current.known:
            on_progress(current)
        if current.typing:
            started_typing = True
        elif started_typing:
            return current  # was typing, now idle: done
        last = current
        sleep(poll_s)
    return last
