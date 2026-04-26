"""Bluetooth keyboard abstraction.

This module provides a thin wrapper around the system-level helper script
(`/usr/local/bin/bt_kb_send`) which delivers text to the BLE HID GATT backend.
"""

from __future__ import annotations

import subprocess

from ..logging.logger import get_logger
from .. import transmission

logger = get_logger()

VERSION = '2026-04-12 19:41:16'

def log_version_info():
    logger.info(f"==== ipr_keyboard.bluetooth.keyboard VERSION: {VERSION} ====")


class BluetoothKeyboard:
    """High-level Bluetooth keyboard interface.

    The transport uses BLE HID over GATT, handled by the system-level
    helper script and its associated daemon.
    """

    def __init__(self, helper_path: str = "/usr/local/bin/bt_kb_send") -> None:
        self.helper_path = helper_path

    def is_available(self) -> bool:
        """Check if the Bluetooth helper script is available.

        Returns:
            True if the helper script exists and is executable, False otherwise.
        """
        import os
        return os.path.isfile(self.helper_path) and os.access(self.helper_path, os.X_OK)

    def send_text(self, text: str) -> bool:
        """Send text via BLE HID keyboard backend.

        Args:
            text: The text to send as keystrokes.

        Returns:
            True on success, False on failure.
        """
        if not text:
            logger.info("BluetoothKeyboard.send_text called with empty text, skipping.")
            return True

        logger.info(
            "Sending text via BLE HID keyboard (len=%d)",
            len(text),
        )

        transmission.set_sending("keyboard")
        try:
            subprocess.run(
                [self.helper_path, text],
                check=True,
            )
            transmission.set_success()
            return True
        except FileNotFoundError:
            logger.error("BT helper not found: %s", self.helper_path)
            transmission.set_failed("BT helper not found")
            return False
        except subprocess.CalledProcessError as exc:
            logger.error("BT helper exited with error: %s", exc)
            transmission.set_failed(f"Send error: {exc.returncode}")
            return False
