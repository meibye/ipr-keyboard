#!/usr/bin/env python3
"""ipr_oled_boot.py — boot progress on the OLED, long before the application.

Runs from ``ipr-oled-boot.service`` (early, as root) and is stopped by
``ipr_keyboard.service`` via ``Conflicts=``, exactly like the white boot blink
on the LED (``ipr_led_boot.sh``).  Without it the panel stays dark for the
~35 s the OS and the application need, which reads as a dead device.

What it shows: the header word ``STARTING...`` in the yellow band and one line
per boot milestone, ticked off as it completes:

    STARTING...          PROD
    OK System
    OK Network
     . Bluetooth
     . Application

It exits as soon as ``ipr_keyboard.service`` is active — the application then
claims the panel and continues with its own boot checklist — or after
BOOT_TIMEOUT_SECS, leaving the last frame on so a stuck boot stays visible.

Uses the project's SSD1306 driver, loaded by path: that module imports nothing
from the rest of the package, so this script needs neither the venv nor the
application logger (which would create root-owned files in the repo).

Configuration comes from /etc/default/ipr-oled (written by
install_oled_support.sh): OLED_BUS, OLED_ADDR, OLED_ROTATE, OLED_CONTRAST,
REPO_DIR.

category: Headless
purpose: Boot-progress screen on the OLED before the application starts
sudo: yes
"""

from __future__ import annotations

import importlib.util
import os
import signal
import subprocess
import sys
import time

DEFAULTS_FILE = "/etc/default/ipr-oled"
DRIVER_REL = "src/ipr_keyboard/oled/ssd1306.py"

BOOT_TIMEOUT_SECS = 240.0
BUS_WAIT_SECS = 20.0
POLL_SECS = 0.5
APP_UNIT = "ipr_keyboard.service"
MODE_FILE = "/var/lib/ipr-keyboard/mode"

# (label, systemd unit or None when the step is "this script is running")
MILESTONES = (
    ("System", None),
    ("Network", "NetworkManager.service"),
    ("Bluetooth", "bluetooth.service"),
    ("Application", APP_UNIT),
)

WIDTH, HEIGHT = 128, 64
LINE_Y = (18, 29, 40, 51)
FONT_DIR = "/usr/share/fonts/truetype/dejavu/"
DONE = "✓"  # check mark
PENDING = "·"  # middle dot


def log(msg: str) -> None:
    print(f"ipr_oled_boot: {msg}", file=sys.stderr, flush=True)


def read_defaults(path: str = DEFAULTS_FILE) -> dict:
    """KEY=value lines from /etc/default/ipr-oled (a shell fragment)."""
    out: dict = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                out[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def load_driver(repo_dir: str):
    """Import the project SSD1306 module from the repository, by path."""
    path = os.path.join(repo_dir, DRIVER_REL)
    spec = importlib.util.spec_from_file_location("ipr_ssd1306_boot", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_font(name: str, size: int):
    from PIL import ImageFont

    for candidate in (FONT_DIR + name, name):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def units_active(units: tuple) -> dict:
    """One ``systemctl is-active`` call for every unit we care about."""
    try:
        res = subprocess.run(
            ["systemctl", "is-active", *units],
            capture_output=True,
            text=True,
            timeout=10,
        )
        states = res.stdout.split()
    except Exception:
        states = []
    if len(states) != len(units):
        return dict.fromkeys(units, False)
    return {unit: state == "active" for unit, state in zip(units, states)}


def development_mode() -> bool:
    try:
        with open(MODE_FILE, encoding="utf-8") as fh:
            return fh.read().strip() == "development"
    except OSError:
        return False


def render(fonts, done: dict, badge: str):
    """The boot screen as a 128x64 1-bit image (the app layout, 4 lines)."""
    from PIL import Image, ImageDraw

    header_font, body_font, badge_font = fonts
    img = Image.new("1", (WIDTH, HEIGHT), 0)
    draw = ImageDraw.Draw(img)

    if badge:
        bw = int(badge_font.getlength(badge)) + 9
        draw.rectangle((WIDTH - bw, 1, WIDTH - 1, 12), fill=1)
        draw.text((WIDTH - bw + 4, 2), badge, font=badge_font, fill=0)
    draw.text((2, 1), "STARTING…", font=header_font, fill=1)

    for (label, _unit), y in zip(MILESTONES, LINE_Y):
        mark = DONE if done.get(label) else PENDING
        draw.text((2, y), f"{mark} {label}", font=body_font, fill=1)
    return img


def wait_for_bus(driver, bus: int, address: int, deadline: float) -> bool:
    """Wait for /dev/i2c-N and an answer at ``address`` (we start very early)."""
    while time.monotonic() < deadline:
        if os.path.exists(driver.device_path(bus)) and driver.probe(bus, address):
            return True
        time.sleep(0.25)
    return False


def main() -> int:
    state = {"stopping": False}

    def _on_term(_signum, _frame):
        state["stopping"] = True

    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGINT, _on_term)

    cfg = read_defaults()
    repo_dir = cfg.get("REPO_DIR", "")
    bus = int(cfg.get("OLED_BUS", "1"), 0)
    address = int(cfg.get("OLED_ADDR", "0x3c"), 0)
    rotate = int(cfg.get("OLED_ROTATE", "0"), 0)
    contrast = int(cfg.get("OLED_CONTRAST", "128"), 0)

    if not repo_dir:
        log(f"no REPO_DIR in {DEFAULTS_FILE} - nothing to do")
        return 0
    try:
        driver = load_driver(repo_dir)
    except Exception as exc:
        log(f"driver not loadable ({exc}) - no boot screen")
        return 0
    if not driver.pil_available():
        log(f"Pillow missing ({driver.pil_unavailable_reason()}) - no boot screen")
        return 0

    started = time.monotonic()
    deadline = started + BOOT_TIMEOUT_SECS
    if not wait_for_bus(driver, bus, address, min(deadline, started + BUS_WAIT_SECS)):
        log(f"nothing at 0x{address:02x} on {driver.device_path(bus)} - no display")
        return 0

    display = driver.Ssd1306(bus, address, contrast, rotate)
    try:
        display.setup()
    except Exception as exc:
        log(f"display setup failed: {exc}")
        return 0

    fonts = (
        load_font("DejaVuSans-Bold.ttf", 12),
        load_font("DejaVuSans.ttf", 9),
        load_font("DejaVuSans-Bold.ttf", 8),
    )
    units = tuple(unit for _label, unit in MILESTONES if unit)
    done = {"System": True}
    badge = "DEV" if development_mode() else "PROD"
    last = None
    log(f"boot screen on {driver.device_path(bus)} 0x{address:02x}")

    try:
        while not state["stopping"] and time.monotonic() < deadline:
            active = units_active(units)
            for label, unit in MILESTONES:
                if unit:
                    done[label] = active.get(unit, False)
            image = render(fonts, done, badge)
            frame = image.tobytes()
            if frame != last:
                display.show(image)
                last = frame
            if done.get("Application"):
                log("application is up - handing the panel over")
                break
            time.sleep(POLL_SECS)
    except Exception as exc:
        log(f"boot screen stopped: {exc}")
    finally:
        # Never blank the panel here: from now on the application (or a stuck
        # boot) owns what is on it; ipr_led_halt.sh clears it at shutdown.
        display.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
