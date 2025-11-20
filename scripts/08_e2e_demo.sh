#!/usr/bin/env bash

# An end-to-end demo script that:
# - Starts ipr_keyboard.main using your uv venv
# - Ensures config points to /mnt/irispen
# - Creates a test file in /mnt/irispen
# - Waits for the app to process it (including Bluetooth send + delete if enabled)
# - Shows you the tail of the log
# - Cleans up the background process

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
IRISPEN_MOUNT="/mnt/irispen"
LOG_FILE="$PROJECT_DIR/logs/ipr_keyboard.log"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Project directory not found: $PROJECT_DIR"
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Virtualenv not found at $VENV_DIR"
  echo "Run: ./scripts/04_setup_venv.sh"
  exit 1
fi

cd "$PROJECT_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

###############################################################################
# 1) Ensure IrisPenFolder exists and config is set
###############################################################################
echo
echo "[08] 1) Ensuring IrisPenFolder directory and config..."

mkdir -p "$IRISPEN_MOUNT"

python - <<PY
from ipr_keyboard.config.manager import ConfigManager

cfg_mgr = ConfigManager.instance()
cfg = cfg_mgr.update(
    IrisPenFolder="$IRISPEN_MOUNT",
    DeleteFiles=True,
    Logging=True,
)
print("Config set for E2E demo:", cfg.to_dict())
PY

###############################################################################
# 2) Start ipr_keyboard.main in background
###############################################################################
echo
echo "[08] 2) Starting ipr_keyboard.main in background..."

python -m ipr_keyboard.main &
APP_PID=$!
echo "[08] ipr_keyboard.main PID: $APP_PID"

cleanup() {
  echo
  echo "[08] Cleaning up: stopping ipr_keyboard.main (PID $APP_PID)..."
  if kill -0 "$APP_PID" 2>/dev/null; then
    kill "$APP_PID" || true
    sleep 1
    if kill -0 "$APP_PID" 2>/dev/null; then
      echo "[08] Force killing PID $APP_PID"
      kill -9 "$APP_PID" || true
    fi
  fi
  echo "[08] Cleanup done."
}
trap cleanup EXIT

echo "[08] Waiting 5 seconds for app to start..."
sleep 5

###############################################################################
# 3) Create test file in IrisPenFolder
###############################################################################
echo
echo "[08] 3) Creating test file in $IRISPEN_MOUNT ..."

TEST_FILE="$IRISPEN_MOUNT/e2e_demo_$(date +%Y%m%d_%H%M%S).txt"
TEST_CONTENT="This is an E2E demo text from ipr_keyboard at $(date)."

echo "$TEST_CONTENT" > "$TEST_FILE"

echo "[08] Created test file: $TEST_FILE"
echo "[08] Content: $TEST_CONTENT"

###############################################################################
# 4) Wait for app to detect and process file
###############################################################################
echo
echo "[08] 4) Waiting up to 20 seconds for the app to process the file..."

# Just sleep; the app loop polls the folder once per second
for i in $(seq 1 20); do
  if [[ ! -f "$TEST_FILE" ]]; then
    echo "[08] File has been deleted (DeleteFiles=True) - likely processed."
    break
  fi
  sleep 1
done

if [[ -f "$TEST_FILE" ]]; then
  echo "[08] WARNING: File still exists after 20 seconds."
  echo "       The app may not be running correctly or not detecting the folder."
fi

###############################################################################
# 5) Show log tail
###############################################################################
echo
echo "[08] 5) Showing tail of the log (if present)..."

if [[ -f "$LOG_FILE" ]]; then
  echo "----- TAIL OF $LOG_FILE -----"
  tail -n 50 "$LOG_FILE" || true
  echo "-----------------------------"
else
  echo "[08] No log file found at $LOG_FILE"
fi

echo
echo "[08] End-to-end demo finished."
echo "     If your Bluetooth helper is real (not placeholder), the text should"
echo "     have been typed on the paired PC. With the placeholder helper, check"
echo "     'journalctl -t bt_kb_send' for the 'Would send over BT:' entries."
