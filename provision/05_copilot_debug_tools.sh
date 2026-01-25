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
#
# Must be run as root.
#
# Usage:
#   sudo ./provision/05_copilot_debug_tools.sh
#
# category: Provisioning
# purpose: Install Copilot debug tools
# sudo: yes

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

# -----------------------------------------------------------------------------
# Derived paths
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALLER="$REPO_ROOT/scripts/rpi-debug/install_dbg_tools.sh"

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
usermod -aG bluetooth,adm "$COPILOT_USER"

# -----------------------------------------------------------------------------
# Ensure log root
# -----------------------------------------------------------------------------
log "Ensuring debug log root exists: $DBG_LOG_ROOT"
mkdir -p "$DBG_LOG_ROOT"
chown root:adm "$DBG_LOG_ROOT"
chmod 2775 "$DBG_LOG_ROOT"

# -----------------------------------------------------------------------------
# Ensure automation clone exists
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
# Install dbg_* tools
# -----------------------------------------------------------------------------
log "Installing dbg_* tools via installer"

bash "$INSTALLER" \
  --ble-service "$DBG_BLE_SERVICE_UNIT" \
  --agent-service "$DBG_AGENT_SERVICE_UNIT" \
  --hci "$BT_HCI" \
  --log-root "$DBG_LOG_ROOT" \
  --copilot-user "$COPILOT_USER" \
  --copilot-repo "$COPILOT_REPO_DIR"

# ---------------------------------------------------------------------------
# Ensure .ssh folder and authorized_keys for COPILOT_USER
# ---------------------------------------------------------------------------
log "Ensuring .ssh folder and authorized_keys for $COPILOT_USER"
sudo -u "$COPILOT_USER" mkdir -p "$COPILOT_REPO_DIR/../.ssh"
sudo -u "$COPILOT_USER" chmod 700 "$COPILOT_REPO_DIR/../.ssh"
SSH_DIR="$(eval echo ~$COPILOT_USER)/.ssh"
sudo -u "$COPILOT_USER" mkdir -p "$SSH_DIR"
sudo -u "$COPILOT_USER" chmod 700 "$SSH_DIR"
AUTH_KEYS="$SSH_DIR/authorized_keys"
if [[ ! -f "$AUTH_KEYS" ]]; then
  sudo -u "$COPILOT_USER" touch "$AUTH_KEYS"
  sudo -u "$COPILOT_USER" chmod 600 "$AUTH_KEYS"
  log "Please paste the public SSH key for Copilot/MCP access into:"
  log "  $AUTH_KEYS"
  log "Then press Enter to continue."
  read -r
else
  log "authorized_keys already exists for $COPILOT_USER"
fi

echo
log "To test SSH connectivity from your PC, run:"
echo "  ssh -i \$HOME/.ssh/copilotdiag_rpi $COPILOT_USER@$(hostname -s | awk '{print $1}')"
# PowerShell equivalent for testing SSH connectivity:
log "To test SSH connectivity from your PC (PowerShell):"
echo '  ssh -i $HOME\.ssh\copilotdiag_rpi {0}@{1}' -f $env:COPILOT_USER, (hostname)

# -----------------------------------------------------------------------------
# Final summary
# -----------------------------------------------------------------------------
echo
log "Copilot debug tooling installed successfully"

log "Installed commands (available system-wide):"
log "  dbg_stack_status.sh"
log "  dbg_diag_bundle.sh"
log "  dbg_pairing_capture.sh <seconds>"
log "  dbg_bt_restart.sh"
log "  dbg_bt_soft_reset.sh"
log "  dbg_bt_bond_wipe.sh <MAC>"

echo
log "Next recommended step:"
log "  sudo dbg_stack_status.sh"

echo ""
log "Next steps:"
log "  1. sudo $REPO_ROOT/provision/06_verify.sh"
echo ""
