#!/usr/bin/env bash
#
# Environment configuration for ipr-keyboard project
# This script should be sourced by other scripts to ensure consistent environment variables
#
# Usage:
#   source scripts/env_set_variables.sh
#
# Or you can set these in your shell profile (~/.bashrc or ~/.bash_profile):
#   export IPR_USER="your_username"
#   export IPR_PROJECT_ROOT="/your/dev/path"
#
# category: Environment
# purpose: Configure environment variables for ipr-keyboard

# Default user - change this to your username
export IPR_USER="${IPR_USER:-meibye}"

# Default project root - change this to your development directory
export IPR_PROJECT_ROOT="${IPR_PROJECT_ROOT:-/home/meibye/dev}"

# Optional: Set IPR_ENV_DEBUG=1 to see environment variable values
if [[ "${IPR_ENV_DEBUG:-0}" == "1" ]]; then
  echo "[ENV] Using IPR_USER: $IPR_USER"
  echo "[ENV] Using IPR_PROJECT_ROOT: $IPR_PROJECT_ROOT"
fi
