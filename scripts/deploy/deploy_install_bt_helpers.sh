#!/usr/bin/env bash
#
# deploy_install_bt_helpers.sh
#
# Install updated Bluetooth keyboard helper scripts to /usr/local/bin.
#
# Use after 'git pull' when any of these changed:
#   scripts/ble/bt_kb_send.sh
#   scripts/ble/bt_kb_send_file.sh
#
# These helpers are called by the main application loop to write to the BLE
# keyboard FIFO.  Reinstalling them takes effect immediately without a service
# restart.
#
# Usage:
#   sudo ./scripts/deploy/deploy_install_bt_helpers.sh
#
# category: Deploy
# purpose: Install Bluetooth keyboard helper scripts to /usr/local/bin
# sudo: yes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[deploy] Installing Bluetooth keyboard helpers…"
bash "$SCRIPT_DIR/../ble/ble_install_helper.sh"

echo ""
echo "[deploy] Done.  Helpers installed to /usr/local/bin."
echo "  No service restart required — helpers are invoked per-send."
