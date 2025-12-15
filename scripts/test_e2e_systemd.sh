#!/usr/bin/env bash
#
# ipr-keyboard End-to-End Systemd Demo Script
#
# Purpose:
#   Tests the ipr-keyboard systemd service end-to-end.
#   Verifies service is running, processes files, and logs actions.
#
# Usage:
#   sudo ./scripts/test_e2e_systemd.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - Service must be installed and enabled
#   - Environment variables set (sources env_set_variables.sh)
#   - IrisPenFolder configured and accessible
#
# Note:
#   This script tests the systemd service, not foreground mode.
#
# category: Testing
# purpose: End-to-end test of ipr-keyboard systemd service
# sudo: yes

set -eo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/env_set_variables.sh"

# Define required variables
SERVICE_NAME="ipr_keyboard.service"
PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
VENV_DIR="$PROJECT_DIR/.venv"

echo "[test_e2e_systemd] Running end-to-end test with systemd service"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

# Check if service is installed
if ! systemctl list-unit-files | grep -q "$SERVICE_NAME"; then
  echo "[test_e2e_systemd] Error: Service $SERVICE_NAME is not installed"
  echo "[test_e2e_systemd] Please run ./scripts/service/svc_install_systemd.sh first"
  exit 1
fi

# Record current service state
SERVICE_WAS_ACTIVE=false
if systemctl is-active --quiet "$SERVICE_NAME"; then
  SERVICE_WAS_ACTIVE=true
  echo "[test_e2e_systemd] Service is currently active"
else
  echo "[test_e2e_systemd] Service is currently inactive"
fi

# Ensure service is running
if ! $SERVICE_WAS_ACTIVE; then
  echo "[test_e2e_systemd] Starting service..."
  systemctl start "$SERVICE_NAME"
  sleep 3
fi

# Verify service is running
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
  echo "[test_e2e_systemd] Error: Failed to start service"
  systemctl status "$SERVICE_NAME"
  exit 1
fi

echo "[test_e2e_systemd] Service is running"

# Get the configured IrisPenFolder using the venv
IRIS_FOLDER=$("$VENV_DIR/bin/python" -c "
from ipr_keyboard.config.manager import ConfigManager
cfg = ConfigManager.instance().get()
print(cfg.IrisPenFolder)
")

echo "[test_e2e_systemd] Configured IrisPenFolder: $IRIS_FOLDER"

# Ensure folder exists
mkdir -p "$IRIS_FOLDER"

# Create a test file
TEST_FILE="$IRIS_FOLDER/systemd_test_$(date +%s).txt"
echo "systemd end-to-end test content from test_e2e_systemd" > "$TEST_FILE"
echo "[test_e2e_systemd] Created test file: $TEST_FILE"

# Wait for processing
echo "[test_e2e_systemd] Waiting 5 seconds for file to be processed..."
sleep 5

# Show application log
echo "[test_e2e_systemd] Application log (last 20 lines):"
tail -n 20 "$PROJECT_DIR/logs/ipr_keyboard.log" 2>/dev/null || echo "Log file not found"

# Show systemd journal
echo "[test_e2e_systemd] systemd journal (last 10 lines):"
journalctl -u "$SERVICE_NAME" -n 10 --no-pager

# Restore original state
if ! $SERVICE_WAS_ACTIVE; then
  echo "[test_e2e_systemd] Stopping service (restoring original state)..."
  systemctl stop "$SERVICE_NAME"
fi

echo "[test_e2e_systemd] systemd-based end-to-end demo completed"
