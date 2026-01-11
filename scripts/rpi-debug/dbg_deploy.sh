#!/usr/bin/env bash
#
# Deploy latest code from GitHub and restart BLE HID service for Copilot/MCP diagnostics
#
# Usage:
#   sudo dbg_deploy.sh
#
# Prerequisites:
#   - Should be run as root for full effect
#   - /etc/ipr_dbg.env should exist (written by install_dbg_tools.sh)
#
# category: Debug
# purpose: Deploy latest code and restart BLE HID service
# sudo: yes
set -euo pipefail

DBG_ENV="/etc/ipr_dbg.env"
[[ -f "$DBG_ENV" ]] && source "$DBG_ENV"

# Source common environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/dbg_common.env"

REPO_DIR="${DBG_COPILOT_REPO:-$COPILOT_REPO}"
BRANCH="${DBG_BRANCH:-main}"
BLE_SERVICE="${DBG_BLE_SERVICE:-$BLE_SERVICE}"
AGENT_SERVICE="${DBG_AGENT_SERVICE:-$AGENT_SERVICE}"

echo "== dbg_deploy: start $(date -Is) =="
echo "Repo:   $REPO_DIR"
echo "Ref:    $BRANCH"
echo "Agent:  $AGENT_SERVICE"
echo "BLE:    $BLE_SERVICE"
echo

if [[ ! -d "$REPO_DIR/.git" ]]; then
  echo "ERROR: Repo not found at $REPO_DIR"
  exit 1
fi

cd "$REPO_DIR"

echo "== Git status before =="
git status --porcelain=v1 || true

echo "== Fetch =="
git fetch --all --prune

echo "== Checkout ref =="
git checkout "$BRANCH"

echo "== Reset hard to origin/$BRANCH =="
git reset --hard "origin/$BRANCH"

echo "== Current commit =="
git rev-parse --short HEAD

echo
echo "== Restart bluetooth app stack (agent + ble) =="
sudo systemctl restart "$AGENT_SERVICE"
sudo systemctl restart "$BLE_SERVICE"

echo
echo "== Status =="
systemctl --no-pager -l status "$AGENT_SERVICE" || true
systemctl --no-pager -l status "$BLE_SERVICE" || true

echo "== dbg_deploy: done $(date -Is) =="
