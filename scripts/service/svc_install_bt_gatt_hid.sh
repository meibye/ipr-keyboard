#!/usr/bin/env bash
#
# svc_install_bt_gatt_hid.sh
#
# VERSION: 2026/02/13 15:23:48
# 
# Installs:
#   - Unified BlueZ Agent service for pairing (bt_hid_agent_unified.service)
#   - BLE HID GATT daemon (bt_hid_ble_daemon.py) for HID over GATT keyboard
#
# Features:
#   - Supports --agent-debug and --ble-debug parameters to enable verbose logging
#   - Updates /opt/ipr_common.env with BT_AGENT_DEBUG and BT_BLE_DEBUG accordingly
#   - Ensures correct discoverability for Windows BLE HID pairing
#
# Debugging:
#   BT_AGENT_DEBUG="1"   -> verbose agent logs (otherwise quiet)
#   BT_BLE_DEBUG="1"     -> verbose BLE daemon logs (otherwise concise)
#
# IMPORTANT (Windows visibility):
#   Windows may not list a BLE HID peripheral unless Adapter1.Discoverable is ON.
#   In dual-mode, this can cause Windows to show TWO devices (BR/EDR + BLE).
#   - If BT_CONTROLLER_MODE=le: Discoverable is set ON (safe; no BR/EDR identity)
#   - Else: Discoverable follows BT_ENABLE_CLASSIC_DISCOVERABLE (default off)
#
# Usage:
#   sudo ./scripts/service/svc_install_bt_gatt_hid.sh [--agent-debug] [--ble-debug]
#
# category: Service
# purpose: Install Bluetooth GATT HID services (agent and BLE daemon)
# parameters: --agent-debug,--ble-debug
# sudo: yes

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

AGENT_SERVICE_NAME="bt_hid_agent_unified"
BLE_SERVICE_NAME="bt_hid_ble"
AGENT_BIN="/usr/local/bin/bt_hid_agent_unified.py"
BLE_BIN="/usr/local/bin/bt_hid_ble_daemon.py"

ENV_FILE="/opt/ipr_common.env"
AGENT_UNIT="/etc/systemd/system/${AGENT_SERVICE_NAME}.service"
BLE_UNIT="/etc/systemd/system/${BLE_SERVICE_NAME}.service"

BT_OVERRIDE_DIR="/etc/systemd/system/bluetooth.service.d"
BT_OVERRIDE_FILE="${BT_OVERRIDE_DIR}/override.conf"
BT_MAIN_CONF="/etc/bluetooth/main.conf"

# Source files
AGENT_BIN_SRC="${SCRIPT_DIR}/bin/bt_hid_agent_unified.py"
BLE_BIN_SRC="${SCRIPT_DIR}/bin/bt_hid_ble_daemon.py"
AGENT_UNIT_SRC="${SCRIPT_DIR}/svc/bt_hid_agent_unified.service"
BLE_UNIT_SRC="${SCRIPT_DIR}/svc/bt_hid_ble.service"

# Parse parameters
AGENT_DEBUG=0
BLE_DEBUG=0
for arg in "$@"; do
  case "$arg" in
    --agent-debug) AGENT_DEBUG=1 ;;
    --ble-debug)   BLE_DEBUG=1 ;;
  esac
done

mkdir -p "$(dirname "$ENV_FILE")"

# Ensure ENV_FILE exists and has sane defaults for stable Windows BLE HID
if [[ ! -f "$ENV_FILE" ]]; then
  cat > "$ENV_FILE" <<EOF
# Common env for IPR BT keyboard services
# Debug
BT_AGENT_DEBUG="0"
BT_BLE_DEBUG="0"

# Prefer LE-only to avoid Windows showing two devices (Classic + BLE)
BT_CONTROLLER_MODE="le"
BT_ENABLE_CLASSIC_DISCOVERABLE="0"

# Adapter to use
BT_HCI="hci0"

# Advertising/local name
BT_DEVICE_NAME="IPR Keyboard (Dev)"

# The keyboard's identity (PnP ID: USB VID/PID/version).  Published by
# bluetoothd as its DeviceID -- see "Device identity" below.  0x1209 is
# pid.codes (open-source hardware); 0x0001 is its test PID.
BT_USB_VID="0x1209"
BT_USB_PID="0x0001"
BT_USB_VER="0x0100"
EOF
fi

# Update debug flags in ENV_FILE
if grep -q '^BT_AGENT_DEBUG=' "$ENV_FILE"; then
  sed -i 's/^BT_AGENT_DEBUG=.*/BT_AGENT_DEBUG="'$AGENT_DEBUG'"/' "$ENV_FILE"
else
  echo 'BT_AGENT_DEBUG="'$AGENT_DEBUG'"' >> "$ENV_FILE"
fi

if grep -q '^BT_BLE_DEBUG=' "$ENV_FILE"; then
  sed -i 's/^BT_BLE_DEBUG=.*/BT_BLE_DEBUG="'$BLE_DEBUG'"/' "$ENV_FILE"
else
  echo 'BT_BLE_DEBUG="'$BLE_DEBUG'"' >> "$ENV_FILE"
fi

# ------------------------------------------------------------------------------
# Bluetooth daemon plugin minimization (stability / remove "unknown display")
# Keep only what BLE HID over GATT needs:
#   - hog (HID over GATT)
#   - gap (advertising / GAP)
#   - scanparam (LE scan parameters)
#   - battery (optional; harmless, used by some hosts)
#
# Disable:
#   - a2dp,avrcp,bap (audio/media)
#   - network (PAN)
#   - input (classic HID)
#   - midi
#   - neard,health,deviceinfo,sap
#   - gamepad plugins (sixaxis, wiimote)
#   - autopair (can fight your custom agent)
# ------------------------------------------------------------------------------
mkdir -p "$BT_OVERRIDE_DIR"

# Ensure Experimental=true in main.conf (some BlueZ builds require it for LE GATT/advertising)
if [[ -f "$BT_MAIN_CONF" ]] && ! grep -q '^Experimental=true' "$BT_MAIN_CONF"; then
  if grep -q '^\[General\]' "$BT_MAIN_CONF"; then
    sed -i '/^\[General\]/a Experimental=true' "$BT_MAIN_CONF"
  else
    printf '\n[General]\nExperimental=true\n' >> "$BT_MAIN_CONF"
  fi
fi

# ------------------------------------------------------------------------------
# Device identity.
#
# bluetoothd publishes a Device Information service (0x180A) of its own,
# carrying its DeviceID.  With DeviceID unset that is its built-in default,
# usb:1d6b:0246:<BlueZ version> -- and it is the one Windows reads: a paired
# laptop's HID hardware ID was ..._VID&021d6b_PID&0246_REV&0552.  So the
# keyboard's identity in Windows was tied to the bluez PACKAGE, and an upgrade
# could change it and force a re-pair.
#
# The daemon used to publish a second 0x180A with the configured identity,
# which Windows never read.  Now there is one: bluetoothd's, set here from the
# same BT_USB_* values.
# ------------------------------------------------------------------------------
hex4() {  # "0x1209" / "1209" / "0X1209" -> "1209"
  local v="${1#0x}"; v="${v#0X}"
  printf '%04x' "$((16#${v:-0}))"
}
env_value() {  # value of KEY in $ENV_FILE, quotes stripped
  grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '"'"'"
}
DEVICE_ID="usb:$(hex4 "$(env_value BT_USB_VID)"):$(hex4 "$(env_value BT_USB_PID)"):$(hex4 "$(env_value BT_USB_VER)")"

set_main_conf_key() {  # key value -- in [General], replacing a commented example too
  local key="$1" value="$2" tmp="${BT_MAIN_CONF}.tmp"
  grep -q '^\[General\]' "$BT_MAIN_CONF" || printf '\n[General]\n' >> "$BT_MAIN_CONF"
  awk -v k="$key" -v v="$value" '
    BEGIN { in_general = 0; done = 0 }
    /^\[/ {
      if (in_general && !done) { print k " = " v; done = 1 }
      in_general = ($0 == "[General]")
    }
    in_general && !done && $0 ~ "^[#[:space:]]*" k "[[:space:]]*=" {
      print k " = " v; done = 1; next
    }
    in_general && $0 ~ "^[[:space:]]*" k "[[:space:]]*=" { next }   # drop duplicates
    { print }
    END { if (!done) print k " = " v }
  ' "$BT_MAIN_CONF" > "$tmp" && mv "$tmp" "$BT_MAIN_CONF"
}

if [[ -f "$BT_MAIN_CONF" ]]; then
  if [[ "$DEVICE_ID" == "usb:0000:0000:0000" ]]; then
    echo "WARN: BT_USB_VID/PID/VER missing from $ENV_FILE -- leaving DeviceID alone"
  else
    set_main_conf_key "DeviceID" "$DEVICE_ID"
    echo "=== [svc_install_bt_gatt_hid] DeviceID = $DEVICE_ID (takes effect when bluetoothd restarts) ==="
  fi
fi

# vcp, micp and bass are BlueZ's LE Audio servers.  Left loaded, they put
# Volume Control, Audio Input Control, Volume Offset Control, Microphone
# Control and Broadcast Audio Scan into the GATT database of a device that is
# a keyboard and nothing else -- services a PC then tries to set up for an
# audio device that does not exist.  This list is the one in force: step 04
# writes it after bt_configure_system.sh (step 01).  The two lists both
# exclude the audio plugins but otherwise still differ (step 01 also drops
# health, battery and deviceinfo; this one drops hostname).  None of those
# adds a GATT service, so the difference is harmless -- but it is real.
echo "=== [svc_install_bt_gatt_hid] Writing $BT_OVERRIDE_FILE ==="
cat > "$BT_OVERRIDE_FILE" <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/libexec/bluetooth/bluetoothd --experimental --noplugin=sap,avrcp,a2dp,network,input,midi,neard,wiimote,sixaxis,autopair,hostname,bap,vcp,micp,bass
ConfigurationDirectoryMode=0755
EOF

# ------------------------------------------------------------------------------
# Install executables from bin/ directory
# ------------------------------------------------------------------------------
echo "=== [svc_install_bt_gatt_hid] Installing executables ==="
if [[ ! -f "$AGENT_BIN_SRC" ]]; then
  echo "ERROR: Source file not found: $AGENT_BIN_SRC"
  exit 1
fi
if [[ ! -f "$BLE_BIN_SRC" ]]; then
  echo "ERROR: Source file not found: $BLE_BIN_SRC"
  exit 1
fi

cp "$AGENT_BIN_SRC" "$AGENT_BIN"
cp "$BLE_BIN_SRC" "$BLE_BIN"
chmod +x "$AGENT_BIN"
chmod +x "$BLE_BIN"
install -m 0755 -o root -g root "${SCRIPT_DIR}/bin/bt_adapter_prepare.sh" /usr/local/bin/bt_adapter_prepare.sh

# ------------------------------------------------------------------------------
# Install service units from svc/ directory
# ------------------------------------------------------------------------------
echo "=== [svc_install_bt_gatt_hid] Installing service units ==="
if [[ ! -f "$AGENT_UNIT_SRC" ]]; then
  echo "ERROR: Source file not found: $AGENT_UNIT_SRC"
  exit 1
fi
if [[ ! -f "$BLE_UNIT_SRC" ]]; then
  echo "ERROR: Source file not found: $BLE_UNIT_SRC"
  exit 1
fi

cp "$AGENT_UNIT_SRC" "$AGENT_UNIT"
cp "$BLE_UNIT_SRC" "$BLE_UNIT"

systemctl daemon-reload

echo "=== [svc_install_bt_gatt_hid] Done ==="
echo ""
echo "Next steps (important):"
echo "  1) Restart bluetooth to apply plugin drop-in:"
echo "     sudo systemctl restart bluetooth"
echo "  2) Restart services:"
echo "     sudo systemctl restart ${AGENT_SERVICE_NAME}.service"
echo "     sudo systemctl restart ${BLE_SERVICE_NAME}.service"
echo ""
echo "Verify:"
echo "  sudo systemctl status bluetooth ${AGENT_SERVICE_NAME}.service ${BLE_SERVICE_NAME}.service -n 30"
echo "  sudo journalctl -u ${AGENT_SERVICE_NAME}.service -n 120 --no-pager"
echo "  sudo journalctl -u ${BLE_SERVICE_NAME}.service -n 200 --no-pager"
echo ""
echo "If you want debug logs, set in ${ENV_FILE}:"
echo "  BT_AGENT_DEBUG=\"1\""
echo "  BT_BLE_DEBUG=\"1\""
echo ""
