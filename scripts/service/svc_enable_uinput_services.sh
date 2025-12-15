#!/bin/bash
#
# Enable ipr-keyboard services for uinput backend
#
# Usage:
#   sudo ./scripts/service/svc_enable_uinput_services.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - uinput services must be installed
#

# category: Service
# purpose: Enable uinput backend services and disable BLE
# sudo: yes

set -eo pipefail
# Only enable uinput backend, not hid_daemon
sudo systemctl enable bt_hid_uinput.service
sudo systemctl start bt_hid_uinput.service
sudo systemctl disable bt_hid_ble.service
sudo systemctl stop bt_hid_ble.service
sudo systemctl enable bt_hid_agent.service
sudo systemctl start bt_hid_agent.service
sudo systemctl enable ipr_backend_manager.service
sudo systemctl start ipr_backend_manager.service
sudo systemctl enable ipr_keyboard.service
sudo systemctl start ipr_keyboard.service
echo "uinput backend services enabled."
