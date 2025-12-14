#!/bin/bash
#
# Enable ipr-keyboard services for BLE backend
#
# Usage:
#   sudo ./scripts/service/svc_enable_ble_services.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - BLE services must be installed
#
# category: Service
# purpose: Enable BLE backend services and disable uinput

set -eo pipefail
sudo systemctl enable bt_hid_ble.service
sudo systemctl start bt_hid_ble.service
sudo systemctl disable bt_hid_uinput.service
sudo systemctl stop bt_hid_uinput.service
sudo systemctl enable bt_hid_agent.service
sudo systemctl start bt_hid_agent.service
sudo systemctl enable ipr_backend_manager.service
sudo systemctl start ipr_backend_manager.service
sudo systemctl enable ipr_keyboard.service
sudo systemctl start ipr_keyboard.service
echo "BLE backend services enabled."
