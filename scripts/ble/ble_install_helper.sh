#!/usr/bin/env bash
#
# ble_install_helper.sh
#
# Install Bluetooth Keyboard Helper Script.
#
# Installs:
#   - /usr/local/bin/bt_kb_send
#       → writes text into /run/ipr_bt_keyboard_fifo
#
# Usage:
#   sudo ./scripts/ble/ble_install_helper.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#
# category: Bluetooth
# purpose: Install Bluetooth keyboard helper
# sudo: yes
#

set -eo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

FIFO_PATH="/run/ipr_bt_keyboard_fifo"
HELPER_PATH="/usr/local/bin/bt_kb_send"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== [ble_install_helper] Installing Bluetooth keyboard helper and dependencies ==="

########################################
# 1. Install system dependencies
########################################
echo "=== [ble_install_helper] Installing OS packages (python3, evdev, bluez, dbus) ==="
apt update
apt install -y \
  python3 \
  python3-pip \
  python3-evdev \
  python3-dbus \
  bluez \
  bluez-tools

########################################
# 2. Install helper script: bt_kb_send
########################################
echo "=== [ble_install_helper] Installing $HELPER_PATH ==="
# bt_kb_send: write text into the BLE keyboard FIFO
# - waits for FIFO to exist
# - waits for Windows to subscribe to InputReport notifications (flag file)
if [[ ! -f "$SCRIPT_DIR/bt_kb_send.sh" ]]; then
  echo "ERROR: bt_kb_send.sh not found at $SCRIPT_DIR/bt_kb_send.sh"
  exit 1
fi

cp "$SCRIPT_DIR/bt_kb_send.sh" "$HELPER_PATH"
chmod +x "$HELPER_PATH"


echo "=== [ble_install_helper] Installation complete. ==="
echo "  - Helper:        $HELPER_PATH"
echo "  - FIFO:          $FIFO_PATH"
echo "  - Service install is managed by: scripts/service/svc_install_bt_gatt_hid.sh"

