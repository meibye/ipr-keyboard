#!/usr/bin/env bash
#
# ble_show_bt_mac_for_windows.sh
#
# Show the Raspberry Pi Bluetooth MAC address in:
#   - Normal Linux format (with colons)
#   - Windows instance-id format (no colons, uppercase)
#
# Usage:
#   ./scripts/ble_switch_backend.sh [uinput|ble]
#
# Prerequisites:
#   - None
#
# category: Bluetooth
# purpose: Show the Raspberry Pi Bluetooth MAC address in Windows format
# sudo: no

set -eo pipefail

get_mac_from_bluetoothctl() {
  if command -v bluetoothctl >/dev/null 2>&1; then
    # bluetoothctl show | grep "Controller" | first field after 'Controller'
    local mac
    mac="$(bluetoothctl show 2>/dev/null | awk '/Controller/ {print $2; exit}')"
    if [[ -n "${mac:-}" ]]; then
      echo "$mac"
      return 0
    fi
  fi
  return 1
}

get_mac_from_hciconfig() {
  if command -v hciconfig >/dev/null 2>&1; then
    local mac
    mac="$(hciconfig hci0 2>/dev/null | awk '/BD Address/ {print $3; exit}')"
    if [[ -n "${mac:-}" ]]; then
      echo "$mac"
      return 0
    fi
  fi
  return 1
}

echo "=== IPR Keyboard - Bluetooth MAC helper ==="

BT_MAC=""

if BT_MAC="$(get_mac_from_bluetoothctl)"; then
  :
elif BT_MAC="$(get_mac_from_hciconfig)"; then
  :
else
  echo "ERROR: Could not determine Bluetooth MAC address."
  echo "Make sure bluetooth is enabled (sudo rfkill unblock bluetooth) and try:"
  echo "  bluetoothctl show"
  exit 1
fi

echo "Detected Bluetooth MAC (Linux format):   $BT_MAC"

# Normalize: remove non-hex chars, uppercase
BT_MAC_WIN="$(echo "$BT_MAC" | tr -d ':-' | tr '[:lower:]' '[:upper:]')"

if [[ ${#BT_MAC_WIN} -ne 12 ]]; then
  echo "WARNING: Normalized MAC '$BT_MAC_WIN' is not 12 hex characters."
else
  echo "Windows InstanceId format (no colons):  $BT_MAC_WIN"
fi

echo
echo "Use this value when running the Windows script:"
echo "  DEV_$BT_MAC_WIN"
echo
echo "Example on Windows:"
echo "  .\\Remove-PiBluetoothDevices.ps1"
echo "  (enter original MAC when prompted: $BT_MAC)"