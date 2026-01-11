#!/usr/bin/env bash
#
# Collect a comprehensive diagnostic bundle for Copilot/MCP Bluetooth troubleshooting
#
# Usage:

# Source common environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/dbg_common.env"
#   sudo dbg_diag_bundle.sh
#
# Prerequisites:
#   - Should be run as root for full diagnostics (can run as user for partial info)
#   - /etc/ipr_dbg.env should exist (written by install_dbg_tools.sh)
#
# category: Debug
# purpose: Collect system and Bluetooth stack diagnostics for troubleshooting
# sudo: yes
set -euo pipefail

DBG_ENV="/etc/ipr_dbg.env"
[[ -f "$DBG_ENV" ]] && source "$DBG_ENV"

BLE_SERVICE="${DBG_BLE_SERVICE:-bt_hid_ble.service}"
AGENT_SERVICE="${DBG_AGENT_SERVICE:-bt_hid_agent_unified.service}"
HCI="${DBG_HCI:-hci0}"

echo "== dbg_diag_bundle: $(date -Is) =="

echo
echo "## System"
uname -a || true
lsb_release -a 2>/dev/null || true
uptime || true

echo
echo "## Bluetooth controller"
sudo btmgmt -i "$HCI" info || true
hciconfig -a "$HCI" 2>/dev/null || true

echo
echo "## Services (bluetooth + agent + ble)"
systemctl --no-pager -l status bluetooth || true
systemctl --no-pager -l status "$AGENT_SERVICE" || true
systemctl --no-pager -l status "$BLE_SERVICE" || true

echo
echo "## Recent logs (bluetooth)"
journalctl -u bluetooth --since "60 min ago" -n 250 --no-pager || true

echo
echo "## Recent logs (agent)"
BLE_SERVICE="${DBG_BLE_SERVICE:-$BLE_SERVICE}"
AGENT_SERVICE="${DBG_AGENT_SERVICE:-$AGENT_SERVICE}"
HCI="${DBG_HCI:-$HCI}"
echo "## Recent logs (ble)"
journalctl -u "$BLE_SERVICE" --since "60 min ago" -n 400 --no-pager || true

echo
echo "## Recent kernel messages (bt-related)"
dmesg | tail -n 250 | sed -n '/Bluetooth\|btusb\|hci/Ip' || true

echo
echo "== dbg_diag_bundle: END =="
