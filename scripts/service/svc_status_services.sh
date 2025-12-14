#!/bin/bash
#
# Show status of all ipr-keyboard related systemd services
#
# Usage:
#   sudo ./scripts/service/svc_status_services.sh
#
# category: Service
# purpose: Show status of all ipr-keyboard services

set -eo pipefail
SERVICES=(
  ipr_keyboard.service
  bt_hid_uinput.service
  bt_hid_ble.service
  bt_hid_agent.service
  ipr_backend_manager.service
)
echo "Service status for ipr-keyboard stack:"
for svc in "${SERVICES[@]}"; do
  echo
  systemctl status "$svc" --no-pager -n 5 || echo "$svc not found."
done
