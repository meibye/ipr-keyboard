#!/usr/bin/env bash
#
# svc_install_ipr_backend_manager.sh
#
# Installs the ipr_backend_manager service and script.
# This service manages the backend switcher.
#

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

echo "=== [svc_install_ipr_backend_manager] Installing ipr_backend_manager service ==="

########################################
# Create backend manager script
########################################
BACKEND_MANAGER="/usr/local/bin/ipr_backend_manager.sh"

echo "=== [svc_install_ipr_backend_manager] Writing $BACKEND_MANAGER ==="
cat > "$BACKEND_MANAGER" << 'EOF'
#!/usr/bin/env bash
# ipr_backend_manager.sh
#
# Simple backend switcher:
#   - Reads /etc/ipr-keyboard/backend (ble | uinput)
#   - Ensures only the corresponding backend services are enabled/running.
#
# Backends:
#   uinput -> bt_hid_daemon.service
#   ble    -> bt_hid_ble.service + bt_hid_agent.service

set -euo pipefail

CONFIG_FILE="/etc/ipr-keyboard/backend"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "ble" > "$CONFIG_FILE"
fi

CURRENT="$(tr -d '[:space:]' < "$CONFIG_FILE")"

echo "[backend-manager] Requested backend: '$CURRENT'"

case "$CURRENT" in
  uinput)
    systemctl stop bt_hid_ble.service bt_hid_agent.service 2>/dev/null || true
    systemctl disable bt_hid_ble.service bt_hid_agent.service 2>/dev/null || true

    systemctl enable bt_hid_daemon.service 2>/dev/null || true
    systemctl restart bt_hid_daemon.service
    echo "[backend-manager] Enabled uinput backend (bt_hid_daemon.service)"
    ;;
  ble)
    systemctl stop bt_hid_daemon.service 2>/dev/null || true
    systemctl disable bt_hid_daemon.service 2>/dev/null || true

    systemctl enable bt_hid_ble.service bt_hid_agent.service 2>/dev/null || true
    systemctl restart bt_hid_ble.service bt_hid_agent.service
    echo "[backend-manager] Enabled BLE backend (bt_hid_ble + bt_hid_agent)"
    ;;
  *)
    echo "[backend-manager] ERROR: Unknown backend '$CURRENT' (expected 'ble' or 'uinput')"
    exit 1
    ;;
esac

exit 0
EOF

chmod +x "$BACKEND_MANAGER"

########################################
# Create systemd service unit
########################################
BACKEND_SERVICE="/etc/systemd/system/ipr_backend_manager.service"

echo "=== [svc_install_ipr_backend_manager] Writing $BACKEND_SERVICE ==="
cat > "$BACKEND_SERVICE" << 'EOF'
[Unit]
Description=IPR Keyboard Backend Manager
After=bluetooth.target
Requires=bluetooth.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/ipr_backend_manager.sh

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

echo "=== [svc_install_ipr_backend_manager] Installation complete ==="
