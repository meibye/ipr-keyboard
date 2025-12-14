#!/usr/bin/env bash
#
# diag_pairing.sh
#
# Comprehensive Bluetooth Pairing Diagnostic Tool for ipr-keyboard
#
# Purpose:
#   Diagnoses all phases of Bluetooth pairing for both uinput and BLE backends:
#   - Adapter status and configuration
#   - Agent service status and recent pairing events
#   - Backend service status
#   - Pairing history and current paired devices
#   - Authentication and authorization events
#
# Usage:
#   sudo ./scripts/diag_pairing.sh
#
# Prerequisites:
#   - Must be run as root (requires bluetoothctl and systemctl access)
#   - Bluetooth services should be installed
#
# category: Diagnostics
# purpose: Diagnose Bluetooth pairing issues for all backends
#

set -eo pipefail

# Color codes for output
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
RESET="\033[0m"

function section() {
  echo -e "\n${YELLOW}=== $1 ===${RESET}"
}

function ok() {
  echo -e "${GREEN}✓ $1${RESET}"
}

function warn() {
  echo -e "${YELLOW}⚠ $1${RESET}"
}

function err() {
  echo -e "${RED}✗ $1${RESET}"
}

function info() {
  echo -e "${BLUE}ℹ $1${RESET}"
}

echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${BLUE}║   ipr-keyboard Bluetooth Pairing Diagnostics Tool             ║${RESET}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${RESET}"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
  err "This script must be run as root (sudo)"
  exit 1
fi

# ---------------------------------------------------------------------------
section "1. Bluetooth Adapter Status"
# ---------------------------------------------------------------------------

if ! command -v bluetoothctl >/dev/null 2>&1; then
  err "bluetoothctl not found. Install bluez package."
  exit 1
fi

if bluetoothctl show >/dev/null 2>&1; then
  ok "Bluetooth adapter detected"
  echo ""
  bluetoothctl show | while IFS=: read -r key value; do
    key=$(echo "$key" | xargs)
    value=$(echo "$value" | xargs)
    case "$key" in
      "Powered")
        if [[ "$value" == "yes" ]]; then
          ok "Adapter Powered: $value"
        else
          err "Adapter Powered: $value (should be 'yes')"
        fi
        ;;
      "Discoverable")
        if [[ "$value" == "yes" ]]; then
          ok "Discoverable: $value (ready for pairing)"
        else
          warn "Discoverable: $value (needs 'yes' for pairing)"
        fi
        ;;
      "Pairable")
        if [[ "$value" == "yes" ]]; then
          ok "Pairable: $value"
        else
          err "Pairable: $value (should be 'yes')"
        fi
        ;;
      "Name"|"Alias"|"Address")
        info "$key: $value"
        ;;
    esac
  done
else
  err "No Bluetooth adapter found"
  exit 1
fi

# ---------------------------------------------------------------------------
section "2. Backend Configuration"
# ---------------------------------------------------------------------------

BACKEND_FILE="/etc/ipr-keyboard/backend"
CONFIG_FILE="config.json"

if [[ -f "$BACKEND_FILE" ]]; then
  BACKEND=$(cat "$BACKEND_FILE" | tr -d '[:space:]')
  info "Backend (from $BACKEND_FILE): $BACKEND"
else
  warn "Backend file not found: $BACKEND_FILE"
  BACKEND="unknown"
fi

if [[ -f "$CONFIG_FILE" ]] && command -v jq >/dev/null 2>&1; then
  CONFIG_BACKEND=$(jq -r '.KeyboardBackend // "not set"' "$CONFIG_FILE")
  info "Backend (from config.json): $CONFIG_BACKEND"
fi

# ---------------------------------------------------------------------------
section "3. Agent Service Status"
# ---------------------------------------------------------------------------

AGENT_SERVICE="bt_hid_agent.service"

if systemctl list-unit-files | grep -q "^$AGENT_SERVICE"; then
  if systemctl is-active --quiet "$AGENT_SERVICE"; then
    ok "$AGENT_SERVICE is active"
  else
    err "$AGENT_SERVICE is NOT active (pairing will fail)"
    systemctl status "$AGENT_SERVICE" --no-pager -l -n 5 2>&1 || true
  fi
  
  if systemctl is-enabled --quiet "$AGENT_SERVICE"; then
    ok "$AGENT_SERVICE is enabled"
  else
    warn "$AGENT_SERVICE is NOT enabled (won't start on boot)"
  fi
else
  err "$AGENT_SERVICE not installed"
  echo "   Install with: sudo ./scripts/ble_install_helper.sh"
fi

# ---------------------------------------------------------------------------
section "4. Backend Service Status"
# ---------------------------------------------------------------------------

if [[ "$BACKEND" == "uinput" ]]; then
  BACKEND_SERVICE="bt_hid_uinput.service"
elif [[ "$BACKEND" == "ble" ]]; then
  BACKEND_SERVICE="bt_hid_ble.service"
else
  warn "Unknown backend: $BACKEND"
  BACKEND_SERVICE=""
fi

if [[ -n "$BACKEND_SERVICE" ]]; then
  if systemctl list-unit-files | grep -q "^$BACKEND_SERVICE"; then
    if systemctl is-active --quiet "$BACKEND_SERVICE"; then
      ok "$BACKEND_SERVICE is active"
    else
      err "$BACKEND_SERVICE is NOT active"
      systemctl status "$BACKEND_SERVICE" --no-pager -l -n 5 2>&1 || true
    fi
  else
    err "$BACKEND_SERVICE not installed"
  fi
fi

# ---------------------------------------------------------------------------
section "5. Paired Devices"
# ---------------------------------------------------------------------------

echo ""
DEVICES=$(bluetoothctl devices 2>/dev/null || echo "")

if [[ -z "$DEVICES" ]]; then
  warn "No paired devices found"
else
  ok "Paired devices:"
  echo "$DEVICES" | while read -r line; do
    if [[ -n "$line" ]]; then
      MAC=$(echo "$line" | awk '{print $2}')
      NAME=$(echo "$line" | cut -d' ' -f3-)
      echo ""
      info "  Device: $NAME ($MAC)"
      
      # Get detailed info
      bluetoothctl info "$MAC" 2>/dev/null | while IFS=: read -r key value; do
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)
        case "$key" in
          "Connected")
            if [[ "$value" == "yes" ]]; then
              ok "    Connected: $value"
            else
              warn "    Connected: $value"
            fi
            ;;
          "Paired")
            if [[ "$value" == "yes" ]]; then
              ok "    Paired: $value"
            else
              err "    Paired: $value"
            fi
            ;;
          "Trusted"|"Blocked"|"LegacyPairing")
            echo "      $key: $value"
            ;;
        esac
      done
    fi
  done
fi

# ---------------------------------------------------------------------------
section "6. Recent Agent Events (Pairing/Auth)"
# ---------------------------------------------------------------------------

echo ""
info "Recent pairing and authorization events from agent:"
echo ""

journalctl -u "$AGENT_SERVICE" -n 50 --no-pager 2>/dev/null | \
  grep -E "\[agent\]|passkey|pincode|Confirmation|Authorization|AuthorizeService" || \
  warn "No recent agent events found"

# ---------------------------------------------------------------------------
section "7. Recent Backend Events"
# ---------------------------------------------------------------------------

if [[ -n "$BACKEND_SERVICE" ]]; then
  echo ""
  info "Recent events from $BACKEND_SERVICE:"
  echo ""
  journalctl -u "$BACKEND_SERVICE" -n 30 --no-pager 2>/dev/null || \
    warn "No recent backend events"
fi

# ---------------------------------------------------------------------------
section "8. Pairing Method Analysis"
# ---------------------------------------------------------------------------

echo ""
info "Analyzing agent pairing method configuration..."
echo ""

# Check agent script for pairing methods
AGENT_SCRIPT="/usr/local/bin/bt_hid_agent.py"

if [[ -f "$AGENT_SCRIPT" ]]; then
  ok "Agent script found: $AGENT_SCRIPT"
  echo ""
  
  # Check RequestPasskey implementation
  if grep -q "def RequestPasskey" "$AGENT_SCRIPT"; then
    info "RequestPasskey method: Found"
    PASSKEY_VALUE=$(grep -A 2 "def RequestPasskey" "$AGENT_SCRIPT" | grep "return" | awk '{print $NF}')
    if [[ "$PASSKEY_VALUE" == "0" ]]; then
      warn "  Returns hardcoded value: 0 (displays as 000000)"
      warn "  This is used when agent generates the passkey"
    fi
  fi
  
  # Check DisplayPasskey implementation  
  if grep -q "def DisplayPasskey" "$AGENT_SCRIPT"; then
    info "DisplayPasskey method: Found"
    info "  This is called when BlueZ generates a passkey to display"
  fi
  
  # Check RequestConfirmation implementation
  if grep -q "def RequestConfirmation" "$AGENT_SCRIPT"; then
    info "RequestConfirmation method: Found"
    info "  Auto-accepts pairing confirmation requests"
  fi
  
  # Check AuthorizeService implementation
  if grep -q "def AuthorizeService" "$AGENT_SCRIPT"; then
    info "AuthorizeService method: Found"
    info "  Auto-accepts HID service authorization"
  fi
  
  echo ""
  info "Agent capability:"
  AGENT_CAP=$(grep "RegisterAgent.*KeyboardOnly" "$AGENT_SCRIPT" || echo "not found")
  if [[ "$AGENT_CAP" != "not found" ]]; then
    ok "  Registered as 'KeyboardOnly' agent"
    info "  This means pairing typically uses DisplayPasskey or RequestConfirmation"
  fi
else
  err "Agent script not found: $AGENT_SCRIPT"
fi

# ---------------------------------------------------------------------------
section "9. FIFO Pipe Status"
# ---------------------------------------------------------------------------

FIFO_PATH="/run/ipr_bt_keyboard_fifo"
echo ""

if [[ -p "$FIFO_PATH" ]]; then
  ok "FIFO exists: $FIFO_PATH"
  ls -l "$FIFO_PATH"
else
  err "FIFO not found: $FIFO_PATH"
  echo "   Backend daemon should create it automatically"
fi

# ---------------------------------------------------------------------------
section "10. Recommendations"
# ---------------------------------------------------------------------------

echo ""

if ! systemctl is-active --quiet "$AGENT_SERVICE"; then
  err "Agent service is not running - start it with:"
  echo "   sudo systemctl start $AGENT_SERVICE"
fi

if [[ "$BACKEND" != "unknown" ]] && [[ -n "$BACKEND_SERVICE" ]]; then
  if ! systemctl is-active --quiet "$BACKEND_SERVICE"; then
    err "Backend service is not running - start it with:"
    echo "   sudo systemctl start $BACKEND_SERVICE"
  fi
fi

ADAPTER_DISCOVERABLE=$(bluetoothctl show | grep "Discoverable:" | awk '{print $2}')
if [[ "$ADAPTER_DISCOVERABLE" != "yes" ]]; then
  warn "Adapter is not discoverable - enable pairing mode with:"
  echo "   sudo bluetoothctl discoverable on"
  echo "   sudo bluetoothctl pairable on"
fi

echo ""
info "To test pairing:"
echo "  1. Ensure agent and backend services are running"
echo "  2. Enable discoverable mode: bluetoothctl discoverable on"
echo "  3. On PC: Add Bluetooth device 'ipr-keyboard'"
echo "  4. Monitor agent logs: sudo journalctl -u $AGENT_SERVICE -f"
echo "  5. Watch for DisplayPasskey or RequestConfirmation events"

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${BLUE}║   Diagnostics Complete                                         ║${RESET}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${RESET}"
