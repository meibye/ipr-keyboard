#!/usr/bin/env bash
#
# BLE Diagnostics Script
#
# Purpose:
#   Performs comprehensive Bluetooth HID diagnostics including adapter checks,
#   service status, HID UUID exposure, and FIFO status.
#
# Usage:
#   sudo /usr/local/bin/ipr_ble_diagnostics.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - Bluetooth HID services must be installed
#
# category: Diagnostics
# purpose: Perform comprehensive BLE HID diagnostics

set -euo pipefail

RED="\033[0;31m"; GREEN="\033[0;32m"; YELLOW="\033[1;33m"; RESET="\033[0m"

say() { echo -e "${YELLOW}== $1 ==${RESET}"; }
ok()  { echo -e "${GREEN}$1${RESET}"; }
err() { echo -e "${RED}$1${RESET}"; }

say "1. Checking Bluetooth adapter"
if ! bluetoothctl show >/dev/null 2>&1; then
    err "No Bluetooth adapter found (bluetoothctl show failed)."
    exit 1
fi
ok "Adapter found"

say "2. Checking HID UUID exposure (0x1812)"
if bluetoothctl show | grep -qi "00001812"; then
    ok "HID service (00001812-0000-1000-8000-00805f9b34fb) exposed"
else
    err "HID service not visible – BLE HID daemon may not be registered"
fi

say "3. Checking BLE HID daemon service"
if systemctl is-active --quiet bt_hid_ble.service; then
    ok "bt_hid_ble.service is active"
else
    err "bt_hid_ble.service is NOT active"
fi

say "4. Checking Agent service"
if systemctl is-active --quiet bt_hid_agent.service; then
    ok "bt_hid_agent.service is active"
else
    err "bt_hid_agent.service is NOT active (pairing likely to fail)"
fi

say "5. Adapter power state (btmgmt info)"
if command -v btmgmt >/dev/null 2>&1; then
    sudo btmgmt info || err "btmgmt info failed"
else
    err "btmgmt not installed; skipping detailed controller info"
fi

say "6. Recent BLE HID daemon logs (bt_hid_ble.service)"
sudo journalctl -u bt_hid_ble.service -n20 --no-pager || echo "No logs yet."

say "7. FIFO existence check"
/bin/ls -l /run/ipr_bt_keyboard_fifo 2>/dev/null && ok "FIFO exists" || err "FIFO missing: /run/ipr_bt_keyboard_fifo"

say "Diagnostics completed."
