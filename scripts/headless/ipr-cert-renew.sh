#!/usr/bin/env bash
#
# ipr-cert-renew.sh
#
# Renew the IPR Keyboard server TLS certificate.
# Without arguments: only renews if the cert expires within 30 days.
# With --force: always renews regardless of expiry.
#
# After renewal, restarts ipr_keyboard.service to load the new certificate.
#
# Usage:
#   sudo /usr/local/sbin/ipr-cert-renew.sh           # auto (timer)
#   sudo /usr/local/sbin/ipr-cert-renew.sh --force   # on-demand (web UI)
#
# Installation:
#   sudo cp scripts/headless/ipr-cert-renew.sh /usr/local/sbin/
#   sudo chmod +x /usr/local/sbin/ipr-cert-renew.sh
#
# category: Headless
# purpose: TLS certificate auto-renewal for the management web interface
# sudo: yes

set -euo pipefail

CERT_FILE="/etc/ipr-ssl/server.crt"
CERT_SCRIPT="/usr/local/sbin/ipr-cert-gen.sh"
RENEW_DAYS=30  # renew when fewer than this many days remain
FORCE=false

for arg in "$@"; do
    [[ "$arg" == "--force" ]] && FORCE=true
done

log() { echo "[ipr-cert-renew] $*"; }

if [[ $EUID -ne 0 ]]; then
    log "ERROR: Must be run as root."
    exit 1
fi

if [[ ! -f "$CERT_FILE" ]]; then
    log "Server certificate not found at $CERT_FILE — run gen_ipr_ssl_cert.sh first."
    exit 1
fi

# Check whether renewal is needed (skip check when --force)
if [[ "$FORCE" == false ]]; then
    # openssl checkend N returns 0 if cert is valid for at least N more seconds
    SECONDS_THRESHOLD=$(( RENEW_DAYS * 86400 ))
    if openssl x509 -in "$CERT_FILE" -noout -checkend "$SECONDS_THRESHOLD" 2>/dev/null; then
        log "Certificate is valid for more than ${RENEW_DAYS} days — no renewal needed."
        exit 0
    fi
    log "Certificate expires within ${RENEW_DAYS} days — renewing."
fi

log "Renewing server certificate ..."
bash "$CERT_SCRIPT" --renew

log "Restarting ipr_keyboard.service to load new certificate ..."
systemctl restart ipr_keyboard.service

EXPIRY=$(openssl x509 -in "$CERT_FILE" -noout -enddate 2>/dev/null | cut -d= -f2 || echo "unknown")
log "Done. New certificate valid until: $EXPIRY"
