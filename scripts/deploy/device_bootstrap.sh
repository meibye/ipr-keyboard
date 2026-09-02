#!/usr/bin/env bash
#
# device_bootstrap.sh
#
# Everything the DEVICE has to do after host_push_to_device.sh has delivered
# the code: verify the prerequisites, then run the provisioning steps in order.
#
# Run this ON the Raspberry Pi, as root:
#
#   ssh ipr-prod
#   sudo ~/dev/ipr-keyboard/scripts/deploy/device_bootstrap.sh
#
# It is a thin, checked wrapper around provision/provision_wizard.sh — it does
# not replace the individual steps, and each step remains runnable on its own
# for troubleshooting.  Safe to re-run: the provisioning steps are idempotent.
#
# Usage:
#   sudo ./scripts/deploy/device_bootstrap.sh [options]
#
#   --check-only     run the preflight checks and stop
#   --yes            skip this script's own confirmation prompt.  The wizard
#                    itself is interactive and still asks its own questions.
#
# category: Deploy
# purpose: Verify prerequisites and run provisioning on a freshly seeded device
# sudo: yes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="/opt/ipr_common.env"

CHECK_ONLY=false
ASSUME_YES=false

log()  { echo "[device_bootstrap] $*"; }
warn() { echo "[device_bootstrap] WARNING: $*" >&2; }
die()  { echo "[device_bootstrap] ERROR: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --check-only)   CHECK_ONLY=true; shift ;;
        --yes|-y)       ASSUME_YES=true; shift ;;
        -h|--help)      sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)              die "Unknown argument: $1" ;;
    esac
done

[[ $EUID -eq 0 ]] || die "Must be run as root: sudo $0"

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
log "Repository: $REPO_ROOT"
FAILED=0

check() {
    local label="$1"; shift
    if "$@" >/dev/null 2>&1; then
        echo "  ok    $label"
    else
        echo "  FAIL  $label"
        FAILED=$((FAILED + 1))
    fi
}

log "Preflight checks ..."
check "environment file $ENV_FILE present"  test -r "$ENV_FILE"
check "provision/ present"                  test -d "$REPO_ROOT/provision"
check "scripts/ present"                    test -d "$REPO_ROOT/scripts"
check "src/ present"                        test -d "$REPO_ROOT/src"
check "pyproject.toml present"              test -f "$REPO_ROOT/pyproject.toml"
check "README.md present (needed by the editable install)" \
                                            test -f "$REPO_ROOT/README.md"
check "config.default.json present"         test -f "$REPO_ROOT/config.default.json"
check "users.default.json present"          test -f "$REPO_ROOT/users.default.json"
check "provision scripts are executable"    test -x "$REPO_ROOT/provision/00_bootstrap.sh"

if [[ $FAILED -gt 0 ]]; then
    echo
    die "$FAILED prerequisite(s) missing.
       Re-run the transfer from the PC:
         ./scripts/deploy/host_push_to_device.sh <host>
       If only the executable flag is missing, repair it here:
         find $REPO_ROOT/scripts $REPO_ROOT/provision \\( -name '*.sh' -o -name '*.py' \\) -exec chmod +x {} +"
fi

# ---------------------------------------------------------------------------
# Report the identity this device is about to take, so a wrong environment file
# is caught before the hostname changes underneath the running SSH session.
# ---------------------------------------------------------------------------
# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

echo
log "This device will be provisioned as:"
log "  DEVICE_TYPE     ${DEVICE_TYPE:-<unset>}"
log "  HOSTNAME        ${HOSTNAME:-<unset>}   (currently: $(hostname -s))"
log "  BT_DEVICE_NAME  ${BT_DEVICE_NAME:-<unset>}"
log "  REPO_DIR        ${REPO_DIR:-<unset>}"

for v in DEVICE_TYPE HOSTNAME BT_DEVICE_NAME REPO_DIR REPO_URL APP_USER APP_GROUP GIT_REF; do
    [[ -n "${!v:-}" ]] || die "$v is not set in $ENV_FILE"
done

if [[ "${REPO_DIR}" != "$REPO_ROOT" ]]; then
    warn "REPO_DIR ($REPO_DIR) differs from this checkout ($REPO_ROOT)."
    warn "The provisioning steps will operate on REPO_DIR."
fi

if [[ "${HOSTNAME}" != "$(hostname -s)" ]]; then
    warn "The hostname changes during step 02. Name resolution for the current"
    warn "SSH session may break; reconnect as ${HOSTNAME}.local afterwards."
fi

$CHECK_ONLY && { echo; log "Checks complete (--check-only)."; exit 0; }

if ! $ASSUME_YES; then
    echo
    read -r -p "[device_bootstrap] Proceed with provisioning? [y/N] " reply
    [[ "$reply" =~ ^[Yy]$ ]] || { log "Aborted."; exit 0; }
fi

# ---------------------------------------------------------------------------
# Provisioning
#
# The wizard runs steps 00-06 with resume points and handles the reboots
# between steps 01 and 02.  Re-run this script after each reboot; the wizard
# picks up where it left off.
# ---------------------------------------------------------------------------
echo
log "Running provision_wizard.sh — it is interactive and will ask its own"
log "questions, including whether to resume a previous run."

cd "$REPO_DIR"
bash "$REPO_DIR/provision/provision_wizard.sh"

echo
log "Provisioning finished. Verify with:"
log "  ./scripts/diag_status.sh"
log "  systemctl status ipr_keyboard bt_hid_ble bt_hid_agent_unified"
log "  curl -k https://localhost/health"
