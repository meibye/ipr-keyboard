#!/usr/bin/env bash
#
# deploy_full_update.sh
#
# Full post-git-pull update sequence for the Raspberry Pi.
#
# Runs the complete set of deployment steps needed after 'git pull' when it is
# unclear which parts changed, or when doing a first-time install after cloning.
#
# Steps performed:
#   1. Reinstall Python package in editable mode  (only with --install-python)
#   2. Install BLE daemon binaries and service files
#   3. Install Bluetooth keyboard helpers
#   4. Reload systemd unit files
#   5. Restart all services in dependency order
#
# For targeted updates (only some parts changed) use the individual deploy_*
# scripts instead to avoid unnecessary restarts.
#
# Usage:
#   sudo ./scripts/deploy/deploy_full_update.sh [--install-python]
#
#   --install-python   Also reinstall the Python package in editable mode.
#                      Needed when pyproject.toml, entry points, or
#                      dependencies changed.
#
# category: Deploy
# purpose: Full post-git-pull update — daemons, helpers, all services (Python install optional)
# parameters: --install-python
# sudo: yes

set -euo pipefail

INSTALL_PYTHON=false
for arg in "$@"; do
    case "$arg" in
        --install-python) INSTALL_PYTHON=true ;;
        *) echo "[deploy] Unknown argument: $arg"; exit 1 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../env_set_variables.sh"

PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
VENV_DIR="$PROJECT_DIR/.venv"

if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "[deploy] ERROR: Project directory not found: $PROJECT_DIR"
    exit 1
fi

echo "========================================================"
echo " Full update — $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================================"
echo ""

# ---- 1. Reinstall Python package (optional) ----
if [[ "$INSTALL_PYTHON" == true ]]; then
    if [[ ! -d "$VENV_DIR" ]]; then
        echo "[deploy] ERROR: Virtualenv not found: $VENV_DIR"
        echo "         Run scripts/sys_setup_venv.sh first."
        exit 1
    fi
    echo "[1/5] Reinstalling Python package…"
    PIP_USER="${SUDO_USER:-$IPR_USER}"
    cd "$PROJECT_DIR"
    if [[ -x "$VENV_DIR/bin/uv" ]]; then
        runuser -u "$PIP_USER" -- "$VENV_DIR/bin/uv" pip install -e .
    elif command -v uv >/dev/null 2>&1; then
        runuser -u "$PIP_USER" -- "$(command -v uv)" pip install -e .
    else
        runuser -u "$PIP_USER" -- "$VENV_DIR/bin/pip" install -e .
    fi
    echo "      OK"
else
    echo "[1/5] Skipping Python package install (pass --install-python to enable)."
fi
echo ""

# ---- 2. Install BLE daemons ----
echo "[2/5] Installing BLE daemon binaries and service files…"
bash "$SCRIPT_DIR/../service/svc_install_bt_gatt_hid.sh"
echo "      OK"
echo ""

# ---- 3. Install BT helpers ----
echo "[3/5] Installing Bluetooth keyboard helpers…"
bash "$SCRIPT_DIR/../ble/ble_install_helper.sh"
echo "      OK"
echo ""

# ---- 4. Reload systemd ----
echo "[4/5] Reloading systemd unit definitions…"
systemctl daemon-reload
echo "      OK"
echo ""

# ---- 5. Restart services ----
echo "[5/5] Restarting all services in dependency order…"
bash "$SCRIPT_DIR/deploy_restart_all_services.sh"

echo ""
echo "========================================================"
echo " Update complete."
echo " Hard-refresh your browser to clear cached dashboard pages."
echo "========================================================"
