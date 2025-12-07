#!/usr/bin/env bash
#
# ipr-keyboard Diagnostic Script
#
# Purpose:
#   Runs a comprehensive set of diagnostic checks for the ipr-keyboard system.
#   Identifies common installation, configuration, and runtime issues.
#
# Prerequisites:
#   - Environment variables set (sources env_set_variables.sh)
#   - Project must be installed
#
# Usage:
#   ./scripts/10_diagnose_failure.sh
#   ./scripts/10_diagnose_failure.sh --test-file
#
# Note:
#   Can be run as user or root. Does not modify system state.

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/env_set_variables.sh"

echo "======================================"
echo "[diag_troubleshoot] ipr_keyboard Diagnostic Tool"
echo "======================================"
echo

# Parse arguments
TEST_FILE_MODE=false
if [[ "${1:-}" == "--test-file" ]]; then
  TEST_FILE_MODE=true
  echo "[diag_troubleshoot] Test file mode enabled"
  echo
fi

PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
VENV_DIR="$PROJECT_DIR/.venv"

echo "[diag_troubleshoot] Checking project directory..."
if [[ -d "$PROJECT_DIR" ]]; then
  echo "✓ Project directory exists: $PROJECT_DIR"
else
  echo "✗ Project directory NOT found: $PROJECT_DIR"
  exit 1
fi
echo

echo "[diag_troubleshoot] Checking virtual environment..."
if [[ -d "$VENV_DIR" ]]; then
  echo "✓ Virtual environment exists: $VENV_DIR"
else
  echo "✗ Virtual environment NOT found: $VENV_DIR"
  echo "  Run: ./scripts/sys_setup_venv.sh"
  exit 1
fi
echo

cd "$PROJECT_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "[diag_troubleshoot] Testing Python imports..."
if python -c "import ipr_keyboard" 2>/dev/null; then
  echo "✓ ipr_keyboard module can be imported"
else
  echo "✗ Failed to import ipr_keyboard module"
  python -c "import ipr_keyboard" 2>&1 || true
fi
echo

echo "[diag_troubleshoot] Checking configuration..."
python -c "
from ipr_keyboard.config.manager import ConfigManager
from ipr_keyboard.utils.helpers import config_path
import json

cfg_path = config_path()
print(f'Config file: {cfg_path}')
if cfg_path.exists():
    print('✓ Config file exists')
    with open(cfg_path) as f:
        config = json.load(f)
    print('Config contents:')
    for k, v in config.items():
        print(f'  {k}: {v}')
else:
    print('✗ Config file does NOT exist')

try:
    mgr = ConfigManager.instance()
    cfg = mgr.get()
    print(f'✓ Config manager loaded successfully')
    print(f'  IrisPenFolder: {cfg.IrisPenFolder}')
    print(f'  DeleteFiles: {cfg.DeleteFiles}')
    print(f'  Logging: {cfg.Logging}')
    print(f'  MaxFileSize: {cfg.MaxFileSize}')
    print(f'  LogPort: {cfg.LogPort}')
except Exception as e:
    print(f'✗ Config manager failed: {e}')
"
echo

echo "[diag_troubleshoot] Checking IrisPenFolder mount point..."
IRIS_FOLDER=$(python -c "
from ipr_keyboard.config.manager import ConfigManager
cfg = ConfigManager.instance().get()
print(cfg.IrisPenFolder)
" 2>/dev/null || echo "/mnt/irispen")

echo "IrisPenFolder: $IRIS_FOLDER"
if [[ -d "$IRIS_FOLDER" ]]; then
  echo "✓ Directory exists"
  echo "  Permissions: $(ls -ld "$IRIS_FOLDER")"
  echo "  Files: $(ls -1 "$IRIS_FOLDER" 2>/dev/null | wc -l)"
  if mountpoint -q "$IRIS_FOLDER" 2>/dev/null; then
    echo "✓ Is a mount point"
    echo "  Mount info: $(mount | grep "$IRIS_FOLDER")"
  else
    echo "⚠ Not a mount point (may be regular directory)"
  fi
else
  echo "✗ Directory does NOT exist"
fi
echo

echo "[diag_troubleshoot] Checking systemd service..."
SERVICE_NAME="ipr_keyboard.service"
if systemctl list-unit-files 2>/dev/null | grep -q "$SERVICE_NAME"; then
  echo "✓ Service is installed"
  if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "✓ Service is enabled"
  else
    echo "⚠ Service is NOT enabled"
  fi
  if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "✓ Service is active (running)"
  else
    echo "⚠ Service is NOT active"
  fi
  echo "  Status:"
  systemctl status "$SERVICE_NAME" --no-pager -l -n 0 2>&1 || true
else
  echo "⚠ Service is NOT installed"
  echo "  Run: sudo ./scripts/svc_install_systemd.sh"
fi
echo

echo "[diag_troubleshoot] Checking log file..."
LOG_FILE="$PROJECT_DIR/logs/ipr_keyboard.log"
if [[ -f "$LOG_FILE" ]]; then
  echo "✓ Log file exists: $LOG_FILE"
  echo "  Size: $(du -h "$LOG_FILE" | cut -f1)"
  echo "  Last 10 lines:"
  tail -n 10 "$LOG_FILE" | sed 's/^/    /'
else
  echo "⚠ Log file does NOT exist: $LOG_FILE"
fi
echo

echo "[diag_troubleshoot] Checking systemd journal..."
if command -v journalctl >/dev/null 2>&1; then
  echo "Last 10 journal entries for $SERVICE_NAME:"
  journalctl -u "$SERVICE_NAME" -n 10 --no-pager 2>&1 || echo "  (no entries or permission denied)"
else
  echo "⚠ journalctl not available"
fi
echo

echo "[diag_troubleshoot] Checking Bluetooth helper..."

echo "[diag_troubleshoot] Checking Bluetooth backend and services..."
BACKEND=$(python -c "from ipr_keyboard.config.manager import ConfigManager; cfg = ConfigManager.instance().get(); print(getattr(cfg, 'KeyboardBackend', 'uinput'))" 2>/dev/null || echo "uinput")
echo "Configured backend: $BACKEND"

if [[ "$BACKEND" == "ble" ]]; then
  SERVICE="bt_hid_ble.service"
else
  SERVICE="bt_hid_uinput.service"
fi

for SVC in "$SERVICE" "bt_hid_agent.service"; do
  if systemctl list-unit-files 2>/dev/null | grep -q "$SVC"; then
    echo "✓ $SVC is installed"
    if systemctl is-enabled --quiet "$SVC" 2>/dev/null; then
      echo "✓ $SVC is enabled"
    else
      echo "⚠ $SVC is NOT enabled"
    fi
    if systemctl is-active --quiet "$SVC" 2>/dev/null; then
      echo "✓ $SVC is active (running)"
    else
      echo "⚠ $SVC is NOT active"
    fi
    echo "  Status:"
    systemctl status "$SVC" --no-pager -l -n 0 2>&1 || true
  else
    echo "⚠ $SVC is NOT installed"
    echo "  Run: sudo ./scripts/ble_install_helper.sh"
  fi
done

echo
python -c "
from ipr_keyboard.bluetooth.keyboard import BluetoothKeyboard
kb = BluetoothKeyboard()
if kb.is_available():
    print('✓ Bluetooth helper is available')
else:
    print('⚠ Bluetooth helper is NOT available')
    print('  Expected at: /usr/local/bin/bt_kb_send')
    print('  Run: sudo ./scripts/ble_install_helper.sh')
"
echo

# Test file mode
if $TEST_FILE_MODE; then
  echo "[diag_troubleshoot] TEST FILE MODE: Creating test file..."
  echo
  
  mkdir -p "$IRIS_FOLDER"
  
  TEST_FILE="$IRIS_FOLDER/diagnostic_test_$(date +%s).txt"
  echo "Diagnostic test content from script 10" > "$TEST_FILE"
  echo "Created test file: $TEST_FILE"
  echo
  
  echo "Waiting 5 seconds for service to process..."
  sleep 5
  echo
  
  echo "Log tail (last 20 lines):"
  tail -n 20 "$LOG_FILE" 2>/dev/null | sed 's/^/  /' || echo "  Log file not found"
  echo
  
  echo "Journal tail (last 10 lines):"
  journalctl -u "$SERVICE_NAME" -n 10 --no-pager 2>&1 | sed 's/^/  /' || echo "  (no entries)"
  echo
  
  if [[ -f "$TEST_FILE" ]]; then
    echo "⚠ Test file still exists (DeleteFiles may be false or processing failed)"
  else
    echo "✓ Test file was deleted (successfully processed)"
  fi
fi

echo "======================================"
echo "[diag_troubleshoot] Diagnostic complete"
echo "======================================"
