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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/bt_agent_unified_env.sh"

bt_agent_unified_require_root

# Unified agent: keep the no-passkey profile even for uinput backend (best-effort).
bt_agent_unified_set_profile_nowinpasskey
bt_agent_unified_disable_legacy_service
bt_agent_unified_enable
bt_agent_unified_restart
sudo systemctl enable bt_hid_uinput.service
sudo systemctl start bt_hid_uinput.service
sudo systemctl disable bt_hid_ble.service
sudo systemctl stop bt_hid_ble.service
sudo systemctl enable bt_hid_agent_unified.service
sudo systemctl start bt_hid_agent_unified.service
sudo systemctl enable ipr_backend_manager.service
sudo systemctl start ipr_backend_manager.service
sudo systemctl enable ipr_keyboard.service
sudo systemctl start ipr_keyboard.service
echo "uinput backend services enabled."
