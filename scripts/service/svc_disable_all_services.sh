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
# sudo: yes

set -e
SERVICES=(
  ipr_keyboard.service
  bt_hid_ble.service
  bt_hid_agent_unified.service
)

for svc in "${SERVICES[@]}"; do
  echo "Stopping $svc..."
  if ! sudo systemctl stop "$svc"; then
    echo "Warning: Failed to stop $svc" >&2
  fi
  if systemctl is-enabled "$svc" &>/dev/null; then
    echo "Disabling $svc..."
    if ! sudo systemctl disable "$svc"; then
      echo "Warning: Failed to disable $svc" >&2
    fi
  else
    echo "$svc is already disabled."
  fi
done
echo "All services stopped and disabled."
