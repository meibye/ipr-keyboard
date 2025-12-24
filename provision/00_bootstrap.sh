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
EOF

log "Bootstrap complete!"
echo ""
log "Next steps:"
log "  1. sudo $REPO_DIR/provision/01_os_base.sh"
log "  2. Then follow remaining provision scripts in order"
echo ""
