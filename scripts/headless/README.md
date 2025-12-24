# Headless Provisioning Scripts

This directory contains scripts for headless provisioning, Wi-Fi setup, factory reset, and USB OTG access for the ipr-keyboard project on Raspberry Pi devices. These scripts enable device recovery, Wi-Fi configuration, and direct access without a display or keyboard.

## Overview

The scripts in this folder support:
- **Wi-Fi provisioning via web interface** (auto-hotspot)
- **Factory reset** (via boot marker or GPIO)
- **USB OTG Ethernet setup** (for Pi Zero 2 W)

These features are essential for headless bring-up, recovery, and first-time setup.

---

## Script Reference

### 1. `net_provision_web.py`
- **Purpose**: Flask web server for Wi-Fi provisioning.
- **How it works**: Runs on port 80 when the device is in hotspot mode. Connect to the Pi's hotspot (SSID: `ipr-setup-XXXX`), then open `http://10.42.0.1/` in a browser to select and join a Wi-Fi network.
- **Usage**: Automatically started by `net_provision_hotspot.sh`.


### 2. `net_provision_hotspot.sh` (auto-installed)
- **Purpose**: Auto-hotspot provisioning. If the Pi cannot connect to known Wi-Fi, it creates a hotspot for browser-based setup.
- **How it works**: Waits for Wi-Fi connection on boot. If not found, starts a hotspot and launches the web UI.
- **Usage**: Automatically installed and enabled as `ipr-provision.service` during provisioning. No manual steps required.
   - Service: `ipr-provision.service` runs `/usr/local/sbin/ipr-provision.sh` (copied from this script).
   - Hotspot is available on boot if Wi-Fi is not connected.

### 3. `net_factory_reset.sh`
- **Purpose**: Factory reset via boot marker file.
- **How it works**: If an empty file named `IPR_RESET_WIFI` is found on the boot partition at boot, all Wi-Fi profiles are wiped and the device reboots into provisioning mode.
- **Usage**: Place an empty file named `IPR_RESET_WIFI` on the boot partition (e.g., using a PC), then reboot the Pi.

### 4. `usb_otg_setup.sh`
- **Purpose**: Enable USB OTG Ethernet gadget mode (Pi Zero 2 W only).
- **How it works**: Configures the Pi Zero to appear as a USB Ethernet device when plugged into a PC/laptop. Allows SSH access at `192.168.7.1`.
- **Usage**: Run once on the Pi Zero. After setup, connect the Pi to a PC via USB and SSH in for headless access.

### 5. `gpio_factory_reset.py`
- **Purpose**: Factory reset via GPIO pin (optional, for advanced users).
- **How it works**: Monitors GPIO17 (Pin 11). If shorted to GND during boot, triggers Wi-Fi reset and provisioning mode.
- **Usage**: Connect GPIO17 to GND and reboot. Used for physical factory reset without file access.

---

## Typical Headless Provisioning Workflow

1. **First Boot or Wi-Fi Lost**:
   - Device starts, cannot connect to Wi-Fi.
   - `net_provision_hotspot.sh` creates a hotspot (`ipr-setup-XXXX`).
   - Connect to the hotspot from a phone/laptop.
   - Open `http://10.42.0.1/` and configure Wi-Fi.

2. **Factory Reset (File Method)**:
   - Place an empty file named `IPR_RESET_WIFI` on the boot partition.
   - Reboot the Pi. Wi-Fi profiles are wiped and provisioning mode is entered.

3. **Factory Reset (GPIO Method)**:
   - Connect GPIO17 (Pin 11) to GND.
   - Reboot the Pi. Wi-Fi profiles are wiped and provisioning mode is entered.

4. **USB OTG Access (Pi Zero 2 W)**:
   - Run `usb_otg_setup.sh` once.
   - Connect Pi Zero to a PC via USB.
   - SSH to `192.168.7.1` for direct access.

---

## Installation

All scripts are installed and enabled automatically by the provisioning system (`provision/` scripts). Manual installation is rarely needed.

## Troubleshooting
- If the device does not create a hotspot, check system logs and ensure the scripts are executable.
- For factory reset, ensure the marker file is named exactly `IPR_RESET_WIFI` (no extension).
- For USB OTG, only Pi Zero 2 W is supported.

---

## References
- [DEVICE_BRINGUP.md](../../DEVICE_BRINGUP.md) — Full bring-up guide
- [provision/README.md](../../provision/README.md) — Provisioning system
- [scripts/README.md](../README.md) — Script documentation

---

For more details, see the main project README and provisioning documentation.
