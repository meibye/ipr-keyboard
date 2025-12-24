#!/usr/bin/env bash
#
# USB OTG (USB Gadget Ethernet) setup for Pi Zero 2 W
# Enables USB OTG mode for direct laptop connection and SSH access
#
# Purpose:
#   - Enables dwc2 USB OTG driver
#   - Configures g_ether (USB Ethernet gadget)
#   - Sets up static IP for usb0 interface (192.168.7.1)
#   - Provides backdoor access when Wi-Fi is unknown
#
# Usage on laptop after USB connection:
#   ssh user@192.168.7.1
#
# Installation:
#   sudo ./scripts/headless/usb_otg_setup.sh
#
# Requirements:
#   - Raspberry Pi Zero 2 W (or other Pi with USB OTG support)
#   - USB connection must be to the data port (not power-only)
#
# category: Headless
# purpose: Enable USB OTG for direct laptop SSH access
# sudo: yes

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[usb_otg]${NC} $*"; }
warn() { echo -e "${YELLOW}[usb_otg]${NC} $*"; }
error() { echo -e "${RED}[usb_otg ERROR]${NC} $*"; }

if [[ $EUID -ne 0 ]]; then
  error "This script must be run as root"
  exit 1
fi

# Detect boot config and cmdline file locations
if [[ -f /boot/firmware/config.txt ]]; then
  BOOT_CONFIG="/boot/firmware/config.txt"
  BOOT_CMDLINE="/boot/firmware/cmdline.txt"
elif [[ -f /boot/config.txt ]]; then
  BOOT_CONFIG="/boot/config.txt"
  BOOT_CMDLINE="/boot/cmdline.txt"
else
  error "Cannot find boot configuration files"
  exit 1
fi

log "Using boot config: $BOOT_CONFIG"
log "Using cmdline: $BOOT_CMDLINE"

# Enable dwc2 overlay in config.txt
log "Configuring USB OTG in $BOOT_CONFIG..."
if grep -q "^dtoverlay=dwc2" "$BOOT_CONFIG"; then
  log "  dtoverlay=dwc2 already present"
else
  echo "dtoverlay=dwc2" >> "$BOOT_CONFIG"
  log "  Added dtoverlay=dwc2"
fi

# Add g_ether module to cmdline.txt
log "Configuring kernel modules in $BOOT_CMDLINE..."
if grep -q "modules-load=dwc2,g_ether" "$BOOT_CMDLINE"; then
  log "  modules-load already configured"
else
  # Append to the end of the line (important: don't add newline!)
  sed -i '$ s/$/ modules-load=dwc2,g_ether/' "$BOOT_CMDLINE"
  log "  Added modules-load=dwc2,g_ether"
fi

# Configure static IP for usb0 interface using NetworkManager
log "Configuring NetworkManager for usb0 interface..."

if nmcli con show ipr-usb0 &>/dev/null; then
  log "  NetworkManager connection 'ipr-usb0' already exists"
else
  log "  Creating NetworkManager connection for usb0..."
  nmcli con add type ethernet ifname usb0 con-name ipr-usb0 \
    ipv4.method manual \
    ipv4.addresses 192.168.7.1/24 \
    ipv6.method ignore
  log "  Created connection 'ipr-usb0'"
fi

# Enable the connection
log "Enabling usb0 connection..."
nmcli con up ipr-usb0 || warn "Connection not yet active (will activate after reboot)"

log "USB OTG configuration complete!"
echo ""
warn "IMPORTANT: Reboot required for USB OTG to take effect"
echo ""
log "After reboot:"
log "  1. Connect Pi Zero's USB data port to laptop"
log "  2. Wait for USB Ethernet to be detected"
log "  3. SSH to: ssh user@192.168.7.1"
echo ""
log "Then provision Wi-Fi:"
log "  nmcli dev wifi rescan"
log "  nmcli dev wifi list"
log "  nmcli dev wifi connect \"SSID\" password \"PASSWORD\""
echo ""
