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
  echo "[14] ERROR: service $SERVICE not running or failed." >&2
#!/usr/bin/env bash
#
# ipr-keyboard Bluetooth Keyboard Test Script
#
# Purpose:
#   Sends a test string via the Bluetooth HID helper or daemon.
#   Useful for manual testing of Bluetooth keyboard functionality.
#
# Usage:
#   ./scripts/14_test_bt_keyboard.sh "Hello world!"
#
# Prerequisites:
#   - Must NOT be run as root
#   - Bluetooth helper or daemon must be installed
#   - Environment variables set (sources 00_set_env.sh)
#
# Note:
#   For manual testing only. Not used in automated workflows.

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/00_set_env.sh"
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
