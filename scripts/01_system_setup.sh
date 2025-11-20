#!/usr/bin/env bash

# Installs required packages and enables Bluetooth.

set -euo pipefail

echo "[01] System setup - installing packages and enabling Bluetooth"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

apt-get update
apt-get install -y \
  python3 python3-venv python3-pip \
  bluez bluez-tools bluetooth \
  git

# Unblock and enable bluetooth service
rfkill unblock bluetooth || true
systemctl enable --now bluetooth

echo "[01] Done."
