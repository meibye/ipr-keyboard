#!/usr/bin/env bash

#
# ipr-keyboard Bluetooth Keyboard Test Script
#
# Purpose:
#   Sends a test string via the Bluetooth HID helper (bt_kb_send) or daemon to verify Bluetooth keyboard emulation is working end-to-end.
#   Useful for troubleshooting Bluetooth pairing, helper/daemon setup, and keyboard pipeline.
#
# Usage:
#   ./scripts/14_test_bt_keyboard.sh ["Your test string"]
#   (If no argument is given, a default Danish test string is sent.)
#
# Prerequisites:
#   - Must NOT be run as root
#   - Bluetooth helper script (`/usr/local/bin/bt_kb_send`) or daemon must be installed and running
#   - Target device must be paired and connected
#   - Environment variables set (sources 00_set_env.sh)
#
# Note:
#   For manual, interactive testing only. Not used in automated workflows or CI.

echo "=== [14] Test Bluetooth keyboard pipeline (FIFO + daemon) ==="

FIFO="/run/bt_keyboard_fifo"
SERVICE="bt_hid_daemon.service"

echo "--- Checking service status ---"
if ! sudo systemctl status "$SERVICE" --no-pager >/dev/null 2>&1; then
  echo "[14] ERROR: service $SERVICE not running or failed." >&2
  echo "     Check logs with: sudo journalctl -u $SERVICE -f" >&2
  exit 1
fi

if [[ ! -p "$FIFO" ]]; then
  echo "[14] ERROR: FIFO $FIFO not found." >&2
  echo "     The daemon should create it automatically." >&2
  echo "     Check logs with: sudo journalctl -u $SERVICE -f" >&2
  exit 1
fi

echo "--- Sending Danish test string via bt_kb_send ---"
echo "If everything is wired to the local virtual keyboard, the Pi should type:"
echo "    Test æøå ÆØÅ"
echo "wherever the text cursor is focused on the Pi."
bt_kb_send "Test æøå ÆØÅ"

echo "=== [14] Test complete ==="
