#!/usr/bin/env bash

# Diagnostic script that checks the most common failure points:
# - Project + venv presence
# - Importing ipr_keyboard inside the venv
# - Config values (especially IrisPenFolder)
# - Mount/FS status for /mnt/irispen
# - Service presence / enabled / active
# - Log file presence + tail
# - journalctl for the service and bt_kb_send
# - Bluetooth helper availability (BluetoothKeyboard.is_available())
#
# Optional --test-file flag that:
# - Reads IrisPenFolder from the current config (using Python in the venv).
# - Creates a unique test file in that folder.
# - Prints the path + content.
# - Waits a bit so the service has a chance to process it.
# - Then shows logs/journal so you can see exactly what happened.

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/00_set_env.sh"

echo "[10] ipr_keyboard diagnostic script"

PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
VENV_DIR="$PROJECT_DIR/.venv"
IRISPEN_MOUNT="/mnt/irispen"
LOG_FILE="$PROJECT_DIR/logs/ipr_keyboard.log"
SERVICE_NAME="ipr_keyboard.service"
APP_USER="$IPR_USER"

TEST_FILE_MODE=0

###############################################################################
# Argument parsing
###############################################################################
while [[ $# -gt 0 ]]; do
  case "$1" in
    --test-file)
      TEST_FILE_MODE=1
      shift
      ;;
    *)
      echo "Usage: $0 [--test-file]"
      echo "  --test-file  Create a test file in the configured IrisPenFolder and then"
      echo "               show logs/journals so you can see how it was processed."
      exit 1
      ;;
  esac
done

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "[10][FATAL] Project directory not found: $PROJECT_DIR"
  exit 1
fi

echo "[10] Project directory: $PROJECT_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "[10][ERROR] Virtualenv not found at $VENV_DIR"
  echo "       Run as user '$APP_USER': $PROJECT_DIR/scripts/04_setup_venv.sh"
else
  echo "[10] Virtualenv found: $VENV_DIR"
fi

###############################################################################
# 0) Root vs non-root
###############################################################################
if [[ $EUID -ne 0 ]]; then
  echo "[10][WARN] Not running as root. Some checks (systemctl/journalctl) may be incomplete."
  echo "       Recommended: sudo $0 [--test-file]"
fi

###############################################################################
# 1) Basic Python import test inside venv
###############################################################################
echo
echo "[10] 1) Testing import of ipr_keyboard inside venv..."

if [[ -d "$VENV_DIR" ]]; then
  sudo -u "$APP_USER" env PROJECT_DIR="$PROJECT_DIR" VENV_DIR="$VENV_DIR" bash <<'EOF'
set -euo pipefail

cd "$PROJECT_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python - <<'PY'
import sys
print("Python executable:", sys.executable)
try:
    import ipr_keyboard
    print("Import ipr_keyboard: OK, version:", getattr(ipr_keyboard, "__version__", "unknown"))
except Exception as e:
    print("Import ipr_keyboard: FAILED ->", repr(e))
PY
EOF
else
  echo "[10][SKIP] Venv missing, skipping Python import test."
fi

###############################################################################
# 2) Config + IrisPenFolder check
###############################################################################
echo
echo "[10] 2) Checking AppConfig (IrisPenFolder, DeleteFiles, Logging)..."

if [[ -d "$VENV_DIR" ]]; then
  sudo -u "$APP_USER" env PROJECT_DIR="$PROJECT_DIR" VENV_DIR="$VENV_DIR" IRISPEN_MOUNT="$IRISPEN_MOUNT" bash <<'EOF'
set -euo pipefail

cd "$PROJECT_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python - <<'PY'
from pathlib import Path
from ipr_keyboard.config.manager import ConfigManager

cfg_mgr = ConfigManager.instance()
cfg = cfg_mgr.get()
print("Current config:", cfg.to_dict())

folder = Path(cfg.IrisPenFolder)
print("IrisPenFolder path exists:", folder.exists())
print("IrisPenFolder path:", folder)

if not folder.exists():
    print("HINT: Ensure your IrisPen USB is mounted and IrisPenFolder is set correctly.")
PY
EOF
else
  echo "[10][SKIP] Venv missing, cannot inspect config."
fi

###############################################################################
# 3) Mount status of IrisPenFolder (default /mnt/irispen)
###############################################################################
echo
echo "[10] 3) Checking mount status for $IRISPEN_MOUNT ..."

if [[ -d "$IRISPEN_MOUNT" ]]; then
  echo "[10] $IRISPEN_MOUNT exists."
else
  echo "[10][ERROR] $IRISPEN_MOUNT does not exist."
  echo "       Run: sudo mkdir -p $IRISPEN_MOUNT and ensure it is mounted."
fi

echo "[10] Current mounts involving $IRISPEN_MOUNT:"
mount | grep " $IRISPEN_MOUNT " || echo "  (no explicit mount found for $IRISPEN_MOUNT)"

echo "[10] Disk usage for $IRISPEN_MOUNT (if accessible):"
df -h "$IRISPEN_MOUNT" || echo "  (df failed; mount may not be available)"

###############################################################################
# 4) Systemd service presence & status
###############################################################################
echo
echo "[10] 4) Checking systemd service $SERVICE_NAME ..."

SERVICE_INSTALLED=0
SERVICE_ACTIVE=0

if command -v systemctl >/dev/null 2>&1; then
  if systemctl list-unit-files | grep -q "^$SERVICE_NAME"; then
    SERVICE_INSTALLED=1
    echo "[10] Service $SERVICE_NAME is installed."

    if systemctl is-enabled --quiet "$SERVICE_NAME"; then
      echo "[10] Service is enabled (will start at boot)."
    else
      echo "[10][WARN] Service is NOT enabled."
      echo "       Enable with: sudo systemctl enable $SERVICE_NAME"
    fi

    if systemctl is-active --quiet "$SERVICE_NAME"; then
      SERVICE_ACTIVE=1
      echo "[10] Service is currently ACTIVE."
    else
      echo "[10][WARN] Service is currently INACTIVE."
      echo "       Start with: sudo systemctl start $SERVICE_NAME"
    fi
  else
    echo "[10][ERROR] Service $SERVICE_NAME is not installed."
    echo "       Run: sudo $PROJECT_DIR/scripts/05_install_service.sh"
  fi
else
  echo "[10][WARN] systemctl not available; cannot check service status."
fi

###############################################################################
# 4b) Optional: create a test file in IrisPenFolder (if --test-file)
###############################################################################
if [[ "$TEST_FILE_MODE" -eq 1 ]]; then
  echo
  echo "[10] 4b) --test-file enabled: creating a test file in configured IrisPenFolder..."

  if [[ "$SERVICE_INSTALLED" -eq 0 ]]; then
    echo "[10][WARN] Service is not installed; the test file may not be processed."
  elif [[ "$SERVICE_ACTIVE" -eq 0 ]]; then
    echo "[10][WARN] Service is not active; start it to process the test file:"
    echo "       sudo systemctl start $SERVICE_NAME"
  fi

  if [[ -d "$VENV_DIR" ]]; then
    sudo -u "$APP_USER" env PROJECT_DIR="$PROJECT_DIR" VENV_DIR="$VENV_DIR" bash <<'EOF'
set -euo pipefail

cd "$PROJECT_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python - <<'PY'
from datetime import datetime
from pathlib import Path
from ipr_keyboard.config.manager import ConfigManager

cfg_mgr = ConfigManager.instance()
cfg = cfg_mgr.get()
folder = Path(cfg.IrisPenFolder)

print("Using IrisPenFolder:", folder)

if not folder.exists():
    print("[10][ERROR] IrisPenFolder does not exist:", folder)
else:
    folder.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_file = folder / f"diagnostic_test_{ts}.txt"
    content = f"Diagnostic test file at {ts}"
    test_file.write_text(content, encoding="utf-8")
    print("[10] Created test file:", test_file)
    print("[10] Content:", content)
PY
EOF
  else
    echo "[10][ERROR] Venv missing; cannot create test file via config."
  fi

  echo "[10] Waiting 10 seconds to give the service a chance to process the file (if running)..."
  sleep 10
fi

###############################################################################
# 5) Log file presence and tail
###############################################################################
echo
echo "[10] 5) Checking log file at $LOG_FILE ..."

if [[ -f "$LOG_FILE" ]]; then
  echo "[10] Log file exists."
  echo "----- TAIL OF $LOG_FILE -----"
  tail -n 50 "$LOG_FILE" || true
  echo "-----------------------------"
else
  echo "[10][WARN] Log file does not exist yet."
  echo "       Service may not have started or may not have logging enabled."
fi

###############################################################################
# 6) journalctl for service and bt_kb_send
###############################################################################
echo
echo "[10] 6) Checking journal for $SERVICE_NAME and bt_kb_send ..."

if command -v journalctl >/dev/null 2>&1; then
  echo "----- journalctl -u $SERVICE_NAME (last 30 lines) -----"
  journalctl -u "$SERVICE_NAME" -n 30 --no-pager || echo "  (no entries yet)"
  echo "------------------------------------------------------"

  echo "----- journalctl -t bt_kb_send (last 10 lines) -----"
  journalctl -t bt_kb_send -n 10 --no-pager || echo "  (no entries yet)"
  echo "----------------------------------------------------"
else
  echo "[10][WARN] journalctl not available; cannot inspect service logs."
fi

###############################################################################
# 7) Bluetooth helper availability (BluetoothKeyboard.is_available)
###############################################################################
echo
echo "[10] 7) Testing BluetoothKeyboard.is_available() ..."

if [[ -d "$VENV_DIR" ]]; then
  sudo -u "$APP_USER" env PROJECT_DIR="$PROJECT_DIR" VENV_DIR="$VENV_DIR" bash <<'EOF'
set -euo pipefail

cd "$PROJECT_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python - <<'PY'
from ipr_keyboard.bluetooth.keyboard import BluetoothKeyboard

kb = BluetoothKeyboard()
available = kb.is_available()
print("Bluetooth helper available:", available)
if not available:
    print("HINT: Ensure /usr/local/bin/bt_kb_send exists and is executable.")
PY
EOF
else
  echo "[10][SKIP] Venv missing, cannot test BluetoothKeyboard."
fi

###############################################################################
# 8) Summary
###############################################################################
echo
echo "[10] Diagnostic summary (manual checklist):"
echo "  - If venv is missing: run 04_setup_venv.sh as user '$APP_USER'."
echo "  - If IrisPenFolder does not exist or is not mounted:"
echo "      * Use 06_setup_irispen_mount.sh to set up /mnt/irispen."
echo "  - If service is not installed:"
echo "      * Run 05_install_service.sh as root."
echo "  - If service is inactive or failing:"
echo "      * Check systemctl status $SERVICE_NAME and journalctl output above."
echo "  - If Bluetooth helper is unavailable:"
echo "      * Ensure /usr/local/bin/bt_kb_send exists, is executable, and does real HID."
echo "  - If --test-file was used:"
echo "      * Check whether the created diagnostic file disappears and how it is logged."

echo
echo "[10] Diagnostics finished."
