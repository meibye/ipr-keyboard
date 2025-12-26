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
BLUE='\033[1;34m'
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

# Helper: Ensure we are in the project directory
ensure_project_dir() {
  local proj_dir="/home/meibye/dev/ipr-keyboard"
  if [[ "$PWD" != "$proj_dir" ]]; then
    if [[ -d "$proj_dir" ]]; then
      cd "$proj_dir"
      echo -e "${BLUE}Changed directory to $proj_dir${NC}"
    else
      echo -e "${RED}Project directory $proj_dir does not exist. Aborting.${NC}"
      exit 1
    fi
  fi
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

# Ensure state directory exists
STATE_DIR="$(dirname "$STATE_FILE")"
mkdir -p "$STATE_DIR"


# Step names for menu
STEP_NAMES=(
  "Install git (required to clone the repository)"
  "Clone the repository"
  "Create device configuration"
  "Make provisioning scripts executable"
  "Bootstrap: Install base tools and clone repo"
  "Setup and test GitHub SSH keys"
  "OS Base: System packages and Bluetooth config (reboot required)"
  "Device Identity: Hostname and Bluetooth name (reboot required)"
  "App Install: Python venv and dependencies"
  "Enable Services: Systemd and BLE backends"
  "Verify: System and service check"
)

# Offer to start over, resume, or select a step
if [[ -f "$STATE_FILE" ]]; then
  source "$STATE_FILE"
  echo -e "${YELLOW}Previous provisioning detected (step: $wizard_step).${NC}"
  echo -e "${YELLOW}Select an option:${NC}"
  echo "  1) Resume from last interrupted step ($wizard_step: ${STEP_NAMES[$((wizard_step-1))]})"
  echo "  2) Start over from the beginning"
  echo "  3) Start from a specific step"
  echo -en "${YELLOW}Enter choice [1/2/3]: ${NC}"
  read -r choice
  case "$choice" in
    2)
      rm -f "$STATE_FILE"
      wizard_step=1
      echo -e "${YELLOW}State cleared. Starting from step 1.${NC}"
      ;;
    3)
      echo -e "${YELLOW}Select a step to start from:${NC}"
      for i in "${!STEP_NAMES[@]}"; do
        printf "  %2d) %s\n" "$((i+1))" "${STEP_NAMES[$i]}"
      done
      echo -en "${YELLOW}Enter step number [1-${#STEP_NAMES[@]}]: ${NC}"
      read -r stepnum
      if [[ "$stepnum" =~ ^[0-9]+$ ]] && (( stepnum >= 1 && stepnum <= ${#STEP_NAMES[@]} )); then
        wizard_step=$stepnum
        echo "wizard_step=$wizard_step" > "$STATE_FILE"
        echo -e "${YELLOW}Starting from step $wizard_step: ${STEP_NAMES[$((wizard_step-1))]}${NC}"
      else
        echo -e "${RED}Invalid step number. Aborting.${NC}"
        exit 1
      fi
      ;;
    *)
      # Default: resume from last step
      ;;
  esac
else
  wizard_step=1
fi


# Step 1: Install git
if [[ "$wizard_step" -le 1 ]]; then
  step "[Step 1/11] Install git (required to clone the repository)"
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
  step "[Step 2/11] Clone the repository"
  mkdir -p /home/meibye/dev
  cd /home/meibye/dev
  if [[ -d ipr-keyboard ]]; then
      warn "Repository directory already exists."
      echo -en "${YELLOW}Delete and re-clone the repository? [y/N]: ${NC}"
      read -r ans
      if [[ "${ans,,}" =~ ^(y|yes)$ ]]; then
          rm -rf ipr-keyboard
          success "Old repository deleted."
      else
          warn "Skipping clone. Using existing repository."
      fi
  fi
  if [[ ! -d ipr-keyboard ]]; then
      if git clone https://github.com/meibye/ipr-keyboard.git; then
          success "Repository cloned successfully."
      else
          warn "Repository may already exist or clone failed."
      fi
  fi
  cd ipr-keyboard
  echo "wizard_step=3" > "$STATE_FILE"
  prompt_continue
fi

# Step 3: Create device configuration
if [[ "$wizard_step" -le 3 ]]; then
  ensure_project_dir
  step "[Step 3/11] Create device configuration"
  cp provision/common.env.example provision/common.env
  echo -e "${YELLOW}Please edit provision/common.env with device-specific values.${NC}"
  nano provision/common.env
  sudo cp provision/common.env /opt/ipr_common.env
  echo "wizard_step=4" > "$STATE_FILE"
  prompt_continue
fi

# Step 4: Make scripts executable
if [[ "$wizard_step" -le 4 ]]; then
  ensure_project_dir
  step "[Step 4/10] Make provisioning scripts executable"
  chmod +x ./provision/*.sh
  success "Scripts are now executable."
  echo "wizard_step=5" > "$STATE_FILE"
  prompt_continue
fi


# Step 5: Run 00_bootstrap.sh
if [[ "$wizard_step" -le 5 ]]; then
  ensure_project_dir
  run_step "./provision/00_bootstrap.sh" "[Step 5/11] Bootstrap: Install base tools and clone repo" 6

  # Check if a new SSH key was generated (look for id_ed25519.pub in /home/$SUDO_USER/.ssh/ or /root/.ssh/)
  SSH_KEY=""
  if [[ -n "${SUDO_USER:-}" && -f "/home/$SUDO_USER/.ssh/id_ed25519.pub" ]]; then
    SSH_KEY="/home/$SUDO_USER/.ssh/id_ed25519.pub"
  elif [[ -f "$HOME/.ssh/id_ed25519.pub" ]]; then
    SSH_KEY="$HOME/.ssh/id_ed25519.pub"
  fi
  if [[ -n "$SSH_KEY" ]]; then
    echo -e "${YELLOW}If a new SSH key was generated, you must add it to your GitHub account before continuing.${NC}"
    echo -e "${YELLOW}Copy the following public key and add it at:${NC} https://github.com/settings/keys"
    echo -e "${BLUE}--- BEGIN PUBLIC KEY ---${NC}"
    cat "$SSH_KEY"
    echo -e "${BLUE}--- END PUBLIC KEY ---${NC}"
    echo -en "${YELLOW}Press Enter after you have added the key to GitHub...${NC}"
    read -r _
  fi
fi

# Step 6: Setup and test GitHub SSH keys
if [[ "$wizard_step" -le 6 ]]; then
  ensure_project_dir
  step "[Step 6/10] Setup and test GitHub SSH keys"
  git remote set-url origin git@github.com:meibye/ipr-keyboard.git

  # Ensure ssh-agent is running and key is added
  SSH_KEY=""
  if [[ -n "${SUDO_USER:-}" && -f "/home/$SUDO_USER/.ssh/id_ed25519" ]]; then
    SSH_KEY="/home/$SUDO_USER/.ssh/id_ed25519"
  elif [[ -f "$HOME/.ssh/id_ed25519" ]]; then
    SSH_KEY="$HOME/.ssh/id_ed25519"
  fi
  if [[ -n "$SSH_KEY" ]]; then
    # Start ssh-agent if not running
    if ! pgrep -u "$USER" ssh-agent > /dev/null; then
      eval "$(ssh-agent -s)"
    fi
    # Check if key is already added
    if ! ssh-add -l | grep -q "$(ssh-keygen -lf "$SSH_KEY" | awk '{print $2}')"; then
      ssh-add "$SSH_KEY"
    fi
  fi

  echo -e "${YELLOW}Testing SSH connection to GitHub. Answer 'yes' if prompted.${NC}"
  ssh -T git@github.com || warn "SSH test failed. You may need to set up your SSH key."
  echo "wizard_step=7" > "$STATE_FILE"
  prompt_continue
fi

# Step 7: Run 01_os_base.sh (reboot required)
if [[ "$wizard_step" -le 7 ]]; then
  ensure_project_dir
  run_step "./provision/01_os_base.sh" "[Step 7/11] OS Base: System packages and Bluetooth config" 8
  prompt_reboot 8
fi

# Step 8: Run 02_device_identity.sh (reboot required)
if [[ "$wizard_step" -le 8 ]]; then
  ensure_project_dir
  run_step "./provision/02_device_identity.sh" "[Step 8/11] Device Identity: Hostname and Bluetooth name" 9
  prompt_reboot 9
fi

# Step 9: Run 03_app_install.sh
if [[ "$wizard_step" -le 9 ]]; then
    ensure_project_dir
    run_step "./provision/03_app_install.sh" "[Step 9/11] App Install: Python venv and dependencies" 10
fi

# Step 10: Run 04_enable_services.sh
if [[ "$wizard_step" -le 10 ]]; then
    ensure_project_dir
    run_step "./provision/04_enable_services.sh" "[Step 10/11] Enable Services: Systemd and BLE backends" 11
fi

# Step 11: Run 05_verify.sh
if [[ "$wizard_step" -le 11 ]]; then
    ensure_project_dir
    run_step "./provision/05_verify.sh" "[Step 11/11] Verify: System and service check" 12
fi

rm -f "$STATE_FILE"
echo -e "${GREEN}All provisioning steps completed!${NC}"
echo -e "${GREEN}Device is ready for use.${NC}"
