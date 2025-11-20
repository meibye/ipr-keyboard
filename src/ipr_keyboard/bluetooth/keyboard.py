from __future__ import annotations

import subprocess
from typing import Optional

from ..logging.logger import get_logger

logger = get_logger()


class BluetoothKeyboard:
    """
    Wrapper around system-level Bluetooth HID sender.
    For now, we call an external script /usr/local/bin/bt_kb_send
    that is responsible for sending keystrokes via Bluetooth.
    """

    def __init__(self, helper_path: str = "/usr/local/bin/bt_kb_send") -> None:
        self.helper_path = helper_path

    def is_available(self) -> bool:
        try:
            subprocess.run(
                [self.helper_path, "--help"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return True
        except FileNotFoundError:
            return False

    def send_text(self, text: str) -> bool:
        logger.info("Sending text via Bluetooth keyboard (len=%d)", len(text))
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
