#!/usr/bin/env bash
#
# install_irispen_mount.sh — mount the IrisPen automatically when plugged in
#
# The pen is an MTP device (USB 0e8d:2008), not a block device: its files
# only become visible after `jmtpfs` mounts it at /mnt/irispen.  Until now
# that was a manual step (scripts/usb_mount_mtp.sh), which an unsupervised
# device can never perform.  This installs:
#
#   /etc/udev/rules.d/69-irispen-mtp.rules   permissions + systemd device unit
#                                            (SYSTEMD_ALIAS=/dev/irispen) that
#                                            wants irispen-mount.service
#   /etc/systemd/system/irispen-mount.service  jmtpfs in the foreground as the
#                                            app user; stopped and unmounted
#                                            by BindsTo when the pen is unplugged
#   /mnt/irispen                             mountpoint owned by the app user
#
# Usage:  sudo ./scripts/headless/install_irispen_mount.sh
# Called by provision/04_enable_services.sh and deploy_full_update.sh.
# Safe to re-run.  Plug the pen out and in (or `udevadm trigger`) to test.
#
# category: Headless
# purpose: udev + systemd automount of the IrisPen MTP filesystem
# sudo: yes

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()   { echo -e "${GREEN}[irispen-mount]${NC} $*"; }
warn()  { echo -e "${YELLOW}[irispen-mount]${NC} $*"; }
error() { echo -e "${RED}[irispen-mount ERROR]${NC} $*" >&2; }

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
APP_GROUP="$(id -gn "${APP_USER}")"
MOUNTPOINT=/mnt/irispen

# ---------------------------------------------------------------------------
# Packages and groups
# ---------------------------------------------------------------------------
if ! command -v jmtpfs >/dev/null 2>&1; then
  log "Installing jmtpfs ..."
  DEBIAN_FRONTEND=noninteractive apt-get install -y jmtpfs || {
    error "jmtpfs could not be installed — the pen cannot be mounted. Install it and re-run."
    exit 1
  }
fi
usermod -aG plugdev "${APP_USER}"

# ---------------------------------------------------------------------------
# Mountpoint
# ---------------------------------------------------------------------------
# A live FUSE mount is invisible to root (EACCES even on stat), so stop the
# service first; it is started again below once the new unit is in place.
systemctl stop irispen-mount.service 2>/dev/null || true
if grep -q " ${MOUNTPOINT} " /proc/mounts; then
  fusermount -u -z "${MOUNTPOINT}" 2>/dev/null || umount -l "${MOUNTPOINT}" 2>/dev/null || true
fi
mkdir -p "${MOUNTPOINT}"
chown "${APP_USER}:${APP_GROUP}" "${MOUNTPOINT}"
chmod 0775 "${MOUNTPOINT}"

# ---------------------------------------------------------------------------
# udev rule: permissions for the app user + a device unit for systemd
# ---------------------------------------------------------------------------
cat > /etc/udev/rules.d/69-irispen-mtp.rules <<'EOF'
# IrisPen (MTP).  Managed by scripts/headless/install_irispen_mount.sh.
# Readable by plugdev (the app user), and exposed to systemd as
# dev-irispen.device so irispen-mount.service starts on plug-in and stops on
# unplug (BindsTo=).
SUBSYSTEM=="usb", ATTR{idVendor}=="0e8d", ATTR{idProduct}=="2008", MODE="0660", GROUP="plugdev", TAG+="uaccess", TAG+="systemd", ENV{SYSTEMD_ALIAS}="/dev/irispen", ENV{SYSTEMD_WANTS}="irispen-mount.service"
EOF
log "Installed /etc/udev/rules.d/69-irispen-mtp.rules"

# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
sed "s/__APP_USER__/${APP_USER}/g" "${SCRIPT_DIR}/irispen-mount.service" \
  > /etc/systemd/system/irispen-mount.service
chmod 0644 /etc/systemd/system/irispen-mount.service
log "Installed irispen-mount.service (runs jmtpfs as ${APP_USER})"

systemctl daemon-reload
udevadm control --reload-rules
udevadm trigger --subsystem-match=usb --action=add
sleep 4
if systemctl is-active --quiet irispen-mount.service; then
  log "Pen detected and mounted at ${MOUNTPOINT} (visible to ${APP_USER} only):"
  runuser -u "${APP_USER}" -- ls "${MOUNTPOINT}" 2>/dev/null | sed 's/^/  /' || true
else
  log "No pen connected right now — it will be mounted automatically when plugged in."
fi
