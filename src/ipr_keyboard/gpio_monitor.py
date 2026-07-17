"""GPIO monitor — reed switch trigger and RGB LED status indicator.

Hardware connections (BCM numbering, Flirc Pi Zero 2 W case):

  Reed switch  GPIO 27  Pin 13   NO type, one leg to GPIO, other leg to GND
  RGB LED red  GPIO 22  Pin 15   150 Ω series resistor, common cathode to GND
  RGB LED grn  GPIO 23  Pin 16   150 Ω series resistor, common cathode to GND
  RGB LED blu  GPIO 24  Pin 18    33 Ω series resistor, common cathode to GND

Test rig (three separate LEDs until RGB package arrives):
  Red    GPIO 22  150 Ω    Yellow (green substitute)  GPIO 23  150 Ω
  Blue   GPIO 24   33 Ω    All cathodes connected to GND independently

Reed switch interaction:
  Tap  (release < 3 s)   Wake LED; show system status for 30 s then off
  Hold ≥ 3 s             Toggle management hotspot; LED confirms with blue
  Hold ≥ 10 s            Factory reset: delete WiFi profiles and reboot;
                         LED confirms with red fast blink

LED colour map:
  White fast blink   Boot / startup (3 s on first run)
  Green solid        All OK — WiFi + Bluetooth connected
  Amber solid        WiFi OK, Bluetooth not yet connected  [test rig: yellow]
  Red slow blink     No WiFi configured / cannot connect
  Blue solid         Hotspot active (setup mode)
  Blue fast blink    Hotspot arming (hold ≥ 3 s while reed closed)
  Red fast blink     Factory reset arming (hold ≥ 10 s while reed closed)
  Off                Idle — no power draw
"""
from __future__ import annotations

import subprocess
import threading
import time
from typing import Tuple

from .logging.logger import get_logger

logger = get_logger()

# ---------------------------------------------------------------------------
# GPIO availability
# ---------------------------------------------------------------------------

try:
    import RPi.GPIO as _GPIO
    _GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    _GPIO_AVAILABLE = False


def gpio_available() -> bool:
    """Return True when running on a Raspberry Pi with RPi.GPIO installed."""
    return _GPIO_AVAILABLE


# ---------------------------------------------------------------------------
# Default pin assignments (overridden by AppConfig.Gpio* fields)
# ---------------------------------------------------------------------------

_REED_PIN: int = 27
_LED_R_PIN: int = 22
_LED_G_PIN: int = 23
_LED_B_PIN: int = 24

_HOLD_HOTSPOT_SECS: float = 3.0
_HOLD_RESET_SECS: float = 10.0
_LED_IDLE_TIMEOUT_SECS: int = 30

_HOTSPOT_SERVICE = "ipr-provision.service"
_WIFI_SERVICE_TIMEOUT = 5   # seconds to wait for hotspot service change

# ---------------------------------------------------------------------------
# System state helpers
# ---------------------------------------------------------------------------


def _hotspot_active() -> bool:
    return subprocess.call(
        ["systemctl", "is-active", "--quiet", _HOTSPOT_SERVICE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ) == 0


def _wifi_connected() -> bool:
    """True when wlan0 has an active (non-hotspot) WiFi connection."""
    try:
        out = subprocess.check_output(
            ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "dev"],
            text=True, stderr=subprocess.DEVNULL,
        )
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 3 and parts[1] == "wifi" and parts[2] == "connected":
                return True
    except Exception:
        pass
    return False


def _bt_connected() -> bool:
    """True when at least one Bluetooth device is connected."""
    try:
        out = subprocess.check_output(
            ["bluetoothctl", "devices", "Connected"],
            text=True, stderr=subprocess.DEVNULL,
        )
        return bool(out.strip())
    except Exception:
        return False


def _state_color() -> Tuple[int, int, int]:
    """Return (R, G, B) 0/1 reflecting the current system state."""
    if _hotspot_active():
        return (0, 0, 1)   # blue  — setup mode
    if not _wifi_connected():
        return (1, 0, 0)   # red   — no home network
    if _bt_connected():
        return (0, 1, 0)   # green — all good
    return (1, 1, 0)       # amber — WiFi OK, BT waiting


# ---------------------------------------------------------------------------
# LED helper (only instantiated on real hardware)
# ---------------------------------------------------------------------------


class _Led:
    def __init__(self, r_pin: int, g_pin: int, b_pin: int) -> None:
        self._pins = (r_pin, g_pin, b_pin)
        for pin in self._pins:
            _GPIO.setup(pin, _GPIO.OUT, initial=_GPIO.LOW)

    def set(self, r: int, g: int, b: int) -> None:
        for pin, val in zip(self._pins, (r, g, b)):
            _GPIO.output(pin, _GPIO.HIGH if val else _GPIO.LOW)

    def off(self) -> None:
        self.set(0, 0, 0)


# ---------------------------------------------------------------------------
# GpioMonitor — public API
# ---------------------------------------------------------------------------


class GpioMonitor:
    """Background thread that drives the reed switch and RGB LED.

    Instantiate once, call start() from main(), call stop() on shutdown.
    Does nothing (and logs a single info line) when GPIO is unavailable.
    """

    def __init__(
        self,
        reed_pin: int = _REED_PIN,
        led_r_pin: int = _LED_R_PIN,
        led_g_pin: int = _LED_G_PIN,
        led_b_pin: int = _LED_B_PIN,
        led_idle_timeout: int = _LED_IDLE_TIMEOUT_SECS,
    ) -> None:
        self._reed_pin = reed_pin
        self._led_r = led_r_pin
        self._led_g = led_g_pin
        self._led_b = led_b_pin
        self._idle_timeout = led_idle_timeout
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._led: _Led | None = None

    def start(self) -> None:
        if not _GPIO_AVAILABLE:
            logger.info("GPIO not available — GPIO monitor disabled (dev/non-Pi host)")
            return
        _GPIO.setmode(_GPIO.BCM)
        _GPIO.setwarnings(False)
        _GPIO.setup(self._reed_pin, _GPIO.IN, pull_up_down=_GPIO.PUD_UP)
        self._led = _Led(self._led_r, self._led_g, self._led_b)
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="gpio-monitor"
        )
        self._thread.start()
        logger.info(
            "GPIO monitor started (reed=GPIO%d, LED R/G/B=GPIO%d/%d/%d)",
            self._reed_pin, self._led_r, self._led_g, self._led_b,
        )

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        if _GPIO_AVAILABLE:
            try:
                _GPIO.cleanup()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Main event loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        assert self._led is not None
        led = self._led

        # Boot indication: white fast blink for 3 s
        self._blink((1, 1, 1), hz=4, duration=3.0)
        led.off()

        while not self._stop.is_set():
            # Wait in 50 ms steps for the reed switch to close (pin LOW)
            if _GPIO.input(self._reed_pin) == _GPIO.HIGH:
                time.sleep(0.05)
                continue

            press_start = time.time()
            current_color = _state_color()
            led.set(*current_color)

            armed: str | None = None  # 'hotspot' or 'reset'

            # Poll while reed stays closed
            while _GPIO.input(self._reed_pin) == _GPIO.LOW and not self._stop.is_set():
                held = time.time() - press_start
                if held >= _HOLD_RESET_SECS:
                    armed = "reset"
                elif held >= _HOLD_HOTSPOT_SECS:
                    if armed != "reset":
                        armed = "hotspot"

                # Visual feedback based on armed state
                if armed == "reset":
                    on = int(time.time() * 8) % 2
                    led.set(on, 0, 0)
                elif armed == "hotspot":
                    on = int(time.time() * 8) % 2
                    led.set(0, 0, on)
                else:
                    led.set(*current_color)

                time.sleep(0.05)

            # Reed released — execute the armed action
            if armed == "reset":
                logger.warning("Factory reset triggered via reed switch (hold ≥ 10 s)")
                self._do_factory_reset(led)
            elif armed == "hotspot":
                logger.info("Hotspot toggle triggered via reed switch (hold ≥ 3 s)")
                self._do_hotspot_toggle()
                led.set(*_state_color())
                self._status_on_then_off(led)
            else:
                # Brief tap — just show status for the idle timeout
                led.set(*_state_color())
                self._status_on_then_off(led)

    def _status_on_then_off(self, led: _Led) -> None:
        """Keep the current LED colour for _idle_timeout seconds, then off."""
        deadline = time.time() + self._idle_timeout
        while time.time() < deadline and not self._stop.is_set():
            # Exit early if reed closes again so the outer loop handles it
            if _GPIO.input(self._reed_pin) == _GPIO.LOW:
                return
            time.sleep(0.1)
        led.off()

    def _blink(
        self, color: Tuple[int, int, int], hz: float, duration: float
    ) -> None:
        assert self._led is not None
        end = time.time() + duration
        half = 0.5 / hz
        while time.time() < end and not self._stop.is_set():
            self._led.set(*color)
            time.sleep(half)
            self._led.off()
            time.sleep(half)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _do_hotspot_toggle(self) -> None:
        if _hotspot_active():
            logger.info("Stopping %s", _HOTSPOT_SERVICE)
            subprocess.run(
                ["sudo", "systemctl", "stop", _HOTSPOT_SERVICE],
                capture_output=True,
            )
        else:
            logger.info("Starting %s", _HOTSPOT_SERVICE)
            subprocess.run(
                ["sudo", "systemctl", "start", _HOTSPOT_SERVICE],
                capture_output=True,
            )
        # Give systemd a moment to change state before we re-read it
        time.sleep(_WIFI_SERVICE_TIMEOUT)

    def _do_factory_reset(self, led: _Led) -> None:
        """Delete all non-hotspot WiFi profiles and reboot."""
        # Continue blinking red while working
        def _blink_red_background() -> None:
            while not self._stop.is_set():
                on = int(time.time() * 8) % 2
                led.set(on, 0, 0)
                time.sleep(0.05)

        blink_thread = threading.Thread(target=_blink_red_background, daemon=True)
        blink_thread.start()

        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "NAME,TYPE", "con", "show"],
                capture_output=True, text=True,
            )
            for line in result.stdout.splitlines():
                parts = line.split(":")
                if len(parts) >= 2 and "802-11-wireless" in parts[1]:
                    name = parts[0]
                    if name == "ipr-hotspot":
                        continue
                    subprocess.run(
                        ["nmcli", "con", "delete", name], capture_output=True
                    )
                    logger.info("Factory reset: deleted WiFi profile %r", name)
        except Exception as exc:
            logger.error("Factory reset error while deleting profiles: %s", exc)

        self._stop.set()  # stop blink thread
        led.set(1, 0, 0)  # solid red briefly
        time.sleep(2)
        subprocess.run(["sudo", "reboot"], capture_output=True)
