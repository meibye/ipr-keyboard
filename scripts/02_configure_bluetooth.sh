#!/usr/bin/env bash

# Configures /etc/bluetooth/main.conf with appropriate Class and AutoEnable.
# It makes a backup first.

set -euo pipefail

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
