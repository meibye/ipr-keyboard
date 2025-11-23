#!/usr/bin/env bash
#
# ipr-keyboard Keyboard Backend Switch Script (legacy)
#
# Purpose:
#   Switches the active keyboard backend between "uinput" (local virtual keyboard) and "ble" (Bluetooth Low Energy HID).
#   Stops both backend services, then enables and starts the selected one.
#
# Usage:
#   ./scripts/15_switch_keyboard_backend.sh [uinput|ble]
#   (If called without an argument, reads backend from config.json.)
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - Environment variables set (sources 00_set_env.sh) if using project directory
#   - jq must be installed (for reading config.json)
#
# Note:
#   This is a legacy script. Prefer using 16_switch_keyboard_backend.sh for environment-variable-based project directory resolution.

#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/meibye/dev/ipr-keyboard"
CONFIG="$PROJECT_DIR/config.json"

BACKEND="${1:-}"

if [[ -z "$BACKEND" ]]; then
  # If no arg, read from config.json
  BACKEND=$(jq -r '.KeyboardBackend // "uinput"' "$CONFIG")
fi

if [[ "$BACKEND" != "uinput" && "$BACKEND" != "ble" ]]; then
  echo "Invalid backend: $BACKEND (must be 'uinput' or 'ble')" >&2
  exit 1
fi

echo "[15] Switching keyboard backend to: $BACKEND"

sudo systemctl stop bt_hid_uinput.service || true
sudo systemctl stop bt_hid_ble.service || true

if [[ "$BACKEND" == "uinput" ]]; then
  sudo systemctl enable --now bt_hid_uinput.service
else
  sudo systemctl enable --now bt_hid_ble.service
fi

echo "[15] Done."
