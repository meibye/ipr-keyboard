#!/bin/bash
#
# Disable all ipr-keyboard related systemd services
#
# Usage:
#   sudo ./scripts/service/svc_disable_all_services.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#
# category: Service
# purpose: Disable all ipr-keyboard systemd services
# sudo: no

set -eo pipefail
SERVICES=(
  ipr_keyboard.service
  bt_hid_uinput.service
  bt_hid_daemon.service
  bt_hid_ble.service
  bt_hid_agent.service
  ipr_backend_manager.service
)

for svc in "${SERVICES[@]}"; do
  echo "Stopping $svc..."
  sudo systemctl stop "$svc"
  if systemctl is-enabled "$svc" &>/dev/null; then
    echo "Disabling $svc..."
    sudo systemctl disable "$svc"
  else
    echo "$svc is already disabled."
  fi
done
echo "All services stopped and disabled."
