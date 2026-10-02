#!/usr/bin/env bash
#
# Provisioning Wizard for ipr-keyboard (with reboot resume)
#
# Guides the user through all provisioning steps, handles reboots, and resumes
# automatically.  Runs interactively by default, or completely unattended with
# --unattended, in which case every question is answered from the answer file
# instead of the keyboard and the reboots are chained through a systemd unit.
#
# Usage:
#   sudo ./provision/provision_wizard.sh                 # interactive (default)
#   sudo ./provision/provision_wizard.sh --unattended    # no questions at all
#   sudo ./provision/provision_wizard.sh --help
#
# Options:
#   -u, --unattended   Never read from the keyboard.  Every decision comes from
#                      the answer file (below) or its documented default, and a
#                      step that would need a human fails fast with the reason
#                      instead of hanging on a prompt.
#       --resume       Continue from the recorded step without asking.  Implied
#                      by --unattended; set by the reboot-resume unit.
#       --from-step N  Start at step N (1..13) instead of the recorded one.
#       --no-reboot    Never reboot.  The wizard stops where a reboot is due and
#                      says what to run after rebooting by hand.
#       --list-steps   Print the step list and exit.
#   -h, --help         Print this help and exit.
#
# Answer file: /opt/ipr_common.env (the same file the steps already read, so
# there is one place to look).  Everything is optional; defaults in brackets.
#
#   INSTALL_COPILOT_TOOLS=yes|no   install the copilotdiag account + dbg_* [yes]
#   RECLONE_REPO=yes|no            delete and re-clone an existing checkout [no]
#   SKIP_GITHUB_SSH=yes|no         skip the GitHub SSH key setup and test [no,
#                                  but forced yes on a payload device]
#   AUTO_REBOOT=yes|no             reboot automatically where a step needs it
#                                  and resume afterwards [yes in --unattended]
#   EDIT_COMMON_ENV=yes|no         open the editor on provision/common.env [yes
#                                  interactively, never in --unattended]
#   FINAL_VERIFY=yes|no            run the full post-provision audit as the
#                                  last step and exit non-zero on failures [yes]
#
# In --unattended the device configuration must already be in place: either
# /opt/ipr_common.env or provision/common.env, edited (not the untouched
# example).  The wizard refuses to continue with the example, because every
# device would then come up with the same hostname and Bluetooth name.
#
# category: Provisioning
# purpose: Stepwise provisioning, interactive or fully unattended, with reboot resume
# sudo: yes

set -eo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m'

STATE_FILE="/opt/ipr_state/provision_wizard_state.txt"
LOG_FILE="/opt/ipr_state/provision_wizard.log"
VERIFY_LOG="/opt/ipr_state/provision_verify.log"
ANSWER_FILE="/opt/ipr_common.env"
RESUME_UNIT="ipr-provision-resume.service"
RESUME_UNIT_PATH="/etc/systemd/system/${RESUME_UNIT}"

# ---------------------------------------------------------------------------
# Options and answers
#
# UNATTENDED is the one switch that matters: with it set, nothing ever reads
# from stdin.  Every question becomes a lookup in the answer file with a
# documented default, so an unattended run is reproducible from the files on
# the device alone.
# ---------------------------------------------------------------------------
UNATTENDED=0
RESUME=0
FROM_STEP=""
ALLOW_REBOOT=1

usage() {
  sed -n '2,/^set -eo pipefail/p' "$0" | sed 's/^# \{0,1\}//; $d'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -u|--unattended) UNATTENDED=1; RESUME=1 ;;
    --resume)        RESUME=1 ;;
    --from-step)     FROM_STEP="${2:-}"; shift ;;
    --no-reboot)     ALLOW_REBOOT=0 ;;
    --list-steps)    LIST_STEPS=1 ;;
    -h|--help)       usage; exit 0 ;;
    *) echo "Unknown option: $1  (try --help)" >&2; exit 2 ;;
  esac
  shift
done

if [[ -n "$FROM_STEP" && ! "$FROM_STEP" =~ ^[0-9]+$ ]]; then
  echo "--from-step takes a number (1..13)" >&2
  exit 2
fi

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
  "Copilot: debug tools"
  "Verify: System and service check"
  "Final verification: full post-provision audit"
  "Device info: Post-provisioning summary"
)

if [[ -n "${LIST_STEPS:-}" ]]; then
  for i in "${!STEP_NAMES[@]}"; do
    printf "  %2d) %s\n" "$((i+1))" "${STEP_NAMES[$i]}"
  done
  exit 0
fi

# answer_for KEY DEFAULT -- a key from the answer file, else the default.
#
# The CR is stripped on purpose: common.env is routinely edited on the
# administrator's Windows PC and copied over as-is, and a trailing \r turns
# "no" into something that matches neither yes nor no -- which silently became
# "yes" for every option.
answer_for() {
  local key="$1" default="$2" val=""
  if [[ -r "$ANSWER_FILE" ]]; then
    val="$(awk -F= -v k="$key" '
      $0 ~ "^[[:space:]]*"k"[[:space:]]*=" { gsub(/["\r ]/,"",$2); print $2; exit }
    ' "$ANSWER_FILE")"
  fi
  echo "${val:-$default}"
}

# Tolerant of a stray CR for the same reason.
is_yes() { local v="${1//$'\r'/}"; [[ "${v,,}" =~ ^(y|yes|true|1)$ ]]; }
is_no()  { local v="${1//$'\r'/}"; [[ "${v,,}" =~ ^(n|no|false|0)$ ]]; }

# ask_yes_no PROMPT DEFAULT ANSWER_KEY
#
# Interactively asks; unattended, takes ANSWER_KEY from the answer file and
# falls back to DEFAULT.  Returns 0 for yes.
ask_yes_no() {
  local prompt="$1" default="$2" key="${3:-}" ans=""
  if (( UNATTENDED )); then
    ans="$default"
    [[ -n "$key" ]] && ans="$(answer_for "$key" "$default")"
    echo -e "${BLUE}${prompt} -> ${ans} (unattended)${NC}"
    is_yes "$ans"
    return
  fi
  echo -en "${YELLOW}${prompt} [$( is_yes "$default" && echo 'Y/n' || echo 'y/N' )]: ${NC}"
  read -r ans
  ans="${ans//$'\r'/}"
  [[ -z "$ans" ]] && ans="$default"
  is_yes "$ans"
}


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
  if (( UNATTENDED )); then
    return 0
  fi
  echo -en "${YELLOW}Continue to next step? [Y/n]: ${NC}"
  read -r ans
  if [[ "${ans,,}" =~ ^(n|no)$ ]]; then
    echo -e "${RED}Aborting provisioning.${NC}"
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# Reboot resume
#
# A reboot in the middle of provisioning used to mean "re-run the wizard by
# hand afterwards", which is the one thing an unattended run cannot do.  The
# wizard therefore arms a one-shot systemd unit before rebooting; the unit
# re-runs the wizard with --unattended --resume once the system is back, then
# disarms itself.  It is armed per reboot, never left enabled: a run that dies
# does not re-run itself on every subsequent boot.
# ---------------------------------------------------------------------------
write_resume_unit() {
  local script_path="$1"
  cat > "$RESUME_UNIT_PATH" <<EOF
[Unit]
Description=Resume IPR provisioning after a reboot
Documentation=file://${PROJECT_DIR}/provision/README.md
After=multi-user.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=no
# Disarm first: each reboot is armed deliberately by the wizard, so a failed
# run cannot keep re-running on every boot.
ExecStartPre=-/usr/bin/systemctl disable ${RESUME_UNIT}
ExecStart=/bin/bash ${script_path} --unattended --resume
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
}

arm_resume() {
  local script_path
  script_path="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
  write_resume_unit "$script_path"
  systemctl enable "$RESUME_UNIT" >/dev/null 2>&1 || true
  success "Armed $RESUME_UNIT -- provisioning continues automatically after the reboot."
  if (( ! UNATTENDED )); then
    # Be explicit: a systemd unit has no console to ask questions on, so the
    # continuation runs unattended whatever this run started as.  The steps
    # after a reboot ask nothing beyond "continue", but the answer file -- not
    # the keyboard -- decides from here.
    warn "The run continues UNATTENDED after the reboot (a boot-time unit has no"
    warn "terminal).  Remaining answers come from $ANSWER_FILE."
    warn "To stay in control instead, answer no here and set AUTO_REBOOT=no."
  fi
  warn "Follow it with:  journalctl -u $RESUME_UNIT -f"
}

disarm_resume() {
  systemctl disable "$RESUME_UNIT" >/dev/null 2>&1 || true
  rm -f "$RESUME_UNIT_PATH"
  systemctl daemon-reload >/dev/null 2>&1 || true
  # Clear any failed state too: a run that died mid-step leaves the unit in
  # `systemctl --failed` long after its file is gone, which looks like a
  # broken device and trips the audit's "no failed units" check.
  systemctl reset-failed "$RESUME_UNIT" >/dev/null 2>&1 || true
}

# ---------------------------------------------------------------------------
# A firmware setting only takes effect at the next boot.  install_oled_support.sh
# adds dtparam=i2c_arm=on and install_gpio_support.sh the gpio= line; both warn
# about it, but nothing acted on the warning: on a fresh image /dev/i2c-1 never
# appeared, the application logged "OLED display disabled", and the closing
# audit failed on N.4.  Detect it by comparing config.txt against the boot
# time and chain one more reboot through the same resume unit.
# ---------------------------------------------------------------------------
firmware_reboot_pending() {
  local cfg now up boot_epoch
  now="$(date +%s)"
  up="$(cut -d. -f1 /proc/uptime 2>/dev/null || echo 0)"
  boot_epoch=$(( now - up ))
  for cfg in /boot/firmware/config.txt /boot/config.txt; do
    [[ -f "$cfg" ]] || continue
    if [[ "$(stat -c %Y "$cfg" 2>/dev/null || echo 0)" -gt "$boot_epoch" ]]; then
      return 0
    fi
  done
  return 1
}

prompt_reboot() {
  local next_step="$1"
  echo "wizard_step=$next_step" > "$STATE_FILE"

  local auto
  auto="$(answer_for AUTO_REBOOT "$( (( UNATTENDED )) && echo yes || echo ask )")"

  if (( ! ALLOW_REBOOT )) || is_no "$auto"; then
    warn "A reboot is required before step $next_step."
    warn "Reboot, then continue with:"
    warn "  sudo $0 --resume$( (( UNATTENDED )) && echo ' --unattended')"
    exit 0
  fi

  if (( UNATTENDED )) || is_yes "$auto"; then
    arm_resume
  else
    echo -en "${YELLOW}System reboot required. Reboot now? [Y/n]: ${NC}"
    read -r ans
    if [[ "${ans,,}" =~ ^(n|no)$ ]]; then
      warn "You must reboot before continuing.  Afterwards run:  sudo $0 --resume"
      exit 0
    fi
    # Interactive runs get the same automatic continuation; it is strictly
    # less work than being told to re-run the wizard by hand.
    arm_resume
  fi

  echo -e "${YELLOW}Rebooting now; provisioning resumes by itself.${NC}"
  sleep 2
  reboot
}

# Helper: Ensure we are in the project directory
# ---------------------------------------------------------------------------
# Source mode
#
# A development device clones from GitHub and works from a git checkout.  A
# target device is seeded from the administrator PC by make_payload.sh, which
# ships only the files the device needs and no .git directory -- and such a
# device usually has no internet access either.  Every git and GitHub step below
# has to be skipped there, or the wizard dies on "not a git repository".
# ---------------------------------------------------------------------------
PROJECT_DIR="${REPO_DIR:-/home/meibye/dev/ipr-keyboard}"
DEVICE_TYPE_ENV=""
if [[ -r /opt/ipr_common.env ]]; then
  DEVICE_TYPE_ENV="$(awk -F= '/^[[:space:]]*DEVICE_TYPE[[:space:]]*=/ {gsub(/[" ]/,"",$2); print $2; exit}' /opt/ipr_common.env)"
fi

is_payload_device() {
  # A checkout wins: if git is there, use it whatever the env file says.
  [[ -d "$PROJECT_DIR/.git" ]] && return 1
  [[ "$DEVICE_TYPE_ENV" == "target" ]] && return 0
  return 1
}

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

# ---------------------------------------------------------------------------
# Library mode
#
# tests/scripts/test_provision_wizard.sh sources this file to exercise the
# answer handling without provisioning anything.  Everything above is pure
# definition; everything below touches the system.
# ---------------------------------------------------------------------------
if [[ -n "${PROVISION_WIZARD_LIB_ONLY:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi

# Main wizard logic
# Ensure state directory exists
STATE_DIR="$(dirname "$STATE_FILE")"
mkdir -p "$STATE_DIR"

# Everything from here is also written to the log, so an unattended run can be
# read back afterwards (and followed live with tail -f).
exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== provisioning run started $(date -Is) (unattended=$UNATTENDED resume=$RESUME) ==="

if (( ! UNATTENDED )); then
  clear
  echo -e "${BLUE}IPR Keyboard - Interactive Provisioning Wizard${NC}"
  echo "This script will guide you through all provisioning steps."
  echo "You must run this as root (sudo)."
  echo ""
else
  echo -e "${BLUE}IPR Keyboard - Unattended Provisioning${NC}"
  echo "Answers come from $ANSWER_FILE; nothing is read from the keyboard."
  echo "Log: $LOG_FILE"
fi



# ---------------------------------------------------------------------------
# Unattended preflight
#
# The one thing an unattended run cannot improvise is the device identity.
# Refuse the untouched example rather than bring every device up as the same
# host with the same Bluetooth name.
# ---------------------------------------------------------------------------
if (( UNATTENDED )); then
  _cfg=""
  for _c in "$ANSWER_FILE" "$PROJECT_DIR/provision/common.env"; do
    [[ -r "$_c" ]] && { _cfg="$_c"; break; }
  done
  if [[ -z "$_cfg" ]]; then
    fail "Unattended run needs a device configuration."
    fail "Create $ANSWER_FILE (or $PROJECT_DIR/provision/common.env) from"
    fail "provision/common.env.example and set at least HOSTNAME and BT_DEVICE_NAME."
    exit 1
  fi
  if [[ -r "$PROJECT_DIR/provision/common.env.example" ]] \
     && cmp -s "$_cfg" "$PROJECT_DIR/provision/common.env.example"; then
    fail "$_cfg is still the unedited example."
    fail "Edit it (HOSTNAME, BT_DEVICE_NAME, DEVICE_TYPE) and run again."
    exit 1
  fi
  success "Unattended preflight: using $_cfg"
  for _k in INSTALL_COPILOT_TOOLS RECLONE_REPO SKIP_GITHUB_SSH AUTO_REBOOT; do
    echo "    $_k=$(answer_for "$_k" "(default)")"
  done
fi

# Offer to start over, resume, or select a step
if [[ -n "$FROM_STEP" ]]; then
  wizard_step="$FROM_STEP"
  echo "wizard_step=$wizard_step" > "$STATE_FILE"
  echo -e "${YELLOW}Starting from step $wizard_step: ${STEP_NAMES[$((wizard_step-1))]}${NC}"
elif (( RESUME )); then
  wizard_step=1
  [[ -f "$STATE_FILE" ]] && source "$STATE_FILE"
  echo -e "${BLUE}Resuming at step $wizard_step: ${STEP_NAMES[$((wizard_step-1))]}${NC}"
elif [[ -f "$STATE_FILE" ]]; then
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
  step "[Step 1/14] Install git (required to clone the repository)"
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
  step "[Step 2/14] Clone the repository"
  if is_payload_device; then
    warn "DEVICE_TYPE=target and no git checkout found."
    warn "Using the files transferred from the administrator PC; not cloning."
    missing=()
    for item in src provision scripts pyproject.toml README.md \
                config.default.json users.default.json; do
      [[ -e "$PROJECT_DIR/$item" ]] || missing+=("$item")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
      fail "Incomplete payload in $PROJECT_DIR -- missing: ${missing[*]}"
      fail "Transfer the files again from the PC:"
      fail "  ./scripts/deploy/host_push_to_device.sh <host>"
      exit 1
    fi
    success "Payload verified -- all required files are present."
    cd "$PROJECT_DIR"
    # Advance both the file and the variable: the next block tests the same
    # condition, so leaving $wizard_step stale would run the clone anyway.
    echo "wizard_step=3" > "$STATE_FILE"
    wizard_step=3
    prompt_continue
  fi
fi

if [[ "$wizard_step" -le 2 ]]; then
  mkdir -p /home/meibye/dev
  cd /home/meibye/dev
  if [[ -d ipr-keyboard ]]; then
      warn "Repository directory already exists."
      if ask_yes_no "Delete and re-clone the repository?" no RECLONE_REPO; then
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
  step "[Step 3/14] Create device configuration"
  _needs_edit=0
  if [[ ! -f provision/common.env ]] || cmp -s provision/common.env.example provision/common.env; then
    _needs_edit=1
  fi

  if (( UNATTENDED )); then
    # No editor, ever.  Either a usable configuration is already there, or the
    # preflight above has already refused the run.
    if (( _needs_edit )); then
      if [[ -r "$ANSWER_FILE" ]]; then
        warn "provision/common.env is missing or unedited; using $ANSWER_FILE as-is."
        cp "$ANSWER_FILE" provision/common.env
      else
        fail "No usable device configuration (provision/common.env is the example)."
        exit 1
      fi
    else
      success "Using existing device configuration (unattended)."
    fi
  elif (( _needs_edit )); then
    cp provision/common.env.example provision/common.env
    echo -e "${YELLOW}Please edit provision/common.env with device-specific values.${NC}"
    "${EDITOR:-nano}" provision/common.env
  elif ask_yes_no "Existing device configuration found. Edit it?" no EDIT_COMMON_ENV; then
    "${EDITOR:-nano}" provision/common.env
  else
    success "Using existing device configuration."
  fi
  sudo cp provision/common.env /opt/ipr_common.env
  echo "wizard_step=4" > "$STATE_FILE"
  prompt_continue
fi

# Step 4: Make scripts executable
if [[ "$wizard_step" -le 4 ]]; then
  ensure_project_dir
  step "[Step 4/14] Make provisioning scripts executable"
  chmod +x ./provision/*.sh
  success "Scripts are now executable."
  echo "wizard_step=5" > "$STATE_FILE"
  prompt_continue
fi


# Step 5: Run 00_bootstrap.sh
if [[ "$wizard_step" -le 5 ]]; then
  ensure_project_dir
  run_step "./provision/00_bootstrap.sh" "[Step 5/14] Bootstrap: Install base tools and clone repo" 6

  # Check if a new SSH key was generated (look for id_ed25519.pub in /home/$SUDO_USER/.ssh/ or /root/.ssh/)
  SSH_KEY=""
  if [[ -n "${SUDO_USER:-}" && -f "/home/$SUDO_USER/.ssh/id_ed25519.pub" ]]; then
    SSH_KEY="/home/$SUDO_USER/.ssh/id_ed25519.pub"
  elif [[ -f "$HOME/.ssh/id_ed25519.pub" ]]; then
    SSH_KEY="$HOME/.ssh/id_ed25519.pub"
  fi
  if [[ -n "$SSH_KEY" ]] && (( ! UNATTENDED )) && ! is_yes "$(answer_for SKIP_GITHUB_SSH no)"; then
    echo -e "${YELLOW}If a new SSH key was generated, you must add it to your GitHub account before continuing.${NC}"
    echo -e "${YELLOW}Copy the following public key and add it at:${NC} https://github.com/settings/keys"
    echo -e "${BLUE}--- BEGIN PUBLIC KEY ---${NC}"
    cat "$SSH_KEY"
    echo -e "${BLUE}--- END PUBLIC KEY ---${NC}"
    echo -en "${YELLOW}Press Enter after you have added the key to GitHub...${NC}"
    read -r _
  elif [[ -n "$SSH_KEY" ]]; then
    warn "A public key exists at $SSH_KEY."
    warn "Add it at https://github.com/settings/keys if this device pulls from GitHub."
  fi
fi

# Step 6: Setup and test GitHub SSH keys
if [[ "$wizard_step" -le 6 ]]; then
  ensure_project_dir
  step "[Step 6/14] Setup and test GitHub SSH keys"

  # Nothing here is reachable without a human and a browser, and an unattended
  # run has neither: the ssh test can block on a host-key prompt, and a device
  # that pulls from GitHub needs its key registered there first.  Skip by
  # default when unattended, or on request.
  if (( UNATTENDED )) || is_yes "$(answer_for SKIP_GITHUB_SSH no)"; then
    warn "Skipping GitHub SSH setup (unattended, or SKIP_GITHUB_SSH=yes)."
    warn "Run it later with: sudo $0 --from-step 6"
    echo "wizard_step=7" > "$STATE_FILE"
    wizard_step=7
  fi

  if is_payload_device; then
    # Nothing here can succeed: 00_bootstrap.sh does not generate a key on a
    # payload device, there is no repository for `git remote set-url` to act
    # on, and the device generally cannot reach GitHub at all.  Left unguarded,
    # the ssh test prompts for a host key and `git remote` then aborts the
    # wizard with "fatal: not a git repository".
    warn "Skipping GitHub SSH setup -- this device is seeded from a transferred"
    warn "payload and has no git checkout. Updates come from the administrator"
    warn "PC; see section 8.5 of the administrator manual."
    # Advance both the file and the variable: the next block tests the same
    # condition, so leaving $wizard_step stale would run the GitHub steps anyway.
    echo "wizard_step=7" > "$STATE_FILE"
    wizard_step=7
    prompt_continue
  fi
fi

if [[ "$wizard_step" -le 6 ]]; then


  # Ensure ssh-agent is running and key is added for the correct user
  SSH_KEY=""
  SSH_USER="${SUDO_USER:-$USER}"
  SSH_HOME="/home/$SSH_USER"
  if [[ -f "$SSH_HOME/.ssh/id_ed25519" ]]; then
    SSH_KEY="$SSH_HOME/.ssh/id_ed25519"
  fi
  echo -e "${YELLOW}Configuring ssh-agent for user: $SSH_USER${NC}"
  if [[ -n "$SSH_KEY" ]]; then
    echo -e "${BLUE}Debug: SSH_USER=$SSH_USER, SSH_KEY=$SSH_KEY, SSH_HOME=$SSH_HOME${NC}"
    # Try to get SSH_AUTH_SOCK from the user's environment
    SSH_AUTH_SOCK_PATH=""
    SSH_ENV_FILE="$SSH_HOME/.ssh/agent.env"
    echo -e "${BLUE}Debug: Checking for running ssh-agent for $SSH_USER...${NC}"
    if sudo -u "$SSH_USER" pgrep ssh-agent > /dev/null; then
      echo -e "${BLUE}Debug: ssh-agent is running for $SSH_USER${NC}"
      SSH_AUTH_SOCK_PATH=$(sudo -u "$SSH_USER" bash -c 'echo $SSH_AUTH_SOCK')
      echo -e "${BLUE}Debug: SSH_AUTH_SOCK from running agent: $SSH_AUTH_SOCK_PATH${NC}"
    else
      echo -e "${YELLOW}Debug: No running ssh-agent found for $SSH_USER${NC}"
    fi
    if [[ -z "$SSH_AUTH_SOCK_PATH" ]]; then
      echo -e "${YELLOW}Debug: Starting new ssh-agent for $SSH_USER and saving env to $SSH_ENV_FILE${NC}"
      rm -f "$SSH_HOME/.ssh/agent.env"
      sudo -u "$SSH_USER" bash -c 'ssh-agent -s' > "$SSH_HOME/.ssh/agent.env"
      echo -e "${BLUE}Debug: Contents of $SSH_ENV_FILE:${NC}"
      # Extract SSH_AUTH_SOCK value directly from agent.env to avoid echo line
      SSH_AUTH_SOCK_PATH=$(awk -F= '/^SSH_AUTH_SOCK=/ {gsub(/;.*/,"",$2); print $2}' "$SSH_HOME/.ssh/agent.env")
      echo -e "${BLUE}Debug: SSH_AUTH_SOCK from new agent: $SSH_AUTH_SOCK_PATH${NC}"
    fi
    if [[ -n "$SSH_AUTH_SOCK_PATH" ]]; then
      echo -e "${BLUE}Debug: Using SSH_AUTH_SOCK=$SSH_AUTH_SOCK_PATH for ssh-add${NC}"
      # Check if key is already added
      KEY_FINGERPRINT=$(ssh-keygen -lf "$SSH_KEY" | awk '{print $2}')
      echo -e "${BLUE}Debug: Key fingerprint: $KEY_FINGERPRINT${NC}"
      if ! sudo -u "$SSH_USER" SSH_AUTH_SOCK="$SSH_AUTH_SOCK_PATH" ssh-add -l | grep -q "$KEY_FINGERPRINT"; then
        echo -e "${YELLOW}Debug: Key not found in agent, adding...${NC}"
        sudo -u "$SSH_USER" SSH_AUTH_SOCK="$SSH_AUTH_SOCK_PATH" ssh-add "$SSH_KEY"
        echo "SSH key $SSH_KEY added to ssh-agent."
      else
        echo -e "${BLUE}Debug: SSH key $SSH_KEY is already added to ssh-agent.${NC}"
      fi
    else
      warn "Could not determine SSH_AUTH_SOCK for $SSH_USER. ssh-add may fail."
    fi
  fi

  echo -e "${YELLOW}Testing SSH connection to GitHub. Answer 'yes' if prompted.${NC}"
  set +e
  SSH_TEST_OUTPUT=$(sudo -u "$SSH_USER" SSH_AUTH_SOCK="$SSH_AUTH_SOCK_PATH" ssh -T git@github.com 2>&1)
  echo "$SSH_TEST_OUTPUT"
  if echo "$SSH_TEST_OUTPUT" | grep -q "successfully authenticated"; then
    success "SSH authentication to GitHub succeeded."
  else
  
    warn "SSH test failed. You may need to set up your SSH key."
  fi
  set -e
  if [[ -d "$PROJECT_DIR/.git" ]]; then
    git -C "$PROJECT_DIR" remote set-url origin git@github.com:meibye/ipr-keyboard.git
  else
    warn "No git checkout at $PROJECT_DIR; skipping 'git remote set-url'."
  fi
  echo "wizard_step=7" > "$STATE_FILE"
  prompt_continue
fi

# Step 7: Run 01_os_base.sh (reboot required)
if [[ "$wizard_step" -le 7 ]]; then
  ensure_project_dir
  run_step "./provision/01_os_base.sh" "[Step 7/14] OS Base: System packages and Bluetooth config" 8
  prompt_reboot 8
fi

# Step 8: Run 02_device_identity.sh (reboot required)
if [[ "$wizard_step" -le 8 ]]; then
  ensure_project_dir
  run_step "./provision/02_device_identity.sh" "[Step 8/14] Device Identity: Hostname and Bluetooth name" 9
  prompt_reboot 9
fi

# Step 9: Run 03_app_install.sh
if [[ "$wizard_step" -le 9 ]]; then
    ensure_project_dir
    run_step "./provision/03_app_install.sh" "[Step 9/14] App Install: Python venv and dependencies" 10
fi

# Step 10: Run 04_enable_services.sh
if [[ "$wizard_step" -le 10 ]]; then
    ensure_project_dir
    run_step "./provision/04_enable_services.sh" "[Step 10/14] Enable Services: Systemd and BLE backends" 11

    # The installers this step runs may have enabled I2C or the LED pins in
    # config.txt.  Without a reboot /dev/i2c-1 does not exist, the display
    # stays disabled and the audit in step 13 fails -- so reboot here, where
    # the resume unit carries the run on by itself.
    if firmware_reboot_pending; then
        warn "config.txt changed since boot (I2C / GPIO firmware settings)."
        warn "A reboot is required before the display and the LED work."
        prompt_reboot 11
    fi
fi

# Step 11: Run 05_copilot_debug_tools.sh
if [[ "$wizard_step" -le 11 ]]; then
    ensure_project_dir
    # Optional tooling, so it must not be able to abort provisioning.
    #
    # Step 05 installs the copilotdiag diagnostics account and the dbg_* helper
    # scripts.  Useful -- .vscode/mcp.json reaches production through that
    # account -- but auxiliary: the device runs perfectly without it.  Running
    # it through run_step meant any failure here exited the wizard before
    # verification (step 12) and the device summary (step 13) had run.
    #
    # Set INSTALL_COPILOT_TOOLS="no" in /opt/ipr_common.env to skip it, e.g. on
    # a hardened production device where a second SSH account is unwanted.
    INSTALL_COPILOT_TOOLS_VAL="yes"
    if [[ -r /opt/ipr_common.env ]]; then
        _v="$(awk -F= '/^[[:space:]]*INSTALL_COPILOT_TOOLS[[:space:]]*=/ {gsub(/[" ]/,"",$2); print $2; exit}' /opt/ipr_common.env)"
        [[ -n "$_v" ]] && INSTALL_COPILOT_TOOLS_VAL="$_v"
    fi

    step "[Step 11/14] Copilot: debug tools"
    if [[ "${INSTALL_COPILOT_TOOLS_VAL,,}" =~ ^(no|false|0)$ ]]; then
        warn "Skipping: INSTALL_COPILOT_TOOLS=$INSTALL_COPILOT_TOOLS_VAL in /opt/ipr_common.env."
    elif bash ./provision/05_copilot_debug_tools.sh; then
        success "[Step 11/14] Copilot: debug tools completed successfully."
    else
        warn "[Step 11/14] Copilot debug tools failed."
        warn "This is optional tooling; provisioning continues. Re-run later with:"
        warn "  sudo ./provision/05_copilot_debug_tools.sh"
    fi
    echo "wizard_step=12" > "$STATE_FILE"
    wizard_step=12
    prompt_continue
fi

# Step 12: Run 06_verify.sh
if [[ "$wizard_step" -le 12 ]]; then
    ensure_project_dir
    run_step "./provision/06_verify.sh" "[Step 12/14] Verify: System and service check" 13
fi

# Step 13: Final verification -- the audit that says whether provisioning
# actually produced a working device.
#
# 06_verify.sh (step 12) reports what the device looks like; this runs the
# full post-provision audit, which checks every artefact the provisioning
# steps were supposed to create and exits with the number of failures.  A
# provisioning run that ends green here needs no further interpretation.
if [[ "$wizard_step" -le 13 ]]; then
    ensure_project_dir
    step "[Step 13/14] Final verification: full post-provision audit"

    if is_no "$(answer_for FINAL_VERIFY yes)"; then
        warn "Skipping: FINAL_VERIFY=no in $ANSWER_FILE."
        VERIFY_FAILURES=0
    elif [[ ! -x ./scripts/headless/test_provision.sh && ! -f ./scripts/headless/test_provision.sh ]]; then
        warn "scripts/headless/test_provision.sh not found -- skipping the audit."
        VERIFY_FAILURES=0
    else
        # The audit writes its own report (colour stripped); no tee here, or
        # the two would race for the same file.
        set +e
        bash ./scripts/headless/test_provision.sh --auto --report "$VERIFY_LOG"
        VERIFY_FAILURES=$?
        set -e
        if [[ "$VERIFY_FAILURES" -eq 0 ]]; then
            success "[Step 13/14] Final verification passed -- no failed checks."
        else
            fail "[Step 13/14] Final verification found $VERIFY_FAILURES failed check(s)."
            fail "Details: $VERIFY_LOG"
            # Do not abort: the device summary (step 14) still has to print, and
            # the failures are repeated in the closing banner.
        fi
    fi
    echo "wizard_step=14" > "$STATE_FILE"
    wizard_step=14
    prompt_continue
fi

# Step 14: Show post-provisioning info (credentials, URLs, SSH)
if [[ "$wizard_step" -le 14 ]]; then
    ensure_project_dir
    run_step "./provision/07_show_info.sh" "[Step 14/14] Device info: Post-provisioning summary" 15
fi

# Provisioning finished: drop the state and make sure no reboot-resume unit is
# left armed on the device.
rm -f "$STATE_FILE"
disarm_resume
if [[ "${VERIFY_FAILURES:-0}" -eq 0 ]]; then
    success "Provisioning complete -- final verification passed."
else
    fail "Provisioning finished, but the final verification reported ${VERIFY_FAILURES} failure(s)."
    fail "Read $VERIFY_LOG, fix, then re-run:  sudo $0 --from-step 13"
fi
echo "=== provisioning run finished $(date -Is) ==="
exit "${VERIFY_FAILURES:-0}"
