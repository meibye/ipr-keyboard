#!/usr/bin/env bash

# Creates and enables the ipr_keyboard systemd service

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/00_set_env.sh"

echo "[05] Installing systemd service ipr_keyboard.service"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

SERVICE_FILE="/etc/systemd/system/ipr_keyboard.service"
PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
VENV_DIR="$PROJECT_DIR/.venv"
USER_NAME="$IPR_USER"

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=IrisPen Bluetooth keyboard service
After=network.target bluetooth.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_DIR/bin/python -m ipr_keyboard.main
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now ipr_keyboard.service

echo "[05] Service installed and started."
echo "Check status with: sudo systemctl status ipr_keyboard.service"
