"""The typing speed, handed to the BLE daemon without restarting it.

The daemon's `BT_KEY_DELAY_MS` is read from `/opt/ipr_common.env` at start, so
changing the typing speed that way means restarting `bt_hid_ble.service` —
which drops the BLE link and makes the user pair again.  Far too much for a
settings change, and impossible as a tuning loop.

So the application writes the chosen value to a small runtime file and the
daemon re-reads it once per send.  The file lives in `/run`, which a reboot
clears: the env var is the default, and this is an override for as long as the
device stays up.  The daemon creates the file and gives it to the application
user; everything here therefore tolerates its absence, because a device whose
daemon is older simply keeps typing at its configured speed.

Mirrors `scripts/service/bin/bt_hid_ble_daemon.py` (KEY_DELAY_PATH and the
range); see docs/operations/performance.md.
"""

from __future__ import annotations

from pathlib import Path

from .logging.logger import get_logger

logger = get_logger()

PATH = Path("/run/ipr_bt_key_delay")

# Mirrors the daemon.  The upper bound is generous (a deliberately slow device
# for a fussy host); the lower bound is where even a perfect host cannot keep
# up, and is checked so a bad config value cannot stop the device typing.
MIN_MS = 1
MAX_MS = 200

# What the dashboard offers.  Each is one step of the ladder in
# docs/operations/performance.md, and the labels say what the user gets rather
# than what the device does.
CHOICES: tuple[tuple[int, str, str], ...] = (
    (20, "Normal", "about 25 characters a second"),
    (12, "Fast", "about 40 a second — usually the practical best"),
    (8, "Faster", "rarely any faster: the PC's radio sets the limit"),
    (4, "Fastest", "no faster in practice, and characters may be lost"),
)


def name_for(ms: int) -> str:
    """"Normal", "Fast", ... or the bare value for a hand-tuned one.

    The dashboard shows this everywhere a speed is named -- the Settings list
    and the trial's results -- so the two cannot describe the same speed in
    different words, which is what made them look unrelated.
    """
    for choice_ms, name, _ in CHOICES:
        if choice_ms == ms:
            return name
    return f"{ms} ms"


def label_for(ms: int) -> str:
    """The full one-line description, as the Settings list shows it."""
    for choice_ms, name, detail in CHOICES:
        if choice_ms == ms:
            return f"{name} — {detail} ({choice_ms} ms)"
    return f"{ms} ms — {chars_per_second(ms):.0f} a second"


def clamp(ms: int) -> int:
    return max(MIN_MS, min(MAX_MS, int(ms)))


def chars_per_second(ms: int) -> float:
    """The NOMINAL rate: two HID reports per character, so the delay counts twice.

    Nominal, not achievable.  Each report is a BLE notification and cannot be
    delivered faster than one connection event, so the real ceiling is
    `floor_chars_per_second` for whatever interval the PC negotiated.  Below
    about 12 ms the delay stops being what limits the device, which is why
    "Faster" and "Fastest" are not.
    """
    ms = clamp(ms)
    return 1000.0 / (2.0 * ms)


# What a host typically negotiates for HID.  Windows commonly settles at the
# upper end, and 2 x 15 ms = 33 characters a second -- measured as 32.9 on a
# Zero 2 W at a 4 ms delay, i.e. the radio, not the setting.
TYPICAL_INTERVAL_MS = 15.0


def floor_chars_per_second(interval_ms: float = TYPICAL_INTERVAL_MS) -> float:
    """The most that can be typed at a given connection interval."""
    return 1000.0 / (2.0 * interval_ms)


def read() -> int | None:
    """The value currently in force, or None when the file says nothing."""
    try:
        raw = PATH.read_text(encoding="ascii").strip()
    except OSError:
        return None
    try:
        ms = int(raw)
    except ValueError:
        return None
    return ms if MIN_MS <= ms <= MAX_MS else None


def apply(ms: int) -> bool:
    """Put `ms` in force for the next send.  True when it was written.

    Writing only on a change keeps this out of the main loop's cost: the loop
    calls it every iteration, and the file is on tmpfs.
    """
    ms = clamp(ms)
    if read() == ms:
        return True
    try:
        PATH.write_text(f"{ms}\n", encoding="ascii")
    except OSError as exc:
        # Not an error worth repeating every second: an older daemon never
        # creates the file, and the device keeps typing at its own speed.
        logger.debug("Could not set the typing delay (%s): %s", PATH, exc)
        return False
    logger.info(
        "Typing delay set to %d ms per report (%.0f chars/s)", ms, chars_per_second(ms)
    )
    return True
