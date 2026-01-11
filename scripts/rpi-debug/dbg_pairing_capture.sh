#!/usr/bin/env bash
#
# Capture a bounded Bluetooth pairing window and collect logs for Copilot/MCP diagnostics
#
# Usage:
#   sudo dbg_pairing_capture.sh [duration_seconds]
#     (default duration: 60 seconds)
#
# Prerequisites:
#   - Should be run as root for full capture (can run as user for partial info)
#   - /etc/ipr_dbg.env should exist (written by install_dbg_tools.sh)
#
# category: Debug
# purpose: Capture pairing attempt and collect logs for troubleshooting
# parameters: [duration_seconds]
# sudo: no
set -euo pipefail

DBG_ENV="/etc/ipr_dbg.env"
[[ -f "$DBG_ENV" ]] && source "$DBG_ENV"

# Source common environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/dbg_common.env"

DURATION="${1:-60}"
BLE_SERVICE="${DBG_BLE_SERVICE:-$BLE_SERVICE}"
AGENT_SERVICE="${DBG_AGENT_SERVICE:-$AGENT_SERVICE}"
HCI="${DBG_HCI:-$HCI}"
LOG_ROOT="${DBG_LOG_ROOT:-$LOG_ROOT}"

TS="$(date -Is | tr ':' '-')"
OUT_DIR="$LOG_ROOT/pairing_${TS}"
mkdir -p "$OUT_DIR"
ln -sfn "$OUT_DIR" "$LOG_ROOT/latest"

echo "== dbg_pairing_capture: starting =="
echo "Duration: ${DURATION}s"
echo "Output:   $OUT_DIR"
echo "HCI:      $HCI"
echo "Agent:    $AGENT_SERVICE"
echo "BLE:      $BLE_SERVICE"
echo
echo "Initiate pairing from Windows DURING the capture window."
echo

# Snapshot before
{
  echo "### SNAPSHOT (before) ###"
  date -Is
  uname -a || true
  sudo btmgmt -i "$HCI" info || true
  systemctl --no-pager -l status bluetooth || true
  systemctl --no-pager -l status "$AGENT_SERVICE" || true
  systemctl --no-pager -l status "$BLE_SERVICE" || true
} > "$OUT_DIR/snapshot_before.txt" 2>&1

# Start btmon (bounded)
BTMON_FILE="$OUT_DIR/btmon.txt"
sudo timeout "${DURATION}"s btmon -i "$HCI" > "$BTMON_FILE" 2>&1 &
BTMON_PID=$!

# Start journals (bounded)
SINCE="$(date -d '2 minutes ago' '+%Y-%m-%d %H:%M:%S')"

J_BLUETOOTH="$OUT_DIR/journal_bluetooth.txt"
J_AGENT="$OUT_DIR/journal_agent.txt"
J_BLE="$OUT_DIR/journal_ble.txt"

sudo timeout "${DURATION}"s journalctl -u bluetooth --since "$SINCE" -f --no-pager > "$J_BLUETOOTH" 2>&1 &
PID_JB=$!

sudo timeout "${DURATION}"s journalctl -u "$AGENT_SERVICE" --since "$SINCE" -f --no-pager > "$J_AGENT" 2>&1 &
PID_JA=$!

sudo timeout "${DURATION}"s journalctl -u "$BLE_SERVICE" --since "$SINCE" -f --no-pager > "$J_BLE" 2>&1 &
PID_JL=$!

# Wait
wait "$BTMON_PID" || true
wait "$PID_JB" || true
wait "$PID_JA" || true
wait "$PID_JL" || true

# Snapshot after
{
  echo "### SNAPSHOT (after) ###"
  date -Is
  sudo btmgmt -i "$HCI" info || true
  systemctl --no-pager -l status bluetooth || true
  systemctl --no-pager -l status "$AGENT_SERVICE" || true
  systemctl --no-pager -l status "$BLE_SERVICE" || true
  echo
  echo "### LAST 250 KERNEL LINES (filtered) ###"
  dmesg | tail -n 250 | sed -n '/Bluetooth\|btusb\|hci/Ip' || true
} > "$OUT_DIR/snapshot_after.txt" 2>&1

# Highlights (bounded)
H="$OUT_DIR/highlights.txt"
{
  echo "### HIGHLIGHTS (best-effort; bounded) ###"
  echo

  echo "## btmon potential errors"
  grep -Ei "error|failed|reject|insufficient|timeout|disconnect|reason|encrypt|auth|pair" "$BTMON_FILE" | tail -n 220 || true
  echo

  echo "## bluetooth potential errors"
  grep -Ei "error|fail|reject|insufficient|timeout|disconnect|reason|encrypt|auth|pair" "$J_BLUETOOTH" | tail -n 220 || true
  echo

  echo "## agent potential errors"
  grep -Ei "error|fail|reject|insufficient|timeout|disconnect|reason|encrypt|auth|pair|passkey|RequestPasskey|RequestConfirmation|AuthorizeService|Authorize" "$J_AGENT" | tail -n 260 || true
  echo

  echo "## ble potential errors"
  grep -Ei "error|fail|reject|insufficient|timeout|disconnect|reason|encrypt|auth|pair|StartNotify|StopNotify|advertis|Advertising|GATT" "$J_BLE" | tail -n 260 || true
  echo
} > "$H" 2>&1

echo "== dbg_pairing_capture: DONE =="
echo "Artifacts: $OUT_DIR"
echo "Symlink:   $LOG_ROOT/latest -> $OUT_DIR"
echo "Key files:"
echo "  highlights.txt"
echo "  btmon.txt"
echo "  journal_bluetooth.txt"
echo "  journal_agent.txt"
echo "  journal_ble.txt"
