#!/usr/bin/env bash
#
# svc_install_all_services.sh
#
# Installs all Bluetooth-related services for ipr-keyboard.
# This script calls individual service installation scripts.
#

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== [svc_install_all_services] Installing all Bluetooth services ==="

# Install bt_hid_uinput service
echo ""
echo "=== Installing bt_hid_uinput service ==="
"$SCRIPT_DIR/svc_install_bt_hid_uinput.sh"

# Install bt_hid_ble service
echo ""
echo "=== Installing bt_hid_ble service ==="
"$SCRIPT_DIR/svc_install_bt_hid_ble.sh"

# Install bt_hid_agent service
echo ""
echo "=== Installing bt_hid_agent service ==="
"$SCRIPT_DIR/svc_install_bt_hid_agent.sh"

# Install bt_hid_daemon service
echo ""
echo "=== Installing bt_hid_daemon service ==="
"$SCRIPT_DIR/svc_install_bt_hid_daemon.sh"

# Install ipr_backend_manager service
echo ""
echo "=== Installing ipr_backend_manager service ==="
"$SCRIPT_DIR/svc_install_ipr_backend_manager.sh"

echo ""
echo "=== [svc_install_all_services] All services installed successfully ==="
echo "Installed services:"
echo "  - bt_hid_uinput.service"
echo "  - bt_hid_ble.service"
echo "  - bt_hid_agent.service"
echo "  - bt_hid_daemon.service"
echo "  - ipr_backend_manager.service"
