"""What the display shows — pure data, no Pillow, no hardware.

``compose(snapshot)`` turns a :class:`Snapshot` of the device into a
:class:`Screen`: a header word for the 16 yellow rows, an optional badge,
and up to three body lines (or a progress bar) for the 48 blue rows.  The
renderer decides fonts and pixels; nothing here knows the display size
except the intent "three short lines".

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


@dataclass(frozen=True)
class Screen:
    header: str
    badge: str = ""
    lines: tuple[Line, ...] = ()
    progress: float | None = None  # None: no bar; < 0: indeterminate; 0..1


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


def compose(snap: Snapshot) -> Screen:
    badge = "DEV" if snap.development else ""

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
            return Screen(
                "MODE: DEVELOPMENT", badge, (Line("Ports open (SSH, dev)", ICON_OK),)
            )
        return Screen("MODE: PRODUCTION", badge, (Line("Ports closed", ICON_OK),))
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
    bt_ok = (
        "bt_hid_ble.service" not in snap.failed_services
        and "bluetooth.service" not in snap.failed_services
    )
    return (
        Line("Services", ICON_OK if snap.services_ok else ICON_WAIT),
        Line("Bluetooth", ICON_OK if bt_ok else ICON_WAIT),
        Line("Dashboard", ICON_OK if snap.ready else ICON_WAIT),
    )


def _gesture_screen(snap: Snapshot, badge: str) -> Screen:
    armed = snap.armed
    if armed is None:
        header = "HOLD…"
    elif armed == "cancel":
        header = "CANCELLED"
    elif armed == "hotspot":
        header = "RELEASE → HOTSPOT OFF" if snap.hotspot_active else "RELEASE → HOTSPOT"
    elif armed == "shutdown":
        header = "RELEASE → SHUTDOWN"
    elif armed == "mode":
        header = "RELEASE → MODE"
    else:
        header = "RELEASE → RESET"
    hotspot_word = "Hotspot off" if snap.hotspot_active else "Hotspot"
    return Screen(
        header,
        badge,
        (
            Line(f"3 s   {hotspot_word}", ICON_MARK if armed == "hotspot" else ""),
            Line("6 s   Shutdown", ICON_MARK if armed == "shutdown" else ""),
            Line(
                "10 s Mode   15 s Reset",
                ICON_MARK if armed in ("mode", "reset") else "",
            ),
        ),
    )


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
