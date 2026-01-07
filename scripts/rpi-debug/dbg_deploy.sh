#!/usr/bin/env bash
set -euo pipefail

# === Adjust these to your environment ===
REPO_DIR="/home/copilotdiag/ipr-keyboard"   # path to repo checkout on the Pi
BRANCH="main"
SERVICE_BT="bt_hid_ble.service"
# ========================================

echo "== dbg_deploy: start $(date -Is) =="

if [ ! -d "$REPO_DIR/.git" ]; then
  echo "ERROR: Repo not found at $REPO_DIR"
  exit 1
fi

cd "$REPO_DIR"

echo "== Git status before =="
git status --porcelain=v1 || true

echo "== Fetch =="
git fetch --all --prune

echo "== Checkout branch =="
git checkout "$BRANCH"

echo "== Reset hard to origin/$BRANCH =="
git reset --hard "origin/$BRANCH"

echo "== Current commit =="
git rev-parse --short HEAD

# If you have a known build/install step, add it here (keep it deterministic).
# Examples:
# ./scripts/install.sh
# uv sync --frozen
# pip install -r requirements.txt

echo "== Restart service =="
sudo systemctl restart "$SERVICE_BT"

echo "== Service status =="
systemctl --no-pager -l status "$SERVICE_BT" || true

echo "== dbg_deploy: done $(date -Is) =="
