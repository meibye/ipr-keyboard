#!/usr/bin/env bash
#
# install_network_helper.sh
#
# One-shot setup: installs the dhcpcd write helper and the sudoers entry
# that allow the ipr_keyboard service to apply network settings without
# a full reboot.
#
# Run as root on the Pi:
#   sudo bash scripts/service/install_network_helper.sh
#
# category: Service
# purpose: Install dhcpcd write helper and sudoers entry for the app user
# sudo: yes

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[network-helper]${NC} $*"; }
warn() { echo -e "${YELLOW}[network-helper]${NC} $*"; }
error(){ echo -e "${RED}[network-helper ERROR]${NC} $*"; }

if [[ $EUID -ne 0 ]]; then
  error "This script must be run as root (sudo bash $0)"
  exit 1
fi

# ---------------------------------------------------------------------------
# Resolve APP_USER
# ---------------------------------------------------------------------------

if [[ -f /opt/ipr_common.env ]]; then
  # shellcheck disable=SC1091
  source /opt/ipr_common.env
fi

if [[ -z "${APP_USER:-}" ]]; then
  # Fall back to the user running the ipr_keyboard service
  APP_USER="$(systemctl show -p User ipr_keyboard.service 2>/dev/null | cut -d= -f2 || true)"
fi

if [[ -z "${APP_USER:-}" ]]; then
  error "Could not determine APP_USER. Set it in /opt/ipr_common.env or pass it:"
  error "  sudo APP_USER=meibye bash $0"
  exit 1
fi

log "App user: $APP_USER"

# ---------------------------------------------------------------------------
# Locate the helper script
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HELPER_SRC="$SCRIPT_DIR/ipr_write_dhcpcd.sh"

if [[ ! -f "$HELPER_SRC" ]]; then
  error "Helper source not found: $HELPER_SRC"
  exit 1
fi

HELPER_DST="/usr/local/bin/ipr_write_dhcpcd.sh"
SUDOERS_DST="/etc/sudoers.d/${APP_USER}-ipr"

# ---------------------------------------------------------------------------
# Install helper
# ---------------------------------------------------------------------------

install -m 0755 -o root -g root "$HELPER_SRC" "$HELPER_DST"
log "Installed $HELPER_DST"

# ---------------------------------------------------------------------------
# Install sudoers entry
# ---------------------------------------------------------------------------

SUDOERS_TMP="$(mktemp)"
trap 'rm -f "$SUDOERS_TMP"' EXIT

cat > "$SUDOERS_TMP" <<SUDOERSEOF
# Managed by install_network_helper.sh — do not edit by hand.
${APP_USER} ALL=(root) NOPASSWD: ${HELPER_DST}, /usr/bin/systemctl restart dhcpcd
SUDOERSEOF

if visudo -cf "$SUDOERS_TMP"; then
  install -m 0440 -o root -g root "$SUDOERS_TMP" "$SUDOERS_DST"
  log "Installed sudoers entry: $SUDOERS_DST"
else
  error "sudoers validation failed — aborting."
  exit 1
fi

# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

log "Smoke-testing sudo grant..."
if su -s /bin/sh "$APP_USER" -c "echo test | sudo $HELPER_DST" > /dev/null 2>&1; then
  log "OK — $APP_USER can write /etc/dhcpcd.conf via the helper."
else
  warn "Smoke test failed. Check that $APP_USER exists and the sudoers entry is correct."
fi

log "Done. Restart the ipr_keyboard service to pick up any code changes:"
log "  sudo systemctl restart ipr_keyboard.service"
