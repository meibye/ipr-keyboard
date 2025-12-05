#!/usr/bin/env bash
#
# ipr-keyboard Development Run Script
#
# Purpose:
#   Runs the ipr-keyboard application in foreground for development and debugging.
#   Logs output to console.
#
# Usage:
#   ./scripts/dev_run_app.sh
#
# Prerequisites:
#   - Must NOT be run as root
#   - Python venv must be set up
#   - Environment variables set (sources env_set_variables.sh)
#
# Note:
#   Press Ctrl+C to stop. Does not run as a service.

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/env_set_variables.sh"

PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
VENV_DIR="$PROJECT_DIR/.venv"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Project directory not found: $PROJECT_DIR"
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Virtual environment not found: $VENV_DIR"
  echo "Please run sys_setup_venv.sh first."
  exit 1
fi

cd "$PROJECT_DIR"

echo "Starting ipr-keyboard in development mode..."
echo "Press Ctrl+C to stop"
echo

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Run the application
exec python -m ipr_keyboard.main
