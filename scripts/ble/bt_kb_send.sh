#!/usr/bin/env bash
# category: Bluetooth
# purpose: Helper script to send text to the BLE keyboard FIFO for testing/debugging.
# parameters: --nowait,--wait,--debug
# sudo: yes
set -euo pipefail

FIFO="/run/ipr_bt_keyboard_fifo"
NOTIFY_FLAG="/run/ipr_bt_keyboard_notifying"

WAIT_SECS="${BT_KB_WAIT_SECS:-10}"


# Parse CLI flags for wait/nowait/debug and capture text payload.
NOWAIT=0
DEBUG=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --nowait)
      NOWAIT=1
      shift
      ;;
    --wait)
      shift
      WAIT_SECS="${1:-}"
      shift || true
      ;;
    --debug)
      DEBUG=1
      shift
      ;;
    *)
      break
      ;;
  esac
done

TEXT="${1:-}"
if [[ -z "$TEXT" ]]; then
  usage
  exit 2
fi

usage() {
  echo "Usage: bt_kb_send [--nowait] [--wait <seconds>] [--debug] \"text...\""
}

# Check BLE daemon status before waiting for FIFO
check_ble_daemon() {
  if command -v systemctl >/dev/null 2>&1; then
    if ! systemctl is-active --quiet bt_hid_ble.service; then
      echo "ERROR: BLE daemon (bt_hid_ble.service) is not running." >&2
      echo "Hint: Start it with: sudo systemctl start bt_hid_ble.service" >&2
      exit 1
    else
      if (( DEBUG == 1 )); then
        echo "[DEBUG] BLE daemon is active." >&2
      fi
    fi
  else
    echo "WARNING: systemctl not found, skipping BLE daemon check." >&2
  fi
}

check_ble_daemon

# Robust FIFO wait: retry if daemon is running, provide guidance if not ready
if (( NOWAIT == 0 )); then
  t=0
  if (( DEBUG == 1 )); then
    echo "[DEBUG] Waiting for FIFO: $FIFO (timeout: $WAIT_SECS s)" >&2
  fi
  while [[ ! -p "$FIFO" ]]; do
    (( t++ )) || true
    if (( t >= WAIT_SECS )); then
      echo "ERROR: FIFO not ready: $FIFO" >&2
      echo "Hint: BLE daemon is running but FIFO is not ready. This may indicate a startup race or daemon issue." >&2
      echo "Check daemon logs: sudo journalctl -u bt_hid_ble.service -n 20" >&2
      exit 1
    fi
    sleep 1
  done
  if (( DEBUG == 1 )); then
    echo "[DEBUG] FIFO is ready after $t seconds." >&2
  fi
fi

if (( DEBUG == 1 )); then
  echo "[DEBUG] Sending text to FIFO: '$TEXT'" >&2
fi
printf "%s" "$TEXT" > "$FIFO"
if (( DEBUG == 1 )); then
  echo "[DEBUG] Done writing to FIFO." >&2
fi
