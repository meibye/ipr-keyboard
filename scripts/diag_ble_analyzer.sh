#!/usr/bin/env bash
#
# diag_ble_analyzer.sh
#
# Wrapper script to run BLE HID analyzer tool.
# Calls /usr/local/bin/ipr_ble_hid_analyzer.py which is installed by ble_setup_extras.sh
#
# This tool monitors DBus signals for GATT characteristic changes and logs HID reports.
# Useful for debugging HID report generation and BLE communication.
#
# Usage:
#   sudo ./scripts/diag_ble_analyzer.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - BLE HID analyzer must be installed via ble_setup_extras.sh
#
# Output: Logs to systemd journal and stdout
#
# category: Diagnostics
# purpose: Monitor GATT HID reports for debugging BLE communication

set -euo pipefail

ANALYZER_TOOL="/usr/local/bin/ipr_ble_hid_analyzer.py"

if [[ ! -x "$ANALYZER_TOOL" ]]; then
  echo "ERROR: BLE HID analyzer tool not found at $ANALYZER_TOOL"
  echo "Please run: sudo ./scripts/ble_setup_extras.sh"
  exit 1
fi

echo "=== Starting BLE HID Analyzer ==="
echo "This will monitor HID reports and log them to systemd journal."
echo "Press Ctrl+C to stop."
echo
"$ANALYZER_TOOL"
