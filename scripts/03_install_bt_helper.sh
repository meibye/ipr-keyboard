#!/usr/bin/env bash

# Installs a placeholder /usr/local/bin/bt_kb_send script.
# You’ll later replace its internals with a real HID implementation; the Python code only cares that this command exists.

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
