#!/usr/bin/env bash
#
# ble_configure_system.sh
#
# Purpose:
#   Configure /etc/bluetooth/main.conf so the Pi behaves like a BLE-only HID
#   peripheral (recommended for BLE HID over GATT). This avoids Windows showing
#   two devices (one BR/EDR "classic" and one BLE advertisement).
#
# What it does:
#   - Ensures AutoEnable = true
#   - Ensures PairableTimeout = 0 (never times out)
#   - Ensures DiscoverableTimeout = 0 (only matters if classic discoverable is enabled)
#   - Sets ControllerMode = le   (DISABLES BR/EDR; only LE)
#
# Notes:
#   - If you want to use the classic/uinput backend (BR/EDR HID), do NOT set
#     ControllerMode=le. In that case, set BT_CONTROLLER_MODE=dual in /opt/ipr_common.env
#     and rerun this script.
#
# Usage:
#   sudo ./scripts/ble_configure_system.sh
#
set -euo pipefail

CONF="/etc/bluetooth/main.conf"
BACKUP="/etc/bluetooth/main.conf.bak.$(date +%Y%m%d%H%M%S)"

if [[ $EUID -ne 0 ]]; then
  echo "ERROR: must be run as root"
  exit 1
fi

# Optional: load desired mode from /opt/ipr_common.env if present
BT_CONTROLLER_MODE="le"
if [[ -f /opt/ipr_common.env ]]; then
  # shellcheck disable=SC1091
  source /opt/ipr_common.env || true
fi
if [[ "${BT_CONTROLLER_MODE:-le}" == "dual" ]]; then
  BT_CONTROLLER_MODE="dual"
else
  BT_CONTROLLER_MODE="le"
fi

echo "[ble_configure_system] Updating $CONF (BT_CONTROLLER_MODE=$BT_CONTROLLER_MODE)"

if [[ -f "$CONF" ]]; then
  echo "[ble_configure_system] Backup $CONF -> $BACKUP"
  cp "$CONF" "$BACKUP"
else
  echo "[ble_configure_system] $CONF does not exist, creating"
  touch "$CONF"
fi

# Ensure we have a [General] section
if ! grep -qE '^\[General\]' "$CONF"; then
  printf '\n[General]\n' >> "$CONF"
fi

set_or_add() {
  local key="$1"
  local value="$2"
  if grep -qE "^[#[:space:]]*${key}[[:space:]]*=" "$CONF"; then
    # replace first match (commented or uncommented)
    sed -i -E "0,/^[#[:space:]]*${key}[[:space:]]*=/{s/^[#[:space:]]*${key}[[:space:]]*=.*/${key} = ${value}/}" "$CONF"
  else
    # append under [General]
    awk -v k="$key" -v v="$value" '
      BEGIN{done=0}
      /^\[General\]/{print; if(!done){print k" = "v; done=1; next}}
      {print}
      END{if(!done){print "\n[General]\n"k" = "v}}
    ' "$CONF" > "${CONF}.tmp"
    mv "${CONF}.tmp" "$CONF"
  fi
}

set_or_add "AutoEnable" "true"
set_or_add "PairableTimeout" "0"
set_or_add "DiscoverableTimeout" "0"
set_or_add "ControllerMode" "$BT_CONTROLLER_MODE"

echo "[ble_configure_system] Restarting bluetooth..."
systemctl restart bluetooth

echo "[ble_configure_system] Done."
