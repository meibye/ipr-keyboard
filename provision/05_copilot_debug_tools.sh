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
#   - sudoers whitelist for controlled diagnostics
#   - SSH forced-command guard + allowlist (ipr_mcp_guard.sh)
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
MCP_GUARD_SRC="$REPO_ROOT/provision/ipr_mcp_guard.sh"

require_cmd git
require_cmd apt-get
require_cmd visudo

[[ -x "$INSTALLER" ]] || die "Missing or non-executable: $INSTALLER"
[[ -f "$MCP_GUARD_SRC" ]] || die "Missing: $MCP_GUARD_SRC"

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
# Ensure log root
# -----------------------------------------------------------------------------
log "Ensuring debug log root exists: $DBG_LOG_ROOT"
mkdir -p "$DBG_LOG_ROOT"
chown root:adm "$DBG_LOG_ROOT" || true
chmod 2775 "$DBG_LOG_ROOT" || true

# -----------------------------------------------------------------------------
# Ensure automation clone exists (owned by COPILOT_USER)
# -----------------------------------------------------------------------------
log "Ensuring automation clone exists"

CLONE_PARENT="$(dirname "$COPILOT_REPO_DIR")"
mkdir -p "$CLONE_PARENT"
chown -R "$COPILOT_USER:$COPILOT_USER" "$CLONE_PARENT"

if [[ ! -d "$COPILOT_REPO_DIR/.git" ]]; then
  log "Cloning repo into $COPILOT_REPO_DIR"
  sudo -u "$COPILOT_USER" git clone "$REPO_URL" "$COPILOT_REPO_DIR"
else
  log "Automation clone already exists"
fi

log "Checking out ref in automation clone"
sudo -u "$COPILOT_USER" bash -lc "
  set -euo pipefail
  cd '$COPILOT_REPO_DIR'
  git fetch --all --prune
  git checkout '$COPILOT_GIT_REF'
  git reset --hard 'origin/$COPILOT_GIT_REF'
  echo 'Automation clone commit:' \$(git rev-parse --short HEAD)
"

# -----------------------------------------------------------------------------
# Install dbg_* tools (writes /etc/ipr_dbg.env and sudoers)
# -----------------------------------------------------------------------------
log "Installing dbg_* tools via installer"

bash "$INSTALLER" \
  --ble-service "$DBG_BLE_SERVICE_UNIT" \
  --agent-service "$DBG_AGENT_SERVICE_UNIT" \
  --hci "$BT_HCI" \
  --log-root "$DBG_LOG_ROOT" \
  --copilot-user "$COPILOT_USER" \
  --copilot-repo "$COPILOT_REPO_DIR"

# -----------------------------------------------------------------------------
# Install MCP forced-command guard + allowlist
# -----------------------------------------------------------------------------
log "Installing MCP SSH guard (/usr/local/bin/ipr_mcp_guard.sh)"
install -m 0755 "$MCP_GUARD_SRC" /usr/local/bin/ipr_mcp_guard.sh

ALLOWLIST="/etc/ipr_mcp_allowlist.conf"
log "Writing MCP allowlist: $ALLOWLIST"
cat > "$ALLOWLIST" <<'EOF'
# Allowlisted commands for MCP SSH forced-command guard (glob patterns allowed)
# Keep this tight: prefer dbg_* wrappers over raw system/journal commands.

# Diagnostics
/usr/local/bin/dbg_stack_status.sh
/usr/local/bin/dbg_diag_bundle.sh
/usr/local/bin/dbg_pairing_capture.sh *
/usr/local/bin/dbg_deploy.sh

# Recovery (conservative)
/usr/local/bin/dbg_bt_restart.sh
/usr/local/bin/dbg_bt_soft_reset.sh

# Destructive (requires explicit user approval in Copilot workflow)
/usr/local/bin/dbg_bt_bond_wipe.sh *
EOF
chmod 0644 "$ALLOWLIST"

# Guard log file (optional; guard will still function if log can't be written)
GUARD_LOG="/var/log/ipr_mcp_guard.log"
touch "$GUARD_LOG" || true
chown root:adm "$GUARD_LOG" || true
chmod 0664 "$GUARD_LOG" || true

# -----------------------------------------------------------------------------
# Ensure .ssh folder and authorized_keys for COPILOT_USER
# -----------------------------------------------------------------------------
log "Ensuring .ssh folder and authorized_keys for $COPILOT_USER"
SSH_DIR="$(eval echo ~"$COPILOT_USER")/.ssh"
install -d -m 0700 -o "$COPILOT_USER" -g "$COPILOT_USER" "$SSH_DIR"

AUTH_KEYS="$SSH_DIR/authorized_keys"
if [[ ! -f "$AUTH_KEYS" ]]; then
  install -m 0600 -o "$COPILOT_USER" -g "$COPILOT_USER" /dev/null "$AUTH_KEYS"
fi

append_guarded_key() {
  local pubkey_line="$1"

  pubkey_line="$(echo "$pubkey_line" | tr -d '\r' | sed -e 's/^ *//' -e 's/ *$//')"
  [[ -n "$pubkey_line" ]] || die "Empty public key line"

  if grep -Fq "$pubkey_line" "$AUTH_KEYS"; then
    warn "Public key already present in $AUTH_KEYS"
    return 0
  fi

  local prefix='command="/usr/local/bin/ipr_mcp_guard.sh",no-pty,no-port-forwarding,no-agent-forwarding '
  echo "${prefix}${pubkey_line}" >> "$AUTH_KEYS"
  chown "$COPILOT_USER:$COPILOT_USER" "$AUTH_KEYS"
  chmod 0600 "$AUTH_KEYS"
  log "Added guarded key entry to $AUTH_KEYS"
}

if [[ -n "$COPILOT_PUBKEY_FILE" ]]; then
  if [[ -f "$COPILOT_PUBKEY_FILE" ]]; then
    log "Installing public key from COPILOT_PUBKEY_FILE=$COPILOT_PUBKEY_FILE"
    append_guarded_key "$(cat "$COPILOT_PUBKEY_FILE")"
  else
    die "COPILOT_PUBKEY_FILE is set but file not found: $COPILOT_PUBKEY_FILE"
  fi
else
  echo
  warn "No COPILOT_PUBKEY_FILE provided."
  warn "Paste ONE public key line now (starting with 'ssh-ed25519' or similar). It will be stored with a forced-command guard."
  echo -n "> "
  read -r PUBKEY_LINE
  append_guarded_key "$PUBKEY_LINE"
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
echo "  ssh -i %USERPROFILE%\\.ssh\\copilotdiag_rpi $COPILOT_USER@$(hostname -s)"
echo

log "Next recommended step on the Pi:"
log "  sudo dbg_stack_status.sh"
echo

log "Next steps:"
log "  1. sudo $REPO_ROOT/provision/06_verify.sh"
