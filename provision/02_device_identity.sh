#!/usr/bin/env bash
#
# Device identity configuration for ipr-keyboard
# Sets hostname, Bluetooth device name, and optional Wi-Fi interface names
#
# Purpose:
#   - Sets device-specific hostname (ipr-dev-pi4 or ipr-target-zero2)
#   - Configures Bluetooth device name
#   - Optionally configures Wi-Fi interface names for dual-band Pi 4
#
# Usage:
#   sudo ./provision/02_device_identity.sh
#
# Prerequisites:
#   - 01_os_base.sh completed and system rebooted
#
# category: Provisioning
# purpose: Configure device identity (hostname, BT name)
# sudo: yes

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[device_identity]${NC} $*"; }
warn() { echo -e "${YELLOW}[device_identity]${NC} $*"; }
error() { echo -e "${RED}[device_identity ERROR]${NC} $*"; }

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

log "Configuring device identity..."
log "  Device Type: $DEVICE_TYPE"
log "  Hostname: $HOSTNAME"
log "  BT Device Name: $BT_DEVICE_NAME"

# Set hostname
CURRENT_HOSTNAME=$(hostname)
if [[ "$CURRENT_HOSTNAME" != "$HOSTNAME" ]]; then
  log "Setting hostname from '$CURRENT_HOSTNAME' to '$HOSTNAME'..."
  hostnamectl set-hostname "$HOSTNAME"
  
  # Update /etc/hosts
  log "Updating /etc/hosts..."
  sed -i "s/127.0.1.1.*/127.0.1.1\t$HOSTNAME/" /etc/hosts
  
  log "Hostname set to: $(hostname)"
else
  log "Hostname already set correctly: $HOSTNAME"
fi


# Set PRETTY_HOSTNAME in /etc/machine-info for Bluetooth name override
MACHINE_INFO="/etc/machine-info"
if grep -q '^PRETTY_HOSTNAME=' "$MACHINE_INFO"; then
  sed -i "s|^PRETTY_HOSTNAME=.*|PRETTY_HOSTNAME=\"$BT_DEVICE_NAME\"|" "$MACHINE_INFO"
  log "Updated PRETTY_HOSTNAME in $MACHINE_INFO"
else
  echo "PRETTY_HOSTNAME=\"$BT_DEVICE_NAME\"" >> "$MACHINE_INFO"
  log "Added PRETTY_HOSTNAME to $MACHINE_INFO"
fi

# Restart Bluetooth to apply name change
log "Restarting Bluetooth service..."
systemctl restart bluetooth

# Verify Bluetooth name
sleep 2
BT_NAME_CHECK=$(bluetoothctl show | grep "Name:" | cut -d: -f2 | xargs || echo "unknown")
if [[ "$BT_NAME_CHECK" == "$BT_DEVICE_NAME" ]]; then
  log "Bluetooth name verified: $BT_NAME_CHECK"
else
  warn "Bluetooth name may not have updated correctly"
  warn "  Expected: $BT_DEVICE_NAME"
  warn "  Got: $BT_NAME_CHECK"
fi

# For RPi 4 with dual-band Wi-Fi, optionally configure predictable interface names
# This is advanced and optional - leaving as a placeholder for future enhancement
if [[ "$DEVICE_TYPE" == "dev" ]]; then
  log "Device is RPi 4 (dev) - Wi-Fi interface management available if needed"
  # Could implement predictable Wi-Fi interface naming here
fi

# Update state
cat >> /opt/ipr_state/bootstrap_info.txt <<EOF

Device Identity configured: $(date -Is)
Hostname: $HOSTNAME
Bluetooth Name: $BT_DEVICE_NAME
EOF

log "Device identity configuration complete!"
echo ""
log "Current identity:"
log "  Hostname: $(hostname)"
log "  BT Name: $BT_NAME_CHECK"
log "  DNS names (once configured):"
if [[ "$DEVICE_TYPE" == "dev" ]]; then
  log "    Wired: ipr-dev-pi4.local"
  log "    Wi-Fi: ipr-dev-pi4-wifi.local (if configured)"
else
  log "    Wi-Fi: ipr-target-zero2.local"
fi
echo ""
warn "Reboot recommended for hostname changes to fully take effect"
log "Next steps:"
log "  1. sudo reboot"
log "  2. After reboot: sudo $REPO_DIR/provision/03_app_install.sh"
echo ""
