#!/usr/bin/env bash
f
set -euo pipefail

#
# 16_switch_keyboard_backend.sh
#
# Switch the active keyboard backend between "uinput" and "ble".
# Supported backends:
#   - uinput  → local virtual keyboard on the Pi
#   - ble     → BLE HID over GATT backend (scaffold)
#
# Behaviour:
#   - If called with an argument, that backend is selected.
#   - If called without argument, backend is read from config.json.
#

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/00_set_env.sh"

CONFIG_PATH="$IPR_PROJECT_ROOT/ipr-keyboard/config.json"

BACKEND="${1:-}"

if [[ -z "$BACKEND" ]]; then
  # Read backend from config.json
  if ! command -v jq >/dev/null 2>&1; then
    echo "[16] ERROR: jq is required to read KeyboardBackend from $CONFIG_PATH" >&2
    exit 1
  fi
  BACKEND="$(jq -r '.KeyboardBackend // "uinput"' "$CONFIG_PATH")"
fi

if [[ "$BACKEND" != "uinput" && "$BACKEND" != "ble" ]]; then
  echo "[16] ERROR: Invalid backend: $BACKEND (must be 'uinput' or 'ble')" >&2
  exit 1
fi

echo "=== [16] Switching keyboard backend to: $BACKEND ==="

# Stop both services first
sudo systemctl stop bt_hid_uinput.service 2>/dev/null || true
sudo systemctl stop bt_hid_ble.service 2>/dev/null || true

if [[ "$BACKEND" == "uinput" ]]; then
  echo "[16] Enabling uinput backend (bt_hid_uinput.service)"
  sudo systemctl disable bt_hid_ble.service 2>/dev/null || true
  sudo systemctl enable bt_hid_uinput.service
  sudo systemctl restart bt_hid_uinput.service
else
  echo "[16] Enabling BLE backend (bt_hid_ble.service)"
  sudo systemctl disable bt_hid_uinput.service 2>/dev/null || true
  sudo systemctl enable bt_hid_ble.service
  sudo systemctl restart bt_hid_ble.service
fi

echo "=== [16] Backend switched to: $BACKEND ==="
echo "Active service: bt_hid_${BACKEND}.service"
