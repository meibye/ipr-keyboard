"""OledManager — the thread that keeps the OLED in step with the device.

Polls at 4 Hz (like the LED, nothing pushes events):

  * the LED/magnet state from ``GpioMonitor.snapshot()`` (phase, gesture,
    probe results), or from :class:`StandaloneSource` when GPIO is off;
  * ``transmission.get()`` for sends;
  * ``usb.detector.pen_presence()`` for the pen;
  * the connected host name, fetched once per Bluetooth connection.

On-policy (docs/architecture/oled-display-design.md § 3): the panel is on
while the LED phase says someone is looking (boot, status window, magnet
held, hotspot up, shutdown…), while a send runs and ``OledSendHoldSeconds``
after it, and for the status window after any status change.  Otherwise it
sleeps (SSD1306 ``0xAE``).  Frames are only written when the screen changes,
except while a long line rolls (``OledMarqueeFps``).

Absent hardware is not an error: ``start()`` logs one warning and returns,
exactly like ``GpioMonitor`` without ``RPi.GPIO``.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from collections.abc import Callable

from .. import transmission
from ..logging.logger import get_logger
from ..usb.detector import pen_presence
from . import screens
from .ssd1306 import Ssd1306, device_path, pil_available, pil_unavailable_reason, probe

logger = get_logger()

TICK_SECS = 0.25
LOW_CONTRAST_AFTER_SECS = 300.0  # dim after 5 min continuously on (burn-in)
LOW_CONTRAST_DIVISOR = 4
HOTSPOT_SECRET = "/etc/ipr-hotspot.secret"
STANDALONE_PROBE_SECS = 5.0

LOG_STARTED = "OLED display started"
LOG_DISABLED = "OLED display disabled"


class StandaloneSource:
    """LED-less stand-in for GpioMonitor: BOOT -> STATUS (idle window) -> IDLE.

    Used when GpioEnabled is false or RPi.GPIO is missing, so the display
    still shows boot, status changes and sends.
    """

    def __init__(self, idle_seconds: float, probe=None, clock=time.monotonic) -> None:
        from ..gpio_monitor import LedSnapshot, Phase, SystemProbe

        self._Snapshot = LedSnapshot
        self._Phase = Phase
        self._probe = probe or SystemProbe()
        self._idle = idle_seconds
        self._clock = clock
        self._ready_at: float | None = None
        self._next_probe = 0.0

    def set_ready(self) -> None:
        if self._ready_at is None:
            self._ready_at = self._clock()

    def snapshot(self):
        now = self._clock()
        if now >= self._next_probe:
            self._next_probe = now + STANDALONE_PROBE_SECS
            try:
                self._probe.refresh()
            except Exception as exc:
                logger.debug("probe refresh failed: %s", exc)
        if self._ready_at is None:
            phase = self._Phase.BOOT
        elif now - self._ready_at < self._idle:
            phase = self._Phase.STATUS
        else:
            phase = self._Phase.IDLE
        p = self._probe
        return self._Snapshot(
            phase=phase,
            armed=None,
            held_secs=0.0,
            ready=self._ready_at is not None,
            hotspot_active=p.hotspot_active,
            wifi_connected=p.wifi_connected,
            bt_connected=p.bt_connected,
            development=p.development,
            services_ok=getattr(p, "services_ok", True),
            failed_services=tuple(getattr(p, "failed_services", ())),
            ssid=getattr(p, "ssid", ""),
            ip=getattr(p, "ip", ""),
        )


def read_hotspot_ssid(path: str = HOTSPOT_SECRET) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("SSID="):
                    return line[5:].strip()
    except OSError:
        pass
    return ""


def bluetooth_host_name() -> str:
    """Name of the connected host via bluetoothctl.

    Called only on the connected edge: every bluetoothctl run registers an
    Adv Monitor app with bluetoothd, which is why the LED probe reads sysfs.
    """
    try:
        out = subprocess.check_output(
            ["bluetoothctl", "devices", "Connected"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        for line in out.splitlines():
            parts = line.split(None, 2)
            if len(parts) >= 3:
                return parts[2].strip()
    except Exception:
        pass
    return ""


class OledManager:
    """Background thread driving the display.  See module docstring."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        bus: int = 1,
        address: int = 0x3C,
        contrast: int = 128,
        rotate: int = 0,
        idle_seconds: float = 30.0,
        display_timeout_minutes: int = 30,
        send_hold_seconds: float = 10.0,
        marquee_fps: float = 8.0,
        source=None,
        display=None,
        renderer=None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        pen: Callable[[], str] = pen_presence,
        tx: Callable[[], dict] = transmission.get,
        bt_host: Callable[[], str] = bluetooth_host_name,
        hotspot_ssid: Callable[[], str] = read_hotspot_ssid,
    ) -> None:
        self._enabled = enabled
        self._bus = bus
        self._address = address
        self._contrast = contrast
        self._rotate = rotate
        self._idle = float(idle_seconds)
        # How long the panel stays on after the last magnet contact or status
        # change.  Separate from the LED's idle window on purpose: the LED is
        # glanceable and costs nothing, the panel is read and wears out.
        self._display_hold = max(60.0, float(display_timeout_minutes) * 60.0)
        self._send_hold = float(send_hold_seconds)
        self._marquee_tick = 1.0 / max(1.0, float(marquee_fps))
        self._source = source
        self._display = display
        self._renderer = renderer
        self._clock = clock
        self._wall_clock = wall_clock
        self._pen = pen
        self._tx = tx
        self._bt_host = bt_host
        self._hotspot_ssid = hotspot_ssid

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.active = False

        # loop state
        self._awake = False
        self._on_since = 0.0
        self._dimmed = False
        self._wake_until = 0.0
        self._last_key: tuple | None = None
        self._last_tx_mark: tuple | None = None
        self._last_screen: screens.Screen | None = None
        self._rolling = False
        self._tx_hold_until = 0.0
        self._bt_was = False
        self._bt_host_name = ""
        self._hotspot_was = False
        self._hotspot_name = ""
        self._last_phase = screens.BOOT  # phase seen by the last tick
        self.frames = 0

    # -- lifecycle --------------------------------------------------------

    def start(self) -> None:
        if not self._enabled:
            logger.info("%s — OledEnabled is false", LOG_DISABLED)
            return
        if self._renderer is None:
            if not pil_available():
                logger.warning(
                    "%s — Pillow not importable (%s). On a Pi: install python3-pil "
                    "and create the venv with --system-site-packages.",
                    LOG_DISABLED,
                    pil_unavailable_reason(),
                )
                return
            from .render import Renderer

            self._renderer = Renderer()
        if self._display is None:
            if not os.path.exists(device_path(self._bus)):
                logger.warning(
                    "%s — %s missing (dtparam=i2c_arm=on + i2c-dev; see "
                    "scripts/headless/install_oled_support.sh)",
                    LOG_DISABLED,
                    device_path(self._bus),
                )
                return
            if not probe(self._bus, self._address):
                logger.warning(
                    "%s — nothing answers at 0x%02X on %s (not connected, or the app "
                    "user is not in group i2c)",
                    LOG_DISABLED,
                    self._address,
                    device_path(self._bus),
                )
                return
            self._display = Ssd1306(
                self._bus, self._address, self._contrast, self._rotate
            )
        if self._source is None:
            self._source = StandaloneSource(self._idle, clock=self._clock)
        try:
            self._display.setup()
        except Exception as exc:
            logger.error("%s — %s", LOG_DISABLED, exc)
            self._display = None
            return
        self._awake = True
        self._on_since = self._clock()
        self.active = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="oled-display"
        )
        self._thread.start()
        logger.info("%s (bus %d, 0x%02X)", LOG_STARTED, self._bus, self._address)

    def set_display_timeout(self, minutes: int) -> None:
        """Change the on-time, from the magnet menu.  Takes effect at once."""
        self._display_hold = max(60.0, float(minutes) * 60.0)
        logger.info("OLED display timeout set to %d minutes", minutes)

    def set_ready(self) -> None:
        """Forwarded to a StandaloneSource; GpioMonitor has its own set_ready()."""
        if isinstance(self._source, StandaloneSource):
            self._source.set_ready()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        if self._display is None:
            return
        # Decide from what the loop last saw — never probe here: stop() runs
        # from the SIGTERM handler, and a probe's subprocess wait sleeps.
        try:
            if self._last_phase == screens.SHUTTING_DOWN:
                # Leave "SHUTTING DOWN" on; ipr-led-halt.service blanks the
                # panel at the same moment it turns the LED off.
                return
            self._display.sleep()
        except Exception:
            pass
        finally:
            try:
                self._display.close()
            except Exception:
                pass

    # -- loop -------------------------------------------------------------

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                rolling = self._tick(self._clock())
            except Exception as exc:
                # The type matters: a StopIteration from screen
                # composition logged as "OLED loop error: " with an
                # empty message, and the panel simply froze on its last
                # frame with nothing to say why.
                logger.error(
                    "OLED loop error: %s: %s", type(exc).__name__, exc,
                    exc_info=True,
                )
                rolling = False
                time.sleep(1.0)
            time.sleep(self._marquee_tick if rolling else TICK_SECS)

    def _tick(self, now: float) -> bool:
        """One poll: returns True when a long line is rolling (redraw faster)."""
        snap = self._snapshot(now)

        # Any contact with the magnet starts a fresh display period -- a tap
        # is how the user says "I am looking at this".
        if snap.held_secs > 0:
            self._wake_until = max(self._wake_until, now + self._display_hold)

        key = screens.status_key(snap)
        if self._last_key is None:
            self._last_key = key
        elif key != self._last_key:
            self._last_key = key
            self._wake_until = now + self._display_hold

        tx_mark = (snap.tx_state, snap.tx_last_at, snap.tx_total, snap.tx_reason)
        if snap.tx_state in ("success", "failed") and tx_mark != self._last_tx_mark:
            self._tx_hold_until = now + self._send_hold
            self._wake_until = max(self._wake_until, self._tx_hold_until)
        self._last_tx_mark = tx_mark
        if snap.tx_recent != (now < self._tx_hold_until):
            snap = screens.Snapshot(
                **{**snap.__dict__, "tx_recent": now < self._tx_hold_until}
            )

        if not (screens.wants_display(snap) or now < self._wake_until):
            self._sleep_panel()
            return False

        self._wake_panel(now)
        screen = screens.compose(snap)
        if screen == self._last_screen and not self._rolling:
            return False
        image, self._rolling = self._renderer.render(screen, now)
        self._display.show(image)
        self._last_screen = screen
        self.frames += 1
        return self._rolling

    def _sleep_panel(self) -> None:
        if not self._awake:
            return
        self._display.sleep()
        self._awake = False
        self._last_screen = None
        self._rolling = False
        self._renderer.reset()

    def _wake_panel(self, now: float) -> None:
        if not self._awake:
            if self._dimmed:
                self._display.contrast(self._contrast)
                self._dimmed = False
            self._display.wake()
            self._awake = True
            self._on_since = now
        elif not self._dimmed and now - self._on_since > LOW_CONTRAST_AFTER_SECS:
            self._display.contrast(max(1, self._contrast // LOW_CONTRAST_DIVISOR))
            self._dimmed = True

    # -- state gathering --------------------------------------------------

    def _snapshot(self, now: float) -> screens.Snapshot:
        led = self._source.snapshot()
        phase = str(getattr(led.phase, "value", led.phase))
        self._last_phase = phase

        if led.bt_connected and not self._bt_was:
            self._bt_host_name = self._bt_host()
        elif not led.bt_connected:
            self._bt_host_name = ""
        self._bt_was = led.bt_connected

        if led.hotspot_active and not self._hotspot_was:
            self._hotspot_name = self._hotspot_ssid()
        self._hotspot_was = led.hotspot_active

        tx = self._tx()
        return screens.Snapshot(
            phase=phase,
            armed=led.armed,
            held_secs=led.held_secs,
            ready=led.ready,
            development=led.development,
            services_ok=led.services_ok,
            failed_services=tuple(led.failed_services),
            bt_connected=led.bt_connected,
            bt_host=self._bt_host_name,
            pen=self._pen(),
            wifi_connected=led.wifi_connected,
            ssid=led.ssid,
            ip=led.ip,
            hotspot_active=led.hotspot_active,
            hotspot_ssid=self._hotspot_name,
            tx_state=str(tx.get("state", "idle")),
            tx_chars=int(tx.get("chars", 0) or 0),
            tx_total=int(tx.get("items_sent", 0) or 0),
            tx_reason=str(tx.get("explanation", "") or ""),
            tx_last_at=tx.get("last_success_at"),
            tx_sent=int(tx.get("chars_sent", 0) or 0),
            menu=getattr(led, "menu", None),
            menu_available=getattr(led, "menu_available", False),
        )
