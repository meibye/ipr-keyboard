#!/usr/bin/env bash
#
# ipr-keyboard Web Server Start Script
#
# Starts the Flask web server for the ipr-keyboard project directly (for development or diagnostics).
#
# Usage:
#   ./scripts/dev_run_webserver.sh
#
# Prerequisites:
#   - Must NOT be run as root
#   - Environment variables set (sources env_set_variables.sh)
#   - Python venv activated or dependencies installed

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env_set_variables.sh"

cd "$IPR_PROJECT_ROOT/ipr-keyboard"

# Run the web server directly
exec python -m ipr_keyboard.web.server
