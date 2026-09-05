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

# ---------------------------------------------------------------------------
# Apply the bluetooth drop-in before anything talks to the adapter.
#
# svc_install_bt_gatt_hid.sh writes /etc/systemd/system/bluetooth.service.d/
# override.conf and prints "Next steps: restart bluetooth" -- advice nothing in
# the automated chain followed.  Starting the agent against a bluetoothd still
# running the old configuration leaves its btmgmt ExecStartPre calls blocked on
# the management socket, and the unit dies on a start-pre timeout:
#
#   Job for bt_hid_agent_unified.service failed because a timeout was exceeded.
#
# Restarting here, and waiting for the adapter to answer, removes that race.
# ---------------------------------------------------------------------------
BT_HCI_DEV="${BT_HCI:-hci0}"

echo "[services] Restarting bluetooth to apply the drop-in ..."
systemctl daemon-reload
systemctl restart bluetooth

echo "[services] Waiting for adapter ${BT_HCI_DEV} to become ready ..."
adapter_ready=false
for _ in $(seq 1 30); do
    if timeout 5 btmgmt -i "$BT_HCI_DEV" info >/dev/null 2>&1; then
        adapter_ready=true
        break
    fi
    sleep 1
done

if $adapter_ready; then
    echo "[services] Adapter ${BT_HCI_DEV} is ready."
else
    echo "[services] WARNING: ${BT_HCI_DEV} did not respond within 30s." >&2
    echo "[services] Continuing, but the BLE services may fail to start." >&2
    echo "[services] Check: systemctl status bluetooth; btmgmt -i ${BT_HCI_DEV} info" >&2
fi


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
