#!/usr/bin/env bash

#
# ipr-keyboard Bluetooth Keyboard Test Script
#
# Purpose:
#   Sends a test string via the Bluetooth HID helper (bt_kb_send) or daemon to verify Bluetooth keyboard emulation is working end-to-end.
#   Useful for troubleshooting Bluetooth pairing, helper/daemon setup, and keyboard pipeline.
#
# Usage:
#   ./scripts/test_bluetooth.sh ["Your test string"]
#   (If no argument is given, a default Danish test string is sent.)
#
# Prerequisites:
#   - Must NOT be run as root
#   - Bluetooth helper script (`/usr/local/bin/bt_kb_send`) or daemon must be installed and running
#   - Target device must be paired and connected
#   - Environment variables set (sources env_set_variables.sh)
#
# Note:
#   For manual, interactive testing only. Not used in automated workflows or CI.


# Source environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env_set_variables.sh"

echo "=== [test_bluetooth] Test Bluetooth keyboard pipeline (helper/daemon) ==="

# Use env var for project root if needed
BT_HELPER="/usr/local/bin/bt_kb_send"
FIFO="/run/ipr_bt_keyboard_fifo"
SERVICE="bt_hid_daemon.service"

# Accept test string as argument, else use default
if [[ -n "$1" ]]; then
  TEST_STRING="$1"
else
  TEST_STRING="Test æøå ÆØÅ"
fi

echo "--- Checking Bluetooth HID helper ---"
if [[ ! -x "$BT_HELPER" ]]; then
  echo "[test_bluetooth] ERROR: Bluetooth helper $BT_HELPER not found or not executable." >&2
  echo "     Install it with: sudo ./scripts/ble_install_helper.sh" >&2
  exit 1
fi

echo "--- Checking daemon service status ---"
if ! sudo systemctl status "$SERVICE" --no-pager >/dev/null 2>&1; then
  echo "[test_bluetooth] ERROR: service $SERVICE not running or failed." >&2
  echo "     Check logs with: sudo journalctl -u $SERVICE -f" >&2
  exit 1
fi

if [[ ! -p "$FIFO" ]]; then
  echo "[test_bluetooth] ERROR: FIFO $FIFO not found." >&2
  echo "     The daemon should create it automatically." >&2
  echo "     Check logs with: sudo journalctl -u $SERVICE -f" >&2
  exit 1
fi

echo "--- Sending test string via bt_kb_send ---"
echo "If everything is wired to the local virtual keyboard, the Pi should type:"
echo "    $TEST_STRING"
echo "wherever the text cursor is focused on the Pi or paired device."
"$BT_HELPER" "$TEST_STRING"

echo "=== [test_bluetooth] Test complete ==="
