#!/usr/bin/env bash
#
# OS baseline configuration for ipr-keyboard
# Installs system packages, configures Bluetooth, and records baseline versions
#
# Purpose:
#   - Runs existing sys_install_packages.sh and ble_configure_system.sh
#   - Records OS/package versions for verification
#   - Ensures both devices have identical OS baseline
#
# Usage:
#   sudo ./provision/01_os_base.sh
#
# Prerequisites:
#   - 00_bootstrap.sh completed successfully
#
# category: Provisioning
# purpose: Configure OS baseline and Bluetooth
# sudo: yes

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[os_base]${NC} $*"; }
warn() { echo -e "${YELLOW}[os_base]${NC} $*"; }
error() { echo -e "${RED}[os_base ERROR]${NC} $*"; }

if [[ $EUID -ne 0 ]]; then
  error "This script must be run as root"
  exit 1
fi

# Load environment
ENV_FILE="/opt/ipr_common.env"
if [[ ! -f "$ENV_FILE" ]]; then
  error "Environment file not found: $ENV_FILE"
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

cd "$REPO_DIR"

# Verify we're in the right place
if [[ ! -f "scripts/sys_install_packages.sh" ]]; then
  error "Cannot find scripts/sys_install_packages.sh - are we in the repo?"
  exit 1
fi

log "Running full system upgrade..."
apt-get update
apt-get -y full-upgrade

log "Running sys_install_packages.sh..."
bash scripts/sys_install_packages.sh

log "Running ble_configure_system.sh..."
bash scripts/ble_configure_system.sh

log "Ensuring Bluetooth is not soft-blocked..."
rfkill unblock bluetooth || true

log "Enabling key services..."
systemctl start dbus
systemctl enable --now bluetooth

log "Recording baseline versions..."
mkdir -p /opt/ipr_state
{
  echo "====================================="
  echo "IPR Keyboard - OS Baseline"
  echo "====================================="
  echo ""
  echo "=== DATE ==="
  date -Is
  echo ""
  echo "=== DEVICE ==="
  echo "Hostname: $(hostname)"
  echo "Device Type: $DEVICE_TYPE"
  echo ""
  echo "=== OS ==="
  cat /etc/os-release
  echo ""
  echo "=== KERNEL ==="
  uname -a
  echo ""
  echo "=== CPU ==="
  cat /proc/cpuinfo | grep -E "(Model|model name|Hardware|Revision)" | head -n 4
  echo ""
  echo "=== BlueZ ==="
  bluetoothd -v || echo "BlueZ version check failed"
  echo ""
  echo "=== Python ==="
  python3 --version
  echo ""
  echo "=== UV ==="
  uv --version || echo "uv not found"
  echo ""
  echo "=== Network Manager ==="
  nmcli --version || echo "NetworkManager not installed"
  echo ""
  echo "=== Manually installed packages ==="
  apt-mark showmanual | sort
  echo ""
} > /opt/ipr_state/baseline_versions.txt

log "Baseline versions saved to /opt/ipr_state/baseline_versions.txt"

# Update state
cat >> /opt/ipr_state/bootstrap_info.txt <<EOF

OS Base completed: $(date -Is)
System packages installed: yes
BlueZ configured: yes
EOF

log "OS baseline configuration complete!"
echo ""
warn "IMPORTANT: Reboot recommended after Bluetooth configuration"
log "Next steps:"
log "  1. sudo reboot"
log "  2. After reboot: sudo $REPO_DIR/provision/02_device_identity.sh"
echo ""
