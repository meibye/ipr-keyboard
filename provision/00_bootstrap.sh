#!/usr/bin/env bash
#
# Bootstrap script for ipr-keyboard provisioning
# This is the first script to run on a fresh Raspberry Pi OS installation
#
# Purpose:
#   - Validates environment configuration
#   - Installs base system tools
#   - Clones the repository (if not already present)
#   - Checks out the specified Git ref
#   - Prepares for subsequent provisioning steps
#
# Usage:
#   sudo ./provision/00_bootstrap.sh
#
# Prerequisites:
#   - Fresh Raspberry Pi OS Lite (64-bit) Bookworm installation
#   - /opt/ipr_common.env file must exist (copy from provision/common.env.example)
#
# category: Provisioning
# purpose: Bootstrap fresh Pi installation
# sudo: yes

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color


log() { echo -e "${GREEN}[bootstrap]${NC} $*"; }
warn() { echo -e "${YELLOW}[bootstrap]${NC} $*"; }
error() { echo -e "${RED}[bootstrap ERROR]${NC} $*"; }

# Check if running as root
if [[ $EUID -ne 0 ]]; then
  error "This script must be run as root"
  echo "Usage: sudo $0"
  exit 1
fi

# Logging helper for git config
log_git_config_action() {
  local msg="$1"
  echo "[GIT CONFIG] $msg" | tee -a /var/log/ipr_bootstrap.log
  echo "[GIT CONFIG] $msg" >> /opt/ipr_state/bootstrap_info.txt
}

# Check for environment file
ENV_FILE="/opt/ipr_common.env"
if [[ ! -f "$ENV_FILE" ]]; then
  error "Environment file not found: $ENV_FILE"
  echo ""
  echo "Please create it first:"
  echo "  1. Copy template: sudo cp provision/common.env.example provision/common.env"
  echo "  2. Edit values: nano provision/common.env"
  echo "  3. Install: sudo cp provision/common.env /opt/ipr_common.env"
  echo ""
  exit 1
fi

# Load environment
log "Loading environment from $ENV_FILE"
# shellcheck disable=SC1090
source "$ENV_FILE"

# Validate required variables
required_vars=("REPO_URL" "REPO_DIR" "APP_USER" "APP_GROUP" "GIT_REF" "HOSTNAME" "BT_DEVICE_NAME" "DEVICE_TYPE")
for var in "${required_vars[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    error "Required variable $var is not set in $ENV_FILE"
    exit 1
  fi
done

log "Configuration:"
log "  Device Type: $DEVICE_TYPE"
log "  Hostname: $HOSTNAME"
log "  BT Device Name: $BT_DEVICE_NAME"
log "  Repository: $REPO_URL"
log "  Repo Dir: $REPO_DIR"
log "  Git Ref: $GIT_REF"
log "  User: $APP_USER"

# Update apt and install base tools
log "Updating apt package lists..."
apt-get update

log "Installing base system tools..."
apt-get install -y --no-install-recommends \
  git \
  ca-certificates \
  curl \
  wget \
  rsync \
  unzip \
  jq \
  python3 \
  python3-venv \
  python3-pip \
  systemd-timesyncd \
  dbus \
  net-tools

# Ensure time sync is enabled
log "Enabling time synchronization..."
systemctl enable --now systemd-timesyncd

# Create repository directory structure
log "Creating repository directory structure..."
mkdir -p "$(dirname "$REPO_DIR")"
chown -R "${APP_USER}:${APP_GROUP}" "$(dirname "$REPO_DIR")"

# Clone repository if not present
if [[ ! -d "$REPO_DIR/.git" ]]; then
  log "Cloning repository from $REPO_URL..."
  sudo -u "$APP_USER" git clone "$REPO_URL" "$REPO_DIR"
else
  log "Repository already exists at $REPO_DIR"
fi

# Set git user config for this environment
if [[ -n "${GIT_USER_EMAIL:-}" ]]; then
  git -C "$REPO_DIR" config --global user.email "$GIT_USER_EMAIL"
  log_git_config_action "Set user.email to $GIT_USER_EMAIL"
else
  log_git_config_action "No GIT_USER_EMAIL provided, not set."
fi
if [[ -n "${GIT_USER_NAME:-}" ]]; then
  git -C "$REPO_DIR" config --global user.name "$GIT_USER_NAME"
  log_git_config_action "Set user.name to $GIT_USER_NAME"
else
  log_git_config_action "No GIT_USER_NAME provided, not set."
fi
if [[ -n "${GIT_REBASE:-}" ]]; then
  git -C "$REPO_DIR" config --global pull.rebase "$GIT_REBASE"
  log_git_config_action "Set pull.rebase to $GIT_REBASE"
else
  log_git_config_action "No GIT_REBASE provided, not set."
fi

# --- SSH Key Generation and GitHub Setup ---
SSH_KEY="/home/$APP_USER/.ssh/id_ed25519"
if [[ ! -f "$SSH_KEY.pub" ]]; then
  log "No SSH key found for $APP_USER. Generating a new SSH key..."
  sudo -u "$APP_USER" mkdir -p "/home/$APP_USER/.ssh"
  sudo -u "$APP_USER" ssh-keygen -t ed25519 -C "$APP_USER@$(hostname)" -f "$SSH_KEY" -N ""
  log "SSH key generated."
else
  log "SSH key already exists for $APP_USER."
fi

PUBKEY=$(sudo -u "$APP_USER" cat "$SSH_KEY.pub")
cat <<INSTRUCTIONS

====================================================================
SSH key for $APP_USER:

$PUBKEY

1. Copy the above public key.
2. Go to https://github.com/settings/keys (GitHub > Settings > SSH and GPG keys).
3. Click "New SSH key", give it a name (e.g., Pi 4 or Pi Zero 2 W), and paste the key.
4. Save the key.
5. On this device, set the repo remote to use SSH:
   git remote set-url origin git@github.com:meibye/ipr-keyboard.git
6. Test with: ssh -T git@github.com
====================================================================

INSTRUCTIONS


# Checkout specified ref
log "Checking out Git ref: $GIT_REF"
cd "$REPO_DIR"
sudo -u "$APP_USER" git fetch --all --tags
sudo -u "$APP_USER" git checkout "$GIT_REF"

# Display current commit
CURRENT_COMMIT=$(git rev-parse HEAD)
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
log "Current commit: $CURRENT_COMMIT"
log "Current branch: $CURRENT_BRANCH"

# --- Wi-Fi Power Save Disable ---
WIFI_PS_STATE="unknown"
if command -v iw &>/dev/null; then
  PS_RESULT=$(iw dev wlan0 get power_save 2>/dev/null | grep -i 'Power save:')
  if [[ "$PS_RESULT" =~ "on" ]]; then
    log "Wi-Fi power save is ON. Disabling..."
    sudo nmcli connection modify preconfigured wifi.powersave disable || true
    WIFI_PS_STATE="disabled"
  elif [[ "$PS_RESULT" =~ "off" ]]; then
    log "Wi-Fi power save is already OFF."
    WIFI_PS_STATE="already off"
  else
    log "Wi-Fi power save state unknown or not supported."
    WIFI_PS_STATE="unknown"
  fi
else
  log "iw command not found; skipping Wi-Fi power save check."
  WIFI_PS_STATE="not checked"
fi

# --- SSH Timeout Hardening ---
SSHD_CONFIG="/etc/ssh/sshd_config"
SSH_CHANGED=0
if [[ -f "$SSHD_CONFIG" ]]; then
  # Set or uncomment ClientAliveInterval
  if grep -qE '^[#[:space:]]*ClientAliveInterval' "$SSHD_CONFIG"; then
    sed -i 's|^[#[:space:]]*ClientAliveInterval.*|ClientAliveInterval 60|' "$SSHD_CONFIG"
    SSH_CHANGED=1
  elif ! grep -q '^ClientAliveInterval' "$SSHD_CONFIG"; then
    echo 'ClientAliveInterval 60' >> "$SSHD_CONFIG"
    SSH_CHANGED=1
  fi
  # Set or uncomment ClientAliveCountMax
  if grep -qE '^[#[:space:]]*ClientAliveCountMax' "$SSHD_CONFIG"; then
    sed -i 's|^[#[:space:]]*ClientAliveCountMax.*|ClientAliveCountMax 3|' "$SSHD_CONFIG"
    SSH_CHANGED=1
  elif ! grep -q '^ClientAliveCountMax' "$SSHD_CONFIG"; then
    echo 'ClientAliveCountMax 3' >> "$SSHD_CONFIG"
    SSH_CHANGED=1
  fi
  if [[ $SSH_CHANGED -eq 1 ]]; then
    log "Reloading SSH daemon to apply timeout settings..."
    systemctl reload sshd || systemctl restart sshd || true
  fi
else
  warn "$SSHD_CONFIG not found; skipping SSH timeout hardening."
fi

# Create state directory for tracking
log "Creating state directory..."
mkdir -p /opt/ipr_state
cat > /opt/ipr_state/bootstrap_info.txt <<EOF
Bootstrap completed: $(date -Is)
Device Type: $DEVICE_TYPE
Hostname: $HOSTNAME
Repository: $REPO_URL
Repository Dir: $REPO_DIR
Git Ref: $GIT_REF
Commit: $CURRENT_COMMIT
Branch: $CURRENT_BRANCH
User: $APP_USER
Wi-Fi Power Save: $WIFI_PS_STATE
SSH Timeout Hardened: $([[ $SSH_CHANGED -eq 1 ]] && echo "yes" || echo "no")
EOF

log "Bootstrap complete!"
echo ""
log "Next steps:"
log "  1. sudo $REPO_DIR/provision/01_os_base.sh"
log "  2. Then follow remaining provision scripts in order"
echo ""
