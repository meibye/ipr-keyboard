#!/usr/bin/env bash

# If you want a simple script to run the app in the foreground (for debugging) instead of via systemd

set -euo pipefail

PROJECT_DIR="/home/meibye/dev/ipr-keyboard"
VENV_DIR="$PROJECT_DIR/.venv"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Project directory not found: $PROJECT_DIR"
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Virtualenv not found at $VENV_DIR"
  echo "Run: scripts/04_setup_venv.sh"
  exit 1
fi

cd "$PROJECT_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Running ipr_keyboard.main in foreground (Ctrl+C to stop)..."
python -m ipr_keyboard.main
