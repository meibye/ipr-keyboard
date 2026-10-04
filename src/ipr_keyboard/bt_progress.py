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


class TypingWatch:
    """Accumulates one logical send out of the daemon's per-line drains.

    The daemon reads its FIFO **line by line** and calls drain_queue after
    each one, so a ten-line text is ten typing/idle cycles, not one.  Anything
    that treats the first `idle` as "the send finished" measures one line and
    then divides the whole text by it -- which is how a trial came to report
    38 characters a second for a 25/s setting, and "incomplete" for every
    speed.

    Feed this to wait_until_idle's on_progress.  It keeps the first and last
    moments typing was actually seen, and sums each drain's characters.
    """

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self.started_at: float | None = None
        self.last_typing_at: float | None = None
        self.chars_typed = 0
        self._drain_sent = 0
        self._drain_total = 0

    def __call__(self, progress: Progress) -> None:
        if not progress.known:
            return
        now = self._clock()
        # A new drain: `sent` restarts from zero, or the length changes.
        if progress.sent < self._drain_sent or progress.total != self._drain_total:
            self.chars_typed += self._drain_sent
            self._drain_sent = 0
            self._drain_total = progress.total
        self._drain_sent = max(self._drain_sent, progress.sent)
        if progress.typing:
            if self.started_at is None:
                self.started_at = now
            self.last_typing_at = now

    @property
    def total_typed(self) -> int:
        """Characters typed across every drain, including the current one."""
        return self.chars_typed + self._drain_sent

    def type_seconds(self) -> float:
        if self.started_at is None or self.last_typing_at is None:
            return 0.0
        return max(0.0, self.last_typing_at - self.started_at)


def publishes(path: str = PROGRESS_FILE) -> bool:
    """Does this daemon report progress at all?

    Deliberately ignores the file's age.  `read` collapses an old file to
    UNKNOWN because a finished send says nothing about now -- but a file that
    parses still proves the daemon is the kind that publishes, and that is what
    a caller needs to know before deciding whether waiting is worthwhile.

    Conflating the two meant a send that followed more than STALE_AFTER_S of
    quiet was never waited for: no progress on the panel and no typing
    measurement, for the commonest case there is -- an idle device, then one
    scan.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            return isinstance(json.load(fh), dict)
    except (OSError, ValueError):
        return False


def wait_until_idle(
    path: str = PROGRESS_FILE,
    timeout_s: float = 120.0,
    poll_s: float = 0.1,
    on_progress=None,
    clock=time.monotonic,
    sleep=time.sleep,
    start_timeout_s: float = 5.0,
    settle_s: float = 0.6,
) -> Progress:
    """Block until the daemon stops typing, so a send ends when it really has.

    Returns the last progress seen.  Returns at once when the daemon publishes
    nothing (an older version), so this can never make a send hang; the
    timeout is the backstop for a daemon that dies mid-text.

    `settle_s` is how long `idle` must LAST before the send counts as over.
    The daemon drains its FIFO one line at a time, publishing idle after each,
    so a single `idle` reading usually means "between two lines" rather than
    "finished" -- and returning on it timed one line out of ten.  The gap
    between drains is sub-millisecond, so anything above the publish interval
    tells the two apart.

    `start_timeout_s` is how long to wait for the typing to BEGIN.  The text
    has only been queued when this is called, and the daemon publishes nothing
    new until it starts, so without this the first reading is the previous
    send's -- stale, hence UNKNOWN, hence an immediate return that skipped the
    wait entirely.  A send that never starts (no host subscribed) costs this
    much and then behaves as before.
    """
    deadline = clock() + timeout_s
    last = read(path)
    if not last.known and not publishes(path):
        return last  # an older daemon: nothing to wait for, ever
    started_typing = last.typing
    if not started_typing:
        start_deadline = min(clock() + start_timeout_s, deadline)
        while clock() < start_deadline:
            current = read(path)
            if current.typing:
                started_typing = True
                last = current
                if on_progress is not None:
                    on_progress(current)
                break
            sleep(poll_s)
        else:
            # It never began.  Report what the file says rather than a wait
            # that silently did nothing.
            return read(path)
    idle_since: float | None = None
    while clock() < deadline:
        current = read(path)
        if on_progress is not None and current.known:
            on_progress(current)
        if current.typing:
            started_typing = True
            idle_since = None
        elif started_typing:
            now = clock()
            if idle_since is None:
                idle_since = now
            elif now - idle_since >= settle_s:
                return current  # idle, and it stayed idle: really done
        last = current
        sleep(poll_s)
    return last
