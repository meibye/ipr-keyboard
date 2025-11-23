#
# Test Bluetooth Keyboard Script
#
# Purpose:
#   Sends a test string via the Bluetooth HID keyboard helper to verify Bluetooth keyboard emulation is working.
#   Useful for troubleshooting Bluetooth pairing and helper script setup.
#
# Usage:
#   ./scripts/14_test_bt_keyboard.sh
#
# Prerequisites:
#   - Bluetooth helper script (`/usr/local/bin/bt_kb_send`) must be installed
#   - Target device must be paired and connected
#
# Note:
#   This script is safe to run multiple times. It is intended for manual testing.

#!/usr/bin/env bash
set -euo pipefail

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
