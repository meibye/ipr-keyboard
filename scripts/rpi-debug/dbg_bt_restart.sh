#!/usr/bin/env bash
#
# Safely restart Bluetooth stack and related services for Copilot/MCP diagnostics
#
# Usage:
#   sudo dbg_bt_restart.sh
#
# Prerequisites:
#   - Should be run as root for full effect
#   - /etc/ipr_dbg.env should exist (written by install_dbg_tools.sh)
#
# category: Debug
# purpose: Safely restart Bluetooth stack and agent/BLE services
# sudo: yes
set -euo pipefail

DBG_ENV="/etc/ipr_dbg.env"
[[ -f "$DBG_ENV" ]] && source "$DBG_ENV"

# Source common environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/dbg_common.env"

BLE_SERVICE="${DBG_BLE_SERVICE:-$BLE_SERVICE}"
AGENT_SERVICE="${DBG_AGENT_SERVICE:-$AGENT_SERVICE}"

echo "== dbg_bt_restart: restart bluetooth stack (safe) =="

# Stop app services first to avoid them talking to a restarting bluetoothd
sudo systemctl stop "$BLE_SERVICE" || true
sudo systemctl stop "$AGENT_SERVICE" || true

# Restart base stack
sudo systemctl restart bluetooth

# Start agent before BLE service (common dependency order)
sudo systemctl start "$AGENT_SERVICE"
sudo systemctl start "$BLE_SERVICE"

echo
echo "== Status =="
systemctl --no-pager -l status bluetooth || true
systemctl --no-pager -l status "$AGENT_SERVICE" || true
systemctl --no-pager -l status "$BLE_SERVICE" || true
