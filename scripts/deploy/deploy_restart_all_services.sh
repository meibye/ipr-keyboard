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
#   1. NetworkManager (base networking)
#   2. bluetooth (base BT stack, depends on networking)
#   3. bt_hid_agent_unified (pairing agent, depends on bluetooth)
#   4. bt_hid_ble (BLE HID daemon, depends on agent)
#   5. ipr_keyboard (main app, depends on agent)
#   6. ipr-provision (provisioning service)
#
# Usage:
#   sudo ./scripts/deploy/deploy_restart_all_services.sh
#
# category: Deploy
# purpose: Restart all ipr-keyboard services in correct dependency order
# sudo: yes

set -euo pipefail

echo "[deploy] Stopping application services…"
systemctl stop ipr-provision.service          || true
systemctl stop ipr_keyboard.service           || true
systemctl stop bt_hid_ble.service             || true
systemctl stop bt_hid_agent_unified.service   || true

echo "[deploy] Restarting base networking…"
systemctl restart NetworkManager.service

echo "[deploy] Restarting Bluetooth base stack…"
systemctl restart bluetooth.service

echo "[deploy] Starting BLE agent…"
systemctl start bt_hid_agent_unified.service

echo "[deploy] Starting BLE HID daemon…"
systemctl start bt_hid_ble.service

echo "[deploy] Starting main application…"
systemctl start ipr_keyboard.service

echo "[deploy] Starting provisioning service…"
systemctl start ipr-provision.service

echo ""
echo "[deploy] Status summary:"
for unit in NetworkManager.service bluetooth.service bt_hid_agent_unified.service bt_hid_ble.service ipr_keyboard.service ipr-provision.service; do
    state=$(systemctl is-active "$unit" 2>/dev/null || echo "unknown")
    printf "  %-42s %s\n" "$unit" "$state"
done

echo ""
echo "[deploy] Done."
