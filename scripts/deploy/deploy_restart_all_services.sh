#!/usr/bin/env bash
#
# deploy_restart_all_services.sh
#
# Restart all ipr-keyboard services in the correct dependency order.
#
# Use when services need restarting without any reinstall — for example after
# a configuration change or to recover from a failed state.
#
# Order:
#   1. bluetooth (base stack)
#   2. bt_hid_agent_unified (pairing agent, depends on bluetooth)
#   3. bt_hid_ble (BLE HID daemon, depends on agent)
#   4. ipr_keyboard (main app, depends on agent)
#
# Usage:
#   sudo ./scripts/deploy/deploy_restart_all_services.sh
#
# category: Deploy
# purpose: Restart all ipr-keyboard services in correct dependency order
# sudo: yes

set -euo pipefail

echo "[deploy] Stopping application services…"
systemctl stop ipr_keyboard.service   || true
systemctl stop bt_hid_ble.service     || true
systemctl stop bt_hid_agent_unified.service || true

echo "[deploy] Restarting Bluetooth base stack…"
systemctl restart bluetooth.service

echo "[deploy] Starting BLE agent…"
systemctl start bt_hid_agent_unified.service

echo "[deploy] Starting BLE HID daemon…"
systemctl start bt_hid_ble.service

echo "[deploy] Starting main application…"
systemctl start ipr_keyboard.service

echo ""
echo "[deploy] Status summary:"
for unit in bluetooth.service bt_hid_agent_unified.service bt_hid_ble.service ipr_keyboard.service; do
    state=$(systemctl is-active "$unit" 2>/dev/null || echo "unknown")
    printf "  %-42s %s\n" "$unit" "$state"
done

echo ""
echo "[deploy] Done."
