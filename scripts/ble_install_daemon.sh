#!/usr/bin/env bash
#
# ipr-keyboard Bluetooth HID Daemon Install Script
#
# Purpose:
#   Installs and configures a Bluetooth HID daemon for advanced keyboard emulation.
#   Optional alternative to the default bt_kb_send helper.
#
# Usage:
#   sudo ./scripts/ble_install_daemon.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - Environment variables set (sources env_set_variables.sh)
#
# Note:
#   This script is OPTIONAL. The main Bluetooth helper is installed by ble_install_helper.sh.
#   Use only if you need an additional HID daemon with a separate FIFO.

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/env_set_variables.sh"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

echo "=== [ble_install_daemon] Install / update Bluetooth HID daemon ==="

########################################
# 1. Install system dependencies
########################################
echo "=== [ble_install_daemon] Installing system packages ==="
apt update
apt install -y \
    python3 \
    python3-pip \
    python3-evdev \
    bluez \
    bluez-tools


########################################
# 2. Install bt_hid_daemon service
########################################
echo "=== [ble_install_daemon] Installing bt_hid_daemon service ==="
"$SCRIPT_DIR/service/svc_install_bt_hid_daemon.sh"

########################################
# 3. Enable and start service
########################################
echo "=== [ble_install_daemon] Enabling and starting bt_hid_daemon.service ==="
systemctl enable bt_hid_daemon.service
systemctl restart bt_hid_daemon.service

########################################
# 4. Note about bt_kb_send
########################################
echo "=== [ble_install_daemon] Skipping creation of /usr/local/bin/bt_kb_send ==="
echo "The Bluetooth keyboard helper is managed by ble_install_helper.sh."

########################################
# 5. Ensure Bluetooth config is HID-capable
########################################
BT_CONF="/etc/bluetooth/main.conf"

if grep -q "^\[General\]" "$BT_CONF" 2>/dev/null; then
  if ! grep -q "^Enable=.*HID" "$BT_CONF" 2>/dev/null; then
    echo "=== [ble_install_daemon] Updating $BT_CONF to include Enable=HID ==="
    sed -i '/^\[General\]/a Enable=HID' "$BT_CONF" || true
    systemctl restart bluetooth || true
  fi
fi

echo "=== [ble_install_daemon] Done. HID daemon installed with Danish mapping. ==="
echo "You can now test locally with:"
echo "  bt_kb_send \"Test æøå ÆØÅ\""
