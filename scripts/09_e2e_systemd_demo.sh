#!/usr/bin/env bash

# systemd-based end-to-end demo.
# This version:
# - Uses the existing ipr_keyboard.service.
# - Adjusts config using your uv venv as user meibye.
# - Creates a test file in /mnt/irispen.
# - Waits for the service to process it.
# - Shows both the app log and relevant journalctl entries.
# - Restores the service’s original active/inactive state.

set -euo pipefail

echo "[09] Running systemd-based end-to-end demo for ipr_keyboard"

if [[ $EUID -ne 0 ]]; then
  echo "Please run this as root: sudo $0"
  exit 1
fi

PROJECT_DIR="/home/meibye/dev/ipr-keyboard"
VENV_DIR="$PROJECT_DIR/.venv"
IRISPEN_MOUNT="/mnt/irispen"
LOG_FILE="$PROJECT_DIR/logs/ipr_keyboard.log"
SERVICE_NAME="ipr_keyboard.service"
APP_USER="meibye"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Project directory not found: $PROJECT_DIR"
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Virtualenv not found at $VENV_DIR"
  echo "Run: sudo -u $APP_USER $PROJECT_DIR/scripts/04_setup_venv.sh"
  exit 1
fi

if ! systemctl list-unit-files | grep -q "^$SERVICE_NAME"; then
  echo "Systemd service $SERVICE_NAME is not installed."
  echo "Run: sudo $PROJECT_DIR/scripts/05_install_service.sh"
  exit 1
fi

echo "[09] Using project dir: $PROJECT_DIR"
echo "[09] Using venv:        $VENV_DIR"
echo "[09] IrisPen mount:     $IRISPEN_MOUNT"
echo "[09] Service:           $SERVICE_NAME"
echo "[09] App user:          $APP_USER"

###############################################################################
# 1) Ensure IrisPenFolder exists and config is set (as user 'meibye')
###############################################################################
echo
echo "[09] 1) Ensuring IrisPenFolder directory and config..."

mkdir -p "$IRISPEN_MOUNT"

sudo -u "$APP_USER" env PROJECT_DIR="$PROJECT_DIR" VENV_DIR="$VENV_DIR" IRISPEN_MOUNT="$IRISPEN_MOUNT" bash <<'EOF'
set -euo pipefail

cd "$PROJECT_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python - <<'PY'
import os
from ipr_keyboard.config.manager import ConfigManager

cfg_mgr = ConfigManager.instance()
folder = os.environ["IRISPEN_MOUNT"]
cfg = cfg_mgr.update(
    IrisPenFolder=folder,
    DeleteFiles=True,
    Logging=True,
)
print("Config set for systemd E2E:", cfg.to_dict())
PY
EOF

###############################################################################
# Record previous service state so we can restore it
###############################################################################
echo
echo "[09] 2) Checking previous service state..."

PRE_WAS_ACTIVE=0
if systemctl is-active --quiet "$SERVICE_NAME"; then
  PRE_WAS_ACTIVE=1
  echo "[09] Service was active before demo."
else
  echo "[09] Service was inactive before demo."
fi

cleanup() {
  echo
  echo "[09] Cleanup: restoring service state..."
  if [[ "$PRE_WAS_ACTIVE" -eq 1 ]]; then
    echo "[09] Service was previously active; leaving it running."
  else
    echo "[09] Service was previously inactive; stopping it now."
    systemctl stop "$SERVICE_NAME" || true
  fi
  echo "[09] Cleanup finished."
}
trap cleanup EXIT

###############################################################################
# 3) Restart service for a clean demo
###############################################################################
echo
echo "[09] 3) Restarting $SERVICE_NAME for this demo..."

systemctl daemon-reload
systemctl restart "$SERVICE_NAME"

echo "[09] Waiting a few seconds for service to settle..."
sleep 5

if systemctl is-active --quiet "$SERVICE_NAME"; then
  echo "[09] Service is active."
else
  echo "[09] ERROR: Service is not active after restart."
  systemctl status "$SERVICE_NAME" --no-pager || true
  exit 1
fi

###############################################################################
# 4) Create test file in IrisPenFolder
###############################################################################
echo
echo "[09] 4) Creating test file in $IRISPEN_MOUNT ..."

TEST_FILE="$IRISPEN_MOUNT/e2e_systemd_$(date +%Y%m%d_%H%M%S).txt"
TEST_CONTENT="This is a systemd E2E demo text from ipr_keyboard at $(date)."

echo "$TEST_CONTENT" > "$TEST_FILE"

echo "[09] Created test file: $TEST_FILE"
echo "[09] Content: $TEST_CONTENT"

###############################################################################
# 5) Wait for service to detect and process file
###############################################################################
echo
echo "[09] 5) Waiting up to 20 seconds for the service to process the file..."

for i in $(seq 1 20); do
  if [[ ! -f "$TEST_FILE" ]]; then
    echo "[09] File has been deleted (DeleteFiles=True) - likely processed."
    break
  fi
  sleep 1
done

if [[ -f "$TEST_FILE" ]]; then
  echo "[09] WARNING: File still exists after 20 seconds."
  echo "       The service may not be detecting the folder or may have failed."
fi

###############################################################################
# 6) Show log tail and journalctl
###############################################################################
echo
echo "[09] 6) Showing tail of the app log (if present)..."

if [[ -f "$LOG_FILE" ]]; then
  echo "----- TAIL OF $LOG_FILE -----"
  tail -n 50 "$LOG_FILE" || true
  echo "-----------------------------"
else
  echo "[09] No log file found at $LOG_FILE"
fi

echo
echo "[09] Showing last 30 lines of journal for $SERVICE_NAME..."
journalctl -u "$SERVICE_NAME" -n 30 --no-pager || true

echo
echo "[09] Showing last 10 lines of journal for bt_kb_send tag (helper)..."
journalctl -t bt_kb_send -n 10 --no-pager || true

echo
echo "[09] Systemd E2E demo finished."
echo "     If your Bluetooth helper is real (not placeholder), the text should"
echo "     have been typed on the paired PC. With the placeholder helper, see"
echo "     the 'Would send over BT:' lines above."
