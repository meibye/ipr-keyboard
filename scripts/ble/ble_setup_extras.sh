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
#   sudo ./scripts/ble_setup_extras.sh
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

if [[ "$EUID" -ne 0 ]]; then
  echo "Please run this script as root (sudo ./scripts/ble_setup_extras.sh)."
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
  echo "  ERROR: $SCRIPT_DIR/../extras/ipr_ble_diagnostics.sh not found"
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
  echo "  ERROR: $SCRIPT_DIR/../extras/ipr_ble_hid_analyzer.py not found"
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
  echo "  WARNING: $PAIRING_TEMPLATE not found in source tree"
  echo "  The template should be part of the source code repository"
fi

# ---------------------------------------------------------------------------
# 7. Register pairing routes in server.py
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Checking pairing routes registration in server.py ==="
SERVER_PY="$PROJECT_ROOT/src/ipr_keyboard/web/server.py"
PAIRING_ROUTES_PY="$PROJECT_ROOT/src/ipr_keyboard/web/pairing_routes.py"

if [[ ! -f "$SERVER_PY" ]]; then
  echo "ERROR: $SERVER_PY not found; cannot register pairing routes."
  exit 1
fi

if [[ ! -f "$PAIRING_ROUTES_PY" ]]; then
  echo "ERROR: $PAIRING_ROUTES_PY not found; pairing routes module missing."
  exit 1
fi

if grep -q "pairing_routes" "$SERVER_PY" || grep -q "pairing_bp" "$SERVER_PY"; then
  echo "  Pairing routes already registered in server.py"
else
  echo "  WARNING: Pairing routes not registered in server.py"
  echo "  Please add the following to server.py create_app() function:"
  echo "    from .pairing_routes import pairing_bp"
  echo "    app.register_blueprint(pairing_bp)"
fi

echo "=== [ble_setup_extras] Setup complete ==="
echo "You can now use:"
echo "  - ipr_ble_diagnostics.sh          (BLE health check)"
echo "  - ipr_ble_hid_analyzer.py         (HID report analyzer)"
echo "  - /pairing                        (web pairing wizard)"

# ---------------------------------------------------------------------------
# Final check: Ensure bt_hid_agent_unified.service is active
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Checking bt_hid_agent_unified.service status ==="
if systemctl is-active --quiet bt_hid_agent_unified.service; then
  echo "[OK] bt_hid_agent_unified.service is active."
else
  echo "[ERROR] bt_hid_agent_unified.service is NOT active!"
  echo "Run: sudo systemctl start bt_hid_agent_unified.service"
fi
