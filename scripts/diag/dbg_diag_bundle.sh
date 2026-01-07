#!/usr/bin/env bash
set -euo pipefail

SERVICE_BT="bt_hid_ble.service"  # adjust if needed
HCI="hci0"

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
echo "## BlueZ + bluetoothd"
bluetoothctl --version 2>/dev/null || true
systemctl --no-pager -l status bluetooth || true

echo
echo "## Your BLE HID service"
systemctl --no-pager -l status "$SERVICE_BT" || true

echo
echo "## Recent logs (bluetooth.service)"
journalctl -u bluetooth --since "60 min ago" -n 300 --no-pager || true

echo
echo "## Recent logs (your service)"
journalctl -u "$SERVICE_BT" --since "60 min ago" -n 500 --no-pager || true

echo
echo "## Recent kernel messages (bt-related)"
dmesg | tail -n 200 | sed -n '/Bluetooth\|btusb\|hci/Ip' || true

echo
echo "== dbg_diag_bundle: END =="
