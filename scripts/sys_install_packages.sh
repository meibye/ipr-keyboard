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
# category: System
# purpose: Install all required system packages for ipr-keyboard
# sudo: yes

set -eo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/env_set_variables.sh"

echo "=== [sys_install_packages] System Setup for ipr_keyboard on Raspberry Pi ==="

# Parse mode
MODE="system"
if [[ "$1" == "--user-venv-setup" ]]; then
    MODE="venv"
elif [[ "$1" == "--system-only" ]]; then
    MODE="system"
fi

# apt with retries.
#
# The 32-bit image (Zero W) pulls from raspbian.raspberrypi.com, which is not a
# server but a redirector that bounces every download to a random community
# mirror. When one of those is down - seen with mirrors.dotsrc.org, which took
# 60 of 122 packages with it - a bare `apt install` fails the whole step. The
# 64-bit images use the deb.debian.org CDN and never hit this. So: retry, and
# run `apt update` in between so the redirector rolls a different mirror.
# ForceIPv4 because the devices have no IPv6 route (the Wi-Fi profile sets
# ipv6.method=ignore) and every attempt otherwise wastes a failed IPv6 dial.
APT_OPTS=(-o Acquire::ForceIPv4=true -o Acquire::Retries=3)
apt_install() {
    local attempt
    for attempt in 1 2 3; do
        if sudo apt install -y "${APT_OPTS[@]}" "$@"; then
            return 0
        fi
        echo "!! apt install failed (attempt $attempt/3) - refreshing mirror and retrying ..." >&2
        sleep 5
        sudo apt update "${APT_OPTS[@]}" || true
    done
    echo "!! apt install failed after 3 attempts. If the errors name a mirror" >&2
    echo "   (e.g. mirrors.dotsrc.org), it is down: wait a few minutes and rerun." >&2
    return 1
}

if [[ "$MODE" == "system" ]]; then
    ########################################
    # 1. System update
    ########################################
    echo "=== Updating apt packages ==="
    sudo apt update "${APT_OPTS[@]}"
    sudo apt full-upgrade -y "${APT_OPTS[@]}"

    ########################################
    # 2. Core dependencies
    ########################################
    echo "=== Installing core system packages ==="
    apt_install \
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
            python3-dbus \
            python3-gi \
            bluez \
            bluez-tools \
            bluetooth \
            libcairo2-dev \
            libgirepository1.0-dev \
            jq \
            python3-rpi-lgpio \
            gpiod \
            nftables

    # python3-rpi-lgpio: RPi.GPIO API over lgpio for the status LED / reed switch
    #   (works on Zero W and Zero 2 W with current kernels; the venv is created
    #   with --system-site-packages so the app can import it).
    # gpiod: gpioset, used by ipr-led-boot.service for the early white blink.
    # nftables: the production/development port policy (install_firewall.sh);
    #   listed here so an offline payload install does not depend on apt later.

    # Note: PyGObject (gi.repository) is only available for the system Python via python3-gi. For venvs, use system Python for scripts requiring gi.

    ########################################
    # 3. MTP support for IRISPen
    ########################################
    echo "=== Installing MTP packages ==="
    apt_install \
            mtp-tools \
            libmtp-runtime \
            libmtp-dev \
            jmtpfs \
            fuse

    ########################################
    # 4. Optional OCR engine (for future use)
    ########################################
    echo "=== Installing optional OCR engine (Tesseract) ==="
    apt_install tesseract-ocr tesseract-ocr-eng

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

    # Ensure uv is available system-wide
    if [ -f "$HOME/.local/bin/uv" ]; then
            sudo ln -sf "$HOME/.local/bin/uv" /usr/local/bin/uv
            echo "Symlinked uv to /usr/local/bin/uv"
    fi

    # Ensure PATH contains ~/.local/bin for uv (for interactive shells)
    if ! grep -q "~/.local/bin" ~/.bashrc; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    fi
    export PATH="$HOME/.local/bin:$PATH"

    ########################################
    # 8. Create standard folders
    ########################################
    PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
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
fi

if [[ "$MODE" == "venv" ]]; then
        ########################################
        # 7. Prepare project venv using uv (user mode)
        ########################################
        PROJECT_DIR="$IPR_PROJECT_ROOT/ipr-keyboard"
        VENV_DIR="$PROJECT_DIR/.venv"

        echo "=== Setting up Python venv with uv (user mode) ==="
        cd "$PROJECT_DIR"

        # Ensure uv is installed for the user
        if ! command -v uv >/dev/null 2>&1; then
                echo "[venv setup] uv not found for user, installing..."
                curl -fsSL https://astral.sh/uv/install.sh | sh
        fi

        # Ensure ~/.local/bin is in PATH for the user (where uv is installed)
        export PATH="$HOME/.local/bin:$PATH"

        if [[ ! -d "$VENV_DIR" ]]; then
                uv venv .venv
                echo "[venv setup] Created virtualenv at $VENV_DIR"
        else
                echo "[venv setup] Virtualenv already exists at $VENV_DIR"
        fi

        # Install project deps (editable mode)
        echo "=== Installing project dependencies in venv ==="
        uv pip install -e ".[dev]" || uv pip install -e .
fi
echo "  ./scripts/dev_run_app.sh"
