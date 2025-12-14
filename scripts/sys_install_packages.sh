#!/usr/bin/env bash
#
# System Setup Script
#
# Purpose:
#   Installs all required system packages and prepares the base environment for ipr-keyboard.
#   Must be run as root. Sources environment variables from env_set_variables.sh.
#
# Usage:
#   sudo ./scripts/sys_install_packages.sh
#
# Prerequisites:
#   - Environment variables set in env_set_variables.sh
#   - Run as root (sudo)
#
# category: System
# purpose: Install required system packages and dependencies

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/env_set_variables.sh"

echo "=== [sys_install_packages] System Setup for ipr_keyboard on Raspberry Pi ==="

########################################
# 1. System update
########################################
echo "=== Updating apt packages ==="
sudo apt update
sudo apt full-upgrade -y


########################################
# 2. Core dependencies
########################################
echo "=== Installing core system packages ==="
sudo apt install -y \
    git \
    unzip \
    build-essential \
    pkg-config \
    libusb-1.0-0-dev \
    libudev-dev \
    python3-dev \
    python3-venv \
    python3-pip \
    python3-systemd \
    bluez \
    bluez-tools \
    bluetooth \
    libcairo2-dev \
    libgirepository1.0-dev \
    jq


########################################
# 3. MTP support for IRISPen
########################################
echo "=== Installing MTP packages ==="
sudo apt install -y \
    mtp-tools \
    libmtp-runtime \
    libmtp-dev \
    jmtpfs \
    fuse


########################################
# 4. Optional OCR engine (for future use)
########################################
echo "=== Installing optional OCR engine (Tesseract) ==="
sudo apt install -y tesseract-ocr tesseract-ocr-eng


########################################
# 5. Bluetooth HID keyboard support
########################################
echo "=== Installing Bluetooth HID support ==="

# Enable experimental Bluetooth if not enabled
if ! grep -q "Experimental=true" /etc/bluetooth/main.conf; then
    echo "Adding Experimental=true to /etc/bluetooth/main.conf"
    sudo sed -i '/^\[General\]/a Experimental=true' /etc/bluetooth/main.conf
fi

sudo systemctl enable bluetooth
########################################
# 6. Install uv (Python package manager)
########################################
echo "=== Installing uv ==="
curl -fsSL https://astral.sh/uv/install.sh | sh

# Ensure PATH contains ~/.local/bin for uv
if ! grep -q "~/.local/bin" ~/.bashrc; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
fi
export PATH="$HOME/.local/bin:$PATH"


########################################
# 7. Prepare project venv using uv
########################################
PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
VENV_DIR="$PROJECT_DIR/.venv"

echo "=== Setting up Python venv with uv ==="
cd "$PROJECT_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
    uv venv .venv
fi

# Install project deps (editable mode)
uv pip install -e ".[dev]" || uv pip install -e .


########################################
# 8. Create standard folders
########################################
echo "=== Creating project directories ==="
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/cache/irispen"
sudo mkdir -p /mnt/irispen


########################################
# 9. Final messages
########################################
echo "=== [sys_install_packages] System setup complete ==="
echo "You may now mount the IRISPen with:"
echo "  ./scripts/usb_mount_mtp.sh"
echo ""
echo "Then run the app in dev mode:"
echo "  ./scripts/dev_run_app.sh"
