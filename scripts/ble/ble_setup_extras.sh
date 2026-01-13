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

# ---------------------------------------------------------------------------
# 6. Pairing wizard HTML template
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Verifying pairing wizard HTML template ==="
TEMPLATES_DIR="$PROJECT_ROOT/src/ipr_keyboard/web/templates"
PAIRING_TEMPLATE="$TEMPLATES_DIR/pairing_wizard.html"

if [[ -f "$PAIRING_TEMPLATE" ]]; then
  echo "  Pairing wizard template exists at $PAIRING_TEMPLATE"
else
  echo -e "  ${YELLOW}WARNING:${NC} $PAIRING_TEMPLATE not found in source tree"
  echo "  The template should be part of the source code repository"
fi

# ---------------------------------------------------------------------------
# 7. Register pairing routes in server.py
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Checking pairing routes registration in server.py ==="
SERVER_PY="$PROJECT_ROOT/src/ipr_keyboard/web/server.py"
PAIRING_ROUTES_PY="$PROJECT_ROOT/src/ipr_keyboard/web/pairing_routes.py"

if [[ ! -f "$SERVER_PY" ]]; then
  echo -e "  ${RED}ERROR:${NC} $SERVER_PY not found; cannot register pairing routes."
  exit 1
fi

if [[ ! -f "$PAIRING_ROUTES_PY" ]]; then
  echo -e "  ${RED}ERROR:${NC} $PAIRING_ROUTES_PY not found; pairing routes module missing."
  exit 1
fi

if grep -q "pairing_routes" "$SERVER_PY" || grep -q "pairing_bp" "$SERVER_PY"; then
  echo "  Pairing routes already registered in server.py"
else
  echo -e "  ${YELLOW}WARNING:${NC} Pairing routes not registered in server.py"
  echo "  Please add the following to server.py create_app() function:"
  echo "    from .pairing_routes import pairing_bp"
  echo "    app.register_blueprint(pairing_bp)"
fi

echo "=== [ble_setup_extras] Setup complete ==="
echo "You can now use:"
echo "  - ipr_ble_diagnostics.sh          (BLE health check)"
echo "  - ipr_ble_hid_analyzer.py         (HID report analyzer)"
echo "  - http://localhost:8080/pairing   (web pairing wizard)"
