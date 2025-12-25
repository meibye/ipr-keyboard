#!/usr/bin/env bash
#
# Application installation for ipr-keyboard
# Creates Python venv and installs application dependencies
#
# Purpose:
#   - Runs existing sys_setup_venv.sh script
#   - Verifies Python environment is correctly configured
#   - Records installed package versions
#
# Usage:
#   sudo ./provision/03_app_install.sh
#
# Prerequisites:
#   - 02_device_identity.sh completed (and system rebooted)
#
# category: Provisioning
# purpose: Install Python environment and dependencies
# sudo: yes (but runs venv setup as user)

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[app_install]${NC} $*"; }
warn() { echo -e "${YELLOW}[app_install]${NC} $*"; }
error() { echo -e "${RED}[app_install ERROR]${NC} $*"; }

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

# Verify scripts exist
if [[ ! -f "scripts/sys_setup_venv.sh" ]]; then
  error "Cannot find scripts/sys_setup_venv.sh"
  exit 1
fi

# 1. Set up Python venv and install dependencies as APP_USER (already uses sudo -u)
echo "[03_app_install] Setting up Python venv and installing dependencies as $APP_USER..."
sudo -u "$APP_USER" bash scripts/sys_setup_venv.sh

# Verify venv was created
if [[ ! -d "$APP_VENV_DIR" ]]; then
  error "Virtual environment was not created at $APP_VENV_DIR"
  exit 1
fi

log "Virtual environment created successfully"

# Verify Python is working
log "Verifying Python environment..."
PYTHON_VERSION=$(sudo -u "$APP_USER" "$APP_VENV_DIR/bin/python" --version)
log "Python version: $PYTHON_VERSION"

# Record installed packages
log "Recording installed Python packages..."
mkdir -p /opt/ipr_state
{
  echo "====================================="
  echo "IPR Keyboard - Python Environment"
  echo "====================================="
  echo ""
  echo "Date: $(date -Is)"
  echo "Virtual Environment: $APP_VENV_DIR"
  echo ""
  echo "=== Python Version ==="
  sudo -u "$APP_USER" "$APP_VENV_DIR/bin/python" --version
  echo ""
  echo "=== Pip Version ==="
  sudo -u "$APP_USER" "$APP_VENV_DIR/bin/pip" --version
  echo ""
  echo "=== UV Version ==="
  uv --version || echo "uv not available"
  echo ""
  echo "=== Installed Packages ==="
  sudo -u "$APP_USER" "$APP_VENV_DIR/bin/pip" list --format=freeze
  echo ""
} > /opt/ipr_state/python_packages.txt

log "Python packages saved to /opt/ipr_state/python_packages.txt"

# Update state
cat >> /opt/ipr_state/bootstrap_info.txt <<EOF

Application Install completed: $(date -Is)
Python venv: $APP_VENV_DIR
Python version: $PYTHON_VERSION
EOF

log "Application installation complete!"
echo ""
log "Python environment ready at: $APP_VENV_DIR"
echo ""
log "Next steps:"
log "  1. sudo $REPO_DIR/provision/04_enable_services.sh"
echo ""
