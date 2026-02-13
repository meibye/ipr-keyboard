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
#   sudo ./scripts/ble/bt_configure_system.sh
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


# set_or_add <key> <value> <section>
set_or_add() {
  local key="$1"
  local value="$2"
  local section="$3"
  local tmpfile="${CONF}.tmp"

  # Ensure section exists
  if ! grep -qE "^\[$section\]" "$CONF"; then
    printf '\n[%s]\n' "$section" >> "$CONF"
  fi

  # awk script: replace or add key in section
  awk -v k="$key" -v v="$value" -v s="$section" '
    BEGIN{in_section=0; done=0}
    /^\[/{
      if(in_section && !done){print k" = "v; done=1}
      in_section=($0=="["s"]")
    }
    in_section && $0 ~ "^[#[:space:]]*"k"[[:space:]]*=" {
      if(!done){print k" = "v; done=1}
      next
    }
    {print}
    END{if(!done){print "\n["s"]\n"k" = "v}}
  ' "$CONF" > "$tmpfile"
  mv "$tmpfile" "$CONF"
}


# Key:Section mapping
# set_or_add "AutoEnable" "true" "General"     # AutoEnable not recognized by older bluez
set_or_add "Experimental" "true" "General"
set_or_add "PairableTimeout" "0" "General"
set_or_add "DiscoverableTimeout" "0" "General"
set_or_add "ControllerMode" "le" "General"
set_or_add "Privacy" "off" "General"
set_or_add "JustWorksRepairing" "always" "General"
set_or_add "AutoEnable" "true" "Policy"

# Create systemd override for bluetooth.service
echo "[ble_configure_system] Creating systemd override for bluetooth.service (ConfigurationDirectoryMode=0755)"
mkdir -p /etc/systemd/system/bluetooth.service.d

echo "[ble_configure_system] Writing override.conf for bluetooth.service..."
cat > /etc/systemd/system/bluetooth.service.d/override.conf <<EOF
[Service]
ConfigurationDirectoryMode=0755
ExecStart=
ExecStart=/usr/libexec/bluetooth/bluetoothd --noplugin=sap,avrcp,a2dp,bap,midi,network,health,wiimote,sixaxis,neard,autopair,battery,input,deviceinfo
EOF

echo "[ble_configure_system] Reloading systemd daemon..."
systemctl daemon-reload

echo "[ble_configure_system] Restarting bluetooth..."
systemctl restart bluetooth

echo "[ble_configure_system] Done."
