#!/usr/bin/env python3
"""
GPIO-based factory reset trigger for ipr-keyboard

This script monitors a GPIO pin for a reset trigger (jumper to ground).
When the pin is grounded during boot, it triggers a factory reset of Wi-Fi settings.

Hardware setup:
  - Connect a jumper wire between GPIO pin (default: GPIO 17) and GND
  - Remove jumper after boot to resume normal operation

GPIO Pin Selection:
  - Default: GPIO 17 (Pin 11)
  - Alternative safe pins for Pi Zero 2 W: GPIO 27 (Pin 13), GPIO 22 (Pin 15)
  - Avoid: GPIO 2, 3 (I2C), GPIO 14, 15 (UART), GPIO 7-11 (SPI)

Installation:
    sudo cp scripts/headless/gpio_factory_reset.py /usr/local/sbin/ipr-gpio-reset.py
    sudo chmod +x /usr/local/sbin/ipr-gpio-reset.py

Service Integration:
    Called by ipr-provision.service before other provisioning checks

Usage:
    sudo python3 /usr/local/sbin/ipr-gpio-reset.py

Configuration:
    Edit GPIO_RESET_PIN below to change the monitored pin

category: Headless
purpose: GPIO-based factory reset trigger
sudo: yes
"""

import subprocess
import sys
import time
from pathlib import Path

# Configuration
GPIO_RESET_PIN = 17  # GPIO17 (Physical Pin 11) - change if needed
HOLD_TIME_SECONDS = 2  # How long pin must be grounded to trigger reset
MARKER_FILE = "/var/run/ipr_gpio_reset_triggered"

# Boot partition locations to try
BOOT_MOUNTS = ["/boot/firmware", "/boot"]


def log(msg):
    """Log message with timestamp"""
    print(f"[ipr-gpio-reset] {msg}", flush=True)


def error(msg):
    """Log error message"""
    print(f"[ipr-gpio-reset ERROR] {msg}", file=sys.stderr, flush=True)


def check_gpio_available():
    """Check if GPIO access is available"""
    try:
        import RPi.GPIO as GPIO

        return True
    except ImportError:
        return False
    except RuntimeError:
        return False


def check_reset_pin(pin, hold_time):
    """
    Check if the specified GPIO pin is grounded for the required hold time.
    Returns True if reset should be triggered.
    """
    try:
        import RPi.GPIO as GPIO

        # Set up GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Configure pin as input with pull-up resistor
        # Pin will read HIGH normally, LOW when grounded
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        log(f"Monitoring GPIO{pin} for factory reset trigger...")
        log(f"Pin must be grounded for {hold_time} seconds to trigger reset")

        # Check if pin is currently grounded
        if GPIO.input(pin) == GPIO.LOW:
            log(f"GPIO{pin} is grounded, verifying hold time...")

            # Verify pin stays grounded for the hold time
            start_time = time.time()
            while time.time() - start_time < hold_time:
                if GPIO.input(pin) == GPIO.HIGH:
                    log("Pin released before hold time elapsed, reset cancelled")
                    GPIO.cleanup()
                    return False
                time.sleep(0.1)

            log(f"✓ GPIO{pin} held for {hold_time}s, factory reset triggered!")
            GPIO.cleanup()
            return True
        else:
            log(f"GPIO{pin} is not grounded, normal boot continues")
            GPIO.cleanup()
            return False

    except Exception as e:
        error(f"GPIO error: {e}")
        return False


def create_reset_marker():
    """Create marker file to trigger Wi-Fi reset via other scripts"""
    # Try to create marker on boot partition
    for boot_mount in BOOT_MOUNTS:
        if Path(boot_mount).exists() and Path(boot_mount).is_mount():
            marker_path = Path(boot_mount) / "IPR_RESET_WIFI"
            try:
                marker_path.touch()
                log(f"Created reset marker: {marker_path}")
                return True
            except Exception as e:
                error(f"Failed to create marker at {marker_path}: {e}")

    error("Could not create reset marker on boot partition")
    return False


def delete_wifi_profiles():
    """Delete Wi-Fi connection profiles using nmcli"""
    log("Deleting Wi-Fi connection profiles...")
    try:
        # Get all connection names
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME", "con", "show"],
            capture_output=True,
            text=True,
            check=True,
        )

        connections = result.stdout.strip().split("\n")
        deleted_count = 0

        for conn_name in connections:
            if not conn_name:
                continue

            # Check if it's a Wi-Fi connection
            try:
                conn_type_result = subprocess.run(
                    ["nmcli", "-t", "-f", "connection.type", "con", "show", conn_name],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                if "802-11-wireless" in conn_type_result.stdout:
                    # Skip the hotspot connection
                    if conn_name == "ipr-hotspot":
                        log(f"Skipping hotspot connection: {conn_name}")
                        continue

                    log(f"Deleting Wi-Fi profile: {conn_name}")
                    subprocess.run(
                        ["nmcli", "con", "delete", conn_name],
                        check=False,  # Don't fail if delete fails
                    )
                    deleted_count += 1
            except subprocess.CalledProcessError:
                pass  # Skip connections we can't query

        log(f"Deleted {deleted_count} Wi-Fi profile(s)")
        return True

    except subprocess.CalledProcessError as e:
        error(f"Failed to delete Wi-Fi profiles: {e}")
        return False


def main():
    """Main entry point"""
    # Check if already triggered in this boot
    if Path(MARKER_FILE).exists():
        log("Reset already triggered in this boot session, skipping")
        return 0

    # Check GPIO availability
    if not check_gpio_available():
        error("RPi.GPIO not available, GPIO reset disabled")
        error("Install with: sudo apt-get install python3-rpi.gpio")
        return 0  # Not an error, just unavailable

    # Check for reset trigger
    if check_reset_pin(GPIO_RESET_PIN, HOLD_TIME_SECONDS):
        # Create marker file to prevent repeated triggers
        Path(MARKER_FILE).touch()

        # Trigger factory reset
        log("Factory reset triggered via GPIO")

        # Create boot partition marker for other scripts
        create_reset_marker()

        # Delete Wi-Fi profiles directly
        delete_wifi_profiles()

        log("Factory reset complete, rebooting in 3 seconds...")
        time.sleep(3)

        # Reboot
        subprocess.run(["reboot"], check=False)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
