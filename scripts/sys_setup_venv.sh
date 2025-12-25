#!/usr/bin/env bash
#
# Python Virtual Environment Setup Script
#
# Purpose:
#   Creates a Python virtual environment using uv and installs the ipr-keyboard package in editable mode with development dependencies.
#
# Usage:
#   ./scripts/sys_setup_venv.sh
#
# Prerequisites:
#   - Must NOT be run as root
#   - Project directory must exist
#   - Environment variables set (sources env_set_variables.sh)
#
# Note:
#   Installs uv package manager if not already present.
#
# category: System
# purpose: Create Python virtual environment with uv
# sudo: no

set -eo pipefail


# Ensure tmux is installed
if ! command -v tmux >/dev/null 2>&1; then
  echo "[sys_setup_venv] tmux not found, installing..."
  sudo apt-get update
  sudo apt-get install -y tmux
else
  echo "[sys_setup_venv] tmux already installed."
fi

# Clone tmux plugin manager (TPM) if not already present
if [[ ! -d "$HOME/.config/tmux/plugins/tpm" ]]; then
  echo "[sys_setup_venv] Cloning tmux plugin manager (TPM)..."
  git clone https://github.com/tmux-plugins/tpm "$HOME/.config/tmux/plugins/tpm"
else
  echo "[sys_setup_venv] TPM already cloned at $HOME/.config/tmux/plugins/tpm."
fi

# Create tmux conf file if it does not exist
TMUX_CONF="$HOME/.config/tmux/tmux.conf"
rm -f "$TMUX_CONF"
if [[ ! -f "$TMUX_CONF" ]]; then
  echo "[sys_setup_venv] Creating default tmux.conf at $TMUX_CONF..."
  cat <<EOF > "$TMUX_CONF"
# Use bash as default
set -g default-shell /usr/bin/bash

# Enable 256-color and true-color (24-bit) support in tmux
set -s default-terminal "xterm-256color"    # Set terminal type for 256-color support
set -as terminal-features ",xterm-256color:clipboard:ccolour:cstyle:focus:title"
set -as terminal-overrides ",xterm*:Tc"

# Performance
set -as terminal-overrides ",xterm*:OT11"   # Silence the OSC 11 (rgb:0c0c...) garbage text
set -s escape-time 10           # Remove delay for exiting insert mode with ESC in Neovim
set -g history-limit 100000     # Increase history size (from 2.000)
set -g mouse on                 # Enable mouse support

# Clipboard: Correct use of Server flags
set -s set-clipboard on                     # Use system clipboard for copy operations
set -as terminal-overrides ',xterm*:Ms=\E]52;%p1%s;%p2%s\7'  # Enable clipboard access in xterm

# General
set -g detach-on-destroy off    # Don't exit from tmux when closing a session
set -g status-interval 3        # Update the status bar every 3 seconds (default: 15 seconds)
set -g allow-passthrough on     # Allow programs in the pane to bypass tmux (e.g. for image preview)
set -g status-position bottom

# Set prefix key
unbind C-b              # Unbind the default prefix key
set -g prefix C-Space   # Set new prefix key to Ctrl+Space
bind C-Space send-prefix # Make Ctrl+Space send the prefix key

# Refresh tmux config with r
unbind r
bind r source-file ~/.config/tmux/tmux.conf \; display "Config Reloaded!"

# Fix Terminal Title display, to not contain tmux specic information
set-option -g set-titles on
set-option -g set-titles-string "#{pane_title}"

# Split horizontally in CWD with unbind |
bind \| split-window -h -c "#{pane_current_path}"

# # Split vertically in CWD with -
unbind \"
bind - split-window -v -c "#{pane_current_path}"

# New window in same path
bind c new-window -c "#{pane_current_path}"

# Enable extended support for some more sophisticated terminal emulator
# features. Disable them if they are causing problems!
####### THE ARE CAUSING PROBLEMS ON THE RPI ########
# set-option -s focus-events on
set-option -s extended-keys on

# Move between panes using Alt-Arrow keys without prefix
bind -n M-Left  select-pane -L
bind -n M-Right select-pane -R
bind -n M-Up    select-pane -U
bind -n M-Down  select-pane -D

# # Use vim arrow keys to resize
# bind -r j resize-pane -D 5
# bind -r k resize-pane -U 5
# bind -r l resize-pane -R 5
# bind -r h resize-pane -L 5

# # Use m key to maximize pane
bind -r m resize-pane -Z

# # Don't exit copy mode when dragging with mouse
# unbind -T copy-mode-vi MouseDragEnd1Pane

# Start windows and panes at 1, not 0
set -g base-index 1
set -g pane-base-index 1
set -g renumber-windows on  # Automatically renumber windows when one is closed
bind ½ move-window -r       # Move current window to the end with "Prefix + ½" 

# tpm plugin manager
set -g @plugin 'tmux-plugins/tpm'

# List of tmux plugins
set -g @plugin 'christoomey/vim-tmux-navigator' # Enable navigating between nvim and tmux
set -g @plugin 'dracula/tmux'                   # Dracula theme for tmux
set -g @plugin 'tmux-plugins/tmux-resurrect'    # Persist tmux sessions after computer restart
set -g @plugin 'tmux-plugins/tmux-continuum'    # Automatically saves sessions every 15 minutes
# set -g @plugin 'hendrikmi/tmux-cpu-mem-monitor' # CPU and memory info
set -g @plugin 'tmux-plugins/tmux-sidebar'      # File explorer sidebar for tmux
set -g @plugin 'jaclu/tmux-menus'               # Easy to use menus for tmux

# Dracula theme settings (https://github.com/dracula/tmux/blob/master/docs/CONFIG.md)
set -g @dracula-show-powerline true             # Enable powerline symbols
set -g @dracula-show-window-status true         # Enable window status
set -g @dracula-cpu-display-load false          # Enable CPU load display
# set -g @dracula-continuum-mode countdown        # Show countdown timer for continuum
set -g @dracula-show-empty-plugins true         # Hide empty plugins section
set -g @dracula-plugins "cpu-usage ram-usage"
set -g @dracula-show-flags true
set -g @dracula-show-left-icon session

# Resurrect
set -g @resurrect-capture-pane-contents 'on'
# set -g @continuum-restore 'on'    # Last saved environment is automatically restored when tmux is started.

# Initialize TMUX plugin manager (keep this line at the very bottom of tmux.conf)
run '~/.config/tmux/plugins/tpm/tpm'
EOF
else
  echo "[sys_setup_venv] tmux.conf already exists at $TMUX_CONF."
fi

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/env_set_variables.sh"

echo "[sys_setup_venv] Setting up Python virtual environment using uv"

if [[ $EUID -eq 0 ]]; then
  echo "Do NOT run this as root. Run as user '$IPR_USER'."
  exit 1
fi

IPR_PROJECT_ROOT="${IPR_PROJECT_ROOT:-$HOME/dev}"
PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
VENV_DIR="$PROJECT_DIR/.venv"
if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Project directory not found: $PROJECT_DIR"
  exit 1
fi

cd "$PROJECT_DIR"

# 1. Install uv if missing
if ! command -v uv >/dev/null 2>&1; then
    echo "[sys_setup_venv] uv not found, installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
else
    echo "[sys_setup_venv] uv already installed."
    export PATH="$HOME/.local/bin:$PATH"
fi

# 2. Create venv using uv (faster than python -m venv)
echo "[sys_setup_venv] Creating virtualenv at $VENV_DIR using uv venv..."
uv venv  --allow-existing "$VENV_DIR"

# 3. Activate venv
#    Not strictly needed for uv pip, but convenient if you run more commands after.
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# 4. Install project with dev extras if present
echo "[sys_setup_venv] Installing project (with dev extras if available) using uv pip..."
if uv pip install -e ".[dev]" ; then
    echo "[sys_setup_venv] Installed editable package with [dev] extras."
else
    echo "[sys_setup_venv] [dev] extras not available or failed; installing without extras."
    uv pip install -e .
fi

# 5. Install Python debugging tools
echo "[sys_setup_venv] Installing debugpy using uv pip..."
if uv pip install debugpy ; then
    echo "[sys_setup_venv] Installed debugpy."
else
    echo "[sys_setup_venv] debugpy not available or failed; installing without extras."
fi

# 6. Create/update ~/.bash_aliases for convenience
ALIASES_FILE="$HOME/.bash_aliases"

echo "[sys_setup_venv] Adding/updating aliases in $ALIASES_FILE..."
# Write new aliases to temp file
{
  echo "alias ll='ls -al'"
  echo "alias activate='source $IPR_PROJECT_ROOT/ipr-keyboard/.venv/bin/activate'"
  echo "alias ipr='cd $IPR_PROJECT_ROOT/ipr-keyboard && activate'"
} > "$ALIASES_FILE.tmp"

# Append only non-duplicate lines from existing aliases file
if [[ -f "$ALIASES_FILE" ]]; then
  grep -v "^alias ll='ls -al'" "$ALIASES_FILE" | \
  grep -v "^alias activate='source $IPR_PROJECT_ROOT/ipr-keyboard/.venv/bin/activate'" | \
  grep -v "^alias ipr='cd $IPR_PROJECT_ROOT/ipr-keyboard && activate'" >> "$ALIASES_FILE.tmp" || true
fi
mv "$ALIASES_FILE.tmp" "$ALIASES_FILE"
echo "[sys_setup_venv] Aliases 'll', 'activate', and 'ipr' are now available in $ALIASES_FILE."

echo "[sys_setup_venv] Virtualenv created at $VENV_DIR and dependencies installed via uv."
