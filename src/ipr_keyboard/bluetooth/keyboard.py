"""Bluetooth keyboard abstraction.

This module provides a thin wrapper around the system-level helper script
(`/usr/local/bin/bt_kb_send`) which is responsible for delivering text to the
active keyboard backend (uinput or BLE HID over GATT).

The backend is selected outside this module via configuration and systemd
services; from the application perspective this class is a simple "send text"
API.
"""

from __future__ import annotations

import subprocess

from ..config.manager import ConfigManager
from ..logging.logger import get_logger

logger = get_logger()


class BluetoothKeyboard:
    """High-level Bluetooth keyboard interface.

    The actual transport (local uinput or BLE HID) is handled by the
    system-level helper script and its associated daemon(s).
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
        """Send text via the configured keyboard backend.

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
        except subprocess.CalledProcessError as exc:
            logger.error("BT helper exited with error: %s", exc)
            return False
