#!/usr/bin/env bash
set -euo pipefail

FIFO="/run/ipr_bt_keyboard_fifo"
NOTIFY_FLAG="/run/ipr_bt_keyboard_notifying"

WAIT_SECS="${BT_KB_WAIT_SECS:-10}"

usage() {
  echo "Usage: bt_kb_send [--nowait] [--wait <seconds>] \"text...\""
}

NOWAIT=0
if [[ "${1:-}" == "--nowait" ]]; then
  NOWAIT=1
  shift
elif [[ "${1:-}" == "--wait" ]]; then
  shift
  WAIT_SECS="${1:-}"
  shift || true
fi

TEXT="${1:-}"
if [[ -z "$TEXT" ]]; then
  usage
  exit 2
fi

# Wait for FIFO
t=0
until [[ -p "$FIFO" ]]; do
  (( t++ )) || true
  if (( t >= WAIT_SECS )); then
    echo "ERROR: FIFO not ready: $FIFO" >&2
    exit 1
  fi
  sleep 1
done

if (( NOWAIT == 0 )); then
  # Wait for HID notify subscription (StartNotify creates the flag file)
  t=0
  until [[ -f "$NOTIFY_FLAG" ]]; do
    (( t++ )) || true
    if (( t >= WAIT_SECS )); then
      echo "ERROR: HID notify not ready (no StartNotify yet). Flag: $NOTIFY_FLAG" >&2
      exit 1
    fi
    sleep 1
  done
fi

printf "%s" "$TEXT" > "$FIFO"
