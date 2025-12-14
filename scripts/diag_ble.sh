#!/usr/bin/env bash
#
# diag_ble.sh
#
# Wrapper script to run BLE diagnostics tool.
# Calls /usr/local/bin/ipr_ble_diagnostics.sh which is installed by ble_setup_extras.sh
#
# Usage:
#   sudo ./scripts/diag_ble.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - BLE diagnostics tool must be installed via ble_setup_extras.sh
#
# category: Diagnostics
# purpose: Run BLE diagnostics to check adapter and services

set -eo pipefail

DIAG_TOOL="/usr/local/bin/ipr_ble_diagnostics.sh"

if [[ ! -x "$DIAG_TOOL" ]]; then
  echo "ERROR: BLE diagnostics tool not found at $DIAG_TOOL"
  echo "Please run: sudo ./scripts/ble_setup_extras.sh"
  exit 1
fi

echo "=== Running BLE Diagnostics ==="
echo
"$DIAG_TOOL"
