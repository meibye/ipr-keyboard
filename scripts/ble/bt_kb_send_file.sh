#!/usr/bin/env bash
# category: Bluetooth
# purpose: Send full file content to BLE keyboard FIFO for end-to-end text validation.
# parameters: --file,--wait,--nowait,--debug,--newline-mode
# sudo: yes
set -euo pipefail

FIFO="/run/ipr_bt_keyboard_fifo"
WAIT_SECS="${BT_KB_WAIT_SECS:-10}"

usage() {
  cat <<'USAGE'
Usage: bt_kb_send_file [--file <path>] [--wait <seconds>] [--nowait] [--debug] [--newline-mode preserve|cr|strip]

Options:
  --file <path>              Input UTF-8 text file to send (required)
  --wait <seconds>           FIFO wait timeout (default: 10)
  --nowait                   Do not wait for FIFO to appear
  --debug                    Print debug logs
  --newline-mode <mode>      preserve: send LF as-is
                             cr: convert LF to CR (Enter key semantics) [default]
                             strip: remove LF
USAGE
}

check_ble_daemon() {
  if command -v systemctl >/dev/null 2>&1; then
    if ! systemctl is-active --quiet bt_hid_ble.service; then
      echo "ERROR: BLE daemon (bt_hid_ble.service) is not running." >&2
      echo "Hint: Start it with: sudo systemctl start bt_hid_ble.service" >&2
      exit 1
    fi
  fi
}

wait_for_fifo() {
  local nowait="$1"
  local debug="$2"

  if (( nowait == 1 )); then
    return
  fi

  local t=0
  if (( debug == 1 )); then
    echo "[DEBUG] Waiting for FIFO: $FIFO (timeout: $WAIT_SECS s)" >&2
  fi

  while [[ ! -p "$FIFO" ]]; do
    (( t++ )) || true
    if (( t >= WAIT_SECS )); then
      echo "ERROR: FIFO not ready: $FIFO" >&2
      echo "Hint: check daemon logs: sudo journalctl -u bt_hid_ble.service -n 20" >&2
      exit 1
    fi
    sleep 1
  done

  if (( debug == 1 )); then
    echo "[DEBUG] FIFO ready after $t second(s)" >&2
  fi
}

ensure_fifo_writable() {
  if [[ -w "$FIFO" ]]; then
    return
  fi

  echo "[WARN] FIFO $FIFO is not writable. Attempting chmod 666..." >&2
  if command -v sudo >/dev/null 2>&1; then
    sudo chmod 666 "$FIFO" || {
      echo "[ERROR] Failed to chmod 666 $FIFO" >&2
      exit 1
    }
  else
    chmod 666 "$FIFO" || {
      echo "[ERROR] Failed to chmod 666 $FIFO" >&2
      exit 1
    }
  fi
}

send_file() {
  local input_file="$1"
  local newline_mode="$2"

  case "$newline_mode" in
    preserve)
      cat "$input_file" > "$FIFO"
      ;;
    cr)
      tr '\n' '\r' < "$input_file" > "$FIFO"
      ;;
    strip)
      tr -d '\n' < "$input_file" > "$FIFO"
      ;;
    *)
      echo "ERROR: invalid --newline-mode '$newline_mode'" >&2
      exit 2
      ;;
  esac
}

NOWAIT=0
DEBUG=0
INPUT_FILE=""
NEWLINE_MODE="cr"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --file)
      INPUT_FILE="${2:-}"
      shift 2
      ;;
    --wait)
      WAIT_SECS="${2:-}"
      shift 2
      ;;
    --nowait)
      NOWAIT=1
      shift
      ;;
    --debug)
      DEBUG=1
      shift
      ;;
    --newline-mode)
      NEWLINE_MODE="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument '$1'" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$INPUT_FILE" ]]; then
  echo "ERROR: --file is required" >&2
  usage
  exit 2
fi

if [[ ! -f "$INPUT_FILE" ]]; then
  echo "ERROR: file not found: $INPUT_FILE" >&2
  exit 2
fi

if ! [[ "$WAIT_SECS" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --wait must be a non-negative integer" >&2
  exit 2
fi

check_ble_daemon
wait_for_fifo "$NOWAIT" "$DEBUG"
ensure_fifo_writable

if (( DEBUG == 1 )); then
  echo "[DEBUG] Sending file: $INPUT_FILE" >&2
  echo "[DEBUG] Newline mode: $NEWLINE_MODE" >&2
fi

send_file "$INPUT_FILE" "$NEWLINE_MODE"

if (( DEBUG == 1 )); then
  echo "[DEBUG] Send complete" >&2
fi
