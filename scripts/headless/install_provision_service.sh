#!/usr/bin/env bash
#
# install_provision_service.sh
#
# Install the ipr-provision headless Wi-Fi provisioning service.
#
# Installs:
#   - net_provision_hotspot.sh  → /usr/local/sbin/ipr-provision.sh
#   - net_provision_web.py      → /usr/local/sbin/ipr-provision-web.py
#   - ipr-provision.service     → /etc/systemd/system/
#
# The service starts the management hotspot at boot and launches the
# provisioning web UI on https://10.42.0.1/ so the device can be
# configured without a keyboard or display.
#
# Usage:
#   sudo ./scripts/headless/install_provision_service.sh
#
# category: Headless
# purpose: Install the ipr-provision hotspot and web provisioning service
# sudo: yes

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Please run as root: sudo $0"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SRC_HOTSPOT="$SCRIPT_DIR/net_provision_hotspot.sh"
SRC_WEB="$SCRIPT_DIR/net_provision_web.py"
SRC_SERVICE="$SCRIPT_DIR/ipr-provision.service"

DEST_HOTSPOT="/usr/local/sbin/ipr-provision.sh"
DEST_WEB="/usr/local/sbin/ipr-provision-web.py"
DEST_SERVICE="/etc/systemd/system/ipr-provision.service"

echo "=== [install_provision_service] Installing ipr-provision service ==="
echo ""

# Verify source files exist
for src in "$SRC_HOTSPOT" "$SRC_WEB" "$SRC_SERVICE"; do
    if [[ ! -f "$src" ]]; then
        echo "ERROR: Source file not found: $src"
        exit 1
    fi
done

# Install scripts
echo "[1/3] Installing scripts to /usr/local/sbin/ ..."
cp "$SRC_HOTSPOT" "$DEST_HOTSPOT"
chmod +x "$DEST_HOTSPOT"
cp "$SRC_WEB" "$DEST_WEB"
chmod +x "$DEST_WEB"
echo "      OK"

# Install service unit
echo "[2/3] Installing systemd unit ..."
cp "$SRC_SERVICE" "$DEST_SERVICE"
systemctl daemon-reload
echo "      OK"

# Enable and start
echo "[3/3] Enabling and starting ipr-provision.service ..."
systemctl enable ipr-provision.service
systemctl restart ipr-provision.service
echo "      OK"

echo ""
echo "=== [install_provision_service] Done ==="
echo ""
echo "Status:"
systemctl --no-pager -l status ipr-provision.service || true
echo ""
echo "Hotspot credentials (once running): cat /etc/ipr-hotspot.secret"
