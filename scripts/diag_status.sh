#!/usr/bin/env bash
#
# ipr-keyboard System Status Script
#
# Presents the current status of the ipr-keyboard setup, including:
# - Which Bluetooth HID service/backend is selected and its status
# - Bluetooth connection and pairing info
# - Key configuration and environment variables
# - USB/IrisPen mount status
# - Web API and logging status
#
# Usage:
#   ./scripts/diag_status.sh
#
# Prerequisites:
#   - Must NOT be run as root
#   - Environment variables set (sources env_set_variables.sh)
#
# category: Diagnostics
# purpose: Show comprehensive system status and configuration
# sudo: no

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env_set_variables.sh"

# Helper for colored output
green='\033[0;32m'
yellow='\033[1;33m'
red='\033[0;31m'
reset='\033[0m'

function status_line() {
  local label="$1"; shift
  local value="$1"; shift
  local color="${2:-$green}"
  printf "%b%-30s%b %s%b\n" "$color" "$label:" "$reset" "$value" "$reset"
}

function section() {
  echo -e "\n${yellow}=== $1 ===${reset}"
}

section "Environment & Configuration"
status_line "User" "$IPR_USER"
status_line "Project Root" "$IPR_PROJECT_ROOT"

CONFIG_FILE="$IPR_PROJECT_ROOT/ipr-keyboard/config.json"
if [[ -f "$CONFIG_FILE" ]]; then
  status_line "Config File" "$CONFIG_FILE"
  echo "  $(jq '.' "$CONFIG_FILE" 2>/dev/null || cat "$CONFIG_FILE")"
else
  status_line "Config File" "NOT FOUND" "$red"
fi

section "Bluetooth HID Service/Backend"

# Detect which backend is selected
BACKEND="unknown"
if [[ -f "$CONFIG_FILE" ]]; then
  BACKEND=$(jq -r '.KeyboardBackend // empty' "$CONFIG_FILE" 2>/dev/null || echo "unknown")
fi
if [[ "$BACKEND" == "" || "$BACKEND" == "null" ]]; then
  BACKEND="default (check config)"
fi
status_line "Selected Backend (config)" "$BACKEND"

# Check for required services
UINPUT_SVC="bt_hid_uinput.service"
BLE_SVC="bt_hid_ble.service"
AGENT_SVC="bt_hid_agent_unified.service"

UINPUT_ACTIVE=false
BLE_ACTIVE=false
AGENT_ACTIVE=false

if systemctl list-units --type=service | grep -q "$UINPUT_SVC"; then
  if systemctl is-active --quiet "$UINPUT_SVC"; then UINPUT_ACTIVE=true; fi
fi
if systemctl list-units --type=service | grep -q "$BLE_SVC"; then
  if systemctl is-active --quiet "$BLE_SVC"; then BLE_ACTIVE=true; fi
fi
if systemctl list-units --type=service | grep -q "$AGENT_SVC"; then
  if systemctl is-active --quiet "$AGENT_SVC"; then AGENT_ACTIVE=true; fi
fi

status_line "$UINPUT_SVC" "$([[ $UINPUT_ACTIVE == true ]] && echo "active" || echo "inactive/missing")" "$([[ $UINPUT_ACTIVE == true ]] && echo "$green" || echo "$red")"
status_line "$BLE_SVC" "$([[ $BLE_ACTIVE == true ]] && echo "active" || echo "inactive/missing")" "$([[ $BLE_ACTIVE == true ]] && echo "$green" || echo "$red")"
status_line "$AGENT_SVC" "$([[ $AGENT_ACTIVE == true ]] && echo "active" || echo "inactive/missing")" "$([[ $AGENT_ACTIVE == true ]] && echo "$green" || echo "$red")"

# Analyze support for selected backend
if [[ "$BACKEND" == "uinput" ]]; then
  if [[ $UINPUT_ACTIVE == true && $AGENT_ACTIVE == true ]]; then
    status_line "uinput backend support" "OK (all required services active)" "$green"
  else
    status_line "uinput backend support" "MISSING required services:" "$red"
    [[ $UINPUT_ACTIVE != true ]] && echo "  - $UINPUT_SVC not active or missing"
    [[ $AGENT_ACTIVE != true ]] && echo "  - $AGENT_SVC not active or missing"
  fi
elif [[ "$BACKEND" == "ble" ]]; then
  if [[ $BLE_ACTIVE == true && $AGENT_ACTIVE == true ]]; then
    status_line "ble backend support" "OK (all required services active)" "$green"
  else
    status_line "ble backend support" "MISSING required services:" "$red"
    [[ $BLE_ACTIVE != true ]] && echo "  - $BLE_SVC not active or missing"
    [[ $AGENT_ACTIVE != true ]] && echo "  - $AGENT_SVC not active or missing"
  fi
else
  status_line "backend support" "Unknown backend config: $BACKEND" "$yellow"
fi

# Check for helper script
if [[ -x "/usr/local/bin/bt_kb_send" ]]; then
  status_line "bt_kb_send helper" "present" "$green"
else
  status_line "bt_kb_send helper" "NOT FOUND" "$red"
fi

section "Bluetooth Connection & Pairing"
# Show paired devices and connection status
if command -v bluetoothctl >/dev/null 2>&1; then
  echo "Paired devices:"
  bluetoothctl devices
  echo
  echo "Connection info for paired devices:"
  while read -r line; do
    mac=$(echo "$line" | awk '{print $2}')
    if [[ -n "$mac" ]]; then
      echo "  Device $mac:"
      bluetoothctl info "$mac" | grep -E 'Device|Connected|Paired|Alias|UUID' | sed 's/^/    /'
    fi
  done < <(bluetoothctl devices)
else
  status_line "bluetoothctl" "NOT INSTALLED" "$red"
fi

section "Bluetooth Adapter"
if command -v bluetoothctl >/dev/null 2>&1; then
  echo "Adapter info:"
  # bluetoothctl show prints Address, Name, Alias, Class, Powered, Discoverable, Pairable, UUIDs, etc.
  bluetoothctl show | sed 's/^/  /'
else
  status_line "bluetoothctl" "NOT INSTALLED" "$red"
fi

section "USB/IrisPen Mount Status"
MOUNT_PATH="/mnt/irispen"
if [[ -f "$CONFIG_FILE" ]]; then
  MOUNT_PATH=$(jq -r '.IrisPenFolder // "/mnt/irispen"' "$CONFIG_FILE" 2>/dev/null || echo "/mnt/irispen")
fi
if mount | grep -q "on $MOUNT_PATH "; then
  status_line "IrisPen mount" "mounted at $MOUNT_PATH" "$green"
else
  status_line "IrisPen mount" "NOT MOUNTED at $MOUNT_PATH" "$red"
fi

section "Web API & Logging"
PORT="8080"
if [[ -f "$CONFIG_FILE" ]]; then
  PORT=$(jq -r '.LogPort // 8080' "$CONFIG_FILE" 2>/dev/null || echo "8080")
fi
status_line "Web API Port" "$PORT"
if ss -tln | grep -q ":$PORT "; then
  status_line "Web API" "LISTENING on port $PORT" "$green"
else
  status_line "Web API" "NOT LISTENING on port $PORT" "$red"
fi
LOG_FILE="$IPR_PROJECT_ROOT/ipr-keyboard/logs/ipr_keyboard.log"
if [[ -f "$LOG_FILE" ]]; then
  status_line "Log File" "$LOG_FILE (exists)" "$green"
  tail -n 3 "$LOG_FILE"
else
  status_line "Log File" "NOT FOUND" "$red"
fi

echo -e "\n${yellow}=== Status check complete ===${reset}"
