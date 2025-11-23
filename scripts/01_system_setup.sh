#!/usr/bin/env bash
set -euo pipefail

echo "=== [01] System Setup for ipr_keyboard on Raspberry Pi ==="

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
    bluez \
    bluez-tools \
    bluetooth \
    libcairo2-dev \
    libgirepository1.0-dev


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
PROJECT_DIR="/home/meibye/dev/ipr-keyboard"
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
#!/usr/bin/env bash
#
# System Setup Script
#
# Purpose:
#   Installs all required system packages and prepares the base environment for ipr-keyboard.
#   Must be run as root. Sources environment variables from 00_set_env.sh.
#
# Usage:
#   sudo ./scripts/01_system_setup.sh
#
# Prerequisites:
#   - Environment variables set in 00_set_env.sh
#   - Run as root (sudo)
#
set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/00_set_env.sh"



########################################
# 9. Permissions
########################################
echo "=== Fixing permissions ==="
sudo chown -R meibye:meibye "$PROJECT_DIR"
sudo chown meibye:meibye /mnt/irispen


########################################
# 10. Final messages
########################################
echo "=== [01] System setup complete ==="
echo "You may now mount the IRISPen with:"
echo "  ./scripts/11_mount_irispen_mtp.sh"
echo ""
echo "Then run the app in dev mode:"
echo "  ./scripts/run_dev.sh"
