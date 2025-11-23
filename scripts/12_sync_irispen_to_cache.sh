#!/usr/bin/env bash
set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/00_set_env.sh"
# ipr-keyboard IrisPen MTP Sync Script
#
# Purpose:
#   Copies files from the IrisPen MTP mount to a local cache directory.
#   Useful for working around MTP limitations and for offline processing.
#
# Usage:
#   ./scripts/12_sync_irispen_to_cache.sh
#
# Prerequisites:
#   - Must NOT be run as root
#   - IrisPen MTP must be mounted
#   - Environment variables set (sources 00_set_env.sh)
#
# Note:
#   Default cache dir is $IPR_PROJECT_ROOT/.irispen_cache

set -euo pipefail

source "$SCRIPT_DIR/00_set_env.sh"
PROJECT_DIR="/home/meibye/dev/ipr-keyboard"
VENV_DIR="$PROJECT_DIR/.venv"
MTP_ROOT="/mnt/irispen"
CACHE_ROOT="$PROJECT_DIR/cache/irispen"

cd "$PROJECT_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "[12][ERROR] venv not found at $VENV_DIR"
  echo "       Run: ./scripts/04_setup_venv.sh"
  exit 1
fi

if ! mount | grep -q " $MTP_ROOT "; then
  echo "[12][ERROR] $MTP_ROOT is not mounted."
  echo "       Mount with: ./scripts/11_mount_irispen_mtp.sh"
  exit 1
fi

echo "[12] Syncing from $MTP_ROOT to $CACHE_ROOT..."

source "$VENV_DIR/bin/activate"

uv run python -m ipr_keyboard.usb.mtp_sync \
  --mtp-root "$MTP_ROOT" \
  --cache-root "$CACHE_ROOT" \
  --delete-source

echo "[12] Sync completed."
