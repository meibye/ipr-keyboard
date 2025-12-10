#!/bin/bash
# Disable all ipr-keyboard related systemd services
set -euo pipefail
SERVICES=(
  ipr_keyboard.service
  bt_hid_uinput.service
  bt_hid_ble.service
  bt_hid_agent.service
  ipr_backend_manager.service
)
for svc in "${SERVICES[@]}"; do
  if systemctl is-enabled "$svc" &>/dev/null; then
    echo "Disabling $svc..."
    sudo systemctl disable "$svc"
    sudo systemctl stop "$svc"
  else
    echo "$svc is already disabled."
  fi
done
echo "All services disabled."
