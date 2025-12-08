#!/usr/bin/env bash
set -euo pipefail

#
# ble_switch_backend.sh
#
# Switch the active keyboard backend between "uinput" and "ble".
#
# The backend can be:
#   - passed as first argument:   ./scripts/ble_switch_backend.sh uinput|ble
#   - read from config.json:      ./scripts/ble_switch_backend.sh
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env_set_variables.sh"

PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
CONFIG_PATH="$PROJECT_DIR/config.json"

BACKEND="${1:-}"

if [[ -z "$BACKEND" ]]; then
  if ! command -v jq >/dev/null 2>&1; then
    echo "[ble_switch_backend] ERROR: jq is required to read KeyboardBackend from $CONFIG_PATH" >&2
    exit 1
  fi
  BACKEND="$(jq -r '.KeyboardBackend // "uinput"' "$CONFIG_PATH")"
fi

if [[ "$BACKEND" != "uinput" && "$BACKEND" != "ble" ]]; then
  echo "[ble_switch_backend] ERROR: Invalid backend: $BACKEND (must be 'uinput' or 'ble')" >&2
  exit 1
fi

echo "=== [ble_switch_backend] Switching keyboard backend to: $BACKEND ==="

# Update /etc/ipr-keyboard/backend file
echo "[ble_switch_backend] Updating /etc/ipr-keyboard/backend to: $BACKEND"
echo "$BACKEND" | sudo tee /etc/ipr-keyboard/backend >/dev/null

# Update config.json if jq is available
if command -v jq >/dev/null 2>&1 && [[ -f "$CONFIG_PATH" ]]; then
  echo "[ble_switch_backend] Updating config.json KeyboardBackend to: $BACKEND"
  TEMP_CONFIG=$(mktemp)
  jq --arg backend "$BACKEND" '.KeyboardBackend = $backend' "$CONFIG_PATH" > "$TEMP_CONFIG"
  mv "$TEMP_CONFIG" "$CONFIG_PATH"
fi

# Stop both services first
sudo systemctl stop bt_hid_uinput.service 2>/dev/null || true
sudo systemctl stop bt_hid_ble.service 2>/dev/null || true

if [[ "$BACKEND" == "uinput" ]]; then
  echo "[ble_switch_backend] Enabling uinput backend (bt_hid_uinput.service)"
  sudo systemctl disable bt_hid_ble.service 2>/dev/null || true
  sudo systemctl enable bt_hid_uinput.service
  sudo systemctl restart bt_hid_uinput.service

else
  echo "[ble_switch_backend] Enabling BLE backend (bt_hid_ble.service)"
  sudo systemctl disable bt_hid_uinput.service 2>/dev/null || true
  sudo systemctl enable bt_hid_ble.service
  sudo systemctl restart bt_hid_ble.service

  # Ensure bt_hid_agent.service is running
  if ! systemctl is-active --quiet bt_hid_agent.service; then
    echo "[ble_switch_backend] bt_hid_agent.service is NOT active. Starting it..."
    sudo systemctl start bt_hid_agent.service
  else
    echo "[ble_switch_backend] bt_hid_agent.service is already active."
  fi
fi

echo "=== [ble_switch_backend] Backend switched to: $BACKEND ==="
echo "Active service: bt_hid_${BACKEND}.service"
echo "Both /etc/ipr-keyboard/backend and config.json have been synchronized."
