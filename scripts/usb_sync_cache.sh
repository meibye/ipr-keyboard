#!/usr/bin/env bash
set -euo pipefail


# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/env_set_variables.sh"

set -euo pipefail

PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
VENV_DIR="$PROJECT_DIR/.venv"
MTP_ROOT="/mnt/irispen"
CACHE_ROOT="$PROJECT_DIR/cache/irispen"

cd "$PROJECT_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "[usb_sync_cache][ERROR] venv not found at $VENV_DIR"
  echo "       Run: ./scripts/04_setup_venv.sh"
  exit 1
fi

if ! mount | grep -q " $MTP_ROOT "; then
  echo "[usb_sync_cache][ERROR] $MTP_ROOT is not mounted."
  echo "       Mount with: ./scripts/11_mount_irispen_mtp.sh"
  exit 1
fi

echo "[usb_sync_cache] Syncing from $MTP_ROOT to $CACHE_ROOT..."

source "$VENV_DIR/bin/activate"

uv run python -m ipr_keyboard.usb.mtp_sync \
  --mtp-root "$MTP_ROOT" \
  --cache-root "$CACHE_ROOT" \
  --delete-source

echo "[usb_sync_cache] Sync completed."
