#!/usr/bin/env bash
#
# IrisPen USB Mount Setup Script
#
# Purpose:
#   Creates and configures a persistent mount point for the IrisPen USB drive.
#   Adds the mount entry to /etc/fstab using the device's UUID for reliability.
#
# Usage:
#   sudo ./scripts/06_setup_irispen_mount.sh /dev/sda1
#   sudo ./scripts/06_setup_irispen_mount.sh /dev/sda1 /media/irispen
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - IrisPen USB device must be plugged in
#   - Device path must be provided as first argument
#   - Environment variables set (sources env_set_variables.sh)
#
# Note:
#   Creates a backup of /etc/fstab before modifying it.

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/env_set_variables.sh"

echo "[usb_setup_mount] Setup persistent mount for IrisPen USB drive"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0 <device>"
  exit 1
fi

DEVICE="${1:-}"
if [[ -z "$DEVICE" ]]; then
  echo "Usage: $0 <device> [mount_point]"
  echo "Example: $0 /dev/sda1"
  echo "         $0 /dev/sda1 /media/irispen"
  exit 1
fi

if [[ ! -b "$DEVICE" ]]; then
  echo "Error: $DEVICE is not a block device"
  exit 1
fi

MOUNT_POINT="${2:-/mnt/irispen}"

# Get UUID and filesystem type
UUID=$(blkid -s UUID -o value "$DEVICE")
FSTYPE=$(blkid -s TYPE -o value "$DEVICE")

if [[ -z "$UUID" || -z "$FSTYPE" ]]; then
  echo "Error: Could not determine UUID or filesystem type for $DEVICE"
  exit 1
fi

echo "[usb_setup_mount] Device: $DEVICE"
echo "[usb_setup_mount] UUID: $UUID"
echo "[usb_setup_mount] Filesystem: $FSTYPE"
echo "[usb_setup_mount] Mount point: $MOUNT_POINT"

# Create mount point
mkdir -p "$MOUNT_POINT"

# Backup fstab
FSTAB_BACKUP="/etc/fstab.bak.$(date +%Y%m%d%H%M%S)"
cp /etc/fstab "$FSTAB_BACKUP"
echo "[usb_setup_mount] Backed up /etc/fstab to $FSTAB_BACKUP"

# Check if already in fstab
if grep -q "$UUID" /etc/fstab; then
  echo "[usb_setup_mount] Warning: UUID $UUID already exists in /etc/fstab"
  echo "[usb_setup_mount] Skipping fstab entry"
else
  # Add to fstab
  echo "UUID=$UUID  $MOUNT_POINT  $FSTYPE  defaults,nofail  0  2" >> /etc/fstab
  echo "[usb_setup_mount] Added entry to /etc/fstab"
fi

# Mount now
if mountpoint -q "$MOUNT_POINT"; then
  echo "[usb_setup_mount] $MOUNT_POINT is already mounted"
else
  mount "$MOUNT_POINT"
  echo "[usb_setup_mount] Mounted $MOUNT_POINT"
fi

echo "[usb_setup_mount] Done. Mount point configured and ready."
