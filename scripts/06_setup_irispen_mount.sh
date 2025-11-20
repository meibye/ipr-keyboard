#!/usr/bin/env bash
#
# Setup IrisPen USB Mount Point
#
# Purpose:
#   Creates and configures a persistent mount point for the IrisPen USB drive.
#   Adds the mount entry to /etc/fstab using the device's UUID for reliability.
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - IrisPen USB device must be plugged in
#   - Device path must be provided as first argument
#
# Usage:
#   sudo ./scripts/06_setup_irispen_mount.sh /dev/sda1
#   sudo ./scripts/06_setup_irispen_mount.sh /dev/sda1 /media/irispen
#
# Arguments:
#   $1 - Device path (e.g., /dev/sda1) - Required
#   $2 - Mount point (default: /mnt/irispen) - Optional
#
# Note:
#   Creates a backup of /etc/fstab before modifying it.

set -euo pipefail

echo "[06] Setup persistent mount for IrisPen USB drive"

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

echo "[06] Device: $DEVICE"
echo "[06] UUID: $UUID"
echo "[06] Filesystem: $FSTYPE"
echo "[06] Mount point: $MOUNT_POINT"

# Create mount point
mkdir -p "$MOUNT_POINT"

# Backup fstab
FSTAB_BACKUP="/etc/fstab.bak.$(date +%Y%m%d%H%M%S)"
cp /etc/fstab "$FSTAB_BACKUP"
echo "[06] Backed up /etc/fstab to $FSTAB_BACKUP"

# Check if already in fstab
if grep -q "$UUID" /etc/fstab; then
  echo "[06] Warning: UUID $UUID already exists in /etc/fstab"
  echo "[06] Skipping fstab entry"
else
  # Add to fstab
  echo "UUID=$UUID  $MOUNT_POINT  $FSTYPE  defaults,nofail  0  2" >> /etc/fstab
  echo "[06] Added entry to /etc/fstab"
fi

# Mount now
if mountpoint -q "$MOUNT_POINT"; then
  echo "[06] $MOUNT_POINT is already mounted"
else
  mount "$MOUNT_POINT"
  echo "[06] Mounted $MOUNT_POINT"
fi

echo "[06] Done. Mount point configured and ready."
