#!/usr/bin/env bash
#
# deploy_reinstall_package.sh
#
# Reinstall the Python package in editable mode and restart the main service.
#
# Use after 'git pull' when pyproject.toml changed, new Python dependencies
# were added, or the package entry points were modified.  For pure .py /
# template changes, deploy_restart_app.sh is faster (no reinstall needed).
#
# Usage:
#   sudo ./scripts/deploy/deploy_reinstall_package.sh
#
# category: Deploy
# purpose: Reinstall Python package (editable) and restart the main service
# sudo: yes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../env_set_variables.sh"

PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
VENV_DIR="$PROJECT_DIR/.venv"

if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "[deploy] ERROR: Project directory not found: $PROJECT_DIR"
    exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
    echo "[deploy] ERROR: Virtualenv not found: $VENV_DIR"
    echo "         Run scripts/sys_setup_venv.sh first."
    exit 1
fi

# Reinstall as the project user (pip must not run as root in the user venv)
PIP_USER="${SUDO_USER:-$IPR_USER}"
echo "[deploy] Reinstalling package as user '$PIP_USER'…"
cd "$PROJECT_DIR"

if command -v uv >/dev/null 2>&1; then
    sudo -u "$PIP_USER" uv pip install -e .
else
    sudo -u "$PIP_USER" "$VENV_DIR/bin/pip" install -e .
fi

echo "[deploy] Restarting ipr_keyboard.service…"
systemctl restart ipr_keyboard.service

echo "[deploy] Status:"
systemctl --no-pager -l status ipr_keyboard.service || true

echo ""
echo "[deploy] Done.  Browser hard-refresh recommended."
