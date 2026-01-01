#!/usr/bin/env bash
#
# svc_install_bt_hid_agent.sh (LEGACY)
#
# This project used to install bt_hid_agent.service.
# It has been replaced by the unified agent:
#   - bt_hid_agent_unified.service
#   - /etc/default/bt_hid_agent_unified
#
# This script remains as a compatibility wrapper for older docs and scripts.
#
# category: Service
# purpose: Install bt_hid_agent service
# sudo: yes

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

echo "=== [svc_install_bt_hid_agent] LEGACY installer invoked ==="
echo "[svc_install_bt_hid_agent] bt_hid_agent.service is deprecated. Installing unified agent instead..."

exec "${SCRIPT_DIR}/svc_install_bt_hid_agent_unified.sh"
