#!/usr/bin/env bash
#
echo -e "${GREEN}All provisioning steps completed!${NC}"
echo -e "${GREEN}Device is ready for use.${NC}"

# Interactive Provisioning Wizard for ipr-keyboard (with reboot resume)
#
# Guides the user through all provisioning steps, handles reboots, and resumes automatically.
#
# Usage:
#   sudo ./provision/00_provision_wizard.sh
#
# category: Provisioning
# purpose: Interactive, stepwise provisioning with color-coded feedback and reboot resume
# sudo: yes

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

STATE_FILE="/opt/ipr_state/provision_wizard_state.txt"

step() {
  local msg="$1"
  echo -e "${BLUE}==== $msg ====${NC}"
}

success() {
  echo -e "${GREEN}✓ $1${NC}"
}

fail() {
  echo -e "${RED}✗ $1${NC}"
}

warn() {
  echo -e "${YELLOW}! $1${NC}"
}

prompt_continue() {
  echo -en "${YELLOW}Continue to next step? [Y/n]: ${NC}"
  read -r ans
  if [[ "${ans,,}" =~ ^(n|no)$ ]]; then
    echo -e "${RED}Aborting provisioning.${NC}"
    exit 1
  fi
}

prompt_reboot() {
  echo -en "${YELLOW}System reboot required. Reboot now? [Y/n]: ${NC}"
  read -r ans
  if [[ "${ans,,}" =~ ^(n|no)$ ]]; then
    warn "You must reboot before continuing."
    exit 1
  fi
  echo "wizard_step=$1" > "$STATE_FILE"
  echo -e "${YELLOW}Rebooting... After reboot, re-run this script to continue.${NC}"
  sleep 2
  reboot
}

run_step() {
  local script="$1"
  local desc="$2"
  local stepnum="$3"
  step "$desc"
  if bash "$script"; then
    success "$desc completed successfully."
  else
    fail "$desc failed!"
    echo -e "${RED}Check logs and fix errors before retrying.${NC}"
    exit 1
  fi
  echo "wizard_step=$stepnum" > "$STATE_FILE"
  prompt_continue
}

# Main wizard logic
clear
echo -e "${BLUE}IPR Keyboard - Interactive Provisioning Wizard${NC}"
echo "This script will guide you through all provisioning steps."
echo "You must run this as root (sudo)."
echo ""

# Offer to start over if state file exists
if [[ -f "$STATE_FILE" ]]; then
  source "$STATE_FILE"
  echo -e "${YELLOW}Previous provisioning detected (step: $wizard_step).${NC}"
  echo -en "${YELLOW}Start over from the beginning? [y/N]: ${NC}"
  read -r ans
  if [[ "${ans,,}" =~ ^(y|yes)$ ]]; then
    rm -f "$STATE_FILE"
    wizard_step=1
    echo -e "${YELLOW}State cleared. Starting from step 1.${NC}"
  fi
else
  wizard_step=1
fi


# Step 1: Install git
if [[ "$wizard_step" -le 1 ]]; then
  step "[Step 1/10] Install git (required to clone the repository)"
  if sudo apt-get update && sudo apt-get install -y git; then
    success "Git installed successfully."
  else
    fail "Failed to install git."
    exit 1
  fi
  echo "wizard_step=2" > "$STATE_FILE"
  prompt_continue
fi

# Step 2: Clone the repository
if [[ "$wizard_step" -le 2 ]]; then
  step "[Step 2/10] Clone the repository"
  mkdir -p /home/meibye/dev
  cd /home/meibye/dev
  if git clone https://github.com/meibye/ipr-keyboard.git; then
    success "Repository cloned successfully."
  else
    warn "Repository may already exist or clone failed."
  fi
  cd ipr-keyboard
  echo "wizard_step=3" > "$STATE_FILE"
  prompt_continue
fi

# Step 3: Create device configuration
if [[ "$wizard_step" -le 3 ]]; then
  step "[Step 3/10] Create device configuration"
  cp provision/common.env.example provision/common.env
  echo -e "${YELLOW}Please edit provision/common.env with device-specific values.${NC}"
  nano provision/common.env
  sudo cp provision/common.env /opt/ipr_common.env
  echo "wizard_step=4" > "$STATE_FILE"
  prompt_continue
fi

# Step 4: Make scripts executable
if [[ "$wizard_step" -le 4 ]]; then
  step "[Step 4/10] Make provisioning scripts executable"
  chmod +x ./provision/*.sh
  success "Scripts are now executable."
  echo "wizard_step=5" > "$STATE_FILE"
  prompt_continue
fi

# Step 5: Run 00_bootstrap.sh
if [[ "$wizard_step" -le 5 ]]; then
  run_step "./provision/00_bootstrap.sh" "[Step 5/10] Bootstrap: Install base tools and clone repo" 6
fi

# Step 6: Setup and test GitHub SSH keys
if [[ "$wizard_step" -le 6 ]]; then
  step "[Step 6/10] Setup and test GitHub SSH keys"
  git remote set-url origin git@github.com:meibye/ipr-keyboard.git
  echo -e "${YELLOW}Testing SSH connection to GitHub. Answer 'yes' if prompted.${NC}"
  ssh -T git@github.com || warn "SSH test failed. You may need to set up your SSH key."
  echo "wizard_step=7" > "$STATE_FILE"
  prompt_continue
fi

# Step 7: Run 01_os_base.sh (reboot required)
if [[ "$wizard_step" -le 7 ]]; then
  run_step "./provision/01_os_base.sh" "[Step 7/10] OS Base: System packages and Bluetooth config" 8
  prompt_reboot 8
fi

# Step 8: Run 02_device_identity.sh (reboot required)
if [[ "$wizard_step" -le 8 ]]; then
  run_step "./provision/02_device_identity.sh" "[Step 8/10] Device Identity: Hostname and Bluetooth name" 9
  prompt_reboot 9
fi

# Step 9: Run 03_app_install.sh, 04_enable_services.sh, 05_verify.sh
if [[ "$wizard_step" -le 9 ]]; then
  run_step "./provision/03_app_install.sh" "[Step 9/10] App Install: Python venv and dependencies" 10
  run_step "./provision/04_enable_services.sh" "[Step 10/10] Enable Services: Systemd and BLE backends" 11
  run_step "./provision/05_verify.sh" "[Final Step] Verify: System and service check" 12
fi

rm -f "$STATE_FILE"
echo -e "${GREEN}All provisioning steps completed!${NC}"
echo -e "${GREEN}Device is ready for use.${NC}"
