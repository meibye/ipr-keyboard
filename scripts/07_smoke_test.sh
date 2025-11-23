
#!/usr/bin/env bash
#
# ipr-keyboard Smoke Test Script
#
# Purpose:
#   Runs basic functionality tests for all major components.
#   Verifies installation and setup.
#
# Usage:
#   ./scripts/07_smoke_test.sh
#
# Prerequisites:
#   - Must NOT be run as root
#   - Python venv must be set up
#   - Environment variables set (sources 00_set_env.sh)
#
# Note:
#   Should be run after setup scripts and before installing as a service.

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/00_set_env.sh"

# Load environment variables
echo "[07] Running smoke tests for ipr_keyboard"

echo "[07] Running smoke tests for ipr_keyboard"

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

echo "[07] Testing imports..."
python -c "from ipr_keyboard.config.manager import ConfigManager; print('[07] ✓ Imports work')"

echo "[07] Testing config manager..."
python -c "
from ipr_keyboard.config.manager import ConfigManager
from pathlib import Path
mgr = ConfigManager()
cfg = mgr.get()
print(f'[07] ✓ Config loaded: IrisPenFolder={cfg.IrisPenFolder}')
"

echo "[07] Testing logger..."
python -c "
from ipr_keyboard.logging.logger import get_logger
logger = get_logger()
logger.info('[07] Test log message from smoke test')
print('[07] ✓ Logger works')
"

echo "[07] Testing web server..."
python -c "
from ipr_keyboard.web.server import create_app
app = create_app()
client = app.test_client()
res = client.get('/health')
assert res.status_code == 200, 'Health check failed'
print('[07] ✓ Web server health check works')
res = client.get('/logs/')
assert res.status_code == 200, 'Logs endpoint failed'
print('[07] ✓ Web server logs endpoint works')
"

echo "[07] Testing USB file operations..."
mkdir -p /tmp/ipr_smoke_test
python -c "
from pathlib import Path
from ipr_keyboard.usb import detector, reader
test_dir = Path('/tmp/ipr_smoke_test')
test_file = test_dir / 'test.txt'
test_file.write_text('smoke test content', encoding='utf-8')
newest = detector.newest_file(test_dir)
assert newest == test_file, 'File detection failed'
content = reader.read_file(newest, max_size=1024)
assert content == 'smoke test content', 'File reading failed'
print('[07] ✓ USB file operations work')
"
rm -rf /tmp/ipr_smoke_test

echo "[07] Testing Bluetooth helper availability..."
python -c "
from ipr_keyboard.bluetooth.keyboard import BluetoothKeyboard
kb = BluetoothKeyboard()
available = kb.is_available()
print(f'[07] ✓ Bluetooth helper check works (available={available})')
if available:
    kb.send_text('SMOKE TEST BT')
    print('[07] ✓ Bluetooth send_text called successfully')
"

echo "[07] All smoke tests passed! ✓"
