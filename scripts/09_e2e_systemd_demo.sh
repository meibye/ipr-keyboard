#!/usr/bin/env bash
#
# End-to-End systemd Demo Script
#
# Purpose:
#   Demonstrates the complete ipr-keyboard workflow using the systemd service.
#   Tests the production deployment scenario.
#
# Workflow:
#   1. Records the current service state
#   2. Ensures the service is started
#   3. Creates a test file in the monitored directory
#   4. Waits for the service to process it
#   5. Shows both application log and systemd journal entries
#   6. Restores the original service state
#
# Prerequisites:
#   - Environment variables set (sources 00_set_env.sh)
#   - systemd service must be installed
#   - Must be run as root (to control systemd service)
#
# Usage:
#   sudo ./scripts/09_e2e_systemd_demo.sh
#
# Note:
#   Automatically restores the service's original active/inactive state.

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/00_set_env.sh"

echo "[09] Running systemd-based end-to-end demo for ipr_keyboard"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

SERVICE_NAME="ipr_keyboard.service"
PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
VENV_DIR="$PROJECT_DIR/.venv"

# Check if service is installed
if ! systemctl list-unit-files | grep -q "$SERVICE_NAME"; then
  echo "[09] Error: Service $SERVICE_NAME is not installed"
  echo "[09] Please run 05_install_service.sh first"
  exit 1
fi

# Record current service state
SERVICE_WAS_ACTIVE=false
if systemctl is-active --quiet "$SERVICE_NAME"; then
  SERVICE_WAS_ACTIVE=true
  echo "[09] Service is currently active"
else
  echo "[09] Service is currently inactive"
fi

# Ensure service is running
if ! $SERVICE_WAS_ACTIVE; then
  echo "[09] Starting service..."
  systemctl start "$SERVICE_NAME"
  sleep 3
fi

# Verify service is running
if ! systemctl is-active --quiet "$SERVICE_NAME"; then
  echo "[09] Error: Failed to start service"
  systemctl status "$SERVICE_NAME"
  exit 1
fi

echo "[09] Service is running"

# Get the configured IrisPenFolder using the venv
IRIS_FOLDER=$("$VENV_DIR/bin/python" -c "
from ipr_keyboard.config.manager import ConfigManager
cfg = ConfigManager.instance().get()
print(cfg.IrisPenFolder)
")

echo "[09] Configured IrisPenFolder: $IRIS_FOLDER"

# Ensure folder exists
mkdir -p "$IRIS_FOLDER"

# Create a test file
TEST_FILE="$IRIS_FOLDER/systemd_test_$(date +%s).txt"
echo "systemd end-to-end test content from script 09" > "$TEST_FILE"
echo "[09] Created test file: $TEST_FILE"

# Wait for processing
echo "[09] Waiting 5 seconds for file to be processed..."
sleep 5

# Show application log
echo "[09] Application log (last 20 lines):"
tail -n 20 "$PROJECT_DIR/logs/ipr_keyboard.log" 2>/dev/null || echo "Log file not found"

# Show systemd journal
echo "[09] systemd journal (last 10 lines):"
journalctl -u "$SERVICE_NAME" -n 10 --no-pager

# Restore original state
if ! $SERVICE_WAS_ACTIVE; then
  echo "[09] Stopping service (restoring original state)..."
  systemctl stop "$SERVICE_NAME"
fi

echo "[09] systemd-based end-to-end demo completed"
