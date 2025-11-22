#!/usr/bin/env bash

# Toggles between mounted / unmounted.

set -euo pipefail

MOUNTPOINT="/mnt/irispen"

if mount | grep -q " $MOUNTPOINT "; then
  echo "[11] Unmounting IRISPen MTP from $MOUNTPOINT..."
  fusermount -u "$MOUNTPOINT" || sudo umount "$MOUNTPOINT" || true
  echo "[11] Unmounted."
  exit 0
fi

echo "[11] Mounting IRISPen MTP at $MOUNTPOINT..."

if ! command -v jmtpfs >/dev/null 2>&1; then
  echo "[11][ERROR] jmtpfs not installed. Run:"
  echo "  sudo apt install jmtpfs"
  exit 1
fi

jmtpfs "$MOUNTPOINT"

echo "[11] Mounted. Contents:"
ls "$MOUNTPOINT" || true
