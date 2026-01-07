#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   dbg_pairing_capture.sh [duration_seconds]
# Example:
#   dbg_pairing_capture.sh 60

DURATION="${1:-60}"
SERVICE_BT="bt_hid_ble.service"   # adjust if needed
HCI="hci0"

TS="$(date -Is | tr ':' '-')"
OUT_DIR="/var/log/ipr/pairing_${TS}"
mkdir -p "$OUT_DIR"

# Update "latest" symlink for convenience
ln -sfn "$OUT_DIR" /var/log/ipr/latest

echo "== dbg_pairing_capture: starting =="
echo "Duration: ${DURATION}s"
echo "Output:   $OUT_DIR"
echo

# Snapshot initial state
{
  echo "### SNAPSHOT (before) ###"
  date -Is
  uname -a || true
  sudo btmgmt -i "$HCI" info || true
  systemctl --no-pager -l status bluetooth || true
  systemctl --no-pager -l status "$SERVICE_BT" || true
} > "$OUT_DIR/snapshot_before.txt" 2>&1

# Start btmon capture (bounded)
BTMON_FILE="$OUT_DIR/btmon.txt"
sudo timeout "${DURATION}"s btmon -i "$HCI" > "$BTMON_FILE" 2>&1 &
BTMON_PID=$!

# Capture journals in parallel (bounded)
SINCE="$(date -d '2 minutes ago' '+%Y-%m-%d %H:%M:%S')"

J_BLUETOOTH="$OUT_DIR/journal_bluetooth.txt"
J_SERVICE="$OUT_DIR/journal_service.txt"

sudo timeout "${DURATION}"s journalctl -u bluetooth --since "$SINCE" -f --no-pager > "$J_BLUETOOTH" 2>&1 &
PID_J1=$!

sudo timeout "${DURATION}"s journalctl -u "$SERVICE_BT" --since "$SINCE" -f --no-pager > "$J_SERVICE" 2>&1 &
PID_J2=$!

echo "== RUNNING =="
echo "Initiate pairing from Windows now."
echo "Capture stops automatically after ${DURATION}s."
echo

wait "$BTMON_PID" || true
wait "$PID_J1" || true
wait "$PID_J2" || true

# Snapshot after
{
  echo "### SNAPSHOT (after) ###"
  date -Is
  sudo btmgmt -i "$HCI" info || true
  systemctl --no-pager -l status bluetooth || true
  systemctl --no-pager -l status "$SERVICE_BT" || true
  echo
  echo "### LAST 200 KERNEL LINES (filtered) ###"
  dmesg | tail -n 200 | sed -n '/Bluetooth\|btusb\|hci/Ip' || true
} > "$OUT_DIR/snapshot_after.txt" 2>&1

# Highlights (best-effort grep)
H="$OUT_DIR/highlights.txt"
{
  echo "### HIGHLIGHTS (best-effort) ###"
  echo
  echo "## btmon potential errors"
  grep -Ei "error|failed|reject|insufficient|timeout|disconnect|reason|encrypt|auth|pair" "$BTMON_FILE" | tail -n 200 || true
  echo
  echo "## bluetooth.service potential errors"
  grep -Ei "error|fail|reject|insufficient|timeout|disconnect|reason|encrypt|auth|pair" "$J_BLUETOOTH" | tail -n 200 || true
  echo
  echo "## ${SERVICE_BT} potential errors"
  grep -Ei "error|fail|reject|insufficient|timeout|disconnect|reason|encrypt|auth|pair|StartNotify|StopNotify" "$J_SERVICE" | tail -n 200 || true
} > "$H" 2>&1

echo "== dbg_pairing_capture: DONE =="
echo "Artifacts:"
echo "  $OUT_DIR/snapshot_before.txt"
echo "  $OUT_DIR/btmon.txt"
echo "  $OUT_DIR/journal_bluetooth.txt"
echo "  $OUT_DIR/journal_service.txt"
echo "  $OUT_DIR/snapshot_after.txt"
echo "  $OUT_DIR/highlights.txt"
echo
echo "Convenience:"
echo "  /var/log/ipr/latest -> $OUT_DIR"
