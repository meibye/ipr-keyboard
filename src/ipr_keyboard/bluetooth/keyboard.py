"""Bluetooth HID keyboard emulation module.

Provides a wrapper around the system-level Bluetooth HID helper script
for sending keyboard input to paired devices.
"""
from __future__ import annotations

import subprocess
from typing import Optional

from ..logging.logger import get_logger

logger = get_logger()


class BluetoothKeyboard:
    """Wrapper around system-level Bluetooth HID sender.
    
    This class provides an interface to send text via Bluetooth keyboard
    emulation by calling an external helper script (bt_kb_send).
    
    Attributes:
        helper_path: Path to the Bluetooth keyboard helper script.
    """

    def __init__(self, helper_path: str = "/usr/local/bin/bt_kb_send") -> None:
        """Initialize the Bluetooth keyboard wrapper.
        
        Args:
            helper_path: Path to the bt_kb_send helper script. Defaults to
                /usr/local/bin/bt_kb_send.
        """
        self.helper_path = helper_path

    def is_available(self) -> bool:
        """Check if the Bluetooth helper script is available.
        
        Returns:
            True if the helper script exists and can be executed, False otherwise.
        """
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
        """Send text via Bluetooth keyboard emulation.
        
        Args:
            text: The text string to send as keyboard input.
            
        Returns:
            True if the text was sent successfully, False if the helper
            script is not found or exits with an error.
        """
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
