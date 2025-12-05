
#!/usr/bin/env bash
#
# ipr-keyboard IrisPen MTP Mount Script
#
# Purpose:
#   Mounts or unmounts the IrisPen as an MTP device for file access.
#   Useful for devices that do not present as USB mass storage.
#
# Usage:
#   sudo ./scripts/11_mount_irispen_mtp.sh mount
#   sudo ./scripts/11_mount_irispen_mtp.sh unmount
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - Environment variables set (sources env_set_variables.sh)
#
# Arguments:
#   mount   - Mount the device
#   unmount - Unmount the device
#
# Note:
#   Requires mtp-tools and simple-mtpfs.

#!/usr/bin/env bash
#
# ipr-keyboard IrisPen MTP Mount Script
#
# Purpose:
#   Mounts or unmounts the IrisPen as an MTP device for file access.
#   Useful for devices that do not present as USB mass storage.

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/env_set_variables.sh"

MOUNTPOINT="/mnt/irispen"

if mount | grep -q " $MOUNTPOINT "; then
  echo "[usb_mount_mtp] Unmounting IRISPen MTP from $MOUNTPOINT..."
  fusermount -u "$MOUNTPOINT" || sudo umount "$MOUNTPOINT" || true
  echo "[usb_mount_mtp] Unmounted."
  exit 0
fi

echo "[usb_mount_mtp] Mounting IRISPen MTP at $MOUNTPOINT..."

if ! command -v jmtpfs >/dev/null 2>&1; then
  echo "[usb_mount_mtp][ERROR] jmtpfs not installed. Run:"
  echo "  sudo apt install jmtpfs"
  exit 1
fi

jmtpfs "$MOUNTPOINT"

echo "[usb_mount_mtp] Mounted. Contents:"
ls "$MOUNTPOINT" || true
