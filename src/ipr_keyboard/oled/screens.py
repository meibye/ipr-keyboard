"""What the display shows — pure data, no Pillow, no hardware.

``compose(snapshot)`` turns a :class:`Snapshot` of the device into a
:class:`Screen`: a header word for the 16 yellow rows, a mode badge, and up
to four body lines (or a progress bar) for the 48 blue rows.  The renderer
decides fonts and pixels; nothing here knows the display size except the
intent "a few short lines" — it packs four by using a smaller font.

A line may ask to be emphasised (``Line.bold``); the gesture screen uses it
for the activity that is currently selected.

The screen map (user-facing) is in docs/hardware/oled-display.md; the
reasoning in docs/architecture/oled-display-design.md.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

# Phase names as strings so this module does not import gpio_monitor.
BOOT = "boot"
IDLE = "idle"
STATUS = "status"
HOTSPOT_BUSY = "hotspot_busy"
HOTSPOT_ON = "hotspot_on"
FAIL_FLASH = "fail_flash"
MODE_CONFIRM = "mode_confirm"
SHUTTING_DOWN = "shutting_down"
RESETTING = "resetting"

HOTSPOT_URL = "10.42.0.1/setup"

# Icons the renderer knows how to draw (8x8 glyphs).
ICON_BT = "bt"
ICON_PEN = "pen"
ICON_NET = "net"
ICON_OK = "ok"
ICON_ERR = "err"
ICON_WAIT = "wait"
ICON_ARROW = "arrow"
ICON_MARK = "mark"


@dataclass(frozen=True)
class Snapshot:
    """Everything the display may show.  Defaults describe a bare boot."""

    phase: str = BOOT
    armed: str | None = None
    held_secs: float = 0.0
    ready: bool = False
    development: bool = False
    services_ok: bool = True
    failed_services: tuple[str, ...] = ()
    bt_connected: bool = False
    bt_host: str = ""
    pen: str = "missing"  # usb.detector.pen_presence()
    wifi_connected: bool = False
    ssid: str = ""
    ip: str = ""
    hotspot_active: bool = False
    hotspot_ssid: str = ""
    tx_state: str = "idle"  # transmission.get()["state"]
    tx_recent: bool = False  # a send finished within OledSendHoldSeconds
    tx_chars: int = 0
    tx_total: int = 0
    tx_reason: str = ""
    tx_last_at: float | None = None  # wall-clock time of the last success


@dataclass(frozen=True)
class Line:
    text: str
    icon: str = ""
    bold: bool = False  # the renderer draws this line in the bold face


@dataclass(frozen=True)
class Screen:
    header: str
    badge: str = ""  # mode badge: "DEV" or "PROD"
    lines: tuple[Line, ...] = ()
    progress: float | None = None  # None: no bar; < 0: indeterminate; 0..1
    compact: bool = False  # keep the four-line grid even with fewer lines


def status_key(snap: Snapshot) -> tuple:
    """The part of the state whose change should wake the display."""
    return (
        snap.bt_connected,
        snap.pen,
        snap.wifi_connected,
        snap.services_ok,
        snap.failed_services,
        snap.hotspot_active,
        snap.development,
    )


def wants_display(snap: Snapshot) -> bool:
    """Phases during which the panel is on regardless of any timer."""
    if snap.held_secs > 0 and snap.phase != BOOT:
        return True
    if snap.tx_state == "sending":
        return True
    return snap.phase != IDLE


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------


BADGE_DEV = "DEV"
BADGE_PROD = "PROD"

# The magnet gestures, in the order they arm while the magnet is held.
GESTURES: tuple[tuple[str, int, str], ...] = (
    ("hotspot", 3, "Hotspot"),
    ("shutdown", 6, "Shutdown"),
    ("mode", 10, "Switch mode"),
    ("reset", 15, "Factory reset"),
)


def compose(snap: Snapshot) -> Screen:
    # The badge is the mode, on every screen: the LED no longer signals it.
    badge = BADGE_DEV if snap.development else BADGE_PROD

    if snap.phase == BOOT:
        return Screen("STARTING…", badge, _boot_lines(snap))
    if snap.phase == SHUTTING_DOWN:
        return Screen(
            "SHUTTING DOWN",
            badge,
            (Line("Wait for the LED to"), Line("go off, then unplug")),
        )
    if snap.phase == RESETTING:
        return Screen(
            "RESETTING…", badge, (Line("Wi-Fi profiles deleted"), Line("Rebooting…"))
        )
    if snap.held_secs > 0:
        return _gesture_screen(snap, badge)
    if snap.tx_state == "sending":
        return Screen(
            "SENDING…",
            badge,
            (Line(_bt_target(snap), ICON_ARROW), Line(_chars(snap.tx_chars))),
            progress=-1.0,
        )
    if snap.phase == HOTSPOT_BUSY:
        verb = "Stopping" if snap.hotspot_active else "Starting"
        return Screen("HOTSPOT…", badge, (Line(f"{verb} the hotspot…", ICON_WAIT),))
    if snap.phase == FAIL_FLASH:
        return Screen(
            "HOTSPOT FAILED",
            badge,
            (
                Line("Try again in a moment", ICON_ERR),
                Line("Details: dashboard events"),
            ),
        )
    if snap.phase == MODE_CONFIRM:
        if snap.development:
            # "Ports open (SSH, dev)" was 120 px on the device font and rolled
            # through the whole three-second confirmation; the slot is 114 px.
            return Screen("MODE: DEV", badge, (Line("Ports open (SSH)", ICON_OK),))
        return Screen("MODE: PROD", badge, (Line("Ports closed", ICON_OK),))
    if snap.phase == HOTSPOT_ON or snap.hotspot_active:
        return Screen(
            "SETUP MODE",
            badge,
            (
                Line(f"Wi-Fi  {snap.hotspot_ssid or 'ipr-setup-…'}", ICON_NET),
                Line(f"Open   {HOTSPOT_URL}", ICON_ARROW),
                Line("Hold 3 s to stop"),
            ),
        )
    if snap.tx_recent and snap.tx_state == "success":
        return Screen(
            "SENT ✓",
            badge,
            (
                Line(_chars(snap.tx_chars), ICON_OK),
                Line(f"{_bt_target(snap)}  {_clock(snap.tx_last_at)}", ICON_ARROW),
                Line(f"Total {snap.tx_total}"),
            ),
        )
    if snap.tx_recent and snap.tx_state == "failed":
        return Screen(
            "SEND FAILED",
            badge,
            (Line(snap.tx_reason or "Send failed", ICON_ERR), Line("Text kept on pen")),
        )
    return _status_screen(snap, badge)


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------


def _boot_lines(snap: Snapshot) -> tuple[Line, ...]:
    """The boot checklist — it continues the one ipr_oled_boot.py starts.

    ``scripts/headless/ipr_oled_boot.py`` owns the panel from a few seconds
    after power-on (System / Network / Bluetooth / Application); the
    application takes it over here and keeps ticking items off until the
    dashboard answers.
    """
    bt_ok = (
        "bt_hid_ble.service" not in snap.failed_services
        and "bluetooth.service" not in snap.failed_services
    )
    net_ok = snap.wifi_connected or snap.hotspot_active
    return (
        Line("Services", ICON_OK if snap.services_ok else ICON_WAIT),
        Line("Network", ICON_OK if net_ok else ICON_WAIT),
        Line("Bluetooth", ICON_OK if bt_ok else ICON_WAIT),
        Line("Dashboard", ICON_OK if snap.ready else ICON_WAIT),
    )


def _gesture_screen(snap: Snapshot, badge: str) -> Screen:
    """The activity list while the magnet is held.

    The selected activity is bold and marked; activities already passed are
    dropped and the rest roll up, so the list shrinks towards the one that
    will fire on release and never needs to be read out of order.  The screen
    is ``compact`` at every stage: the lines keep their size and position
    while the list shrinks.
    """
    armed = snap.armed
    if armed == "cancel":
        return Screen(
            "CANCELLED",
            badge,
            (Line("Nothing will happen", ICON_ERR), Line("Take the magnet off")),
        )

    if armed is None:
        header = "HOLD…"
        remaining = GESTURES
    else:
        # The header stays short and still ("RELEASE →"); the bold body line
        # names the activity.  Spelling the activity out in the header made it
        # too wide for the band beside the mode badge, so it rolled while the
        # user was counting seconds.
        header = "RELEASE →"
        start = next(i for i, (key, _, _) in enumerate(GESTURES) if key == armed)
        remaining = GESTURES[start:]

    lines = tuple(
        Line(
            f"{secs} s  {_gesture_label(snap, key, label)}",
            ICON_MARK if key == armed else "",
            bold=key == armed,
        )
        for key, secs, label in remaining
    )
    # compact: every stage of the gesture keeps the four-line grid, so the
    # remaining activities move up a slot instead of changing size as the
    # list shrinks.
    return Screen(header, badge, lines, compact=True)


def _gesture_label(snap: Snapshot, key: str, label: str) -> str:
    if key == "hotspot" and snap.hotspot_active:
        return "Hotspot off"
    if key == "mode":
        return "To production" if snap.development else "To development"
    return label


def _status_screen(snap: Snapshot, badge: str) -> Screen:
    problem = False

    if not snap.services_ok:
        problem = True
        names = (
            ", ".join(s.removesuffix(".service") for s in snap.failed_services)
            or "core service"
        )
        bt_line = Line(f"Service down: {names}", ICON_ERR)
    elif snap.bt_connected:
        bt_line = Line(snap.bt_host or "PC connected", ICON_BT)
    else:
        bt_line = Line("Waiting for PC…", ICON_BT)

    if snap.pen == "ready":
        pen_line = Line("Pen ready", ICON_PEN)
    elif snap.pen == "busy":
        pen_line = Line("Pen busy (mounting)", ICON_PEN)
    elif snap.pen == "disabled":
        problem = True
        pen_line = Line("USB port off — reboot", ICON_ERR)
    else:
        pen_line = Line("Plug in the pen", ICON_PEN)

    if snap.wifi_connected:
        net_line = Line(f"{snap.ssid or 'Wi-Fi'}  {snap.ip}".rstrip(), ICON_NET)
    else:
        problem = True
        net_line = Line("No Wi-Fi — hold 3 s", ICON_ERR)

    return Screen(
        "PROBLEM" if problem else "READY", badge, (bt_line, pen_line, net_line)
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bt_target(snap: Snapshot) -> str:
    return snap.bt_host or "PC"


def _chars(n: int) -> str:
    return "1 character" if n == 1 else f"{n} characters"


def _clock(ts: float | None) -> str:
    if not ts:
        return ""
    return time.strftime("%H:%M", time.localtime(ts))
