#!/usr/bin/env bash
#
# Bluetooth Configuration Script
#
# Purpose:
#   Configures /etc/bluetooth/main.conf with appropriate Class and AutoEnable for HID keyboard profile.
#   Makes a backup before modifying. Must be run as root.
#
# Usage:
#   sudo ./scripts/02_configure_bluetooth.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - Environment variables set (sources env_set_variables.sh)
#
# Note:
#   This script is required for enabling Bluetooth HID keyboard emulation.
#
# category: Bluetooth
# purpose: Configure Bluetooth for HID keyboard profile
# sudo: yes

set -eo pipefail


# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/env_set_variables.sh"
echo "[ble_configure_system] Configure /etc/bluetooth/main.conf for HID keyboard profile"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

CONF="/etc/bluetooth/main.conf"
BACKUP="/etc/bluetooth/main.conf.bak.$(date +%Y%m%d%H%M%S)"

if [[ -f "$CONF" ]]; then
  echo "Backing up $CONF to $BACKUP"
  cp "$CONF" "$BACKUP"
fi

# Insert comment about this script above the changes
if ! grep -q '# Modified by ble_configure_system.sh' "$CONF"; then
  sed -i '1i# Modified by ble_configure_system.sh' "$CONF"
fi

# Update or insert the required settings idempotently (match commented or uncommented lines)
sed -i \
  -e '/^[#[:space:]]*Class[[:space:]]*=.*/{s/^#\?//;s|Class[[:space:]]*=.*|Class = 0x002540|;b};$aClass = 0x002540' \
  -e '/^[#[:space:]]*DiscoverableTimeout[[:space:]]*=.*/{s/^#\?//;s|DiscoverableTimeout[[:space:]]*=.*|DiscoverableTimeout = 0|;b};$aDiscoverableTimeout = 0' \
  -e '/^[#[:space:]]*PairableTimeout[[:space:]]*=.*/{s/^#\?//;s|PairableTimeout[[:space:]]*=.*|PairableTimeout = 0|;b};$aPairableTimeout = 0' \
  -e '/^[#[:space:]]*AutoEnable[[:space:]]*=.*/{s/^#\?//;s|AutoEnable[[:space:]]*=.*|AutoEnable = true|;b};$aAutoEnable = true' \
  "$CONF"

echo "Restarting bluetooth service..."
systemctl restart bluetooth

echo "[ble_configure_system] Done."
