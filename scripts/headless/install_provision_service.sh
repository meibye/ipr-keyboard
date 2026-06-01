#!/usr/bin/env bash
#
# install_provision_service.sh
#
# Install the ipr-provision headless Wi-Fi provisioning service.
#
# Installs:
#   - net_provision_hotspot.sh  → /usr/local/sbin/ipr-provision.sh
#   - ipr-provision.service     → /etc/systemd/system/
#   - TLS certificates          → /etc/ipr-ssl/ (via gen_ipr_ssl_cert.sh)
#
# The service configures the Wi-Fi hotspot at boot.
# The management web UI is served by ipr_keyboard.service on HTTPS port 443.
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
SRC_SERVICE="$SCRIPT_DIR/ipr-provision.service"
SRC_CERT_SCRIPT="$SCRIPT_DIR/gen_ipr_ssl_cert.sh"

DEST_HOTSPOT="/usr/local/sbin/ipr-provision.sh"
DEST_SERVICE="/etc/systemd/system/ipr-provision.service"

echo "=== [install_provision_service] Installing ipr-provision service ==="
echo ""

# Verify source files exist
for src in "$SRC_HOTSPOT" "$SRC_SERVICE" "$SRC_CERT_SCRIPT"; do
    if [[ ! -f "$src" ]]; then
        echo "ERROR: Source file not found: $src"
        exit 1
    fi
done

# Remove retired provisioning web server if present
if [[ -f /usr/local/sbin/ipr-provision-web.py ]]; then
    echo "[pre] Removing retired ipr-provision-web.py ..."
    rm -f /usr/local/sbin/ipr-provision-web.py
    echo "      OK"
fi

# Install hotspot script
echo "[1/4] Installing hotspot script to /usr/local/sbin/ ..."
cp "$SRC_HOTSPOT" "$DEST_HOTSPOT"
chmod +x "$DEST_HOTSPOT"
echo "      OK"

# Generate TLS certificates
echo "[2/4] Generating TLS certificates ..."
bash "$SRC_CERT_SCRIPT"
echo "      OK"

# Install service unit
echo "[3/4] Installing systemd unit ..."
cp "$SRC_SERVICE" "$DEST_SERVICE"
systemctl daemon-reload
echo "      OK"

# Enable and start
echo "[4/4] Enabling and starting ipr-provision.service ..."
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
echo "CA certificate for browser trust:   https://10.42.0.1/setup/ca.crt"
