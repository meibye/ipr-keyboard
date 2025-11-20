#!/usr/bin/env bash
#
# Install Bluetooth Keyboard Helper Script
#
# Purpose:
#   Installs a placeholder Bluetooth HID keyboard helper script at
#   /usr/local/bin/bt_kb_send. The Python application calls this script
#   to send text via Bluetooth keyboard emulation.
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#
# Usage:
#   sudo ./scripts/03_install_bt_helper.sh
#
# Note:
#   This installs a placeholder that logs messages. Replace the script's
#   internals with a real HID implementation for actual Bluetooth keyboard
#   functionality.

set -euo pipefail

echo "[03] Installing placeholder Bluetooth keyboard helper /usr/local/bin/bt_kb_send"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

HELPER="/usr/local/bin/bt_kb_send"

cat <<'EOF' > "$HELPER"
#!/usr/bin/env bash
# Placeholder for Bluetooth HID sender.
# Expected usage:
#   bt_kb_send "some text to type"
#
# Replace this with a real HID implementation later.

MSG="$*"

# Log to syslog
logger -t bt_kb_send "Would send over BT: $MSG"

# Also show on stdout for debugging
echo "bt_kb_send: $MSG"
EOF

chmod +x "$HELPER"

echo "[03] Installed placeholder helper. (No real keystrokes are sent yet.)"
