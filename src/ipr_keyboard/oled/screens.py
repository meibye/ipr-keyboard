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
# Something the USER has to do before the device can work, as opposed to
# ICON_ERR, which is a fault.  A glyph, because "Plug in the pen" among three
# lines of ordinary text was not noticed at all.
ICON_WARN = "warn"
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
    # A PC has been paired before (bt_link.Link.has_bond).  When one has and it
    # is not here, the next move is on the PC -- the device is a BLE peripheral
    # and cannot call it back.
    bt_bonded: bool = False
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
    tx_sent: int = 0  # characters the BLE daemon has actually typed so far
    menu: object | None = None  # menu.MenuView while the magnet menu is open
    menu_available: bool = False  # holding opens a menu, not the timed ladder


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
    if snap.menu is not None:
        return True
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
    if snap.menu is not None:
        return _menu_screen(snap, badge)
    if snap.held_secs > 0:
        if snap.menu_available:
            return _menu_hold_screen(snap, badge)
        return _gesture_screen(snap, badge)
    if snap.tx_state == "sending":
        return Screen(
            "SENDING…",
            badge,
            (
                Line(_bt_target(snap), ICON_ARROW),
                Line(_sending_counts(snap)),
            ),
            # Real progress when the daemon reports it, a sweep when it does
            # not: an indeterminate bar for a send that takes tens of seconds
            # says only "something is happening".
            progress=(snap.tx_sent / snap.tx_chars)
            if (snap.tx_sent and snap.tx_chars)
            else -1.0,
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
                # Holding opens the menu on a device with a panel, so the
                # old "Hold 3 s to stop" did nothing at all when followed.
                Line(
                    "Hold: menu to stop"
                    if snap.menu_available
                    else "Hold 3s to stop"
                ),
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


# Mirrors gpio_monitor.HOLD_MENU_SECS; this module deliberately imports
# nothing from there (see the module docstring).
MENU_HOLD_SECS = 1.2
# Mirrors gpio_monitor.MENU_SELECT_SECS: how long a hold inside the menu must
# last to count as "choose this".
MENU_SELECT_SECS = 1.0
# A tap is a press and a release; showing the bar for one made the screen
# flicker on every step through the list.  Nothing appears until the magnet
# has clearly been *held* -- but early enough that there is visible travel
# before the choice fires, since the bar filling is the only warning that it
# is about to.
PROGRESS_AFTER_SECS = 0.25


def _menu_hold_screen(snap: Snapshot, badge: str) -> Screen:
    """While the magnet is held on a device whose hold opens the menu.

    The timed activity list belongs to devices without a display; here the
    hold does one thing, so the screen says so and shows how far along it is.
    """
    if snap.armed == "menu":
        return Screen(
            "RELEASE → MENU",
            badge,
            (Line("Let go to open the menu", ICON_MARK),),
        )
    if snap.held_secs < PROGRESS_AFTER_SECS:
        # Too short to be a hold yet: say nothing rather than flash a bar.
        return Screen("HOLD…", badge, (Line("Hold for the menu", ICON_WAIT),))
    progress = min(1.0, max(0.0, snap.held_secs / MENU_HOLD_SECS))
    return Screen(
        "HOLD…",
        badge,
        (Line("Keep holding for the menu", ICON_WAIT),),
        progress=progress,
    )


def _menu_screen(snap: Snapshot, badge: str) -> Screen:
    """The magnet menu: a list to step through, or a confirmation / reveal.

    Uses the same compact four-line grid as the gesture list, so the selected
    line is bold with a marker and nothing changes size as the list scrolls.
    """
    view = snap.menu
    if view.detail:
        # compact here too: the confirmation and the recovery key are
        # longer than the 114 px slot allows at the larger face.
        return Screen(
            view.title,
            badge,
            tuple(Line(t) for t in view.detail),
            compact=True,
        )
    title = view.title
    if getattr(view, "position", None):
        item, total = view.position
        title = f"{title} {item}/{total}"
    lines = tuple(
        Line(text, ICON_MARK if i == view.selected else "", bold=i == view.selected)
        for i, text in enumerate(view.lines)
    )
    # While the magnet is held, fill a bar towards the moment the highlighted
    # item is chosen: with one control and no labels, "how long do I hold?"
    # is otherwise guesswork.  Only two lines fit beside the bar, so the list
    # is trimmed to the selection and its neighbour.
    if snap.held_secs >= PROGRESS_AFTER_SECS:
        progress = min(1.0, snap.held_secs / MENU_SELECT_SECS)
        keep = lines[view.selected : view.selected + 2] or lines[:2]
        return Screen(title, badge, keep, progress=progress)
    return Screen(title, badge, lines, compact=True)


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
        # Defensive: an armed value outside the ladder (the menu adds one)
        # used to raise StopIteration here and freeze the whole display.
        start = next((i for i, (key, _, _) in enumerate(GESTURES) if key == armed), 0)
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
    """The home screen: one line each for the PC, the pen and the network.

    Two kinds of bad news, kept apart because the user can only act on one of
    them.  A *fault* (ICON_ERR, header PROBLEM) is the device's problem.
    Something *outstanding* (ICON_WARN, header NOT READY) is waiting on the
    user — and it has to be visible as a shape, not only as a sentence: with
    the pen unplugged the screen used to read READY with "Plug in the pen"
    sitting unremarked in the middle, which nobody noticed.
    """
    fault = False      # the device is broken
    outstanding = False  # the user has something to do

    if not snap.services_ok:
        fault = True
        names = (
            ", ".join(s.removesuffix(".service") for s in snap.failed_services)
            or "core service"
        )
        bt_line = Line(f"Service down: {names}", ICON_ERR)
    elif snap.bt_connected:
        bt_line = Line(snap.bt_host or "PC connected", ICON_BT)
    elif snap.bt_bonded:
        # Paired, but away.  The device advertises and waits -- a BLE
        # peripheral cannot call the host back -- so say whose move it is.
        # "Waiting for PC…" was true and useless: after one reboot a Windows
        # host took 26 minutes, with nothing suggesting the user could help.
        # Kept out of the NOT READY tier on purpose: a PC that is merely
        # switched off is not something to fix.
        bt_line = Line("Reconnect from PC", ICON_BT)
    else:
        # Never paired: pairing is the thing to do, not reconnecting.
        bt_line = Line("Waiting for PC…", ICON_BT)

    if snap.pen == "ready":
        pen_line = Line("Pen ready", ICON_PEN)
    elif snap.pen == "busy":
        pen_line = Line("Pen busy (mounting)", ICON_PEN)
    elif snap.pen == "disabled":
        fault = True
        pen_line = Line("USB port off — reboot", ICON_ERR)
    else:
        # Nothing can be scanned without it, so this is not a neutral state.
        outstanding = True
        pen_line = Line("Plug in the pen", ICON_WARN)

    if snap.wifi_connected:
        net_line = Line(f"{snap.ssid or 'Wi-Fi'}  {snap.ip}".rstrip(), ICON_NET)
    else:
        outstanding = True
        # The old text said "hold 3 s", which stopped being true when the hold
        # started opening the menu instead of running a timed ladder.
        net_line = Line(
            "No Wi-Fi: see menu" if snap.menu_available else "No Wi-Fi — hold 3 s",
            ICON_WARN,
        )

    header = "PROBLEM" if fault else ("NOT READY" if outstanding else "READY")
    return Screen(header, badge, (bt_line, pen_line, net_line))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bt_target(snap: Snapshot) -> str:
    return snap.bt_host or "PC"


def _sending_counts(snap: Snapshot) -> str:
    """ "120 of 384 characters" while typing, the total before it starts."""
    if snap.tx_sent and snap.tx_chars:
        return f"{snap.tx_sent} of {snap.tx_chars} characters"
    return _chars(snap.tx_chars)


def _chars(n: int) -> str:
    return "1 character" if n == 1 else f"{n} characters"


def _clock(ts: float | None) -> str:
    if not ts:
        return ""
    return time.strftime("%H:%M", time.localtime(ts))
