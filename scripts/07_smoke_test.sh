#!/usr/bin/env bash

# Purpose:
# Run a set of quick smoke tests against your project using the uv-created venv:
#
# Ensures venv exists and imports work.
#
# Config manager: updates config to point to /mnt/irispen.
#
# Logger: writes a test line.
#
# Web server: creates Flask app and hits /health and /logs/ via its test client.
#
# USB: creates a dummy file in /mnt/irispen and uses detector + reader.
#
# Bluetooth: checks helper availability and calls send_text("SMOKE TEST BT").
#
# No infinite loops, no systemd involvement.
# Run as your configured user:
#    ./scripts/07_smoke_test.sh

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/00_set_env.sh"

echo "[07] Running ipr_keyboard smoke tests"

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
  echo "Virtualenv not found at $VENV_DIR"
  echo "Run: ./scripts/04_setup_venv.sh"
  exit 1
fi

cd "$PROJECT_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "[07] Using Python: $(which python)"

###############################################################################
# 1) Config + Logger test
###############################################################################
echo
echo "[07] 1) Testing ConfigManager and logger..."

python - <<'PY'
from ipr_keyboard.config.manager import ConfigManager
from ipr_keyboard.logging.logger import get_logger

cfg_mgr = ConfigManager.instance()

cfg = cfg_mgr.update(
    IrisPenFolder="/mnt/irispen",
    Logging=True,
)

print("Config after update:", cfg.to_dict())

logger = get_logger()
logger.info("SMOKE: logger is working")
print("Logger wrote a SMOKE line to the log file.")
PY

###############################################################################
# 2) Web server (Flask app) test using test_client
###############################################################################
echo
echo "[07] 2) Testing web server endpoints via Flask test_client..."

python - <<'PY'
from ipr_keyboard.web.server import create_app

app = create_app()
client = app.test_client()

# /health
resp = client.get("/health")
print("GET /health:", resp.status_code, resp.json)

# /logs/
resp_logs = client.get("/logs/")
print("GET /logs/:", resp_logs.status_code)
if resp_logs.is_json:
    log_snip = resp_logs.json.get("log", "")[:200]
    print("Log snippet:", repr(log_snip))
PY

###############################################################################
# 3) USB handling: create dummy file, detect newest, read content
###############################################################################
echo
echo "[07] 3) Testing USB detector + reader with dummy file in /mnt/irispen..."

python - <<'PY'
from pathlib import Path
from ipr_keyboard.usb import detector, reader

folder = Path("/mnt/irispen")
folder.mkdir(parents=True, exist_ok=True)

dummy = folder / "smoke_test_usb.txt"
dummy.write_text("SMOKE USB CONTENT", encoding="utf-8")

newest = detector.newest_file(folder)
print("Newest file:", newest)

text = reader.read_file(newest, max_size=1024)
print("Read content:", repr(text))
PY

###############################################################################
# 4) Bluetooth helper: test availability + send_text
###############################################################################
echo
echo "[07] 4) Testing BluetoothKeyboard wrapper (using bt_kb_send helper)..."

python - <<'PY'
from ipr_keyboard.bluetooth.keyboard import BluetoothKeyboard

kb = BluetoothKeyboard()
available = kb.is_available()
print("Bluetooth helper available:", available)

# This will call /usr/local/bin/bt_kb_send "SMOKE TEST BT"
result = kb.send_text("SMOKE TEST BT")
print("send_text() returned:", result)
PY

###############################################################################
# 5) Optional: show systemd service status if it exists
###############################################################################
echo
echo "[07] 5) Checking systemd service (if installed)..."

if command -v systemctl >/dev/null 2>&1; then
    if systemctl list-unit-files | grep -q '^ipr_keyboard.service'; then
        systemctl is-active --quiet ipr_keyboard.service \
          && echo "[07] ipr_keyboard.service is active." \
          || echo "[07] ipr_keyboard.service is present but not active."
    else
        echo "[07] ipr_keyboard.service not installed (this is fine for dev)."
    fi
else
    echo "[07] systemctl not available (non-systemd environment)."
fi

echo
echo "[07] Smoke tests finished."
