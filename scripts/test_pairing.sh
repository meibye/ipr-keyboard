#!/usr/bin/env bash
#
# test_pairing.sh
#
# Interactive Bluetooth Pairing Test Script for ipr-keyboard
#
# Purpose:
#   Tests the Bluetooth pairing workflow for both uinput and BLE backends.
#   Monitors agent events in real-time and provides step-by-step guidance.
#
# Usage:
#   sudo ./scripts/test_pairing.sh [uinput|ble]
#
# Prerequisites:
#   - Must be run as root
#   - Agent and backend services must be installed
#   - Bluetooth adapter must be available

set -euo pipefail

# Color codes
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
MAGENTA="\033[0;35m"
CYAN="\033[0;36m"
RESET="\033[0m"

function section() {
  echo -e "\n${CYAN}╔════════════════════════════════════════════════════════════════╗${RESET}"
  echo -e "${CYAN}║ $1${RESET}"
  echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${RESET}"
}

function step() {
  echo -e "\n${YELLOW}➜ STEP $1: $2${RESET}"
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

function prompt() {
  echo -e "${MAGENTA}▶ $1${RESET}"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
  err "This script must be run as root (sudo)"
  exit 1
fi

# Parse backend argument
BACKEND="${1:-}"
if [[ -z "$BACKEND" ]]; then
  # Try to detect from config
  if [[ -f "/etc/ipr-keyboard/backend" ]]; then
    BACKEND=$(cat /etc/ipr-keyboard/backend | tr -d '[:space:]')
  elif [[ -f "config.json" ]] && command -v jq >/dev/null 2>&1; then
    BACKEND=$(jq -r '.KeyboardBackend // "ble"' config.json)
  else
    BACKEND="ble"
  fi
  info "Auto-detected backend: $BACKEND"
fi

if [[ "$BACKEND" != "uinput" && "$BACKEND" != "ble" ]]; then
  err "Invalid backend: $BACKEND (must be 'uinput' or 'ble')"
  exit 1
fi

section "Bluetooth Pairing Test - $BACKEND Backend"

# Determine services based on backend
AGENT_SERVICE="bt_hid_agent.service"
if [[ "$BACKEND" == "uinput" ]]; then
  BACKEND_SERVICE="bt_hid_uinput.service"
else
  BACKEND_SERVICE="bt_hid_ble.service"
fi

# ---------------------------------------------------------------------------
step "1" "Verify Prerequisites"
# ---------------------------------------------------------------------------

if ! command -v bluetoothctl >/dev/null 2>&1; then
  err "bluetoothctl not found. Install bluez package."
  exit 1
fi
ok "bluetoothctl found"

if ! systemctl list-unit-files | grep -q "^$AGENT_SERVICE"; then
  err "$AGENT_SERVICE not installed"
  exit 1
fi
ok "$AGENT_SERVICE installed"

if ! systemctl list-unit-files | grep -q "^$BACKEND_SERVICE"; then
  err "$BACKEND_SERVICE not installed"
  exit 1
fi
ok "$BACKEND_SERVICE installed"

# ---------------------------------------------------------------------------
step "2" "Start Required Services"
# ---------------------------------------------------------------------------

echo ""
info "Starting $AGENT_SERVICE..."
systemctl start "$AGENT_SERVICE"
if systemctl is-active --quiet "$AGENT_SERVICE"; then
  ok "$AGENT_SERVICE is running"
else
  err "$AGENT_SERVICE failed to start"
  systemctl status "$AGENT_SERVICE" --no-pager -l -n 10
  exit 1
fi

echo ""
info "Starting $BACKEND_SERVICE..."
systemctl start "$BACKEND_SERVICE"
if systemctl is-active --quiet "$BACKEND_SERVICE"; then
  ok "$BACKEND_SERVICE is running"
else
  err "$BACKEND_SERVICE failed to start"
  systemctl status "$BACKEND_SERVICE" --no-pager -l -n 10
  exit 1
fi

sleep 2

# ---------------------------------------------------------------------------
step "3" "Configure Adapter for Pairing"
# ---------------------------------------------------------------------------

echo ""
info "Powering on adapter..."
bluetoothctl power on
ok "Adapter powered on"

echo ""
info "Making adapter discoverable..."
bluetoothctl discoverable on
ok "Adapter is discoverable"

echo ""
info "Making adapter pairable..."
bluetoothctl pairable on
ok "Adapter is pairable"

echo ""
info "Current adapter status:"
bluetoothctl show | grep -E "Powered|Discoverable|Pairable|Name|Alias"

# ---------------------------------------------------------------------------
step "4" "Monitor Agent Events (Background)"
# ---------------------------------------------------------------------------

LOG_FILE="/tmp/pairing_test_$(date +%s).log"

echo ""
info "Starting agent event monitor in background..."
info "Log file: $LOG_FILE"

# Start journalctl in background to capture events
journalctl -u "$AGENT_SERVICE" -f --no-pager > "$LOG_FILE" 2>&1 &
JOURNAL_PID=$!

function cleanup() {
  if [[ -n "${JOURNAL_PID:-}" ]]; then
    kill "$JOURNAL_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

sleep 1
ok "Agent monitor started (PID: $JOURNAL_PID)"

# ---------------------------------------------------------------------------
step "5" "Initiate Pairing from Host Device"
# ---------------------------------------------------------------------------

echo ""
prompt "═══════════════════════════════════════════════════════════════"
prompt "ACTION REQUIRED:"
prompt "  1. On your PC/phone, open Bluetooth settings"
prompt "  2. Search for new devices"
prompt "  3. Look for device named 'ipr-keyboard' or similar"
prompt "  4. Click to pair/connect"
prompt "  5. Watch for passkey display below"
prompt "═══════════════════════════════════════════════════════════════"
echo ""
echo -e "${YELLOW}Press ENTER when you've started pairing from the host device...${RESET}"
read -r

# ---------------------------------------------------------------------------
step "6" "Monitor Pairing Events (30 seconds)"
# ---------------------------------------------------------------------------

echo ""
info "Monitoring for pairing events..."
echo ""
echo -e "${CYAN}┌─────────────────────── LIVE AGENT EVENTS ───────────────────────┐${RESET}"

TIMEOUT=30
START_TIME=$(date +%s)

while true; do
  CURRENT_TIME=$(date +%s)
  ELAPSED=$((CURRENT_TIME - START_TIME))
  
  if [[ $ELAPSED -ge $TIMEOUT ]]; then
    break
  fi
  
  # Show new log entries with highlighting
  if [[ -f "$LOG_FILE" ]]; then
    tail -n 50 "$LOG_FILE" | grep -E "\[agent\]" | tail -n 10 | while read -r line; do
      if echo "$line" | grep -qi "passkey"; then
        # Extract and highlight passkey
        if echo "$line" | grep -qE "passkey=[0-9]{6}"; then
          PASSKEY=$(echo "$line" | grep -oE "passkey=[0-9]{6}" | cut -d= -f2)
          echo -e "${GREEN}>>> PASSKEY: ${MAGENTA}${PASSKEY}${GREEN} <<<${RESET}"
        fi
        echo -e "${YELLOW}$line${RESET}"
      elif echo "$line" | grep -qi "pincode"; then
        echo -e "${YELLOW}$line${RESET}"
      elif echo "$line" | grep -qi "confirmation"; then
        echo -e "${GREEN}$line${RESET}"
      elif echo "$line" | grep -qi "authorize"; then
        echo -e "${BLUE}$line${RESET}"
      else
        echo "$line"
      fi
    done
  fi
  
  sleep 2
done

echo -e "${CYAN}└──────────────────────────────────────────────────────────────────┘${RESET}"

# ---------------------------------------------------------------------------
step "7" "Verify Pairing Result"
# ---------------------------------------------------------------------------

echo ""
info "Checking paired devices..."
DEVICES=$(bluetoothctl devices 2>/dev/null || echo "")

if [[ -z "$DEVICES" ]]; then
  err "No devices paired"
else
  ok "Paired devices:"
  echo "$DEVICES"
  
  echo ""
  info "Checking connection status..."
  echo "$DEVICES" | while read -r line; do
    if [[ -n "$line" ]]; then
      MAC=$(echo "$line" | awk '{print $2}')
      NAME=$(echo "$line" | cut -d' ' -f3-)
      
      CONNECTED=$(bluetoothctl info "$MAC" | grep "Connected:" | awk '{print $2}')
      PAIRED=$(bluetoothctl info "$MAC" | grep "Paired:" | awk '{print $2}')
      
      echo ""
      echo "  Device: $NAME ($MAC)"
      echo "    Paired: $PAIRED"
      echo "    Connected: $CONNECTED"
    fi
  done
fi

# ---------------------------------------------------------------------------
step "8" "Test Keyboard Input (Optional)"
# ---------------------------------------------------------------------------

echo ""
prompt "Would you like to test sending text via Bluetooth? (y/n)"
read -r -p "> " TEST_INPUT

if [[ "$TEST_INPUT" =~ ^[Yy]$ ]]; then
  FIFO_PATH="/run/ipr_bt_keyboard_fifo"
  
  if [[ ! -p "$FIFO_PATH" ]]; then
    err "FIFO not found: $FIFO_PATH"
  else
    ok "FIFO found: $FIFO_PATH"
    echo ""
    prompt "Enter text to send (or press ENTER to skip):"
    read -r -p "> " TEST_TEXT
    
    if [[ -n "$TEST_TEXT" ]]; then
      echo ""
      info "Sending text via FIFO..."
      echo "$TEST_TEXT" > "$FIFO_PATH"
      ok "Text sent. Check if it appeared on the paired device."
    fi
  fi
fi

# ---------------------------------------------------------------------------
section "Pairing Test Complete"
# ---------------------------------------------------------------------------

echo ""
info "Full agent log saved to: $LOG_FILE"
echo ""
info "To view agent events later:"
echo "  journalctl -u $AGENT_SERVICE -n 50"
echo ""
info "To unpair a device:"
echo "  bluetoothctl remove <MAC_ADDRESS>"
echo ""
ok "Test completed successfully"
