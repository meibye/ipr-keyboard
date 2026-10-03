"""GPIO monitor — reed switch trigger and RGB LED status indicator.

Hardware connections (BCM numbering, Flirc Pi Zero 2 W case):

  Reed switch  GPIO 27  Pin 13   NO type, one leg to GPIO, other leg to GND
  RGB LED red  GPIO 22  Pin 15   150 Ω series resistor, common cathode to GND
  RGB LED grn  GPIO 23  Pin 16   150 Ω series resistor, common cathode to GND
  RGB LED blu  GPIO 24  Pin 18    22 Ω series resistor, common cathode to GND

Reed switch interaction (the magnet is the only control on the device):
  Press                  LED blinks white three times ("magnet registered"),
                         then goes dark, so every arming colour below appears
                         against dark — visible even when the LED was solid
                         blue (hotspot) before the magnet arrived
  Tap  (release < 3 s)   Wake LED; show system status for GpioLedIdleSeconds
  Hold ≥ 3 s             LED solid blue; release to toggle the management hotspot
  Hold ≥ 6 s             LED solid white; release for a controlled shutdown
  Hold ≥ 10 s            LED solid purple; release to toggle production/development mode
  Hold ≥ 15 s            LED solid red; release to delete WiFi profiles and reboot
  Hold ≥ 20 s            LED goes off; release does nothing (cancel)
  While held the phases are STEADY colours, each entered through a short off
  gap, so a step is visible as a "click" even between similar hues.  Blinking
  is reserved for things in progress after release.

LED colour map:
  White solid        Power on — firmware / kernel (config.txt gpio= line)
  White fast blink   Booting — ipr-led-boot.service, then this module until the
                     web dashboard answers /health
  Green solid        All OK — WiFi + Bluetooth connected
  Amber solid        WiFi OK, Bluetooth not yet connected
  Red slow blink     No WiFi configured / cannot connect
  Red solid          A core service is not running (bluetooth, bt_hid_ble,
                     bt_hid_agent_unified) — see /var/lib/ipr-keyboard/incidents.log
  Blue solid (held)  Hotspot arming (hold ≥ 3 s)
  Blue fast blink    Hotspot starting or stopping (after release)
  Blue solid         Hotspot active (setup mode) — stays on while the hotspot is up
  White solid        Shutdown arming (hold ≥ 6 s, while held) — same colour family
                     as boot: white means the device is powering up or down
  White solid        Shutting down — wait until the LED goes off before unplugging
                     (ipr-led-halt.service turns it off just before the kernel halts)
  Purple solid       Mode toggle arming (hold ≥ 10 s, while held)
  Purple solid 3 s   Mode changed (confirmation)
  White blink x3     Magnet registered (press acknowledged), then dark
  Red solid (held)   Factory reset arming (hold ≥ 15 s); also, when not held, a
                     core service down
  Red fast blink     Factory reset in progress, or a failed hotspot request
  Off                Idle — no power draw

The LED does not signal DEVELOPMENT mode: it has no blink of its own for the
mode, because a periodic blink on an idle device is read as a fault.  The mode
is shown on the OLED instead — permanently, in the header badge (``DEV`` /
``PROD``) — see docs/hardware/oled-display.md.

The boot phases before this module runs are driven by the firmware
(``gpio=22,23,24=op,dh`` in config.txt) and by ``ipr-led-boot.service``;
``ipr_keyboard.service`` declares ``Conflicts=`` on the latter so the pins are
handed over cleanly.  See docs/hardware/gpio-wiring.md.

Privileged actions (hotspot start/stop, factory reset) go through
``/usr/local/bin/ipr_hotspot_ctl.sh`` via a NOPASSWD sudoers entry installed by
``scripts/headless/install_gpio_support.sh``; the mode toggle goes through
``/usr/local/bin/ipr_mode_ctl.sh`` (``install_firewall.sh``).  The mode itself is
read from ``/var/lib/ipr-keyboard/mode`` (see docs/operations/network-modes.md).

Design: :class:`LedLogic` is a pure, clock-free state machine (testable with a
fake clock/probe/actions).  :class:`GpioMonitor` is the thread that samples the
reed switch, ticks the logic and renders frames to the LED.
"""

from __future__ import annotations

import os
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from enum import Enum
from collections.abc import Callable
from typing import Protocol

from .logging.logger import get_logger

logger = get_logger()

# ---------------------------------------------------------------------------
# GPIO availability
# ---------------------------------------------------------------------------

_GPIO_IMPORT_ERROR: str | None = None
try:
    import RPi.GPIO as _GPIO  # rpi-lgpio shim on Bookworm/Trixie, RPi.GPIO on older

    _GPIO_AVAILABLE = True
except (ImportError, RuntimeError) as _exc:  # pragma: no cover - platform specific
    _GPIO = None  # type: ignore[assignment]
    _GPIO_AVAILABLE = False
    _GPIO_IMPORT_ERROR = f"{type(_exc).__name__}: {_exc}"


def gpio_available() -> bool:
    """Return True when running on a Raspberry Pi with an RPi.GPIO-compatible module."""
    return _GPIO_AVAILABLE


def gpio_unavailable_reason() -> str | None:
    """Why RPi.GPIO could not be imported (None when it is available)."""
    return _GPIO_IMPORT_ERROR


# ---------------------------------------------------------------------------
# Defaults (overridden by AppConfig.Gpio* fields)
# ---------------------------------------------------------------------------

_REED_PIN: int = 27
_LED_R_PIN: int = 22
_LED_G_PIN: int = 23
_LED_B_PIN: int = 24

HOLD_HOTSPOT_SECS: float = 3.0
HOLD_SHUTDOWN_SECS: float = 6.0
HOLD_MODE_SECS: float = 10.0
HOLD_RESET_SECS: float = 15.0
HOLD_CANCEL_SECS: float = 20.0
PHASE_GAP_SECS: float = 0.3          # dark gap when a held phase changes
MODE_CONFIRM_SECS: float = 3.0
HOLD_MENU_SECS: float = 1.2          # open the menu (display present)
MENU_SELECT_SECS: float = 1.0        # hold inside the menu = activate
# The magnet is pressed against a glass panel by hand, and it wobbles.  At
# 20 Hz a wobble shows up as the contact opening for a sample or two, which
# taken literally ends the press: one deliberate hold arrived as two taps
# (so "Back" and "Exit" stepped past instead of being chosen), and a tap
# whose release bounced arrived as a hold.  An open is only believed once it
# has lasted this long.
REED_OPEN_DEBOUNCE_SECS: float = 0.15
ACK_BLINK_SECS: float = 0.6          # "magnet registered" blink after a press
ACK_BLINK_HALF_SECS: float = 0.12    # 0.6 s / 0.12 s = on-off-on-off-on
LED_IDLE_TIMEOUT_SECS: int = 30

HOTSPOT_REQUEST_TIMEOUT_SECS: float = 40.0  # nmcli con up on a Zero W can be slow
FAIL_FLASH_SECS: float = 3.0
PROBE_INTERVAL_ACTIVE_SECS: float = 2.0  # while the LED is showing status
PROBE_INTERVAL_IDLE_SECS: float = 5.0  # while the LED is off / blue solid


class _ReedFilter:
    """One clean press out of the raw 20 Hz reed samples.

    Two rules, and the second is the one that matters:

    * An open is only believed once it has lasted ``REED_OPEN_DEBOUNCE_SECS``,
      so a wobble no longer ends the press.
    * The hold clock STOPS at the first sign of that open.  A magnet lifted
      just short of the select threshold therefore cannot drift past it while
      the filter is still waiting to see whether the open is real -- which is
      how a tap came to be read as a hold.
    """

    def __init__(self, debounce: float = REED_OPEN_DEBOUNCE_SECS) -> None:
        self._debounce = debounce
        self.closed = False
        self.press_start = 0.0
        self._open_since: float | None = None

    def update(self, now: float, raw_closed: bool) -> None:
        if raw_closed:
            self._open_since = None
            if not self.closed:
                self.closed = True
                self.press_start = now
            return
        if not self.closed:
            return
        if self._open_since is None:
            self._open_since = now
        elif now - self._open_since >= self._debounce:
            self.closed = False
            self._open_since = None

    def held(self, now: float) -> float:
        """How long the press has lasted, frozen while the contact is open."""
        if not self.closed:
            return 0.0
        return max(0.0, (self._open_since if self._open_since else now) - self.press_start)

    @property
    def settling(self) -> bool:
        """Open, but not yet believed: do not fire a threshold in here."""
        return self.closed and self._open_since is not None


HOTSPOT_CTL = "/usr/local/bin/ipr_hotspot_ctl.sh"
MODE_CTL = "/usr/local/bin/ipr_mode_ctl.sh"
HOTSPOT_CONNECTION = "ipr-hotspot"
MODE_FILE = "/var/lib/ipr-keyboard/mode"
CORE_SERVICES = ("bluetooth.service", "bt_hid_ble.service", "bt_hid_agent_unified.service")

Color = tuple[int, int, int]
OFF: Color = (0, 0, 0)
WHITE: Color = (1, 1, 1)
RED: Color = (1, 0, 0)
GREEN: Color = (0, 1, 0)
AMBER: Color = (1, 1, 0)
BLUE: Color = (0, 0, 1)
PURPLE: Color = (1, 0, 1)

FAST_HZ = 4.0
SLOW_HZ = 1.0


# ---------------------------------------------------------------------------
# System probes — what the LED reflects
# ---------------------------------------------------------------------------


class SystemProbe:
    """Snapshot of the network/Bluetooth state, refreshed on demand.

    One ``nmcli`` call answers both "is the hotspot up" and "is home WiFi up";
    ``bluetoothctl`` answers "is a host connected".  Cached between refreshes
    so the LED loop never runs a subprocess more often than the logic asks.
    """

    def __init__(self) -> None:
        self.hotspot_active = False
        self.wifi_connected = False
        self.bt_connected = False
        self.development = False
        self.services_ok = True
        # Extra detail for the OLED display; the LED only uses the booleans.
        self.failed_services: tuple[str, ...] = ()
        self.ssid = ""  # active WiFi profile name (empty when not connected)
        self.ip = ""  # our address on the route out (empty without a route)

    def refresh(self) -> None:
        self.hotspot_active, self.wifi_connected, self.ssid = self._network_state()
        self.bt_connected = self._bt_state()
        self.development = self._mode_state()
        self.failed_services = self._failed_services()
        self.services_ok = not self.failed_services
        self.ip = self._ip_state()

    @staticmethod
    def _failed_services() -> tuple[str, ...]:
        """Core services that are not active (one systemctl call); () = all OK."""
        try:
            out = subprocess.run(
                ["systemctl", "is-active", *CORE_SERVICES],
                capture_output=True, text=True, timeout=5,
            ).stdout.split()
            if len(out) != len(CORE_SERVICES):
                return ()  # cannot tell — do not raise a false alarm
            return tuple(svc for svc, st in zip(CORE_SERVICES, out) if st != "active")
        except Exception:
            return ()

    @staticmethod
    def _ip_state() -> str:
        """Our IPv4 address on the default route, without a subprocess.

        A UDP connect() sends nothing; the kernel just picks the source
        address it would use.  Empty when there is no route at all.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk:
                sk.connect(("10.255.255.255", 1))
                return sk.getsockname()[0]
        except OSError:
            return ""

    @staticmethod
    def _mode_state() -> bool:
        """True in development mode (ports open); missing/unknown = production."""
        try:
            with open(MODE_FILE, encoding="utf-8") as fh:
                return fh.read().strip() == "development"
        except OSError:
            return False

    @staticmethod
    def _network_state() -> tuple[bool, bool, str]:
        hotspot = wifi = False
        ssid = ""
        try:
            out = subprocess.check_output(
                ["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "con", "show", "--active"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            for line in out.splitlines():
                parts = line.split(":")
                if len(parts) < 2:
                    continue
                name, ctype = parts[0], parts[1]
                if name == HOTSPOT_CONNECTION:
                    hotspot = True
                elif "wireless" in ctype:
                    wifi = True
                    ssid = name
        except Exception:
            pass
        return hotspot, wifi, ssid

    @staticmethod
    def _bt_state() -> bool:
        """True when a host is connected — read from sysfs, not bluetoothctl.

        Every ``bluetoothctl`` invocation registers (and drops) an "Adv Monitor
        app" with bluetoothd, which at this probe's rate flooded the journal
        and cost CPU on a Zero.  The kernel exposes each active link as
        /sys/class/bluetooth/<hci>/<hci>:<handle>; existence is enough.
        """
        try:
            root = "/sys/class/bluetooth"
            for hci in os.listdir(root):
                if not hci.startswith("hci"):
                    continue
                for entry in os.listdir(os.path.join(root, hci)):
                    if entry.startswith(hci + ":"):
                        return True
            return False
        except OSError:
            return False


# ---------------------------------------------------------------------------
# Privileged actions — run through the root helper, never block the LED loop
# ---------------------------------------------------------------------------


class Actions(Protocol):
    def reboot(self) -> None: ...
    def hotspot_start(self) -> None: ...
    def hotspot_stop(self) -> None: ...
    def factory_reset(self) -> None: ...
    def mode_toggle(self) -> None: ...
    def shutdown(self) -> None: ...


class SystemActions:
    """Runs ``sudo -n ipr_hotspot_ctl.sh <cmd>`` in a background thread."""

    def hotspot_start(self) -> None:
        self._spawn("start")

    def hotspot_stop(self) -> None:
        self._spawn("stop")

    def factory_reset(self) -> None:
        self._spawn("factory-reset")

    def mode_toggle(self) -> None:
        self._spawn("toggle", helper=MODE_CTL)

    def shutdown(self) -> None:
        self._spawn("poweroff")

    def reboot(self) -> None:
        self._spawn("reboot")

    @staticmethod
    def _spawn(cmd: str, helper: str = HOTSPOT_CTL) -> None:
        def _worker() -> None:
            logger.info("Running %s %s", helper, cmd)
            try:
                res = subprocess.run(
                    ["sudo", "-n", helper, cmd],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except Exception as exc:
                logger.error("%s %s failed to run: %s", helper, cmd, exc)
                return
            if res.returncode == 0:
                logger.info("%s %s: OK", helper, cmd)
            else:
                logger.error(
                    "%s %s: exit %d — %s",
                    helper,
                    cmd,
                    res.returncode,
                    (res.stderr or res.stdout).strip()[-400:],
                )

        threading.Thread(target=_worker, daemon=True, name=f"hotspot-{cmd}").start()


# ---------------------------------------------------------------------------
# LED state machine (pure — no threads, no GPIO, no wall clock)
# ---------------------------------------------------------------------------


class Phase(str, Enum):
    BOOT = "boot"  # white fast blink until set_ready()
    IDLE = "idle"  # off
    STATUS = "status"  # colour for the idle timeout
    HOTSPOT_BUSY = "hotspot_busy"  # request sent, waiting for NM
    HOTSPOT_ON = "hotspot_on"  # blue solid while the hotspot is up
    FAIL_FLASH = "fail_flash"  # red fast blink after a failed request
    MODE_CONFIRM = "mode_confirm"  # purple solid after a mode toggle
    SHUTTING_DOWN = "shutting_down"  # white solid until the kernel halts
    RESETTING = "resetting"  # red fast blink until reboot
    MENU = "menu"  # the magnet menu is open on the display


@dataclass(frozen=True)
class Frame:
    """What the LED should show: a colour and a blink rate (0 = solid)."""

    color: Color
    hz: float = 0.0

    def is_on(self, now: float) -> bool:
        if self.color == OFF:
            return False
        if self.hz <= 0:
            return True
        return int(now * self.hz * 2) % 2 == 0


FRAME_OFF = Frame(OFF)
FRAME_ACK = Frame(WHITE)  # one "on" slot of the press-acknowledge blink
FRAME_BOOT = Frame(WHITE, FAST_HZ)
FRAME_HOTSPOT_BUSY = Frame(BLUE, FAST_HZ)
FRAME_ARM_HOTSPOT = Frame(BLUE)
FRAME_ARM_SHUTDOWN = Frame(WHITE)
FRAME_ARM_MODE = Frame(PURPLE)
FRAME_ARM_RESET = Frame(RED)
FRAME_HOTSPOT_ON = Frame(BLUE)
FRAME_RESET = Frame(RED, FAST_HZ)
# White for the power transitions: white = booting, white = shutting down.
# Cyan was tried first and was indistinguishable from the 3 s blue blink on
# the small LED, so users released too early and started the hotspot.
FRAME_SHUTDOWN = Frame(WHITE)
FRAME_MODE_CONFIRM = Frame(PURPLE)


@dataclass(frozen=True)
class LedSnapshot:
    """What the OLED display needs to know about the LED/magnet state.

    Read from the display thread; a torn read between two ticks is harmless
    (the next frame corrects it).
    """

    phase: Phase
    armed: str | None
    held_secs: float  # 0 when the magnet is not on the switch
    ready: bool
    hotspot_active: bool
    wifi_connected: bool
    bt_connected: bool
    development: bool
    services_ok: bool
    failed_services: tuple[str, ...] = ()
    ssid: str = ""
    ip: str = ""
    menu: object | None = None  # menu.MenuView while the menu is open
    menu_available: bool = False  # a menu exists: the ladder is not used


def status_frame(probe: SystemProbe) -> Frame:
    """Colour for the normal operational status (hotspot handled separately)."""
    if probe.hotspot_active:
        return FRAME_HOTSPOT_ON
    if not getattr(probe, "services_ok", True):
        return Frame(RED)  # solid: something on the device itself is broken
    if not probe.wifi_connected:
        return Frame(RED, SLOW_HZ)
    if probe.bt_connected:
        return Frame(GREEN)
    return Frame(AMBER)


def ack_frame(elapsed: float) -> Frame:
    """The "magnet registered" blink: white on/off slots from the press itself.

    Timed against the press rather than the wall clock so the user always sees
    the same three flashes, whenever the magnet happens to land.
    """
    on = int(elapsed / ACK_BLINK_HALF_SECS) % 2 == 0
    return FRAME_ACK if on else FRAME_OFF


class LedLogic:
    """Reed-switch gestures and LED phases.

    Call :meth:`tick` at ~20 Hz with the current time and reed state; it returns
    the :class:`Frame` to render.  Time is always passed in, so tests can drive
    it with a fake clock.
    """

    def __init__(
        self,
        probe: SystemProbe,
        actions: Actions,
        idle_timeout: float = LED_IDLE_TIMEOUT_SECS,
        hold_hotspot: float = HOLD_HOTSPOT_SECS,
        hold_shutdown: float = HOLD_SHUTDOWN_SECS,
        hold_mode: float = HOLD_MODE_SECS,
        hold_reset: float = HOLD_RESET_SECS,
        hold_cancel: float = HOLD_CANCEL_SECS,
        request_timeout: float = HOTSPOT_REQUEST_TIMEOUT_SECS,
        menu=None,
        on_display_timeout=None,
        on_menu_timeout=None,
        recovery_info=None,
    ) -> None:
        # The menu replaces the timed ladder, but only where it can be read:
        # the application passes one in when the display is live, and a device
        # without a panel keeps the ladder exactly as it was.
        self._menu = menu
        self._on_display_timeout = on_display_timeout
        self._on_menu_timeout = on_menu_timeout
        self._recovery_info = recovery_info
        self._probe = probe
        self._actions = actions
        self._idle_timeout = idle_timeout
        self._hold_hotspot = hold_hotspot
        self._hold_shutdown = hold_shutdown
        self._hold_mode = hold_mode
        self._hold_reset = hold_reset
        self._hold_cancel = hold_cancel
        self._request_timeout = request_timeout

        self.phase = Phase.BOOT
        self._deadline = 0.0  # phase-specific timeout
        self._next_probe = 0.0
        self._reed_was = False
        self._press_start = 0.0
        self._reed = _ReedFilter()
        # A threshold that fired while the magnet was still down has already
        # done its work; the release that follows must not also count.
        self._press_spent = False
        self._armed: str | None = None  # None | "hotspot" | "shutdown" | "mode" | "reset" | "cancel"
        self._armed_at = 0.0            # when the current held phase began (for the off gap)
        self._busy_target = False  # HOTSPOT_BUSY: expected hotspot_active
        self._ready = False

    # -- external events --------------------------------------------------

    def set_ready(self) -> None:
        """The application is up (dashboard answers) — leave the boot phase."""
        self._ready = True

    @property
    def armed(self) -> str | None:
        return self._armed

    def snapshot(self, now: float) -> LedSnapshot:
        """Current phase, gesture and probe state for the display."""
        p = self._probe
        return LedSnapshot(
            phase=self.phase,
            armed=self._armed,
            held_secs=self._reed.held(now),
            ready=self._ready,
            hotspot_active=p.hotspot_active,
            wifi_connected=p.wifi_connected,
            bt_connected=p.bt_connected,
            development=p.development,
            services_ok=getattr(p, "services_ok", True),
            failed_services=tuple(getattr(p, "failed_services", ())),
            ssid=getattr(p, "ssid", ""),
            ip=getattr(p, "ip", ""),
            menu=self._menu.view() if (self._menu and self._menu.open) else None,
            menu_available=self._menu is not None,
        )

    # -- main step --------------------------------------------------------

    def tick(self, now: float, reed_closed: bool) -> Frame:
        self._maybe_probe(now)
        # Everything below sees the debounced press, never the raw sample.
        self._reed.update(now, reed_closed)
        reed_closed = self._reed.closed
        self._handle_reed(now, reed_closed)

        if self.phase == Phase.BOOT and self._ready:
            self._enter_status(now)

        if self._menu is not None and self._menu.open:
            self._menu.tick(now)
            self._drain_menu(now)
            if not self._menu.open and self.phase == Phase.MENU:
                self._enter_status(now)
        elif self.phase == Phase.MENU:
            self._enter_status(now)

        # Phase transitions driven by time / probe results
        if self.phase == Phase.HOTSPOT_BUSY:
            if self._probe.hotspot_active == self._busy_target:
                logger.info("Hotspot is now %s", "up" if self._busy_target else "down")
                if self._busy_target:
                    self.phase = Phase.HOTSPOT_ON
                else:
                    self._enter_status(now)
            elif now >= self._deadline:
                logger.error(
                    "Hotspot request timed out (expected active=%s)", self._busy_target
                )
                self.phase = Phase.FAIL_FLASH
                self._deadline = now + FAIL_FLASH_SECS
        elif self.phase == Phase.FAIL_FLASH and now >= self._deadline:
            self._enter_status(now)
        elif self.phase == Phase.MODE_CONFIRM and now >= self._deadline:
            self._enter_status(now)
        elif self.phase == Phase.STATUS:
            if self._probe.hotspot_active:
                self.phase = Phase.HOTSPOT_ON
            elif now >= self._deadline and not reed_closed:
                self.phase = Phase.IDLE
        elif self.phase == Phase.HOTSPOT_ON and not self._probe.hotspot_active:
            self._enter_status(now)
        elif self.phase == Phase.IDLE and self._probe.hotspot_active:
            self.phase = Phase.HOTSPOT_ON

        return self._frame(reed_closed, now)

    # -- helpers ----------------------------------------------------------

    def _maybe_probe(self, now: float) -> None:
        if now < self._next_probe:
            return
        interval = (
            PROBE_INTERVAL_IDLE_SECS
            if self.phase in (Phase.IDLE, Phase.HOTSPOT_ON, Phase.BOOT)
            else PROBE_INTERVAL_ACTIVE_SECS
        )
        self._next_probe = now + interval
        if self.phase in (Phase.RESETTING, Phase.SHUTTING_DOWN):
            return
        try:
            self._probe.refresh()
        except Exception as exc:  # never let a probe kill the LED loop
            logger.debug("probe refresh failed: %s", exc)

    def _enter_status(self, now: float) -> None:
        self.phase = Phase.STATUS
        self._deadline = now + self._idle_timeout
        self._next_probe = 0.0  # refresh immediately on the next tick

    def _handle_reed(self, now: float, closed: bool) -> None:
        # The menu owns the magnet while it is open: a tap moves, a long press
        # activates.  Everything below (the timed ladder) is what a device
        # without a display still uses.
        if self._menu is not None and self._menu.open:
            self._handle_reed_in_menu(now, closed)
            self._reed_was = closed
            return

        if closed and not self._reed_was:
            # Press: show status right away (hotspot/reset phases keep their frame)
            self._press_start = self._reed.press_start
            self._press_spent = False
            self._armed = None
            if self.phase in (Phase.IDLE, Phase.STATUS):
                self._enter_status(now)
                self._probe_now()
        elif closed:
            held = self._reed.held(now)
            if self._menu is not None:
                # With a display, one hold opens the menu and the ladder below
                # is not used at all: no second-counting, and the destructive
                # actions sit behind a confirmation instead of a threshold.
                #
                # The menu opens the moment the threshold is crossed, while the
                # magnet is still down.  Waiting for the release meant guessing
                # the duration with no confirmation, so a hold meant as "open"
                # or "choose" was routinely let go a fraction too early and
                # arrived as a tap.  Now the panel answers under your hand.
                if (
                    not self._press_spent
                    and not self._reed.settling
                    and held >= HOLD_MENU_SECS
                ):
                    self._press_spent = True
                    self._arm("menu", now, held, "menu armed")
                    self._open_menu(now)
                return
            if held >= self._hold_cancel:
                self._arm("cancel", now, held, "gesture cancelled")
            elif held >= self._hold_reset:
                self._arm("reset", now, held, "factory reset armed")
            elif held >= self._hold_mode:
                self._arm("mode", now, held, "mode toggle armed")
            elif held >= self._hold_shutdown:
                self._arm("shutdown", now, held, "shutdown armed")
            elif held >= self._hold_hotspot:
                self._arm("hotspot", now, held, "hotspot toggle armed")
        elif self._reed_was:
            # Release: fire whatever was armed
            armed, self._armed = self._armed, None
            spent, self._press_spent = self._press_spent, False
            if spent:
                pass  # the threshold already fired while the magnet was down
            elif self.phase in (Phase.RESETTING, Phase.SHUTTING_DOWN, Phase.BOOT):
                pass  # ignore gestures while booting, resetting or shutting down
            elif armed == "menu":
                self._open_menu(now)
            elif armed == "cancel":
                logger.info("Gesture cancelled (held ≥ %.0f s)", self._hold_cancel)
                if self.phase in (Phase.STATUS, Phase.IDLE):
                    self._enter_status(now)
            elif armed == "shutdown":
                logger.warning("Shutdown triggered via reed switch (hold ≥ %.0f s)",
                               self._hold_shutdown)
                self.phase = Phase.SHUTTING_DOWN
                self._actions.shutdown()
            elif armed == "reset":
                logger.warning(
                    "Factory reset triggered via reed switch (hold ≥ %.0f s)",
                    self._hold_reset,
                )
                self.phase = Phase.RESETTING
                self._actions.factory_reset()
            elif armed == "mode":
                logger.warning(
                    "Mode toggle triggered via reed switch (hold ≥ %.0f s) — now %s",
                    self._hold_mode,
                    "PRODUCTION" if self._probe.development else "DEVELOPMENT",
                )
                self._actions.mode_toggle()
                self.phase = Phase.MODE_CONFIRM
                self._deadline = now + MODE_CONFIRM_SECS
                self._next_probe = now + 1.0  # pick the new mode up soon
            elif armed == "hotspot" and self.phase != Phase.HOTSPOT_BUSY:
                self._start_hotspot_request(now)
            elif self.phase in (Phase.STATUS, Phase.IDLE):
                self._enter_status(now)
        self._reed_was = closed

    def _handle_reed_in_menu(self, now: float, closed: bool) -> None:
        """Reed events while the menu is open: tap = next, hold = choose.

        The hold fires the instant MENU_SELECT_SECS is reached, with the magnet
        still down, so the panel confirms the choice while the bar that
        predicted it is still on screen.  Classifying on release meant judging
        the duration blind: let go a fraction early and the press became a tap
        that stepped to the next item, which is why "Back" and "Exit" were the
        hardest things in the menu to pick.
        """
        if closed and not self._reed_was:
            self._press_start = self._reed.press_start
            self._press_spent = False
            return
        if closed:
            if (
                not self._press_spent
                and not self._reed.settling
                and self._reed.held(now) >= MENU_SELECT_SECS
            ):
                self._press_spent = True
                self._menu.select(now)
                self._drain_menu(now)
            return
        if self._reed_was:
            spent, self._press_spent = self._press_spent, False
            if not spent:
                self._menu.tap(now)
                self._drain_menu(now)

    def _drain_menu(self, now: float) -> None:
        """Run whatever the menu asked for."""
        while True:
            action = self._menu.take_action()
            if action is None:
                return
            logger.info("Menu action: %s", action)
            if action == "hotspot":
                self._start_hotspot_request(now)
            elif action == "mode":
                self._actions.mode_toggle()
                self.phase = Phase.MODE_CONFIRM
                self._deadline = now + MODE_CONFIRM_SECS
                self._next_probe = now + 1.0
                self._menu.leave()
            elif action == "shutdown":
                logger.warning("Shutdown requested from the menu")
                self.phase = Phase.SHUTTING_DOWN
                self._actions.shutdown()
            elif action == "reboot":
                logger.warning("Restart requested from the menu")
                self.phase = Phase.RESETTING  # red blink until it goes down
                self._actions.reboot()
            elif action == "reset":
                logger.warning("Factory reset confirmed from the menu")
                self.phase = Phase.RESETTING
                self._actions.factory_reset()
            elif action.startswith("timeout:"):
                minutes = int(action.split(":", 1)[1])
                if self._on_display_timeout:
                    self._on_display_timeout(minutes)
            elif action.startswith("menusecs:"):
                seconds = int(action.split(":", 1)[1])
                if self._on_menu_timeout:
                    self._on_menu_timeout(seconds)
            elif action == "recovery":
                if self._recovery_info:
                    lines = self._recovery_info()
                    if lines:
                        self._menu.show_detail(tuple(lines), now)

    def _open_menu(self, now: float) -> None:
        self._menu.enter(now)
        self.phase = Phase.MENU
        logger.info("Magnet menu opened")

    def _arm(self, what: str, now: float, held: float, what_log: str) -> None:
        if self._armed != what:
            logger.info("Reed held %.0f s — %s", held, what_log)
            self._armed = what
            self._armed_at = now

    def _start_hotspot_request(self, now: float) -> None:
        """Toggle the hotspot.  Shared by the timed ladder and the menu."""
        if self.phase == Phase.HOTSPOT_BUSY:
            return
        self._probe_now()
        self._busy_target = not self._probe.hotspot_active
        logger.info(
            "Hotspot %s requested", "start" if self._busy_target else "stop"
        )
        self.phase = Phase.HOTSPOT_BUSY
        self._deadline = now + self._request_timeout
        self._next_probe = now + PROBE_INTERVAL_ACTIVE_SECS
        if self._busy_target:
            self._actions.hotspot_start()
        else:
            self._actions.hotspot_stop()

    def _probe_now(self) -> None:
        try:
            self._probe.refresh()
        except Exception as exc:
            logger.debug("probe refresh failed: %s", exc)

    def _frame(self, reed_closed: bool, now: float = 0.0) -> Frame:
        if self.phase == Phase.RESETTING:
            return FRAME_RESET
        if self.phase == Phase.SHUTTING_DOWN:
            return FRAME_SHUTDOWN
        if reed_closed and self.phase != Phase.BOOT:
            # Held: the press is acknowledged by a short white blink, then dark
            # until the first threshold, then one STEADY colour per phase, each
            # entered through a short dark gap so the step registers even
            # between similar hues.
            if self._armed is None or self._armed == "cancel":
                if self._armed is None and now - self._press_start < ACK_BLINK_SECS:
                    return ack_frame(now - self._press_start)
                return FRAME_OFF
            if now - self._armed_at < PHASE_GAP_SECS:
                return FRAME_OFF
            return {
                # The menu is not an armed action with a colour of its own:
                # the panel shows the progress towards opening it.
                "menu": FRAME_OFF,
                "hotspot": FRAME_ARM_HOTSPOT,
                "shutdown": FRAME_ARM_SHUTDOWN,
                "mode": FRAME_ARM_MODE,
                "reset": FRAME_ARM_RESET,
            }[self._armed]
        if self.phase == Phase.BOOT:
            return FRAME_BOOT
        if self.phase == Phase.MENU:
            # Deliberately the ordinary status colour.  Blue is documented as
            # "the hotspot is up" everywhere, including both manuals, and a
            # second meaning for it made the LED ambiguous.  The panel says
            # the menu is open; the LED keeps saying what the device is doing.
            return status_frame(self._probe)
        if self.phase == Phase.HOTSPOT_BUSY:
            return FRAME_HOTSPOT_BUSY
        if self.phase == Phase.FAIL_FLASH:
            return FRAME_RESET
        if self.phase == Phase.MODE_CONFIRM:
            return FRAME_MODE_CONFIRM
        if self.phase == Phase.HOTSPOT_ON:
            return FRAME_HOTSPOT_ON
        if self.phase == Phase.STATUS:
            return status_frame(self._probe)
        return FRAME_OFF


# ---------------------------------------------------------------------------
# Hardware backend
# ---------------------------------------------------------------------------


class _RpiGpioBackend:
    """Reed input + three LED outputs via the RPi.GPIO API (rpi-lgpio shim)."""

    _CLAIM_ATTEMPTS = 10  # ipr-led-boot.service may still be releasing
    _CLAIM_RETRY_SECS = 0.5  # the lines when we start

    def __init__(self, reed_pin: int, led_pins: tuple[int, int, int]) -> None:
        self._reed = reed_pin
        self._leds = led_pins
        self._last: Color | None = None

    def setup(self) -> None:
        _GPIO.setmode(_GPIO.BCM)
        _GPIO.setwarnings(False)
        last_exc: Exception | None = None
        for attempt in range(1, self._CLAIM_ATTEMPTS + 1):
            try:
                _GPIO.setup(self._reed, _GPIO.IN, pull_up_down=_GPIO.PUD_UP)
                for pin in self._leds:
                    _GPIO.setup(pin, _GPIO.OUT, initial=_GPIO.LOW)
                return
            except Exception as exc:  # GPIO busy — boot blinker not gone yet
                last_exc = exc
                logger.info(
                    "GPIO claim attempt %d/%d failed: %s",
                    attempt,
                    self._CLAIM_ATTEMPTS,
                    exc,
                )
                time.sleep(self._CLAIM_RETRY_SECS)
        raise RuntimeError(f"could not claim GPIO lines: {last_exc}")

    def reed_closed(self) -> bool:
        return _GPIO.input(self._reed) == _GPIO.LOW

    def led(self, color: Color) -> None:
        if color == self._last:
            return
        for pin, val in zip(self._leds, color):
            _GPIO.output(pin, _GPIO.HIGH if val else _GPIO.LOW)
        self._last = color

    def cleanup(self) -> None:
        try:
            self.led(OFF)
            _GPIO.cleanup()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# GpioMonitor — public API
# ---------------------------------------------------------------------------


class GpioMonitor:
    """Background thread that drives the reed switch and RGB LED.

    Instantiate once, call start() from main() before the other subsystems so
    the boot blink continues seamlessly, call set_ready() when the dashboard
    answers, and stop() on shutdown.  Logs a warning and does nothing when GPIO
    is unavailable.
    """

    TICK_SECS = 0.05

    def __init__(
        self,
        reed_pin: int = _REED_PIN,
        led_r_pin: int = _LED_R_PIN,
        led_g_pin: int = _LED_G_PIN,
        led_b_pin: int = _LED_B_PIN,
        led_idle_timeout: int = LED_IDLE_TIMEOUT_SECS,
        probe: SystemProbe | None = None,
        actions: Actions | None = None,
        backend: object | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._reed_pin = reed_pin
        self._led_pins = (led_r_pin, led_g_pin, led_b_pin)
        self._logic = LedLogic(
            probe or SystemProbe(),
            actions or SystemActions(),
            idle_timeout=led_idle_timeout,
        )
        self._backend = backend
        self._clock = clock
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.active = False

    # -- lifecycle --------------------------------------------------------

    def start(self) -> None:
        if self._backend is None:
            if not _GPIO_AVAILABLE:
                logger.warning(
                    "GPIO monitor disabled — RPi.GPIO not importable (%s). "
                    "On a Pi: create the venv with --system-site-packages and "
                    "install python3-rpi-lgpio.",
                    _GPIO_IMPORT_ERROR,
                )
                return
            self._backend = _RpiGpioBackend(self._reed_pin, self._led_pins)
        try:
            self._backend.setup()  # type: ignore[attr-defined]
        except Exception as exc:
            logger.error("GPIO monitor disabled — %s", exc)
            self._backend = None
            return
        self.active = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="gpio-monitor"
        )
        self._thread.start()
        logger.info(
            "GPIO monitor started (reed=GPIO%d, LED R/G/B=GPIO%d/%d/%d)",
            self._reed_pin,
            *self._led_pins,
        )

    def set_ready(self) -> None:
        """Application is fully up: end the boot blink and show status."""
        self._logic.set_ready()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        if self._backend is None:
            return
        if self._logic.phase == Phase.SHUTTING_DOWN:
            # Leave the LED white while the OS finishes stopping; the pins keep
            # their level after our lines are released, and ipr-led-halt.service
            # turns them off just before the kernel halts ("safe to unplug").
            try:
                self._backend.led(WHITE)  # type: ignore[attr-defined]
            except Exception:
                pass
            return
        self._backend.cleanup()  # type: ignore[attr-defined]

    @property
    def phase(self) -> Phase:
        return self._logic.phase

    def snapshot(self) -> LedSnapshot:
        """State for the OLED display (see oled/manager.py)."""
        return self._logic.snapshot(self._clock())

    # -- loop -------------------------------------------------------------

    def _run(self) -> None:
        backend = self._backend
        assert backend is not None
        while not self._stop.is_set():
            now = self._clock()
            try:
                closed = backend.reed_closed()  # type: ignore[attr-defined]
                frame = self._logic.tick(now, closed)
                color = frame.color if frame.is_on(now) else OFF
                backend.led(color)  # type: ignore[attr-defined]
            except Exception as exc:
                logger.error("GPIO monitor loop error: %s", exc)
                time.sleep(1.0)
                continue
            time.sleep(self.TICK_SECS)
