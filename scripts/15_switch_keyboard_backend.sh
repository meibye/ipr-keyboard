#!/usr/bin/env bash
set -euo pipefail

#
# 15_switch_keyboard_backend.sh
#
# Switch the active keyboard backend between "uinput" and "ble".
#
# The backend can be:
#   - passed as first argument:   ./scripts/15_switch_keyboard_backend.sh uinput|ble
#   - read from config.json:      ./scripts/15_switch_keyboard_backend.sh
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/00_set_env.sh"

PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
CONFIG_PATH="$PROJECT_DIR/config.json"

BACKEND="${1:-}"

if [[ -z "$BACKEND" ]]; then
  if ! command -v jq >/dev/null 2>&1; then
    echo "[15] ERROR: jq is required to read KeyboardBackend from $CONFIG_PATH" >&2
    exit 1
  fi
  BACKEND="$(jq -r '.KeyboardBackend // "uinput"' "$CONFIG_PATH")"
fi

if [[ "$BACKEND" != "uinput" && "$BACKEND" != "ble" ]]; then
  echo "[15] ERROR: Invalid backend: $BACKEND (must be 'uinput' or 'ble')" >&2
  exit 1
fi

echo "=== [15] Switching keyboard backend to: $BACKEND ==="

# Stop both services first
sudo systemctl stop bt_hid_uinput.service 2>/dev/null || true
sudo systemctl stop bt_hid_ble.service 2>/dev/null || true

if [[ "$BACKEND" == "uinput" ]]; then
  echo "[15] Enabling uinput backend (bt_hid_uinput.service)"
  sudo systemctl disable bt_hid_ble.service 2>/dev/null || true
  sudo systemctl enable bt_hid_uinput.service
  sudo systemctl restart bt_hid_uinput.service
else
  echo "[15] Enabling BLE backend (bt_hid_ble.service)"
  sudo systemctl disable bt_hid_uinput.service 2>/dev/null || true
  sudo systemctl enable bt_hid_ble.service
  sudo systemctl restart bt_hid_ble.service
fi

echo "=== [15] Backend switched to: $BACKEND ==="
echo "Active service: bt_hid_${BACKEND}.service"
