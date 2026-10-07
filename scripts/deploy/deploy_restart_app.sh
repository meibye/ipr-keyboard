#!/usr/bin/env bash
#
# deploy_restart_app.sh
#
# Restart the main application service after code or template changes.
#
# Use after 'git pull' when only Python source files (.py) or HTML templates
# changed.  The package is installed in editable mode, so no reinstall is
# needed — a service restart is sufficient.
#
# Usage:
#   sudo ./scripts/deploy/deploy_restart_app.sh
#
# category: Deploy
# purpose: Restart the main application service after code or template changes
# sudo: yes

set -euo pipefail

echo "[deploy] Restarting ipr_keyboard.service…"
systemctl restart ipr_keyboard.service

echo "[deploy] Status:"
systemctl --no-pager -l status ipr_keyboard.service || true

echo ""
echo "[deploy] Done."
echo "  Tip: hard-refresh your browser (long-press the reload button on mobile,"
echo "       Ctrl+Shift+R on desktop) to clear cached pages."
