#!/usr/bin/env bash
#
# Perform a non-destructive Bluetooth stack reset (power cycle adapter) for Copilot/MCP diagnostics
#
# Usage:
#   sudo dbg_bt_soft_reset.sh
#
# Prerequisites:
#   - Should be run as root for full effect
#   - /etc/ipr_dbg.env should exist (written by install_dbg_tools.sh)
#
# category: Debug
# purpose: Non-destructive Bluetooth stack reset (power cycle adapter)
# sudo: yes
set -euo pipefail

DBG_ENV="/etc/ipr_dbg.env"
[[ -f "$DBG_ENV" ]] && source "$DBG_ENV"

BLE_SERVICE="${DBG_BLE_SERVICE:-bt_hid_ble.service}"
AGENT_SERVICE="${DBG_AGENT_SERVICE:-bt_hid_agent_unified.service}"
HCI="${DBG_HCI:-hci0}"

echo "== dbg_bt_soft_reset: non-destructive reset (power cycle adapter) =="

sudo systemctl stop "$BLE_SERVICE" || true
sudo systemctl stop "$AGENT_SERVICE" || true

sudo systemctl restart bluetooth

# Toggle controller power (best-effort; not all adapters support every command)
# Source common environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/dbg_common.env"
sudo btmgmt -i "$HCI" power off || true
sleep 1
sudo btmgmt -i "$HCI" power on || true

sudo systemctl start "$AGENT_SERVICE"
sudo systemctl start "$BLE_SERVICE"

echo
echo "== Status =="
sudo btmgmt -i "$HCI" info || true
systemctl --no-pager -l status bluetooth || true
systemctl --no-pager -l status "$AGENT_SERVICE" || true
systemctl --no-pager -l status "$BLE_SERVICE" || true
