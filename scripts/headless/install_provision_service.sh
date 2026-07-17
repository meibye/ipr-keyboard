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
SRC_CERT_RENEW="$SCRIPT_DIR/ipr-cert-renew.sh"
SRC_CERT_RENEW_SVC="$SCRIPT_DIR/ipr-cert-renew.service"
SRC_CERT_RENEW_TIMER="$SCRIPT_DIR/ipr-cert-renew.timer"

DEST_HOTSPOT="/usr/local/sbin/ipr-provision.sh"
DEST_CERT_GEN="/usr/local/sbin/ipr-cert-gen.sh"
DEST_CERT_RENEW="/usr/local/sbin/ipr-cert-renew.sh"
DEST_SERVICE="/etc/systemd/system/ipr-provision.service"
DEST_CERT_RENEW_SVC="/etc/systemd/system/ipr-cert-renew.service"
DEST_CERT_RENEW_TIMER="/etc/systemd/system/ipr-cert-renew.timer"

echo "=== [install_provision_service] Installing ipr-provision service ==="
echo ""

# Verify source files exist
for src in "$SRC_HOTSPOT" "$SRC_SERVICE" "$SRC_CERT_SCRIPT" \
           "$SRC_CERT_RENEW" "$SRC_CERT_RENEW_SVC" "$SRC_CERT_RENEW_TIMER"; do
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
echo "[1/6] Installing hotspot script to /usr/local/sbin/ ..."
cp "$SRC_HOTSPOT" "$DEST_HOTSPOT"
chmod +x "$DEST_HOTSPOT"
echo "      OK"

# Install cert generation + renewal scripts
echo "[2/6] Installing certificate scripts to /usr/local/sbin/ ..."
cp "$SRC_CERT_SCRIPT" "$DEST_CERT_GEN"
chmod +x "$DEST_CERT_GEN"
cp "$SRC_CERT_RENEW" "$DEST_CERT_RENEW"
chmod +x "$DEST_CERT_RENEW"
echo "      OK"

# Generate TLS certificates (first-time only; --renew preserves existing CA)
echo "[3/6] Generating TLS certificates ..."
bash "$DEST_CERT_GEN"
echo "      OK"

# Install service units
echo "[4/6] Installing systemd units ..."
cp "$SRC_SERVICE" "$DEST_SERVICE"
cp "$SRC_CERT_RENEW_SVC" "$DEST_CERT_RENEW_SVC"
cp "$SRC_CERT_RENEW_TIMER" "$DEST_CERT_RENEW_TIMER"
systemctl daemon-reload
echo "      OK"

# Enable and start ipr-provision
echo "[5/6] Enabling and starting ipr-provision.service ..."
systemctl enable ipr-provision.service
systemctl restart ipr-provision.service
echo "      OK"

# Enable cert renewal timer
echo "[6/6] Enabling ipr-cert-renew.timer (daily auto-renewal check) ..."
systemctl enable ipr-cert-renew.timer
systemctl start ipr-cert-renew.timer
echo "      OK"

echo ""
echo "=== [install_provision_service] Done ==="
echo ""
echo "Status:"
systemctl --no-pager -l status ipr-provision.service || true
echo ""
echo "Hotspot credentials (once running): cat /etc/ipr-hotspot.secret"
echo "CA certificate for browser trust:   https://10.42.0.1/setup/ca.crt"
echo "Certificate auto-renewal:           daily check via ipr-cert-renew.timer"
