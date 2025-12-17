#!/usr/bin/env bash
#
# scripts/lib/bt_agent_unified_env.sh
#
# Shared helper for managing the unified BlueZ agent service and its environment file:
#   - Service: bt_hid_agent_unified.service
#   - Config : /etc/default/bt_hid_agent_unified
#
# Usage (from another script):
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   source "${SCRIPT_DIR}/lib/bt_agent_unified_env.sh"
#   bt_agent_unified_set_profile_nowinpasskey
#   bt_agent_unified_restart
#
# category: Service
# purpose: BlueZ agent serviceconfiguration helper functions
# sudo: yes

set -euo pipefail

BT_AGENT_SUDO=""
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  BT_AGENT_SUDO="sudo"
fi

BT_AGENT_UNIFIED_SERVICE="bt_hid_agent_unified.service"
BT_AGENT_LEGACY_SERVICE="bt_hid_agent.service"
BT_AGENT_ENV_FILE="/etc/default/bt_hid_agent_unified"

bt_agent_unified_require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    echo "[bt_agent_unified] Please run as root (sudo)." >&2
    exit 1
  fi
}

bt_agent_unified_ensure_env_file() {
  if [[ ! -f "$BT_AGENT_ENV_FILE" ]]; then
    $BT_AGENT_SUDO install -d -m 0755 /etc/default
    $BT_AGENT_SUDO tee "$BT_AGENT_ENV_FILE" >/dev/null <<'EOF'
# Unified BlueZ agent config (ipr-keyboard)
BT_AGENT_MODE=nowinpasskey
BT_AGENT_CAPABILITY=NoInputNoOutput
BT_AGENT_PATH=/ipr/agent
BT_AGENT_ADAPTER=hci0
BT_AGENT_EXTRA_ARGS=
EOF
    $BT_AGENT_SUDO chmod 0644 "$BT_AGENT_ENV_FILE"
  fi
}

bt_agent_unified_set_kv() {
  local key="$1"
  local val="$2"
  bt_agent_unified_ensure_env_file

  if grep -qE "^${key}=" "$BT_AGENT_ENV_FILE"; then
    $BT_AGENT_SUDO sed -i "s|^${key}=.*|${key}=${val}|" "$BT_AGENT_ENV_FILE"
  else
    echo "${key}=${val}" | $BT_AGENT_SUDO tee -a "$BT_AGENT_ENV_FILE" >/dev/null
  fi
}

bt_agent_unified_set_profile_nowinpasskey() {
  # Best default for Windows: JustWorks-like, no passkey UI.
  bt_agent_unified_set_kv BT_AGENT_MODE nowinpasskey
  bt_agent_unified_set_kv BT_AGENT_CAPABILITY NoInputNoOutput
  bt_agent_unified_set_kv BT_AGENT_EXTRA_ARGS ""
}

bt_agent_unified_set_profile_fixedpin() {
  local pin="${1:-0000}"
  bt_agent_unified_set_kv BT_AGENT_MODE fixedpin
  bt_agent_unified_set_kv BT_AGENT_CAPABILITY KeyboardDisplay
  bt_agent_unified_set_kv BT_AGENT_EXTRA_ARGS "--fixed-pin ${pin}"
}

bt_agent_unified_disable_legacy_service() {
  # Avoid DefaultAgent collisions.
  $BT_AGENT_SUDO systemctl disable --now "$BT_AGENT_LEGACY_SERVICE" 2>/dev/null || true
}

bt_agent_unified_enable() {
  $BT_AGENT_SUDO systemctl enable "$BT_AGENT_UNIFIED_SERVICE" >/dev/null 2>&1 || true
}

bt_agent_unified_restart() {
  $BT_AGENT_SUDO systemctl daemon-reload >/dev/null 2>&1 || true
  $BT_AGENT_SUDO systemctl restart "$BT_AGENT_UNIFIED_SERVICE"
}

bt_agent_unified_ensure_running() {
  if ! $BT_AGENT_SUDO systemctl is-active --quiet "$BT_AGENT_UNIFIED_SERVICE"; then
    bt_agent_unified_restart
  fi
}
