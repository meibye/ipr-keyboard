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
set -g default-terminal "screen-256color" # Set terminal type for 256-color support
set -ga terminal-overrides ",*256col*:Tc" # Override to enable true-color for compatible terminals

# General
set -g set-clipboard on         # Use system clipboard
set -g detach-on-destroy off    # Don't exit from tmux when closing a session
set -g escape-time 0            # Remove delay for exiting insert mode with ESC in Neovim
set -g history-limit 1000000    # Increase history size (from 2,000)
set -g mouse on                 # Enable mouse support
set -g status-interval 3        # Update the status bar every 3 seconds (default: 15 seconds)
set -g allow-passthrough on     # Allow programs in the pane to bypass tmux (e.g. for image preview)
set -g status-position bottom

# Set prefix key
unbind C-b              # Unbind the default prefix key
set -g prefix C-Space   # Set new prefix key to Ctrl+Space

# Refresh tmux config with r
unbind r
bind r source-file ~/.config/tmux/tmux.conf

# Split horizontally in CWD with \
unbind %
bind \\\ split-window -h -c "#{pane_current_path}"

# Split vertically in CWD with -
unbind \"
bind - split-window -v -c "#{pane_current_path}"

# New window in same path
bind c new-window -c "#{pane_current_path}"

# Use vim arrow keys to resize
bind -r j resize-pane -D 5
bind -r k resize-pane -U 5
bind -r l resize-pane -R 5
bind -r h resize-pane -L 5

# Use m key to maximize pane
bind -r m resize-pane -Z

# Enable vi mode to allow us to use vim keys to move around in copy mode (Prefix + [ places us in copy mode)
set-window-option -g mode-keys vi

# Start selecting text with "v"
bind-key -T copy-mode-vi 'v' send -X begin-selection 

# Copy text with "y"
bind -T copy-mode-vi 'y' send-keys -X copy-pipe-and-cancel "pbcopy"

# Paste yanked text with "Prefix + P" ("Prefix + p" goes to previous window)
bind P paste-buffer

# Don't exit copy mode when dragging with mouse
unbind -T copy-mode-vi MouseDragEnd1Pane

# Start windows and panes at 1, not 0
set -g base-index 1
set -g pane-base-index 1
set -g renumber-windows on # Automatically renumber windows when one is closed

# tpm plugin manager
set -g @plugin 'tmux-plugins/tpm'

# List of tmux plugins
set -g @plugin 'christoomey/vim-tmux-navigator' # Enable navigating between nvim and tmux
set -g @plugin 'tmux-plugins/tmux-resurrect'    # Persist tmux sessions after computer restart
set -g @plugin 'tmux-plugins/tmux-continuum'    # Automatically saves sessions every 15 minutes
set -g @plugin 'hendrikmi/tmux-cpu-mem-monitor' # CPU and memory info

# Style
gray_light="#D8DEE9"
gray_medium="#ABB2BF"
gray_dark="#3B4252"
green_soft="#A3BE8C"
blue_muted="#81A1C1"
cyan_soft="#88C0D0"

set -g status-position top
set -g status-left-length 100
set -g status-style "fg=\${gray_light},bg=default"
set -g status-left "#[fg=\${green_soft},bold] #S #[fg=\${gray_light},nobold] | "
set -g status-right " #{cpu}   #{mem} "
set -g window-status-current-format "#[fg=\${cyan_soft},bold]  #[underscore]#I:#W"
set -g window-status-format " #I:#W"
set -g message-style "fg=\${gray_light},bg=default"
set -g mode-style "fg=\${gray_dark},bg=\${blue_muted}"
set -g pane-border-style "fg=\${gray_dark}"
set -g pane-active-border-style "fg=\${green_soft}"

# Resurrect
set -g @resurrect-capture-pane-contents 'on'
# set -g @continuum-restore 'on'

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


# 5. Create/update ~/.bash_aliases for convenience
ALIASES_FILE="$HOME/.bash_aliases"
echo "[sys_setup_venv] Adding/updating aliases in $ALIASES_FILE..."
{
  echo "alias ll='ls -al'"
  echo "alias activate='source $IPR_PROJECT_ROOT/ipr-keyboard/.venv/bin/activate'"
} > "$ALIASES_FILE.tmp"

# Merge with existing aliases if present, avoiding duplicates
if [[ -f "$ALIASES_FILE" ]]; then
  grep -v "^alias ll='ls -al'" "$ALIASES_FILE" | \
  grep -v "^alias activate='source $IPR_PROJECT_ROOT/ipr-keyboard/.venv/bin/activate'" >> "$ALIASES_FILE.tmp" || true
fi
mv "$ALIASES_FILE.tmp" "$ALIASES_FILE"
echo "[sys_setup_venv] Aliases 'll' and 'activate' are now available in $ALIASES_FILE."

echo "[sys_setup_venv] Virtualenv created at $VENV_DIR and dependencies installed via uv."
