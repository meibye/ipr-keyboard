#!/usr/bin/env bash
#
# install_observability.sh — make failures visible on an unsupervised device
#
# Installs, idempotently:
#   /etc/systemd/journald.conf.d/ipr.conf      persistent journal, capped (64 MB,
#                                              1 month) so it survives reboots
#                                              without wearing the SD card
#   /etc/systemd/system/ipr-failure@.service   OnFailure= handler: appends one
#                                              line per failed unit to
#                                              /var/lib/ipr-keyboard/incidents.log
#   drop-ins for ipr_keyboard, bt_hid_ble, bt_hid_agent_unified,
#   irispen-mount and ipr-provision                OnFailure=ipr-failure@%n.service
#
# Together with the status LED (red solid when a core service is down) and
# the dashboard's system state, this is what an administrator can check
# after the fact:  cat /var/lib/ipr-keyboard/incidents.log
#
# Usage:  sudo ./scripts/headless/install_observability.sh
# Called by provision/04_enable_services.sh and deploy_full_update.sh.
#
# category: Headless
# purpose: Persistent journal and OnFailure incident log for core services
# sudo: yes

set -euo pipefail

GREEN='\033[0;32m'; NC='\033[0m'
log() { echo -e "${GREEN}[observability]${NC} $*"; }

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi

if [[ -f /opt/ipr_common.env ]]; then
  # shellcheck disable=SC1091
  source /opt/ipr_common.env
fi
APP_USER="${APP_USER:-$(systemctl show -p User ipr_keyboard.service 2>/dev/null | cut -d= -f2 || true)}"
APP_USER="${APP_USER:-${SUDO_USER:-root}}"

# ---------------------------------------------------------------------------
# 1. Persistent, capped journal
# ---------------------------------------------------------------------------
mkdir -p /etc/systemd/journald.conf.d /var/log/journal
cat > /etc/systemd/journald.conf.d/ipr.conf <<'EOF'
# Managed by scripts/headless/install_observability.sh
# Keep logs across reboots so a failure on an unsupervised device can still
# be read days later; cap size and age to protect the SD card.
[Journal]
Storage=persistent
SystemMaxUse=64M
SystemMaxFileSize=8M
MaxRetentionSec=1month
Compress=yes
EOF
systemd-tmpfiles --create --prefix /var/log/journal >/dev/null 2>&1 || true
systemctl restart systemd-journald
log "Journal: persistent, max 64 MB / 1 month"

# ---------------------------------------------------------------------------
# 2. Incident log handler
# ---------------------------------------------------------------------------
INCIDENTS=/var/lib/ipr-keyboard/incidents.log
mkdir -p "$(dirname "${INCIDENTS}")"
touch "${INCIDENTS}"
chown root:"$(id -gn "${APP_USER}")" "${INCIDENTS}"
chmod 0664 "${INCIDENTS}"

cat > /etc/systemd/system/ipr-failure@.service <<'EOF'
# Managed by scripts/headless/install_observability.sh
# Started by OnFailure= of the core units with %i = the failed unit's name.
[Unit]
Description=IPR Keyboard — record failure of %i

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'printf "%%s  %%s failed (result=%%s)\n" "$(date -Is)" "%i" "$(systemctl show -p Result --value %i)" >> /var/lib/ipr-keyboard/incidents.log'
EOF

for unit in ipr_keyboard.service bt_hid_ble.service bt_hid_agent_unified.service \
            irispen-mount.service ipr-provision.service; do
  d="/etc/systemd/system/${unit}.d"
  mkdir -p "${d}"
  cat > "${d}/20-onfailure.conf" <<'EOF'
# Managed by scripts/headless/install_observability.sh
[Unit]
OnFailure=ipr-failure@%n.service
EOF
done
systemctl daemon-reload
log "OnFailure handler installed; incidents go to ${INCIDENTS}"
log "Read it with:  cat ${INCIDENTS}"
