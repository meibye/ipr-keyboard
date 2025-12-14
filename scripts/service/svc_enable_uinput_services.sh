#!/bin/bash
# Enable ipr-keyboard services for uinput backend
set -euo pipefail
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
