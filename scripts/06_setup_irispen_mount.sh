#!/usr/bin/env bash

# Purpose:
# Create and configure a persistent mount point for the IrisPen USB drive, e.g.:
#
# Device: /dev/sda1 (or whatever you pass as argument)
#
# Mount point: /mnt/irispen by default
#
# Writes a proper UUID=… entry into /etc/fstab, using the actual filesystem type.
#
# Usage example:
#
# sudo ./scripts/06_setup_irispen_mount.sh /dev/sda1
#    or with custom mountpoint:
# sudo ./scripts/06_setup_irispen_mount.sh /dev/sda1 /media/irispen

set -euo pipefail

echo "[06] Setup persistent mount for IrisPen USB drive"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0 /dev/sdXN [/mnt/irispen]"
  exit 1
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: sudo $0 /dev/sdXN [/mnt/irispen]"
  echo
  echo "Example:"
  echo "  sudo $0 /dev/sda1 /mnt/irispen"
  echo
  echo "Available block devices:"
  lsblk -fp
  exit 1
fi

DEVICE="$1"
MOUNTPOINT="${2:-/mnt/irispen}"

if [[ ! -b "$DEVICE" ]]; then
  echo "Error: $DEVICE is not a block device."
  echo "Check with: lsblk -fp"
  exit 1
fi

echo "[06] Using device: $DEVICE"
echo "[06] Mountpoint: $MOUNTPOINT"

mkdir -p "$MOUNTPOINT"

UUID=$(blkid -s UUID -o value "$DEVICE" || true)
FSTYPE=$(blkid -s TYPE -o value "$DEVICE" || true)

if [[ -z "$UUID" || -z "$FSTYPE" ]]; then
  echo "Error: Could not determine UUID or filesystem type for $DEVICE."
  echo "blkid output:"
  blkid "$DEVICE" || true
  exit 1
fi

echo "[06] Detected UUID:   $UUID"
echo "[06] Detected FSType: $FSTYPE"

FSTAB="/etc/fstab"
BACKUP="/etc/fstab.bak.$(date +%Y%m%d%H%M%S)"

echo "[06] Backing up $FSTAB to $BACKUP"
cp "$FSTAB" "$BACKUP"

# Remove any existing lines referencing this UUID or mountpoint to avoid duplicates
sed -i "\|UUID=$UUID|d" "$FSTAB"
sed -i "\| $MOUNTPOINT |d" "$FSTAB"

# Append new fstab line
cat <<EOF >> "$FSTAB"
# IrisPen USB drive (added by 06_setup_irispen_mount.sh)
UUID=$UUID  $MOUNTPOINT  $FSTYPE  defaults,nofail  0  0
EOF

echo "[06] Updated $FSTAB with IrisPen entry."
echo "[06] Mounting $MOUNTPOINT..."

mount "$MOUNTPOINT"

echo "[06] Mountpoint status:"
mount | grep " $MOUNTPOINT " || echo "Warning: $MOUNTPOINT not found in mount output."

echo "[06] Done. You can now set IrisPenFolder to $MOUNTPOINT in config.json."
