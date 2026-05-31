#!/usr/bin/env bash
#
# deploy_install_ble_daemons.sh
#
# Install updated BLE daemon binaries and service files, then restart BLE services.
#
# Use after 'git pull' when any of these changed:
#   scripts/service/bin/bt_hid_ble_daemon.py
#   scripts/service/bin/bt_hid_agent_unified.py
#   scripts/service/svc/bt_hid_ble.service
#   scripts/service/svc/bt_hid_agent_unified.service
#
# Parameters: --agent-debug, --ble-debug  (passed through to svc_install_bt_gatt_hid.sh)
#
# Usage:
#   sudo ./scripts/deploy/deploy_install_ble_daemons.sh [--agent-debug] [--ble-debug]
#
# category: Deploy
# purpose: Install BLE daemon binaries and service files, restart BLE services
# parameters: --agent-debug,--ble-debug
# sudo: yes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[deploy] Installing BLE GATT HID daemons…"
bash "$SCRIPT_DIR/../service/svc_install_bt_gatt_hid.sh" "$@"

echo ""
echo "[deploy] Restarting BLE services in dependency order…"
systemctl restart bt_hid_agent_unified.service
systemctl restart bt_hid_ble.service

echo "[deploy] Status:"
systemctl --no-pager -l status bt_hid_agent_unified.service || true
systemctl --no-pager -l status bt_hid_ble.service || true

echo ""
echo "[deploy] Done."
