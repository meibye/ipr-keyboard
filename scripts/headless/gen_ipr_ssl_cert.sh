#!/usr/bin/env bash
#
# gen_ipr_ssl_cert.sh
#
# Generate a private CA and a CA-signed server certificate for the IPR Keyboard
# web interface.  Both the hotspot endpoint (10.42.0.1) and the mDNS hostname
# (<hostname>.local) are covered by the server cert's SAN list.
#
# After running this script, users can eliminate browser certificate warnings by
# downloading and installing the CA cert once:
#   https://10.42.0.1/setup/ca.crt
#
# Usage:
#   sudo ./scripts/headless/gen_ipr_ssl_cert.sh [--force] [--hostname NAME] [--user USER]
#
# Options:
#   --force           Regenerate all certificate files even if they already exist.
#   --hostname NAME   Override the device hostname used in the SAN list.
#                     Defaults to $(hostname -s).
#   --user USER       App user who needs read access to server.key.
#                     Defaults to $IPR_USER or 'meibye'.
#
# Outputs (under /etc/ipr-ssl/):
#   ca.key        CA private key        (root:root 0600)
#   ca.crt        CA certificate        (root:root 0644)
#   server.key    Server private key    (root:ipr-ssl 0640)
#   server.crt    Server certificate    (root:root 0644)
#
# category: Headless
# purpose: Generate private CA + server cert for HTTPS web interface
# sudo: yes

set -euo pipefail

SSL_DIR="/etc/ipr-ssl"
CA_KEY="$SSL_DIR/ca.key"
CA_CRT="$SSL_DIR/ca.crt"
SRV_KEY="$SSL_DIR/server.key"
SRV_CRT="$SSL_DIR/server.crt"
CSR_TMP="/tmp/ipr-server.csr"
EXT_TMP="/tmp/ipr-server.ext"

FORCE=false
DEVICE_HOSTNAME=""
APP_USER="${IPR_USER:-meibye}"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)    FORCE=true; shift ;;
        --hostname) DEVICE_HOSTNAME="$2"; shift 2 ;;
        --user)     APP_USER="$2"; shift 2 ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
    echo "[gen_ipr_ssl_cert] ERROR: Must be run as root."
    exit 1
fi

if ! command -v openssl &>/dev/null; then
    echo "[gen_ipr_ssl_cert] ERROR: openssl is not installed."
    exit 1
fi

DEVICE_HOSTNAME="${DEVICE_HOSTNAME:-$(hostname -s)}"
log() { echo "[gen_ipr_ssl_cert] $*"; }

# ---------------------------------------------------------------------------
# Directory and group setup
# ---------------------------------------------------------------------------
log "Setting up $SSL_DIR ..."
groupadd -f ipr-ssl
if id "$APP_USER" &>/dev/null; then
    usermod -aG ipr-ssl "$APP_USER"
    log "Added $APP_USER to group ipr-ssl."
else
    log "WARNING: user '$APP_USER' not found — skipping group membership."
fi

mkdir -p "$SSL_DIR"
chown root:ipr-ssl "$SSL_DIR"
# 0750: root can read/write/list; ipr-ssl group can traverse and read files
chmod 0750 "$SSL_DIR"

# ---------------------------------------------------------------------------
# Skip if files exist and --force not set
# ---------------------------------------------------------------------------
if [[ "$FORCE" == false ]] && \
   [[ -f "$CA_KEY" && -f "$CA_CRT" && -f "$SRV_KEY" && -f "$SRV_CRT" ]]; then
    log "Certificate files already exist. Use --force to regenerate."
    log "  CA cert:     $CA_CRT"
    log "  Server cert: $SRV_CRT"
    exit 0
fi

# ---------------------------------------------------------------------------
# Step 1: Root CA
# ---------------------------------------------------------------------------
log "Generating root CA key and certificate ..."
openssl genrsa -out "$CA_KEY" 2048 2>/dev/null
chmod 0600 "$CA_KEY"

openssl req -x509 -new -nodes \
    -key "$CA_KEY" \
    -sha256 -days 3650 \
    -out "$CA_CRT" \
    -subj "/CN=IPR Keyboard Local CA/O=IPR Keyboard" \
    2>/dev/null
chmod 0644 "$CA_CRT"
log "  CA cert: $CA_CRT"

# ---------------------------------------------------------------------------
# Step 2: Server key and CSR
# ---------------------------------------------------------------------------
log "Generating server key and certificate request ..."
openssl genrsa -out "$SRV_KEY" 2048 2>/dev/null

openssl req -new \
    -key "$SRV_KEY" \
    -subj "/CN=IPR Keyboard/O=IPR Keyboard" \
    -out "$CSR_TMP" \
    2>/dev/null

# ---------------------------------------------------------------------------
# Step 3: SAN extension file
# ---------------------------------------------------------------------------
cat > "$EXT_TMP" <<EXTEOF
[SAN]
subjectAltName=IP:10.42.0.1,IP:127.0.0.1,DNS:${DEVICE_HOSTNAME}.local,DNS:localhost
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
EXTEOF

# ---------------------------------------------------------------------------
# Step 4: Sign server cert with CA
# ---------------------------------------------------------------------------
log "Signing server certificate (hostname: ${DEVICE_HOSTNAME}.local) ..."
openssl x509 -req \
    -in "$CSR_TMP" \
    -CA "$CA_CRT" \
    -CAkey "$CA_KEY" \
    -CAcreateserial \
    -out "$SRV_CRT" \
    -days 3650 \
    -sha256 \
    -extensions SAN \
    -extfile "$EXT_TMP" \
    2>/dev/null

# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------
chown root:ipr-ssl "$SRV_KEY"
chmod 0640 "$SRV_KEY"
chmod 0644 "$SRV_CRT"

# Clean up temp files
rm -f "$CSR_TMP" "$EXT_TMP"

log ""
log "Certificates generated successfully."
log "  CA cert:     $CA_CRT   (distribute to clients for trusted HTTPS)"
log "  Server cert: $SRV_CRT"
log "  SANs:        IP:10.42.0.1, IP:127.0.0.1, DNS:${DEVICE_HOSTNAME}.local"
log ""
log "Users can download the CA cert at: https://10.42.0.1/setup/ca.crt"
log "Install it in the OS/browser trust store to eliminate certificate warnings."
