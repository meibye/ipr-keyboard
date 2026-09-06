#!/usr/bin/env bash
#
# BLE Setup Extras Script
#
# Set up all extra RPi-side components for ipr-keyboard Bluetooth GATT HID:
#   - BLE diagnostics script
#   - BLE HID analyzer
#   - Pairing wizard HTML template
#   - Pairing routes in src/ipr_keyboard/web/server.py
#
# Usage:
#   sudo ./scripts/ble/ble_setup_extras.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - Bluetooth GATT HID services must be installed
#
# category: Bluetooth
# purpose: Set up BLE extras including diagnostics and pairing wizard
# sudo: yes
#

set -eo pipefail
# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [[ "$EUID" -ne 0 ]]; then
  echo -e "${RED}Please run this script as root (sudo ./scripts/ble/ble_setup_extras.sh).${NC}"
  exit 1
fi

echo "=== [ble_setup_extras] Setting up ipr-keyboard RPi extras ==="

# ---------------------------------------------------------------------------
# Locate project root (assume scripts/ble/ is at $PROJECT_ROOT/scripts/ble)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Script dir:    $SCRIPT_DIR"
echo "Project root:  $PROJECT_ROOT"

# ---------------------------------------------------------------------------
# 3. BLE diagnostics script
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Installing BLE diagnostics script ==="
BLE_DIAG="/usr/local/bin/ipr_ble_diagnostics.sh"

if [[ -f "$SCRIPT_DIR/../extras/ipr_ble_diagnostics.sh" ]]; then
  cp "$SCRIPT_DIR/../extras/ipr_ble_diagnostics.sh" "$BLE_DIAG"
  chmod +x "$BLE_DIAG"
  echo "  Installed $BLE_DIAG from extras/ipr_ble_diagnostics.sh"
else
  echo -e "  ${RED}ERROR:${NC} $SCRIPT_DIR/../extras/ipr_ble_diagnostics.sh not found"
  exit 1
fi

# ---------------------------------------------------------------------------
# 5. BLE HID analyzer (DBus signal listener for HID reports)
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Installing BLE HID analyzer ==="
BLE_ANALYZER="/usr/local/bin/ipr_ble_hid_analyzer.py"

if [[ -f "$SCRIPT_DIR/../extras/ipr_ble_hid_analyzer.py" ]]; then
  cp "$SCRIPT_DIR/../extras/ipr_ble_hid_analyzer.py" "$BLE_ANALYZER"
  chmod +x "$BLE_ANALYZER"
  echo "  Installed $BLE_ANALYZER from extras/ipr_ble_hid_analyzer.py"
else
  echo -e "  ${RED}ERROR:${NC} $SCRIPT_DIR/../extras/ipr_ble_hid_analyzer.py not found"
  exit 1
fi

# The legacy pairing wizard (pairing_routes.py + pairing_wizard.html) was
# removed: it was never registered in server.py, so it had never actually
# served a request.  Pairing lives in server.py itself, and the dashboard uses
# POST /api/actions/pairing -- see docs/ui/api-contract.md.

echo "=== [ble_setup_extras] Setup complete ==="
echo "You can now use:"
echo "  - ipr_ble_diagnostics.sh          (BLE health check)"
echo "  - ipr_ble_hid_analyzer.py         (HID report analyzer)"
