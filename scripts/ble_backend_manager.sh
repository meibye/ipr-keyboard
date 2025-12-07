#!/usr/bin/env bash
#
# ble_backend_manager.sh
#
# Wrapper script to manually trigger the backend manager.
# Calls /usr/local/bin/ipr_backend_manager.sh which is installed by ble_setup_extras.sh
#
# This script reads /etc/ipr-keyboard/backend and ensures only the selected backend
# services are enabled and running.
#
# Usage:
#   sudo ./scripts/ble_backend_manager.sh
#
# See also:
#   - ble_switch_backend.sh — Higher-level backend switching with prompts
#   - /etc/ipr-keyboard/backend — Backend selection file
#

set -euo pipefail

MANAGER_SCRIPT="/usr/local/bin/ipr_backend_manager.sh"

if [[ ! -x "$MANAGER_SCRIPT" ]]; then
  echo "ERROR: Backend manager script not found at $MANAGER_SCRIPT"
  echo "Please run: sudo ./scripts/ble_setup_extras.sh"
  exit 1
fi

if [[ "$EUID" -ne 0 ]]; then
  echo "ERROR: This script must be run as root (use sudo)"
  exit 1
fi

echo "=== Running Backend Manager ==="
echo "Reading backend selection from /etc/ipr-keyboard/backend"
echo

if [[ -f "/etc/ipr-keyboard/backend" ]]; then
  BACKEND=$(cat /etc/ipr-keyboard/backend | tr -d '[:space:]')
  echo "Current backend: $BACKEND"
  echo
fi

"$MANAGER_SCRIPT"

echo
echo "=== Backend Manager Complete ==="
echo "Use 'systemctl status' to check service status:"
echo "  systemctl status bt_hid_uinput.service"
echo "  systemctl status bt_hid_ble.service"
echo "  systemctl status bt_hid_agent.service"
