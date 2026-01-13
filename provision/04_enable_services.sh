#!/usr/bin/env bash
#
# Service installation for ipr-keyboard
# Installs and enables systemd services for the application
#
# Purpose:
#   - Runs existing service installation scripts
#   - Configures BLE backend (BLE HID over GATT only)
#   - Enables all required services
#
# Usage:
#   sudo ./provision/04_enable_services.sh
#
# Prerequisites:
#   - 03_app_install.sh completed successfully
#
# category: Provisioning
# purpose: Install and enable systemd services
# sudo: yes

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[services]${NC} $*"; }
warn() { echo -e "${YELLOW}[services]${NC} $*"; }
error() { echo -e "${RED}[services ERROR]${NC} $*"; }

if [[ $EUID -ne 0 ]]; then
  error "This script must be run as root"
  exit 1
fi

# Load environment
ENV_FILE="/opt/ipr_common.env"
if [[ ! -f "$ENV_FILE" ]]; then
  error "Environment file not found: $ENV_FILE"
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

cd "$REPO_DIR"

# Verify required scripts exist
required_scripts=(
  "scripts/service/svc_install_bt_gatt_hid.sh"
  "scripts/service/svc_install_systemd.sh"
  "scripts/ble/ble_setup_extras.sh"
  "scripts/ble/ble_install_helper.sh"
  "scripts/service/svc_enable_services.sh"
)

for script in "${required_scripts[@]}"; do
  if [[ ! -f "$script" ]]; then
    error "Required script not found: $script"
    exit 1
  fi
done

log "Installing Bluetooth GATT HID services (agent and BLE daemon)..."
bash scripts/service/svc_install_bt_gatt_hid.sh

log "Installing BLE helper and backend services..."
bash scripts/ble/ble_install_helper.sh

log "Installing core ipr_keyboard.service..."
bash scripts/service/svc_install_systemd.sh

log "Installing BLE extras (backend manager, diagnostics, etc.)..."
bash scripts/ble/ble_setup_extras.sh

log "Enabling BLE service set..."
bash scripts/service/svc_enable_services.sh

# Install and enable headless Wi-Fi provisioning service
log "Installing headless Wi-Fi provisioning service (ipr-provision) ..."
PROVISION_SCRIPT="scripts/headless/net_provision_hotspot.sh"
PROVISION_TARGET="/usr/local/sbin/ipr-provision.sh"
PROVISION_SERVICE="scripts/headless/ipr-provision.service"

if [[ -f "$PROVISION_SCRIPT" ]]; then
  cp "$PROVISION_SCRIPT" "$PROVISION_TARGET"
  chmod +x "$PROVISION_TARGET"
  log "Installed $PROVISION_TARGET"
else
  warn "Headless provisioning script not found: $PROVISION_SCRIPT"
fi

# Install systemd service unit if present
if [[ -f "$PROVISION_SERVICE" ]]; then
  cp "$PROVISION_SERVICE" /etc/systemd/system/ipr-provision.service
  systemctl daemon-reload
  systemctl enable ipr-provision.service
  systemctl start ipr-provision.service
  log "Enabled and started ipr-provision.service"
else
  warn "Headless provisioning service unit not found: $PROVISION_SERVICE"
fi

# Wait for services to start
sleep 3


log "Verifying service status..."
systemctl --no-pager status ipr_keyboard.service || true
systemctl --no-pager status bt_hid_ble.service || true
systemctl --no-pager status bt_hid_agent_unified.service || true
systemctl --no-pager status ipr-provision.service || true

# Update state

cat >> /opt/ipr_state/bootstrap_info.txt <<EOF

Services Enabled completed: $(date -Is)
Backend: BLE (HID over GATT)
Services:
  - ipr_keyboard.service
  - bt_hid_ble.service
  - bt_hid_agent_unified.service
  - ipr-provision.service
EOF

# Record enabled services
{
  echo "====================================="
  echo "IPR Keyboard - Enabled Services"
  echo "====================================="
  echo ""
  echo "Date: $(date -Is)"
  echo ""
  echo "=== ipr_keyboard.service ==="
  systemctl status ipr_keyboard.service --no-pager || echo "Not running"
  echo ""
  echo "=== bt_hid_ble.service ==="
  systemctl status bt_hid_ble.service --no-pager || echo "Not running"
  echo ""
  echo "=== bt_hid_agent_unified.service ==="
  systemctl status bt_hid_agent_unified.service --no-pager || echo "Not running"
  echo ""
  echo "=== ipr-provision.service ==="
  systemctl status ipr-provision.service --no-pager || echo "Not running"
  echo ""
} > /opt/ipr_state/service_status.txt

log "Service status saved to /opt/ipr_state/service_status.txt"

log "Service installation complete!"
echo ""
log "Active services:"
systemctl --no-pager list-units "ipr*" "bt_hid*" --all
echo ""
log "Next steps:"
log "  1. sudo $REPO_DIR/provision/05_copilot_debug_tools.sh"
echo ""
