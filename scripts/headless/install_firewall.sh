#!/usr/bin/env bash
#
# install_firewall.sh — network exposure control (production/development mode)
#
# Installs, idempotently:
#   /usr/local/sbin/ipr-firewall.sh            <- ipr_fw_ctl.sh
#   /usr/local/bin/ipr_mode_ctl.sh             <- ipr_mode_ctl.sh (+ sudoers for the app user)
#   /etc/systemd/system/ipr-firewall.service   <- ipr-firewall.service (boot, before networking)
#   /etc/NetworkManager/dispatcher.d/90-ipr-firewall
#   /var/lib/ipr-keyboard/mode                 <- created as "development" if missing
#   nftables package                           <- apt, if missing
#
# The mode file is seeded as DEVELOPMENT on purpose: this script runs during
# provisioning over SSH, and production mode would cut that session.  Put the
# device into production mode as the last commissioning step:
#     sudo ipr_mode_ctl.sh production        (or hold the magnet 10 s)
#
# Usage:  sudo ./scripts/headless/install_firewall.sh
# Called by provision/04_enable_services.sh and deploy_full_update.sh.
#
# category: Headless
# purpose: Install nftables-based port policy, mode switch and its triggers
# sudo: yes

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()   { echo -e "${GREEN}[firewall]${NC} $*"; }
warn()  { echo -e "${YELLOW}[firewall]${NC} $*"; }
error() { echo -e "${RED}[firewall ERROR]${NC} $*" >&2; }

if [[ $EUID -ne 0 ]]; then
  error "Run as root: sudo bash $0"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f /opt/ipr_common.env ]]; then
  # shellcheck disable=SC1091
  source /opt/ipr_common.env
fi
APP_USER="${APP_USER:-$(systemctl show -p User ipr_keyboard.service 2>/dev/null | cut -d= -f2 || true)}"
APP_USER="${APP_USER:-${SUDO_USER:-}}"
if [[ -z "${APP_USER}" ]]; then
  error "Could not determine APP_USER. Set it in /opt/ipr_common.env or run: sudo APP_USER=<user> bash $0"
  exit 1
fi

# ---------------------------------------------------------------------------
# nftables
# ---------------------------------------------------------------------------
if ! command -v nft >/dev/null 2>&1; then
  log "Installing nftables ..."
  if ! DEBIAN_FRONTEND=noninteractive apt-get install -y nftables; then
    error "nftables could not be installed — the network stays unfiltered. Install it and re-run."
    exit 1
  fi
fi
# We manage our own table; Debian's nftables.service would load /etc/nftables.conf
# on top of it.  Leave that unit alone but make sure it does not flush ours.
if systemctl is-enabled --quiet nftables.service 2>/dev/null; then
  warn "nftables.service is enabled; it loads /etc/nftables.conf (usually empty). Keeping it."
fi

# ---------------------------------------------------------------------------
# Scripts, unit, dispatcher
# ---------------------------------------------------------------------------
install -m 0755 -o root -g root "${SCRIPT_DIR}/ipr_fw_ctl.sh"   /usr/local/sbin/ipr-firewall.sh
install -m 0755 -o root -g root "${SCRIPT_DIR}/ipr_mode_ctl.sh" /usr/local/bin/ipr_mode_ctl.sh
install -m 0644 -o root -g root "${SCRIPT_DIR}/ipr-firewall.service" /etc/systemd/system/ipr-firewall.service
install -d -m 0755 /etc/NetworkManager/dispatcher.d
install -m 0755 -o root -g root "${SCRIPT_DIR}/90-ipr-firewall" /etc/NetworkManager/dispatcher.d/90-ipr-firewall
log "Installed ipr-firewall.sh, ipr_mode_ctl.sh, ipr-firewall.service, dispatcher hook"

# ---------------------------------------------------------------------------
# mDNS: IPv4 only.  avahi also advertised an AAAA record (SLAAC leaks an IPv6
# address in even with ipv6.method=ignore); Windows then resolves
# <host>.local to that IPv6 address only, and the dashboard listens on IPv4,
# so https://<host>.local/ "did not work" while the IP did.
# ---------------------------------------------------------------------------
AVAHI_CONF=/etc/avahi/avahi-daemon.conf
if [[ -f "${AVAHI_CONF}" ]]; then
  sed -i -E 's/^#?use-ipv6=.*/use-ipv6=no/; s/^#?publish-aaaa-on-ipv4=.*/publish-aaaa-on-ipv4=no/' "${AVAHI_CONF}"
  grep -q '^use-ipv6=no' "${AVAHI_CONF}" || sed -i '/^\[server\]/a use-ipv6=no' "${AVAHI_CONF}"
  grep -q '^publish-aaaa-on-ipv4=no' "${AVAHI_CONF}" || sed -i '/^\[publish\]/a publish-aaaa-on-ipv4=no' "${AVAHI_CONF}"
  systemctl restart avahi-daemon 2>/dev/null || true
  log "avahi: IPv4 only (<host>.local resolves to the IPv4 address the dashboard listens on)"
fi

# ---------------------------------------------------------------------------
# Mode file (development on first install — see header)
# ---------------------------------------------------------------------------
MODE_FILE=/var/lib/ipr-keyboard/mode
mkdir -p "$(dirname "${MODE_FILE}")"
if [[ ! -f "${MODE_FILE}" ]]; then
  echo development > "${MODE_FILE}"
  chmod 0644 "${MODE_FILE}"
  warn "Mode file created as DEVELOPMENT (ssh + dashboard reachable)."
  warn "Switch to production when commissioning is done:  sudo ipr_mode_ctl.sh production"
else
  log "Mode file present: $(cat "${MODE_FILE}")"
fi

# ---------------------------------------------------------------------------
# sudoers: the magnet (gpio_monitor) toggles the mode through the helper
# ---------------------------------------------------------------------------
SUDOERS_DST="/etc/sudoers.d/${APP_USER}-ipr-mode"
SUDOERS_TMP="$(mktemp)"
trap 'rm -f "${SUDOERS_TMP}"' EXIT
cat > "${SUDOERS_TMP}" <<EOF
# Managed by install_firewall.sh — do not edit by hand.
${APP_USER} ALL=(root) NOPASSWD: /usr/local/bin/ipr_mode_ctl.sh
EOF
if visudo -cf "${SUDOERS_TMP}" >/dev/null; then
  install -m 0440 -o root -g root "${SUDOERS_TMP}" "${SUDOERS_DST}"
  log "Installed sudoers entry ${SUDOERS_DST}"
else
  error "sudoers validation failed — not installed"
  exit 1
fi

# ---------------------------------------------------------------------------
# Activate
# ---------------------------------------------------------------------------
systemctl daemon-reload
systemctl enable ipr-firewall.service >/dev/null 2>&1 || true
/usr/local/sbin/ipr-firewall.sh apply
log "Firewall applied.  Current state:"
/usr/local/sbin/ipr-firewall.sh status | sed 's/^/  /'
