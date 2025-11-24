
#!/usr/bin/env bash
#
# Python Virtual Environment Setup Script
#
# Purpose:
#   Creates a Python virtual environment using uv and installs the ipr-keyboard package in editable mode with development dependencies.
#
# Usage:
#   ./scripts/04_setup_venv.sh
#
# Prerequisites:
#   - Must NOT be run as root
#   - Project directory must exist
#   - Environment variables set (sources 00_set_env.sh)
#
# Note:
#   Installs uv package manager if not already present.

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/00_set_env.sh"

echo "[04] Setting up Python virtual environment using uv"

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

cd "$PROJECT_DIR"

# 1. Install uv if missing
if ! command -v uv >/dev/null 2>&1; then
    echo "[04] uv not found, installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "[04] uv already installed."
fi

# 2. Create venv using uv (faster than python -m venv)
echo "[04] Creating virtualenv at $VENV_DIR using uv venv..."
uv venv  --allow-existing "$VENV_DIR"

# 3. Activate venv
#    Not strictly needed for uv pip, but convenient if you run more commands after.
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# 4. Install project with dev extras if present
echo "[04] Installing project (with dev extras if available) using uv pip..."
if uv pip install -e ".[dev]" ; then
    echo "[04] Installed editable package with [dev] extras."
else
    echo "[04] [dev] extras not available or failed; installing without extras."
    uv pip install -e .
fi


# 5. Create/update ~/.bash_aliases for convenience
ALIASES_FILE="$HOME/.bash_aliases"
echo "[04] Adding/updating aliases in $ALIASES_FILE..."
{
  echo "alias ll='ls -al'"
  echo "alias activate='source $IPR_PROJECT_ROOT/ipr-keyboard/.venv/bin/activate'"
} > "$ALIASES_FILE.tmp"

# Merge with existing aliases if present, avoiding duplicates
if [[ -f "$ALIASES_FILE" ]]; then
  grep -v "^alias ll='ls -al'" "$ALIASES_FILE" | \
  grep -v "^alias activate='source $IPR_PROJECT_ROOT/ipr-keyboard/.venv/bin/activate'" >> "$ALIASES_FILE.tmp"
fi
mv "$ALIASES_FILE.tmp" "$ALIASES_FILE"
echo "[04] Aliases 'll' and 'activate' are now available in $ALIASES_FILE."

echo "[04] Virtualenv created at $VENV_DIR and dependencies installed via uv."
