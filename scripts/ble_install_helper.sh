#!/usr/bin/env bash
#
# ble_install_helper.sh
#
# Install Bluetooth Keyboard Helper Script and backend daemons.
#
# Installs:
#   - /usr/local/bin/bt_kb_send
#       → writes text into /run/ipr_bt_keyboard_fifo
#   - /usr/local/bin/bt_hid_uinput_daemon.py
#       → reads FIFO, types on the Pi via uinput (local virtual keyboard)
#   - /usr/local/bin/bt_hid_ble_daemon.py
#       → BLE HID over GATT daemon structure (BlueZ-based)
#   - systemd services:
#       * bt_hid_uinput.service
#       * bt_hid_ble.service
#
# The active backend is controlled by:
#   - KeyboardBackend in config.json ("uinput" or "ble")
#   - Enabling/disabling the corresponding systemd units
#
# Usage:
#   sudo ./scripts/ble_install_helper.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#
# category: Bluetooth
# purpose: Install Bluetooth keyboard helper and backend daemons
# sudo: yes
#

set -eo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

FIFO_PATH="/run/ipr_bt_keyboard_fifo"
HELPER_PATH="/usr/local/bin/bt_kb_send"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/bt_agent_unified_env.sh"

echo "=== [ble_install_helper] Installing Bluetooth keyboard helper and backends ==="

########################################
# 1. Install system dependencies
########################################
echo "=== [ble_install_helper] Installing OS packages (python3, evdev, bluez, dbus) ==="
apt update
apt install -y \
  python3 \
  python3-pip \
  python3-evdev \
  python3-dbus \
  bluez \
  bluez-tools

########################################
# 2. Create helper script: bt_kb_send
########################################
echo "=== [ble_install_helper] Writing $HELPER_PATH ==="
# bt_kb_send: write text into the BLE keyboard FIFO
# - waits for FIFO to exist
# - waits for Windows to subscribe to InputReport notifications (flag file)
cat > "$HELPER_PATH" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

FIFO="/run/ipr_bt_keyboard_fifo"
NOTIFY_FLAG="/run/ipr_bt_keyboard_notifying"

WAIT_SECS="${BT_KB_WAIT_SECS:-10}"

usage() {
  echo "Usage: bt_kb_send [--nowait] [--wait <seconds>] \"text...\""
}

NOWAIT=0
if [[ "${1:-}" == "--nowait" ]]; then
  NOWAIT=1
  shift
elif [[ "${1:-}" == "--wait" ]]; then
  shift
  WAIT_SECS="${1:-}"
  shift || true
fi

TEXT="${1:-}"
if [[ -z "$TEXT" ]]; then
  usage
  exit 2
fi

# Wait for FIFO
t=0
until [[ -p "$FIFO" ]]; do
  (( t++ )) || true
  if (( t >= WAIT_SECS )); then
    echo "ERROR: FIFO not ready: $FIFO" >&2
    exit 1
  fi
  sleep 1
done

if (( NOWAIT == 0 )); then
  # Wait for HID notify subscription (StartNotify creates the flag file)
  t=0
  until [[ -f "$NOTIFY_FLAG" ]]; do
    (( t++ )) || true
    if (( t >= WAIT_SECS )); then
      echo "ERROR: HID notify not ready (no StartNotify yet). Flag: $NOTIFY_FLAG" >&2
      exit 1
    fi
    sleep 1
  done
fi

printf "%s" "$TEXT" > "$FIFO"
EOF

chmod +x "$HELPER_PATH"

########################################
# 3. Install backend services
########################################
echo "=== [ble_install_helper] Installing bt_hid_uinput service ==="
"$SCRIPT_DIR/service/svc_install_bt_hid_uinput.sh"

echo "=== [ble_install_helper] Installing bt_hid_ble service ==="
"$SCRIPT_DIR/service/svc_install_bt_hid_ble.sh"

echo "=== [ble_install_helper] Enabling BLE backend by default ==="
systemctl enable bt_hid_ble.service || true
systemctl disable bt_hid_uinput.service
systemctl restart bt_hid_ble.service

########################################
# 4. Install Bluetooth agent
########################################
echo "=== [ble_install_helper] Installing bt_hid_agent_unified service ==="
"$SCRIPT_DIR/service/svc_install_bt_hid_agent_unified.sh"

bt_agent_unified_require_root
bt_agent_unified_disable_legacy_service
bt_agent_unified_set_profile_nowinpasskey
bt_agent_unified_enable
bt_agent_unified_restart

echo "=== [ble_install_helper] Installation complete. ==="
echo "  - Helper:        $HELPER_PATH"
echo "  - FIFO:          $FIFO_PATH"
echo "  - Backends:      uinput (active), ble (fully working BLE HID over GATT)"
echo "  - Agent:         bt_hid_agent_unified.service (handles pairing & service authorization)"
echo "To switch backend later, use scripts/ble_switch_backend.sh."
