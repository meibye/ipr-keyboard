"""Bluetooth HID keyboard emulation module.

Provides a wrapper around the system-level Bluetooth HID helper script
for sending keyboard input to paired devices.
"""

from __future__ import annotations

import subprocess

from ..config.manager import ConfigManager
from ..logging.logger import get_logger

logger = get_logger()


class BluetoothKeyboard:
    """High-level Bluetooth keyboard interface.

    This class is intentionally thin: it delegates to the system-level
    helper script (`/usr/local/bin/bt_kb_send`), which in turn feeds the
    active keyboard backend (uinput or BLE HID over GATT).
    """

    def __init__(self, helper_path: str = "/usr/local/bin/bt_kb_send") -> None:
        self.helper_path = helper_path

    def send_text(self, text: str) -> bool:
        """Send text via the configured Bluetooth keyboard backend.

        Args:
            text: The text to send as keystrokes.

        Returns:
            True on success, False on failure.
        """
        if not text:
            logger.info("BluetoothKeyboard.send_text called with empty text, skipping.")
            return True

        cfg = ConfigManager.instance().get()
        logger.info(
            "Sending text via Bluetooth keyboard (len=%d, backend=%s)",
            len(text),
            cfg.KeyboardBackend,
        )

        try:
            subprocess.run(
                [self.helper_path, text],
                check=True,
            )
            return True
        except FileNotFoundError:
            logger.error("BT helper not found: %s", self.helper_path)
            return False
        except subprocess.CalledProcessError as e:
            logger.error("BT helper exited with error: %s", e)
            return False
