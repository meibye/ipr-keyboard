#!/usr/bin/env bash
#
# ipr-keyboard End-to-End Demo Script
#
# Purpose:
#   Demonstrates the full workflow of the ipr-keyboard application in foreground mode.
#   Tests file detection, reading, Bluetooth forwarding, and logging.
#
# Workflow:
#   1. Starts ipr_keyboard in the background
#   2. Creates a test file in the monitored directory
#   3. Waits for the application to process it
#   4. Shows the application log
#   5. Cleans up the background process
#
# Prerequisites:
#   - Must NOT be run as root
#   - Python venv must be set up
#   - Environment variables set (sources env_set_variables.sh)
#   - IrisPenFolder configured and accessible
#
# Usage:
#   ./scripts/test_e2e_demo.sh
#
# Note:
#   The test file will be deleted if DeleteFiles is enabled in config.
#
# category: Testing
# purpose: End-to-end test of ipr-keyboard in foreground mode
# sudo: no

set -eo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/env_set_variables.sh"

echo "[test_e2e_demo] Running end-to-end demo for ipr_keyboard"

if [[ $EUID -eq 0 ]]; then
  echo "Do NOT run this as root. Run as user '$IPR_USER'."
  exit 1
fi

PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
VENV_DIR="$PROJECT_DIR/.venv"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Project directory not found: $PROJECT_DIR"
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Virtual environment not found: $VENV_DIR"
  echo "Please run ./scripts/sys_setup_venv.sh first."
  exit 1
fi

cd "$PROJECT_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Start the application in the background
echo "[test_e2e_demo] Starting ipr_keyboard in background..."
python -m ipr_keyboard.main > /tmp/ipr_e2e_demo.log 2>&1 &
APP_PID=$!

echo "[test_e2e_demo] Application started with PID $APP_PID"

# Give it time to start
sleep 3

# Check if it's still running
if ! kill -0 $APP_PID 2>/dev/null; then
  echo "[test_e2e_demo] Error: Application failed to start"
  cat /tmp/ipr_e2e_demo.log
  exit 1
fi

echo "[test_e2e_demo] Application is running"

# Get the configured IrisPenFolder
IRIS_FOLDER=$(python -c "
from ipr_keyboard.config.manager import ConfigManager
cfg = ConfigManager.instance().get()
print(cfg.IrisPenFolder)
")

echo "[test_e2e_demo] Configured IrisPenFolder: $IRIS_FOLDER"

# Create the folder if it doesn't exist
mkdir -p "$IRIS_FOLDER"

# Create a test file
TEST_FILE="$IRIS_FOLDER/e2e_test_$(date +%s).txt"
echo "End-to-end test content from test_e2e_demo" > "$TEST_FILE"
echo "[test_e2e_demo] Created test file: $TEST_FILE"

# Wait for processing
echo "[test_e2e_demo] Waiting 5 seconds for file to be processed..."
sleep 5

# Show the log
echo "[test_e2e_demo] Log output:"
tail -n 20 logs/ipr_keyboard.log || echo "Log file not found"

# Clean up
echo "[test_e2e_demo] Stopping application (PID $APP_PID)..."
kill $APP_PID 2>/dev/null || true
wait $APP_PID 2>/dev/null || true

echo "[test_e2e_demo] End-to-end demo completed"
