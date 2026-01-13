#!/usr/bin/env bash
#
# Check status of Bluetooth stack and related services for Copilot/MCP diagnostics
#
# Usage:
#   sudo dbg_stack_status.sh
#
# Prerequisites:
#   - Should be run as root for full status (but can run as user for partial info)
#   - /etc/ipr_dbg.env should exist (written by install_dbg_tools.sh)
#
# category: Debug
# purpose: Check status of Bluetooth stack and related services
# sudo: no
set -euo pipefail

DBG_ENV="/etc/ipr_dbg.env"
[[ -f "$DBG_ENV" ]] && source "$DBG_ENV"

# Source common environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/dbg_common.env"

BLE_SERVICE="${DBG_BLE_SERVICE:-$BLE_SERVICE}"
AGENT_SERVICE="${DBG_AGENT_SERVICE:-$AGENT_SERVICE}"
HCI="${DBG_HCI:-$HCI}"

# Colors (works in most terminals; safe fallback)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { echo -e "${GREEN}OK${NC}   $*"; }
warn() { echo -e "${YELLOW}WARN${NC} $*"; }
fail() { echo -e "${RED}FAIL${NC} $*"; }
info() { echo -e "${CYAN}INFO${NC} $*"; }

have_cmd() { command -v "$1" >/dev/null 2>&1; }

is_active() {
  local unit="$1"
  systemctl is-active --quiet "$unit"
}

is_enabled() {
  local unit="$1"
  systemctl is-enabled --quiet "$unit" 2>/dev/null
}

unit_summary() {
  local unit="$1"
  local active="no"
  local enabled="no"

  if is_active "$unit"; then active="yes"; fi
  if is_enabled "$unit"; then enabled="yes"; fi

  echo "$unit active=$active enabled=$enabled"
}

print_unit_detail() {
  local unit="$1"
  echo "---- $unit ----"
  systemctl --no-pager -l status "$unit" || true
  echo
}

print_last_logs() {
  local unit="$1"
  local lines="${2:-80}"
  echo "---- last ${lines} log lines: $unit ----"
  journalctl -u "$unit" -n "$lines" --no-pager || true
  echo
}

adapter_summary() {
  echo "---- adapter: $HCI ----"
  if have_cmd btmgmt; then
    sudo btmgmt -i "$HCI" info || true
  else
    warn "btmgmt not found"
  fi
  echo
  if have_cmd hciconfig; then
    hciconfig -a "$HCI" 2>/dev/null || true
    echo
  fi
  if have_cmd rfkill; then
    rfkill list bluetooth || true
    echo
  fi
}

echo "== dbg_stack_status: $(date -Is) =="
info "HCI=$HCI  AGENT=$AGENT_SERVICE  BLE=$BLE_SERVICE"
echo

# Evaluate service states
BLUETOOTH_OK=0
AGENT_OK=0
BLE_OK=0

if is_active bluetooth; then
  ok "$(unit_summary bluetooth)"
  BLUETOOTH_OK=1
else
  fail "$(unit_summary bluetooth)"
fi

if is_active "$AGENT_SERVICE"; then
  ok "$(unit_summary "$AGENT_SERVICE")"
  AGENT_OK=1
else
  warn "$(unit_summary "$AGENT_SERVICE")"
fi

if is_active "$BLE_SERVICE"; then
  ok "$(unit_summary "$BLE_SERVICE")"
  BLE_OK=1
else
  warn "$(unit_summary "$BLE_SERVICE")"
fi

echo

# Quick interpretation
if [[ "$BLUETOOTH_OK" -ne 1 ]]; then
  fail "Stack is down: bluetooth service is not active."
elif [[ "$AGENT_OK" -ne 1 && "$BLE_OK" -ne 1 ]]; then
  warn "BlueZ is up but both agent and BLE HID services are not active. Pairing will fail."
elif [[ "$AGENT_OK" -ne 1 ]]; then
  warn "Agent service is not active. Pairing/auth flows may fail or be inconsistent."
elif [[ "$BLE_OK" -ne 1 ]]; then
  warn "BLE HID service is not active. Device may not advertise / HID over GATT will fail."
else
  ok "Stack appears up (bluetooth + agent + BLE HID are active)."
fi

echo
adapter_summary

# Helpful fast checks without dumping everything
info "Recent error hints (best-effort grep; bounded)"
echo "---- bluetooth errors (last 120 lines) ----"
journalctl -u bluetooth -n 120 --no-pager 2>/dev/null | grep -Ei "error|fail|reject|insufficient|timeout|disconnect|reason|encrypt|auth|pair" | tail -n 40 || true
echo
echo "---- agent errors (last 160 lines) ----"
journalctl -u "$AGENT_SERVICE" -n 160 --no-pager 2>/dev/null | grep -Ei "error|fail|reject|insufficient|timeout|disconnect|reason|encrypt|auth|pair|passkey|RequestPasskey|RequestConfirmation" | tail -n 60 || true
echo
echo "---- ble errors (last 160 lines) ----"
journalctl -u "$BLE_SERVICE" -n 160 --no-pager 2>/dev/null | grep -Ei "error|fail|reject|insufficient|timeout|disconnect|reason|encrypt|auth|pair|StartNotify|StopNotify" | tail -n 60 || true
echo

info "If you need full status dumps, run:"
echo "  sudo systemctl status bluetooth $AGENT_SERVICE $BLE_SERVICE -l"
echo "  sudo dbg_diag_bundle.sh"
echo "  sudo dbg_pairing_capture.sh 60"

exit 0
