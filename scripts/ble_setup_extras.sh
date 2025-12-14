#!/usr/bin/env bash
#
# BLE Setup Extras Script
#
# Set up all extra RPi-side components for ipr-keyboard:
#   - Backend manager (prevents uinput + BLE running at same time)
#   - /etc/ipr-keyboard/backend selector
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
#   - BLE services must be installed
#
# category: Bluetooth
# purpose: Set up BLE extras including diagnostics and pairing wizard
#

set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
  echo "Please run this script as root (sudo ./scripts/ble_setup_extras.sh)."
  exit 1
fi

echo "=== [ble_setup_extras] Setting up ipr-keyboard RPi extras ==="

# ---------------------------------------------------------------------------
# Locate project root (assume scripts/ is at $PROJECT_ROOT/scripts)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Script dir:    $SCRIPT_DIR"
echo "Project root:  $PROJECT_ROOT"

# ---------------------------------------------------------------------------
# 1. Backend selector file: /etc/ipr-keyboard/backend
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Configuring backend selector ==="
BACKEND_DIR="/etc/ipr-keyboard"
BACKEND_FILE="$BACKEND_DIR/backend"
CONFIG_FILE="$PROJECT_ROOT/config.json"

mkdir -p "$BACKEND_DIR"

if [[ ! -f "$BACKEND_FILE" ]]; then
  # Try to read backend from config.json if it exists
  BACKEND_VALUE="ble"  # default
  if [[ -f "$CONFIG_FILE" ]] && command -v jq >/dev/null 2>&1; then
    CONFIG_BACKEND=$(jq -r '.KeyboardBackend // "ble"' "$CONFIG_FILE")
    if [[ "$CONFIG_BACKEND" == "uinput" || "$CONFIG_BACKEND" == "ble" ]]; then
      BACKEND_VALUE="$CONFIG_BACKEND"
      echo "  Using backend from config.json: $BACKEND_VALUE"
    fi
  fi
  echo "$BACKEND_VALUE" > "$BACKEND_FILE"
  echo "  Created $BACKEND_FILE with backend '$BACKEND_VALUE'"
else
  echo "  $BACKEND_FILE already exists (content: '$(cat "$BACKEND_FILE")')"
fi

# ---------------------------------------------------------------------------
# 2. Install backend manager service
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Installing backend manager service ==="
"$SCRIPT_DIR/svc_install_ipr_backend_manager.sh"

systemctl enable ipr_backend_manager.service
systemctl start ipr_backend_manager.service
echo "  Enabled and started ipr_backend_manager.service"

# ---------------------------------------------------------------------------
# 3. BLE diagnostics script
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Installing BLE diagnostics script ==="
BLE_DIAG="/usr/local/bin/ipr_ble_diagnostics.sh"

if [[ -f "$SCRIPT_DIR/extras/ipr_ble_diagnostics.sh" ]]; then
  cp "$SCRIPT_DIR/extras/ipr_ble_diagnostics.sh" "$BLE_DIAG"
  chmod +x "$BLE_DIAG"
  echo "  Installed $BLE_DIAG from extras/ipr_ble_diagnostics.sh"
else
  echo "  ERROR: $SCRIPT_DIR/extras/ipr_ble_diagnostics.sh not found"
  exit 1
fi

# ---------------------------------------------------------------------------
# 5. BLE HID analyzer (DBus signal listener for HID reports)
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Installing BLE HID analyzer ==="
BLE_ANALYZER="/usr/local/bin/ipr_ble_hid_analyzer.py"

if [[ -f "$SCRIPT_DIR/extras/ipr_ble_hid_analyzer.py" ]]; then
  cp "$SCRIPT_DIR/extras/ipr_ble_hid_analyzer.py" "$BLE_ANALYZER"
  chmod +x "$BLE_ANALYZER"
  echo "  Installed $BLE_ANALYZER from extras/ipr_ble_hid_analyzer.py"
else
  echo "  ERROR: $SCRIPT_DIR/extras/ipr_ble_hid_analyzer.py not found"
  exit 1
fi

# ---------------------------------------------------------------------------
# 6. Pairing wizard HTML template
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Installing pairing wizard HTML template ==="
TEMPLATES_DIR="$PROJECT_ROOT/src/ipr_keyboard/web/templates"
PAIRING_TEMPLATE="$TEMPLATES_DIR/pairing_wizard.html"

mkdir -p "$TEMPLATES_DIR"

if [[ -f "$TEMPLATES_DIR/pairing_wizard.html" ]]; then
  echo "  Pairing wizard template already exists at $PAIRING_TEMPLATE"
else
  echo "  ERROR: $TEMPLATES_DIR/pairing_wizard.html should exist in source tree"
  echo "  Template should be part of the source code, not dynamically generated"
  exit 1
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
echo "  - /etc/ipr-keyboard/backend       (backend selector: 'ble' or 'uinput')"

echo "  - ipr_backend_manager.service     (ensures only one backend is active)"

# ---------------------------------------------------------------------------
# Final check: Ensure bt_hid_agent.service is active
# ---------------------------------------------------------------------------
echo "=== [ble_setup_extras] Checking bt_hid_agent.service status ==="
if systemctl is-active --quiet bt_hid_agent.service; then
  echo "[OK] bt_hid_agent.service is active."
else
  echo "[ERROR] bt_hid_agent.service is NOT active!"
  echo "Run: sudo systemctl start bt_hid_agent.service"
fi
