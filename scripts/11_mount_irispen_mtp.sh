
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
#   - Environment variables set (sources 00_set_env.sh)
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
source "$SCRIPT_DIR/00_set_env.sh"

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
