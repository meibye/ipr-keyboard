#!/usr/bin/env bash
#
# svc_install_all_services.sh
#
# Installs all Bluetooth GATT HID services for ipr-keyboard.
#
# Usage:
#   sudo ./scripts/service/svc_install_all_services.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#
# category: Service
# purpose: Install Bluetooth GATT HID services
# sudo: yes
#

set -eo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== [svc_install_all_services] Installing Bluetooth GATT HID services ==="

# Install Bluetooth GATT HID services (agent + BLE daemon)
echo ""
echo "=== Installing Bluetooth GATT HID services ==="
"$SCRIPT_DIR/svc_install_bt_gatt_hid.sh"

echo ""
echo "=== [svc_install_all_services] All services installed successfully ==="
echo "Installed services:"
echo "  - bt_hid_agent_unified.service"
echo "  - bt_hid_ble.service"
