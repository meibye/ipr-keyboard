#!/usr/bin/env bash
#
# provision/05_copilot_debug_tools.sh
#
# Optional provisioning step.
#
# Sets up:
#   - Dedicated Copilot/MCP diagnostics user
#   - Separate automation clone (safe git reset --hard)
#   - dbg_* tooling installed into /usr/local/bin
#   - sudoers whitelist for controlled diagnostics (MCP server whitelist)
#
# Must be run as root.
#
# Usage:
#   sudo ./provision/05_copilot_debug_tools.sh
#
# category: Provisioning
# purpose: Install Copilot debug tools
# sudo: yes
#
set -euo pipefail

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[copilot]${NC} $*"; }
warn() { echo -e "${YELLOW}[copilot]${NC} $*"; }
die()  { echo -e "${RED}[copilot ERROR]${NC} $*"; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

# -----------------------------------------------------------------------------
# Load common environment
# -----------------------------------------------------------------------------
ENV_FILE="/opt/ipr_common.env"
[[ -f "$ENV_FILE" ]] || die "Missing $ENV_FILE. Create it from provision/common.env.example first."

# shellcheck disable=SC1090
source "$ENV_FILE"

# -----------------------------------------------------------------------------
# Required variables (validated)
# -----------------------------------------------------------------------------
: "${REPO_URL:?Missing REPO_URL}"
: "${GIT_REF:?Missing GIT_REF}"

: "${COPILOT_USER:?Missing COPILOT_USER}"
: "${COPILOT_REPO_DIR:?Missing COPILOT_REPO_DIR}"
: "${COPILOT_GIT_REF:?Missing COPILOT_GIT_REF}"

: "${DBG_LOG_ROOT:?Missing DBG_LOG_ROOT}"
: "${DBG_BLE_SERVICE_UNIT:?Missing DBG_BLE_SERVICE_UNIT}"
: "${DBG_AGENT_SERVICE_UNIT:?Missing DBG_AGENT_SERVICE_UNIT}"

: "${BT_HCI:?Missing BT_HCI}"

# Optional (non-interactive key install)
# If set, must point to a file containing a single public key line (ssh-ed25519 ...).
COPILOT_PUBKEY_FILE="${COPILOT_PUBKEY_FILE:-}"

# -----------------------------------------------------------------------------
# Derived paths
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALLER="$REPO_ROOT/scripts/rpi-debug/install_dbg_tools.sh"

require_cmd git
require_cmd apt-get
require_cmd visudo

[[ -x "$INSTALLER" ]] || die "Missing or non-executable: $INSTALLER"

log "Starting Copilot debug tooling setup"
log "Using repo root: $REPO_ROOT"
echo

log "Configuration summary:"
log "  COPILOT_USER          = $COPILOT_USER"
log "  COPILOT_REPO_DIR      = $COPILOT_REPO_DIR"
log "  COPILOT_GIT_REF       = $COPILOT_GIT_REF"
log "  DBG_LOG_ROOT          = $DBG_LOG_ROOT"
log "  DBG_AGENT_SERVICE     = $DBG_AGENT_SERVICE_UNIT"
log "  DBG_BLE_SERVICE       = $DBG_BLE_SERVICE_UNIT"
log "  BT_HCI                = $BT_HCI"
echo

# -----------------------------------------------------------------------------
# Ensure required packages
# -----------------------------------------------------------------------------
log "Ensuring required packages are installed"
apt-get update
apt-get install -y bluez bluez-tools

# -----------------------------------------------------------------------------
# Ensure Copilot user exists
# -----------------------------------------------------------------------------
if ! id "$COPILOT_USER" >/dev/null 2>&1; then
  log "Creating user: $COPILOT_USER (non-interactive)"
  adduser --disabled-password --gecos "copilotdiag,,," "$COPILOT_USER"
else
  log "User already exists: $COPILOT_USER"
fi

# Groups needed for diagnostics
usermod -aG bluetooth,adm "$COPILOT_USER" || true

# -----------------------------------------------------------------------------
# Ensure .ssh folder and authorized_keys for $COPILOT_USER
# -----------------------------------------------------------------------------
log "Ensuring .ssh folder and authorized_keys for $COPILOT_USER"
SSH_DIR="/home/$COPILOT_USER/.ssh"
AUTH_KEYS="/home/$COPILOT_USER/.ssh/authorized_keys"
install -d -m 0700 -o "$COPILOT_USER" -g "$COPILOT_USER" "$SSH_DIR"
if [[ ! -f "$AUTH_KEYS" ]]; then
  install -m 0600 -o "$COPILOT_USER" -g "$COPILOT_USER" /dev/null "$AUTH_KEYS"
else
  chown "$COPILOT_USER:$COPILOT_USER" "$AUTH_KEYS"
  chmod 0600 "$AUTH_KEYS"
fi

# -----------------------------------------------------------------------------
# Run the dbg_tools installer script
# -----------------------------------------------------------------------------
append_key() {
  local pubkey_line="$1"

  pubkey_line="$(echo "$pubkey_line" | tr -d '\r' | sed -e 's/^ *//' -e 's/ *$//')"
  [[ -n "$pubkey_line" ]] || die "Empty public key line"

  # Check if the key is already present
  if grep -Fq "$pubkey_line" "$AUTH_KEYS"; then
    warn "Public key already present in $AUTH_KEYS"
    return 0
  fi

  echo "$pubkey_line" >> "$AUTH_KEYS"
  chown "$COPILOT_USER:$COPILOT_USER" "$AUTH_KEYS"
  chmod 0600 "$AUTH_KEYS"
  log "Added key entry to $AUTH_KEYS"
}

if [[ -n "$COPILOT_PUBKEY_FILE" ]]; then
  if [[ -f "$COPILOT_PUBKEY_FILE" ]]; then
    log "Installing public key from COPILOT_PUBKEY_FILE=$COPILOT_PUBKEY_FILE"
    append_key "$(cat "$COPILOT_PUBKEY_FILE")"
  else
    die "COPILOT_PUBKEY_FILE is set but file not found: $COPILOT_PUBKEY_FILE"
  fi
elif [[ -f "/tmp/copilot_pubkey.txt" ]]; then
  log "Detected transferred public key at /tmp/copilot_pubkey.txt"
  append_key "$(cat /tmp/copilot_pubkey.txt)"
  log "Public key from /tmp/copilot_pubkey.txt installed."
else
  echo
  warn "No COPILOT_PUBKEY_FILE provided and no /tmp/copilot_pubkey.txt found."
  warn "Paste ONE public key line now (starting with 'copilotdiag' or similar). It will be stored with a forced-command guard."
  echo -n "> "
  read -r PUBKEY_LINE
  append_key "$PUBKEY_LINE"
fi

echo
log "Copilot/MCP SSH access is guarded by: /usr/local/bin/ipr_mcp_guard.sh"
log "Allowlist: $ALLOWLIST"
log "Guard log: $GUARD_LOG"
echo

# -----------------------------------------------------------------------------
# Final summary
# -----------------------------------------------------------------------------
log "Copilot debug tooling installed successfully"

log "Installed commands (available system-wide):"
log "  dbg_stack_status.sh"
log "  dbg_diag_bundle.sh"
log "  dbg_pairing_capture.sh <seconds>"
log "  dbg_bt_restart.sh"
log "  dbg_bt_soft_reset.sh"
log "  dbg_bt_bond_wipe.sh <MAC>"
log "  dbg_deploy.sh"
echo

log "Quick test from Windows (OpenSSH):"
log "SSH command prompt for Copilot diagnostics user (Windows OpenSSH):"
echo "  ssh -i %USERPROFILE%\\.ssh\\copilotdiag_rpi $COPILOT_USER@$(hostname -s)"
echo
log "PowerShell equivalent:"
echo "  ssh -i \$env:USERPROFILE\\.ssh\\copilotdiag_rpi $COPILOT_USER@$(hostname -s)"
echo

log "Next recommended step on the Pi:"
log "  sudo dbg_stack_status.sh"
echo

log "Next steps:"
log "  1. sudo $REPO_ROOT/provision/06_verify.sh"
