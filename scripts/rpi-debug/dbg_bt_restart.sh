#!/usr/bin/env bash
set -euo pipefail

SERVICE_BT="bt_hid_ble.service"  # adjust

echo "== dbg_bt_restart: restarting services (safe) =="

sudo systemctl restart bluetooth
sudo systemctl restart "$SERVICE_BT"

echo
echo "== Status =="
systemctl --no-pager -l status bluetooth || true
systemctl --no-pager -l status "$SERVICE_BT" || true
