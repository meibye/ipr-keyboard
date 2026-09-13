"""GPIO monitor — reed switch trigger and RGB LED status indicator.

Hardware connections (BCM numbering, Flirc Pi Zero 2 W case):

  Reed switch  GPIO 27  Pin 13   NO type, one leg to GPIO, other leg to GND
  RGB LED red  GPIO 22  Pin 15   150 Ω series resistor, common cathode to GND
  RGB LED grn  GPIO 23  Pin 16   150 Ω series resistor, common cathode to GND
  RGB LED blu  GPIO 24  Pin 18    22 Ω series resistor, common cathode to GND

Reed switch interaction (the magnet is the only control on the device):
  Press                  LED goes dark at once ("press registered"), so every
                         arming colour below blinks against dark — visible even
                         when the LED was solid blue (hotspot) or solid purple
  Tap  (release < 3 s)   Wake LED; show system status for GpioLedIdleSeconds
  Hold ≥ 3 s             LED blinks blue; release to toggle the management hotspot
  Hold ≥ 6 s             LED blinks cyan; release for a controlled shutdown
  Hold ≥ 10 s            LED blinks purple; release to toggle production/development mode
  Hold ≥ 15 s            LED blinks red; release to delete WiFi profiles and reboot
  Hold ≥ 20 s            LED goes off; release does nothing (cancel)

LED colour map:
  White solid        Power on — firmware / kernel (config.txt gpio= line)
  White fast blink   Booting — ipr-led-boot.service, then this module until the
                     web dashboard answers /health
  Green solid        All OK — WiFi + Bluetooth connected
  Amber solid        WiFi OK, Bluetooth not yet connected
  Red slow blink     No WiFi configured / cannot connect
  Red solid          A core service is not running (bluetooth, bt_hid_ble,
                     bt_hid_agent_unified) — see /var/lib/ipr-keyboard/incidents.log
  Blue fast blink    Hotspot request in progress (arming, starting or stopping)
  Blue solid         Hotspot active (setup mode) — stays on while the hotspot is up
  Cyan fast blink    Shutdown arming (hold ≥ 6 s)
  Cyan solid         Shutting down — wait until the LED goes off before unplugging
                     (ipr-led-halt.service turns it off just before the kernel halts)
  Purple fast blink  Mode toggle arming (hold ≥ 10 s)
  Purple solid 3 s   Mode changed (confirmation)
  Purple blip        Every 4 s while in DEVELOPMENT mode (ports open) — on top of
                     whatever else the LED shows, including off
  Red fast blink     Factory reset arming (hold ≥ 15 s) / in progress, or a failed
                     hotspot request
  Off                Idle — no power draw

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
MODE_CONFIRM_SECS: float = 3.0
DEV_BLIP_PERIOD_SECS: float = 4.0    # development-mode heartbeat
DEV_BLIP_ON_SECS: float = 0.15
LED_IDLE_TIMEOUT_SECS: int = 30

HOTSPOT_REQUEST_TIMEOUT_SECS: float = 40.0  # nmcli con up on a Zero W can be slow
FAIL_FLASH_SECS: float = 3.0
PROBE_INTERVAL_ACTIVE_SECS: float = 2.0  # while the LED is showing status
PROBE_INTERVAL_IDLE_SECS: float = 5.0  # while the LED is off / blue solid

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
CYAN: Color = (0, 1, 1)

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

    def refresh(self) -> None:
        self.hotspot_active, self.wifi_connected = self._network_state()
        self.bt_connected = self._bt_state()
        self.development = self._mode_state()
        self.services_ok = self._services_state()

    @staticmethod
    def _services_state() -> bool:
        """True when every core service is active (one systemctl call)."""
        try:
            out = subprocess.run(
                ["systemctl", "is-active", *CORE_SERVICES],
                capture_output=True, text=True, timeout=5,
            ).stdout.split()
            return bool(out) and all(s == "active" for s in out)
        except Exception:
            return True  # cannot tell — do not raise a false alarm

    @staticmethod
    def _mode_state() -> bool:
        """True in development mode (ports open); missing/unknown = production."""
        try:
            with open(MODE_FILE, encoding="utf-8") as fh:
                return fh.read().strip() == "development"
        except OSError:
            return False

    @staticmethod
    def _network_state() -> tuple[bool, bool]:
        hotspot = wifi = False
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
        except Exception:
            pass
        return hotspot, wifi

    @staticmethod
    def _bt_state() -> bool:
        try:
            out = subprocess.check_output(
                ["bluetoothctl", "devices", "Connected"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            return bool(out.strip())
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Privileged actions — run through the root helper, never block the LED loop
# ---------------------------------------------------------------------------


class Actions(Protocol):
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
    SHUTTING_DOWN = "shutting_down"  # cyan solid until the kernel halts
    RESETTING = "resetting"  # red fast blink until reboot


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
FRAME_BOOT = Frame(WHITE, FAST_HZ)
FRAME_HOTSPOT_BUSY = Frame(BLUE, FAST_HZ)
FRAME_HOTSPOT_ON = Frame(BLUE)
FRAME_RESET = Frame(RED, FAST_HZ)
FRAME_MODE_ARM = Frame(PURPLE, FAST_HZ)
FRAME_SHUTDOWN_ARM = Frame(CYAN, FAST_HZ)
FRAME_SHUTDOWN = Frame(CYAN)
FRAME_MODE_CONFIRM = Frame(PURPLE)


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
    ) -> None:
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
        self._armed: str | None = None  # None | "hotspot" | "shutdown" | "mode" | "reset" | "cancel"
        self._busy_target = False  # HOTSPOT_BUSY: expected hotspot_active
        self._ready = False

    # -- external events --------------------------------------------------

    def set_ready(self) -> None:
        """The application is up (dashboard answers) — leave the boot phase."""
        self._ready = True

    @property
    def armed(self) -> str | None:
        return self._armed

    def dev_blip(self, now: float) -> bool:
        """True during the short purple blip that marks DEVELOPMENT mode.

        Shown every DEV_BLIP_PERIOD_SECS on top of whatever the LED shows
        (including off), except while booting, arming a gesture or confirming
        a mode change — the user must be able to tell at a glance that the
        device has open ports.
        """
        if not self._probe.development:
            return False
        if self.phase in (Phase.BOOT, Phase.MODE_CONFIRM, Phase.RESETTING, Phase.SHUTTING_DOWN):
            return False
        if self._armed is not None:
            return False
        return (now % DEV_BLIP_PERIOD_SECS) < DEV_BLIP_ON_SECS

    # -- main step --------------------------------------------------------

    def tick(self, now: float, reed_closed: bool) -> Frame:
        self._maybe_probe(now)
        self._handle_reed(now, reed_closed)

        if self.phase == Phase.BOOT and self._ready:
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

        return self._frame(reed_closed)

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
        if closed and not self._reed_was:
            # Press: show status right away (hotspot/reset phases keep their frame)
            self._press_start = now
            self._armed = None
            if self.phase in (Phase.IDLE, Phase.STATUS):
                self._enter_status(now)
                self._probe_now()
        elif closed:
            held = now - self._press_start
            if held >= self._hold_cancel:
                if self._armed != "cancel":
                    logger.info("Reed held %.0f s — gesture cancelled", held)
                self._armed = "cancel"
            elif held >= self._hold_reset:
                if self._armed != "reset":
                    logger.info("Reed held %.0f s — factory reset armed", held)
                self._armed = "reset"
            elif held >= self._hold_mode:
                if self._armed != "mode":
                    logger.info("Reed held %.0f s — mode toggle armed", held)
                self._armed = "mode"
            elif held >= self._hold_shutdown:
                if self._armed != "shutdown":
                    logger.info("Reed held %.0f s — shutdown armed", held)
                self._armed = "shutdown"
            elif held >= self._hold_hotspot and self._armed is None:
                logger.info("Reed held %.0f s — hotspot toggle armed", held)
                self._armed = "hotspot"
        elif self._reed_was:
            # Release: fire whatever was armed
            armed, self._armed = self._armed, None
            if self.phase in (Phase.RESETTING, Phase.SHUTTING_DOWN, Phase.BOOT):
                pass  # ignore gestures while booting, resetting or shutting down
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
                self._probe_now()
                self._busy_target = not self._probe.hotspot_active
                logger.info(
                    "Hotspot %s requested via reed switch",
                    "start" if self._busy_target else "stop",
                )
                self.phase = Phase.HOTSPOT_BUSY
                self._deadline = now + self._request_timeout
                self._next_probe = now + PROBE_INTERVAL_ACTIVE_SECS
                if self._busy_target:
                    self._actions.hotspot_start()
                else:
                    self._actions.hotspot_stop()
            elif self.phase in (Phase.STATUS, Phase.IDLE):
                self._enter_status(now)
        self._reed_was = closed

    def _probe_now(self) -> None:
        try:
            self._probe.refresh()
        except Exception as exc:
            logger.debug("probe refresh failed: %s", exc)

    def _frame(self, reed_closed: bool) -> Frame:
        if self.phase == Phase.RESETTING:
            return FRAME_RESET
        if self.phase == Phase.SHUTTING_DOWN:
            return FRAME_SHUTDOWN
        if reed_closed and self.phase != Phase.BOOT:
            if self._armed is None:
                # Dark while held before the first threshold: the press is
                # acknowledged and the 3 s blue blink is unmistakable even
                # when the LED was solid blue (hotspot on) a moment ago.
                return FRAME_OFF
            if self._armed == "cancel":
                return FRAME_OFF
            if self._armed == "reset":
                return FRAME_RESET
            if self._armed == "mode":
                return FRAME_MODE_ARM
            if self._armed == "shutdown":
                return FRAME_SHUTDOWN_ARM
            if self._armed == "hotspot":
                return FRAME_HOTSPOT_BUSY
        if self.phase == Phase.BOOT:
            return FRAME_BOOT
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
            # Leave the LED cyan while the OS finishes stopping; the pins keep
            # their level after our lines are released, and ipr-led-halt.service
            # turns them off just before the kernel halts ("safe to unplug").
            try:
                self._backend.led(CYAN)  # type: ignore[attr-defined]
            except Exception:
                pass
            return
        self._backend.cleanup()  # type: ignore[attr-defined]

    @property
    def phase(self) -> Phase:
        return self._logic.phase

    # -- loop -------------------------------------------------------------

    def _run(self) -> None:
        backend = self._backend
        assert backend is not None
        while not self._stop.is_set():
            now = self._clock()
            try:
                closed = backend.reed_closed()  # type: ignore[attr-defined]
                frame = self._logic.tick(now, closed)
                if self._logic.dev_blip(now):
                    color = PURPLE
                else:
                    color = frame.color if frame.is_on(now) else OFF
                backend.led(color)  # type: ignore[attr-defined]
            except Exception as exc:
                logger.error("GPIO monitor loop error: %s", exc)
                time.sleep(1.0)
                continue
            time.sleep(self.TICK_SECS)
