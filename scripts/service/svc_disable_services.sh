#!/bin/bash
# Disable all ipr-keyboard related services

set -euo pipefail

SERVICES=(
  ipr_keyboard.service
  bt_hid_ble.service
  bt_hid_agent_unified.service
  ipr-provision.service
)

for svc in "${SERVICES[@]}"; do
  if systemctl is-enabled --quiet "$svc"; then
    systemctl disable "$svc"
  fi
  if systemctl is-active --quiet "$svc"; then
    systemctl stop "$svc"
  fi
  echo "Disabled and stopped $svc"
done

echo "All IPR Keyboard services disabled."
