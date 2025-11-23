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
#   - Environment variables set (sources 00_set_env.sh)
#
# Note:
#   This script is required for enabling Bluetooth HID keyboard emulation.

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/00_set_env.sh"
echo "[02] Configure /etc/bluetooth/main.conf for HID keyboard profile"

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

cat <<'EOF' >> "$CONF"

# ---- ipr_keyboard custom config ----
[General]
Class = 0x002540
DiscoverableTimeout = 0
PairableTimeout = 0

[Policy]
AutoEnable=true
# ---- end ipr_keyboard custom config ----
EOF

echo "Restarting bluetooth service..."
systemctl restart bluetooth

echo "[02] Done."
