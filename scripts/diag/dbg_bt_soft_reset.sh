#!/usr/bin/env bash
set -euo pipefail

SERVICE_BT="bt_hid_ble.service"
HCI="hci0"

echo "== dbg_bt_soft_reset: non-destructive soft reset =="

sudo systemctl stop "$SERVICE_BT" || true

sudo systemctl restart bluetooth

sudo btmgmt -i "$HCI" power off || true
sleep 1
sudo btmgmt -i "$HCI" power on || true

sudo systemctl start "$SERVICE_BT"

echo
echo "== Status =="
sudo btmgmt -i "$HCI" info || true
systemctl --no-pager -l status bluetooth || true
systemctl --no-pager -l status "$SERVICE_BT" || true
