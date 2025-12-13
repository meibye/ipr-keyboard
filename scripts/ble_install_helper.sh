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

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

FIFO_PATH="/run/ipr_bt_keyboard_fifo"
HELPER_PATH="/usr/local/bin/bt_kb_send"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
cat > "$HELPER_PATH" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

FIFO="/run/ipr_bt_keyboard_fifo"

if [[ ! -p "$FIFO" ]]; then
  echo "bt_kb_send: FIFO $FIFO not found or not a pipe" >&2
  exit 1
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: bt_kb_send \"text to send\"" >&2
  exit 1
fi

TEXT="$*"
printf '%s\n' "$TEXT" > "$FIFO"
EOF

chmod +x "$HELPER_PATH"

########################################
# 3. Install backend services
########################################
echo "=== [ble_install_helper] Installing bt_hid_uinput service ==="
"$SCRIPT_DIR/svc_install_bt_hid_uinput.sh"

echo "=== [ble_install_helper] Installing bt_hid_ble service ==="
"$SCRIPT_DIR/svc_install_bt_hid_ble.sh"

echo "=== [ble_install_helper] Enabling uinput backend by default ==="
systemctl disable bt_hid_ble.service || true
systemctl enable bt_hid_uinput.service
systemctl restart bt_hid_uinput.service

########################################
# 4. Install Bluetooth agent
########################################
echo "=== [ble_install_helper] Installing bt_hid_agent service ==="
"$SCRIPT_DIR/svc_install_bt_hid_agent.sh"

systemctl enable bt_hid_agent.service
systemctl restart bt_hid_agent.service

echo "=== [ble_install_helper] Installation complete. ==="
echo "  - Helper:        $HELPER_PATH"
echo "  - FIFO:          $FIFO_PATH"
echo "  - Backends:      uinput (active), ble (fully working BLE HID over GATT)"
echo "  - Agent:         bt_hid_agent.service (handles pairing & service authorization)"
echo "To switch backend later, use scripts/ble_switch_backend.sh."
