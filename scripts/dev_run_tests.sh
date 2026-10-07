#!/usr/bin/env bash
#
# dev_run_tests.sh
#
# Run the pytest test suite on the Raspberry Pi (or any dev machine).
#
# Usage:
#   ./scripts/dev_run_tests.sh               # run all tests
#   ./scripts/dev_run_tests.sh --cov         # run with coverage
#   ./scripts/dev_run_tests.sh tests/web/    # run a specific sub-suite
#   ./scripts/dev_run_tests.sh -k test_auth  # run matching tests
#
# Prerequisites:
#   - Package installed with dev extras: uv pip install -e '.[dev]'
#     (sys_setup_venv.sh does this automatically)
#
# category: Development
# purpose: Run pytest test suite with optional arguments
# sudo: no

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

if [[ ! -d "$VENV_DIR" ]]; then
    echo "[test] ERROR: Virtualenv not found at $VENV_DIR"
    echo "       Run ./scripts/sys_setup_venv.sh first."
    exit 1
fi

PYTEST="$VENV_DIR/bin/python"

if ! "$PYTEST" -m pytest --version >/dev/null 2>&1; then
    echo "[test] ERROR: pytest not available in $VENV_DIR"
    echo "       Run: $VENV_DIR/bin/pip install -e '.[dev]'"
    exit 1
fi

cd "$PROJECT_DIR"

if [[ $# -eq 0 ]]; then
    exec "$PYTEST" -m pytest -v tests/
elif [[ "$1" == "--cov" ]]; then
    shift
    exec "$PYTEST" -m pytest -v --cov=ipr_keyboard --cov-report=term-missing tests/ "$@"
else
    exec "$PYTEST" -m pytest "$@"
fi
