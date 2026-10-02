"""SSD1306 128x64 OLED driver over Linux i2c-dev — standard library only.

The panel hangs on I2C bus 1 (GPIO 2 SDA / GPIO 3 SCL) at address 0x3C.
Every transfer is ``os.write()`` on ``/dev/i2c-<bus>`` after an
``ioctl(I2C_SLAVE)``; the first byte is the SSD1306 control byte
(0x00 = commands follow, 0x40 = display data follows).  No smbus2, no luma,
no C extension: the same code runs on the ARMv6 Zero W and on the Zero 2 W.

Pillow is only needed to turn an image into the page-ordered framebuffer;
the import is guarded so the application starts without it (the display is
then disabled with a warning — see manager.py).

This module deliberately imports nothing from the rest of the package (not
even the logger): ``scripts/headless/ipr_oled_boot.py`` loads it by path, as
root, before the application exists.
"""

from __future__ import annotations

import os
import time

_PIL_IMPORT_ERROR: str | None = None
try:
    from PIL import Image as _Image

    _PIL_AVAILABLE = True
except ImportError as _exc:  # pragma: no cover - platform specific
    _Image = None  # type: ignore[assignment]
    _PIL_AVAILABLE = False
    _PIL_IMPORT_ERROR = f"{type(_exc).__name__}: {_exc}"

try:
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows dev host
    _fcntl = None  # type: ignore[assignment]


def pil_available() -> bool:
    """True when Pillow is importable (Debian python3-pil through the venv)."""
    return _PIL_AVAILABLE


def pil_unavailable_reason() -> str | None:
    return _PIL_IMPORT_ERROR


I2C_SLAVE = 0x0703  # linux/i2c-dev.h

WIDTH = 128
HEIGHT = 64
PAGES = HEIGHT // 8

_CTRL_CMD = 0x00
_CTRL_DATA = 0x40
_CMD_NOP = 0xE3
_CMD_DISPLAY_OFF = 0xAE
_CMD_DISPLAY_ON = 0xAF
_CMD_CONTRAST = 0x81

# Bit-reversal table: Pillow packs 8 pixels per byte MSB-first (top pixel is
# bit 7); the SSD1306 wants the top pixel of a page in bit 0.
_REVERSE = bytes(int(f"{i:08b}"[::-1], 2) for i in range(256))

_WRITE_CHUNK = 256  # bytes of display data per os.write (plus the control byte)


def device_path(bus: int) -> str:
    return f"/dev/i2c-{bus}"


def probe(bus: int, address: int) -> bool:
    """True when something acknowledges a NOP command at ``address``.

    False for a missing /dev/i2c-N, a bus we may not open (group ``i2c``),
    or an address that does not answer — all of which mean "no display".
    """
    if _fcntl is None:
        return False
    try:
        fd = os.open(device_path(bus), os.O_RDWR)
    except OSError:
        return False
    try:
        _fcntl.ioctl(fd, I2C_SLAVE, address)
        os.write(fd, bytes([_CTRL_CMD, _CMD_NOP]))
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


class Ssd1306:
    """A 128x64 SSD1306 on i2c-dev.  ``setup()`` before use, ``close()`` after.

    The duck-typed interface the manager relies on — ``setup``, ``show``,
    ``sleep``, ``wake``, ``contrast``, ``close`` — is what tests fake.
    """

    def __init__(
        self,
        bus: int = 1,
        address: int = 0x3C,
        contrast: int = 128,
        rotate: int = 0,
    ) -> None:
        self._bus = bus
        self._address = address
        self._contrast = max(0, min(255, int(contrast)))
        self._rotate = 180 if int(rotate) == 180 else 0
        self._fd: int | None = None
        self.last_frame_ms = 0.0

    # -- lifecycle --------------------------------------------------------

    def setup(self) -> None:
        if _fcntl is None:
            raise RuntimeError("i2c-dev is only available on Linux")
        self._fd = os.open(device_path(self._bus), os.O_RDWR)
        _fcntl.ioctl(self._fd, I2C_SLAVE, self._address)
        # Standard init for a 128x64 panel with the internal charge pump.
        seg_remap = 0xA1 if self._rotate == 0 else 0xA0
        com_scan = 0xC8 if self._rotate == 0 else 0xC0
        self._cmd(
            _CMD_DISPLAY_OFF,
            0xD5,
            0x80,  # clock divide / oscillator
            0xA8,
            0x3F,  # multiplex ratio 64
            0xD3,
            0x00,  # display offset
            0x40,  # start line 0
            0x8D,
            0x14,  # charge pump on
            0x20,
            0x00,  # horizontal addressing mode
            seg_remap,
            com_scan,
            0xDA,
            0x12,  # COM pins: alternative, no remap
            _CMD_CONTRAST,
            self._contrast,
            0xD9,
            0xF1,  # pre-charge
            0xDB,
            0x40,  # VCOMH deselect
            0xA4,  # display follows RAM
            0xA6,  # normal (not inverted)
        )
        self.clear()
        self._cmd(_CMD_DISPLAY_ON)

    def close(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            finally:
                self._fd = None

    # -- drawing ----------------------------------------------------------

    def clear(self) -> None:
        self._blit(bytes(WIDTH * PAGES))

    def show(self, image) -> None:
        """Write a Pillow image (any mode, 128x64) to the panel."""
        if image.size != (WIDTH, HEIGHT):
            raise ValueError(f"image must be {WIDTH}x{HEIGHT}, got {image.size}")
        started = time.monotonic()
        self._blit(pack_framebuffer(image))
        self.last_frame_ms = (time.monotonic() - started) * 1000.0

    def sleep(self) -> None:
        self._cmd(_CMD_DISPLAY_OFF)

    def wake(self) -> None:
        self._cmd(_CMD_DISPLAY_ON)

    def contrast(self, value: int) -> None:
        self._contrast = max(0, min(255, int(value)))
        self._cmd(_CMD_CONTRAST, self._contrast)

    # -- low level --------------------------------------------------------

    def _cmd(self, *cmds: int) -> None:
        self._write(bytes([_CTRL_CMD, *cmds]))

    def _blit(self, data: bytes) -> None:
        # Reset the RAM pointer to the top-left, then stream the whole frame.
        self._cmd(0x21, 0, WIDTH - 1, 0x22, 0, PAGES - 1)
        for i in range(0, len(data), _WRITE_CHUNK):
            self._write(bytes([_CTRL_DATA]) + data[i : i + _WRITE_CHUNK])

    def _write(self, payload: bytes) -> None:
        if self._fd is None:
            raise RuntimeError("display not set up")
        os.write(self._fd, payload)


def pack_framebuffer(image) -> bytes:
    """Pillow image -> 1024 bytes in SSD1306 page order (8 pages x 128 columns).

    Done with C-level Pillow/bytes operations only: on a Zero W a Python
    per-pixel loop over 8192 pixels costs tens of milliseconds per frame.
    """
    if _Image is None:  # pragma: no cover - guarded at start()
        raise RuntimeError("Pillow is not available")
    mono = image if image.mode == "1" else image.convert("1")
    # Transpose so each source column becomes a packed row of 8 bytes
    # (one byte per page), then flip the bit order within each byte.
    columns = mono.transpose(_Image.Transpose.TRANSPOSE).tobytes().translate(_REVERSE)
    # columns[x * 8 + page] -> page-major order the panel expects.
    return b"".join(columns[page::PAGES] for page in range(PAGES))
