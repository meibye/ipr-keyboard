
#!/usr/bin/env bash
#
# Systemd Service Installation Script
#
# Purpose:
#   Creates and enables the ipr_keyboard systemd service that runs the application automatically on system boot.
#
# Usage:
#   sudo ./scripts/05_install_service.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - Virtual environment must already be set up
#   - Environment variables set (sources env_set_variables.sh)
#
# Note:
#   The service runs as the configured user (not root) for security.

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/env_set_variables.sh"

echo "[svc_install_systemd] Installing systemd service ipr_keyboard.service"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

SERVICE_FILE="/etc/systemd/system/ipr_keyboard.service"
PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
VENV_DIR="$PROJECT_DIR/.venv"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Project directory not found: $PROJECT_DIR"
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Virtual environment not found: $VENV_DIR"
  echo "Please run 04_setup_venv.sh first."
  exit 1
fi

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=IrisPen to Bluetooth Keyboard Bridge
After=network.target bluetooth.target

[Service]
Type=simple
User=$IPR_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_DIR/bin/python -m ipr_keyboard.main
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ipr_keyboard.service

echo "[svc_install_systemd] Service installed and enabled."
echo "     Start now:   sudo systemctl start ipr_keyboard"
echo "     Check status: sudo systemctl status ipr_keyboard"
