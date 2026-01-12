#!/bin/bash
#
# Enable ipr-keyboard services
#
# Usage:
#   sudo ./scripts/service/svc_enable_services.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - Bluetooth GATT HID services must be installed
#
# category: Service
# purpose: Enable Bluetooth GATT HID services
# sudo: yes

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../lib/bt_agent_unified_env.sh"

bt_agent_unified_require_root


# Unified agent: default profile is the one that avoids Windows passkeys.
bt_agent_unified_set_profile_nowinpasskey
bt_agent_unified_disable_legacy_service
bt_agent_unified_enable
bt_agent_unified_restart
sudo systemctl enable bt_hid_ble.service
sudo systemctl start bt_hid_ble.service
sudo systemctl enable bt_hid_agent_unified.service
sudo systemctl start bt_hid_agent_unified.service
sudo systemctl enable ipr_keyboard.service
sudo systemctl start ipr_keyboard.service
echo "Bluetooth GATT HID services enabled."
