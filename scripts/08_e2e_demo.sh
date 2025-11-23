# ipr-keyboard End-to-End Demo Script
#
# Purpose:
#
#   Demonstrates the full workflow of the ipr-keyboard application in foreground mode.
#   Tests file detection, reading, Bluetooth forwarding, and logging.
#
# Prerequisites:
#   - Must NOT be run as root
#   - Python venv must be set up
#   - Environment variables set (sources 00_set_env.sh)
#   - IrisPenFolder configured and accessible
#
# Usage:
#   ./scripts/08_e2e_demo.sh
#
# Note:
#   This script runs the app in foreground (not as a service).
#
set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/00_set_env.sh"
echo "[08] Running end-to-end demo for ipr_keyboard"

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
  echo "Please run 04_setup_venv.sh first."
  exit 1
fi
cd "$PROJECT_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Start the application in the background
echo "[08] Starting ipr_keyboard in background..."
python -m ipr_keyboard.main > /tmp/ipr_e2e_demo.log 2>&1 &
APP_PID=$!
echo "[08] Application started with PID $APP_PID"

# Give it time to start
sleep 3

# Check if it's still running
if ! kill -0 $APP_PID 2>/dev/null; then
  echo "[08] Error: Application failed to start"
  cat /tmp/ipr_e2e_demo.log
  exit 1
fi
echo "[08] Application is running"

# Get the configured IrisPenFolder
IRIS_FOLDER=$(python -c "
from ipr_keyboard.config.manager import ConfigManager
cfg = ConfigManager.instance().get()
print(cfg.IrisPenFolder)
")
echo "[08] Configured IrisPenFolder: $IRIS_FOLDER"

# Create the folder if it doesn't exist
mkdir -p "$IRIS_FOLDER"

# Create a test file
TEST_FILE="$IRIS_FOLDER/e2e_test_$(date +%s).txt"
echo "End-to-end test content from script 08" > "$TEST_FILE"
echo "[08] Created test file: $TEST_FILE"
# Wait for processing
echo "[08] Waiting 5 seconds for file to be processed..."
sleep 5

# Show the log
echo "[08] Log output:"
tail -n 20 logs/ipr_keyboard.log || echo "Log file not found"

# Clean up
echo "[08] Stopping application (PID $APP_PID)..."
kill $APP_PID 2>/dev/null || true
wait $APP_PID 2>/dev/null || true
echo "[08] End-to-end demo completed"
#!/usr/bin/env bash
#
# End-to-End Demo Script
#
# Purpose:
#   Demonstrates the complete ipr-keyboard workflow by starting the application,
#   creating a test file, and verifying it's processed correctly.
#
# Workflow:
#   1. Starts ipr_keyboard in the background
#   2. Ensures config points to /mnt/irispen
#   3. Creates a test file in the monitored directory
#   4. Waits for the application to process it
#   5. Shows the application log
#   6. Cleans up the background process
#
# Prerequisites:
#   - Environment variables set (sources 00_set_env.sh)
#   - Virtual environment must be set up
#   - Must NOT be run as root
#   - /mnt/irispen should exist or be configured
#
# Usage:
#   ./scripts/08_e2e_demo.sh
#
# Note:
#   The test file will be deleted if DeleteFiles is enabled in config.

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/00_set_env.sh"

echo "[08] Running end-to-end demo for ipr_keyboard"

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
  echo "Please run 04_setup_venv.sh first."
  exit 1
fi

cd "$PROJECT_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Start the application in the background
echo "[08] Starting ipr_keyboard in background..."
python -m ipr_keyboard.main > /tmp/ipr_e2e_demo.log 2>&1 &
APP_PID=$!

echo "[08] Application started with PID $APP_PID"

# Give it time to start
sleep 3

# Check if it's still running
if ! kill -0 $APP_PID 2>/dev/null; then
  echo "[08] Error: Application failed to start"
  cat /tmp/ipr_e2e_demo.log
  exit 1
fi

echo "[08] Application is running"

# Get the configured IrisPenFolder
IRIS_FOLDER=$(python -c "
from ipr_keyboard.config.manager import ConfigManager
cfg = ConfigManager.instance().get()
print(cfg.IrisPenFolder)
")

echo "[08] Configured IrisPenFolder: $IRIS_FOLDER"

# Create the folder if it doesn't exist
mkdir -p "$IRIS_FOLDER"

# Create a test file
TEST_FILE="$IRIS_FOLDER/e2e_test_$(date +%s).txt"
echo "End-to-end test content from script 08" > "$TEST_FILE"
echo "[08] Created test file: $TEST_FILE"

# Wait for processing
echo "[08] Waiting 5 seconds for file to be processed..."
sleep 5

# Show the log
echo "[08] Log output:"
tail -n 20 logs/ipr_keyboard.log || echo "Log file not found"

# Clean up
echo "[08] Stopping application (PID $APP_PID)..."
kill $APP_PID 2>/dev/null || true
wait $APP_PID 2>/dev/null || true

echo "[08] End-to-end demo completed"
