#!/usr/bin/env bash
#
# Run Application in Development Mode
#
# Purpose:
#   Convenience script to run the ipr-keyboard application in the foreground
#   for debugging and development purposes (instead of using systemd).
#
# Prerequisites:
#   - Environment variables set (sources 00_set_env.sh)
#   - Virtual environment must be set up
#
# Usage:
#   ./scripts/run_dev.sh
#
# Note:
#   The application will run in the foreground and can be stopped with Ctrl+C.
#   All log output will be visible in the terminal.

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/00_set_env.sh"


#!/usr/bin/env bash
#
# ipr-keyboard Development Run Script
#
# Purpose:
#   Runs the ipr-keyboard application in foreground for development and debugging.
#   Logs output to console.
#
# Usage:
#   ./scripts/run_dev.sh
#
# Prerequisites:
#   - Must NOT be run as root
#   - Python venv must be set up
#   - Environment variables set (sources 00_set_env.sh)
#
# Note:
#   Press Ctrl+C to stop. Does not run as a service.

PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"

# Load environment variables
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

echo "Starting ipr-keyboard in development mode..."
echo "Press Ctrl+C to stop"
echo

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Run the application
exec python -m ipr_keyboard.main
